<?php
declare(strict_types=1);
namespace Mosa2\Phase2;

/** Restricted SQL expression parser. Unknown syntax is never discarded.
 * Parentheses disappear only by parsing their complete enclosed expression.
 * Operator precedence, operand order, literal bytes and identifier case survive.
 */
final class CheckExpression
{
    private array $tokens = [];
    private int $position = 0;

    public function __construct(string $expression, bool $qualifiedUtf8 = false, bool $informationSchema = false)
    {
        $offset = 0;
        while ($offset < strlen($expression)) {
            // Observed on the qualified 8.0.26 server: INFORMATION_SCHEMA escapes
            // the delimiter quotes; SHOW CREATE does not. Decode only complete
            // _utf8mb4 ASCII-lowercase literals (including empty), never content.
            // Caller must cross-check SHOW CREATE and the qualified UTF8 session.
            $delimiter = $informationSchema ? chr(92)."'" : "'";
            $prefix = '_utf8mb4'.$delimiter;
            if ($qualifiedUtf8 && substr($expression, $offset, strlen($prefix)) === $prefix) {
                $start = $offset + strlen($prefix);
                $end = strpos($expression, $delimiter, $start);
                if ($end === false) throw new \RuntimeException('unterminated_introducer');
                $value = substr($expression, $start, $end-$start);
                if (!preg_match('/\A(?:[a-z]*|1m|5m|1h|1d|mosa2-market-unit-v1)\z/', $value)) throw new \RuntimeException('unsupported_introduced_literal');
                $this->tokens[] = "'".$value."'";
                $offset = $end + strlen($delimiter);
                continue;
            }
            if (!preg_match("/\G(\s+|'(?:''|[^'\\\\])*'|`[a-zA-Z_][a-zA-Z_0-9]*`|[a-zA-Z_][a-zA-Z_0-9]*|[0-9]+|<>|>=|<=|[=><(),])/A", $expression, $match, 0, $offset)) {
                throw new \RuntimeException('unsupported_token_at_'.$offset);
            }
            $offset += strlen($match[0]);
            if (trim($match[0]) !== '') $this->tokens[] = $match[0];
        }
    }

    private function peek(): ?string { return $this->tokens[$this->position] ?? null; }
    private function take(): string
    {
        if ($this->peek() === null) throw new \RuntimeException('unexpected_end');
        return $this->tokens[$this->position++];
    }
    private function accept(string $keyword): bool
    {
        if (strtoupper($this->peek() ?? '') !== $keyword) return false;
        $this->position++;
        return true;
    }
    private function expect(string $token): void
    {
        if (!$this->accept($token)) throw new \RuntimeException('expected_'.$token);
    }
    public function parse(): array
    {
        $node = $this->orExpression();
        if ($this->peek() !== null) throw new \RuntimeException('trailing_token');
        return $node;
    }
    private function orExpression(): array
    {
        $left = $this->andExpression();
        while ($this->accept('OR')) $left = ['OR', $left, $this->andExpression()];
        return $left;
    }
    private function andExpression(): array
    {
        $left = $this->comparison();
        while ($this->accept('AND')) $left = ['AND', $left, $this->comparison()];
        return $left;
    }
    private function comparison(): array
    {
        $left = $this->atom();
        if ($this->accept('IS')) {
            $negated = $this->accept('NOT');
            if ($this->accept('NULL')) return [$negated ? 'IS NOT NULL' : 'IS NULL', $left];
            if (!$negated && $this->accept('TRUE')) return ['IS TRUE', $left];
            throw new \RuntimeException('unsupported_is');
        }
        $negated = $this->accept('NOT');
        if ($this->accept('IN')) {
            $this->expect('(');
            $values = [$this->atom()];
            while ($this->accept(',')) $values[] = $this->atom();
            $this->expect(')');
            return [$negated ? 'NOT IN' : 'IN', $left, $values];
        }
        if ($negated) throw new \RuntimeException('unsupported_not');
        if (in_array($this->peek(), ['=', '<>', '>', '<', '>=', '<='], true)) {
            $operator = $this->take();
            return [$operator, $left, $this->atom()];
        }
        return $left;
    }
    private function atom(): array
    {
        if ($this->accept('(')) {
            $node = $this->orExpression();
            $this->expect(')');
            return $node;
        }
        $token = $this->take();
        if ($token[0] === "'") return ['literal', $token];
        if (ctype_digit($token)) return ['number', $token];
        if ($token[0] === '`') return ['identifier', substr($token, 1, -1)];
        if (!preg_match('/\A[a-zA-Z_][a-zA-Z_0-9]*\z/', $token)) throw new \RuntimeException('unsupported_atom');
        if ($this->accept('(')) {
            $function = strtoupper($token);
            if (!in_array($function, ['TRIM', 'CHAR_LENGTH'], true)) throw new \RuntimeException('unsupported_function');
            $argument = $this->orExpression();
            $this->expect(')');
            return ['function', $function, $argument];
        }
        if (in_array(strtoupper($token), ['AND','OR','NOT','IN','NULL','TRUE','FALSE'], true)) throw new \RuntimeException('unsupported_keyword');
        return ['identifier', $token];
    }
}

/** SQL AND/OR are associative under three-valued logic. Flatten only the
 * same operator, in the original operand order. Mixed operators, IS TRUE,
 * comparisons, names and literal bytes remain separate and significant.
 */
function canonicalCheckTree(array $node): array
{
    foreach ($node as $key=>$value) if (is_array($value)) $node[$key]=canonicalCheckTree($value);
    if (!in_array($node[0]??null,['AND','OR'],true)) return $node;
    $result=[$node[0]];
    foreach (array_slice($node,1) as $child) {
        if ($child[0]===$node[0]) foreach (array_slice($child,1) as $operand) $result[]=$operand;
        else $result[]=$child;
    }
    return $result;
}

function compareCheck(string $table, string $constraint, string $expected, string $actual, string $show, bool $qualifiedUtf8 = false): array
{
    $result = ['table'=>$table, 'constraint'=>$constraint, 'expected'=>$expected,
        'server_check_clause'=>$actual, 'show_create_table'=>$show,
        'normalized_expected'=>null, 'normalized_server'=>null, 'normalized_show'=>null, 'equal'=>false, 'decision'=>''];
    foreach (['expected'=>$expected, 'server'=>$actual] as $side=>$expression) {
        try { $result['normalized_'.$side] = canonicalCheckTree((new CheckExpression($expression, $qualifiedUtf8 && $side==='server', $side==='server'))->parse()); }
        catch (\RuntimeException $error) { $result['decision'] .= $side.':'.$error->getMessage().';'; }
    }
    if ($result['decision'] !== '') return $result;
    $result['equal'] = $result['normalized_expected'] === $result['normalized_server'];
    if ($qualifiedUtf8) {
        $pattern = '/^\s*CONSTRAINT `'.preg_quote($constraint, '/').'` CHECK \((.*)\),?$/m';
        if (preg_match_all($pattern, $show, $matches) !== 1) {
            $result['equal']=false; $result['decision']='missing_or_ambiguous_show_check'; return $result;
        }
        try { $result['normalized_show']=canonicalCheckTree((new CheckExpression($matches[1][0],true,false))->parse()); }
        catch (\RuntimeException $error) { $result['equal']=false; $result['decision']='show:'.$error->getMessage(); return $result; }
        $result['equal']=$result['equal'] && $result['normalized_show']===$result['normalized_expected'];
    }
    $result['decision'] = $result['equal'] ? 'identical_expression_tree' : 'expression_tree_mismatch';
    return $result;
}
