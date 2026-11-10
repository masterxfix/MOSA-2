<?php
declare(strict_types=1);
require_once dirname(__DIR__,2).'/api/fundamentals_read.php';

class FundamentalsFixtureStatement extends PDOStatement {
    public function __construct(private array $rows,private bool $fail=false) {}
    public function execute(?array $params=null): bool {
        if ($this->fail) throw new PDOException('simulated_query_failure');
        return true;
    }
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args): array { return $this->rows; }
    public function fetchColumn(int $column=0): mixed { return '1'; }
}

class FundamentalsFixtureConnection extends PDO {
    public array $queries=[];
    public bool $rolledBack=false;
    private bool $transaction=false;
    public function __construct(private string $scenario) {}
    public function exec(string $statement): int|false { return 0; }
    public function beginTransaction(): bool { return $this->transaction=true; }
    public function inTransaction(): bool { return $this->transaction; }
    public function rollBack(): bool { $this->transaction=false; return $this->rolledBack=true; }
    public function query(string $query,?int $fetchMode=null,mixed ...$args): PDOStatement|false {
        return new FundamentalsFixtureStatement([]);
    }
    public function prepare(string $query,array $options=[]): PDOStatement|false {
        $this->queries[]=$query;
        $assets=count($this->queries)===1;
        $rows=$assets&&$this->scenario==='stored'?[['asset_id'=>42,'name'=>'Beispiel AG','isin'=>'DE0007164600']]:[];
        return new FundamentalsFixtureStatement($rows,$assets&&$this->scenario==='error');
    }
}

$scenario=$argv[1];
$db=new FundamentalsFixtureConnection($scenario);
$report=[];
try {
    $report['payload']=\Mosa2\FundamentalsRead\read($db,$scenario==='unknown'?'DE0007164600':null,'2026-11-10 08:00:00.000000');
} catch (Throwable $error) {
    $report['error']=$error->getMessage();
}
$report['queries']=count($db->queries);
$report['rolled_back']=$db->rolledBack;
echo json_encode($report,JSON_THROW_ON_ERROR);
