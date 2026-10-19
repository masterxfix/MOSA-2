<?php
declare(strict_types=1);
namespace Mosa2\Phase3K;
use PDO;
use function Mosa2\Phase2\{check,same,qi,splitSql,rows,compareCheck,contract};
require_once __DIR__.'/../phase3b/postcheck.php';

const DIGEST='199933884802bd139b706e50e57e04687e9cbe5f8bd1366e98e302af7d47b8ee';
const ORDER=['m2_units','m2_asset_source_routes','m2_market_observations','m2_market_current','m2_market_bars'];

function statements(string $sql): array {
    same(hash('sha256',$sql),DIGEST,'unit_migration_digest');
    $parts=splitSql(preg_replace('/^\s*--[^\n]*$/m','',$sql),';');
    same(array_pop($parts),'','unit_semicolon');same(count($parts),5,'five_statements');
    foreach($parts as $i=>$part)check(str_starts_with($part,($i===0?'CREATE TABLE ':'ALTER TABLE ').ORDER[$i].($i===0?' (':"\n")),'ddl_order');
    return $parts;
}

function definition(array &$table,string $line,bool $modify=false): void {
    if(preg_match('/\A([a-z_0-9]+) (INT UNSIGNED|SMALLINT UNSIGNED|VARCHAR\(\d+\)|CHAR\(\d+\)|BINARY\(32\)|DATETIME\(6\)|DECIMAL\(\d+,\d+\))(?: COLLATE ([a-z0-9_]+))? (NOT NULL|NULL)(?: DEFAULT (1))?\z/',$line,$c)) {
        same(isset($table['columns'][$c[1]]),$modify,'column_add_modify');
        $text=str_starts_with($c[2],'VARCHAR')||str_starts_with($c[2],'CHAR(');
        $table['columns'][$c[1]]=['type'=>strtolower($c[2]),'nullable'=>$c[4]==='NULL'?'YES':'NO',
            'extra'=>'','collation'=>$text?($c[3]?:'utf8mb4_0900_ai_ci'):null,'charset'=>$text?'utf8mb4':null,'default'=>$c[5]??null];
        return;
    }
    check(!$modify,'modify_column_only');
    if(preg_match('/\A(PRIMARY KEY|(?:UNIQUE )?KEY ([a-z_0-9]+)) \(([^()]+)\)\z/',$line,$k)) {
        $key=$k[1]==='PRIMARY KEY'?'PRIMARY':$k[2];check(!isset($table['indexes'][$key]),'duplicate_index');
        $table['indexes'][$key]=['unique'=>$key==='PRIMARY'||str_starts_with($k[1],'UNIQUE'),'columns'=>array_map('trim',explode(',',$k[3]))];
    } elseif(preg_match('/\ACONSTRAINT ([a-z_0-9]+) FOREIGN KEY \(([^()]+)\) REFERENCES (m2_[a-z_]+) \(([^()]+)\) ON DELETE RESTRICT\z/',$line,$f)) {
        check(!isset($table['fks'][$f[1]]),'duplicate_fk');
        $table['fks'][$f[1]]=['columns'=>array_map('trim',explode(',',$f[2])),'table'=>$f[3],
            'targets'=>array_map('trim',explode(',',$f[4])),'delete'=>'RESTRICT'];
    } elseif(preg_match('/\ACONSTRAINT ([a-z_0-9]+) CHECK \((.*)\)\z/s',$line,$c)) {
        check(!isset($table['checks'][$c[1]]),'duplicate_check');
        (new \Mosa2\Phase2\CheckExpression($c[2]))->parse();$table['checks'][$c[1]]=$c[2];
    } else throw new \RuntimeException('unit_definition_grammar');
}

function schemas(string $root,int $stage=5): array {
    check($stage>=0&&$stage<=5,'schema_stage');
    [$core,$market]=\Mosa2\Phase3B\schemas($root);$all=$core+$market;
    foreach(array_slice(statements(file_get_contents($root.'/0003.sql')),0,$stage) as $i=>$sql) {
        $name=ORDER[$i];
        if($i===0) {
            check((bool)preg_match('/\ACREATE TABLE m2_units \((.*)\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci\z/s',$sql,$m),'unit_create');
            $all[$name]=['columns'=>[],'indexes'=>[],'fks'=>[],'checks'=>[],'ddl'=>$sql];$body=$m[1];
        } else $body=substr($sql,strlen('ALTER TABLE '.$name));
        foreach(splitSql(trim($body),',') as $line) {
            if($i===0) {definition($all[$name],$line);continue;}
            if(preg_match('/\ADROP INDEX ([a-z_]+)\z/',$line,$m)) {
                check(isset($all[$name]['indexes'][$m[1]]),'drop_existing_index');unset($all[$name]['indexes'][$m[1]]);continue;
            }
            check((bool)preg_match('/\A(ADD COLUMN|MODIFY COLUMN|ADD) (.*)\z/s',$line,$m),'unit_alter');
            definition($all[$name],$m[2],$m[1]==='MODIFY COLUMN');
        }
    }
    return $all;
}

function totals(array $schema): array {
    $r=['tables'=>count($schema),'columns'=>0,'primary'=>0,'unique'=>0,'secondary'=>0,'foreign_keys'=>0,'checks'=>0];
    foreach($schema as $t) {
        $r['columns']+=count($t['columns']);$r['foreign_keys']+=count($t['fks']);$r['checks']+=count($t['checks']);
        foreach($t['indexes'] as $key=>$v)$r[$key==='PRIMARY'?'primary':($v['unique']?'unique':'secondary')]++;
    }return $r;
}

function showColumns(string $show,array $expected): void {
    preg_match_all('/^  `([a-z_0-9]+)` ([^\n]+),?$/m',$show,$matches,PREG_SET_ORDER);
    same(array_column($matches,1),array_keys($expected),'show_column_order');
    foreach($matches as $m) {
        $column=$expected[$m[1]];$tail=rtrim($m[2],',');
        check(str_starts_with(strtolower($tail),$column['type'].' ')||strtolower($tail)===$column['type'],'show_column_type');
        same(str_contains($tail,'NOT NULL'),$column['nullable']==='NO','show_nullability');
        same(str_contains($tail,'AUTO_INCREMENT'),$column['extra']==='auto_increment','show_auto_increment');
        if($column['collation']!==null&&$column['collation']!=='utf8mb4_0900_ai_ci')
            check(str_contains($tail,'COLLATE '.$column['collation']),'show_column_collation');
        if($column['default']!==null)check(str_contains($tail,"DEFAULT '".$column['default']."'")||str_contains($tail,'DEFAULT '.$column['default']),'show_column_default');
    }
}

function showForeignKeys(string $show): array {
    $result=[];
    $identifier='`([a-z_][a-z_0-9]*)`';
    $list=function(string $text): array {
        $columns=[];
        foreach(explode(',',$text) as $part) {
            check(preg_match('/\A\s*`([a-z_][a-z_0-9]*)`\s*\z/',$part,$m)===1,'show_fk_identifier');
            $columns[]=$m[1];
        }
        same(count(array_unique($columns)),count($columns),'show_fk_duplicate_column');
        return $columns;
    };
    foreach(explode("\n",$show) as $line) {
        if(!preg_match('/^\s*CONSTRAINT\b.*\bFOREIGN KEY\b/',$line))continue;
        check(preg_match('/^\s*CONSTRAINT '.$identifier.' FOREIGN KEY\s*\(([^()]*)\) REFERENCES '.$identifier.'\s*\(([^()]*)\)(?: ON DELETE (RESTRICT|NO ACTION|CASCADE|SET NULL))?(?: ON UPDATE (RESTRICT|NO ACTION|CASCADE|SET NULL))?\s*,?\s*$/',$line,$m)===1,'show_fk_grammar');
        check(!isset($result[$m[1]]),'show_fk_duplicate_constraint');
        $columns=$list($m[2]);$targets=$list($m[4]);
        same(count($columns),count($targets),'show_fk_arity');
        check(in_array($m[6]??'NO ACTION',['NO ACTION','RESTRICT'],true),'show_fk_update_rule');
        $result[$m[1]]=['columns'=>$columns,'table'=>$m[3],'targets'=>$targets,'delete'=>$m[5]??'NO ACTION'];
    }
    return $result;
}

function compareShowForeignKeys(string $show,array $expected,string $name): void {
    same(showForeignKeys($show),$expected,'show_fk:'.$name);
}

function structure(PDO $p,array $schema,?string $diagnosticsPath=null): array {
    $names=array_keys($schema);sort($names);same(\Mosa2\Phase2\tables($p),$names,'unit_table_set');$evidence=[];
    foreach($schema as $name=>$t) {
        $show=$p->query('SHOW CREATE TABLE '.qi($name))->fetch(PDO::FETCH_NUM)[1];
        $meta=rows($p,'SELECT ENGINE,TABLE_COLLATION,TABLE_TYPE,AUTO_INCREMENT FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=?',$name);
        same(array_diff_key($meta[0],['AUTO_INCREMENT'=>true]),['ENGINE'=>'InnoDB','TABLE_COLLATION'=>'utf8mb4_0900_ai_ci','TABLE_TYPE'=>'BASE TABLE'],'unit_table_options');
        $columns=rows($p,'SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,EXTRA,COLLATION_NAME,CHARACTER_SET_NAME,COLUMN_DEFAULT,GENERATION_EXPRESSION FROM information_schema.columns WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? ORDER BY ORDINAL_POSITION',$name);
        $actual=[];foreach($columns as $c) {
            same($c['GENERATION_EXPRESSION'],'','unit_generated');
            $actual[$c['COLUMN_NAME']]=['type'=>$c['COLUMN_TYPE'],'nullable'=>$c['IS_NULLABLE'],'extra'=>$c['EXTRA'],
                'collation'=>$c['COLLATION_NAME'],'charset'=>$c['CHARACTER_SET_NAME'],'default'=>$c['COLUMN_DEFAULT']];
        }
        same(array_keys($actual),array_keys($t['columns']),'unit_column_order:'.$name);same($actual,$t['columns'],'unit_columns:'.$name);showColumns($show,$actual);
        $indexes=rows($p,'SELECT INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SEQ_IN_INDEX,SUB_PART,INDEX_TYPE,IS_VISIBLE,COLLATION,EXPRESSION FROM information_schema.statistics WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? ORDER BY INDEX_NAME,SEQ_IN_INDEX',$name);
        $actual=[];foreach($indexes as $v) {
            same([$v['SUB_PART'],$v['INDEX_TYPE'],$v['IS_VISIBLE'],$v['COLLATION'],$v['EXPRESSION']],[null,'BTREE','YES','A',null],'unit_index_options');
            $actual[$v['INDEX_NAME']]['unique']=(int)$v['NON_UNIQUE']===0;$actual[$v['INDEX_NAME']]['columns'][]=$v['COLUMN_NAME'];
        }
        same($actual,$t['indexes'],'unit_indexes:'.$name);
        foreach($actual as $key=>$index) {
            $needle=($key==='PRIMARY'?'PRIMARY KEY':($index['unique']?'UNIQUE KEY ':'KEY ').qi($key)).' ('.implode(',',array_map(__NAMESPACE__.'\\showIdentifier',$index['columns'])).')';
            check(str_contains($show,$needle),'show_index:'.$name);
        }
        $constraints=rows($p,'SELECT CONSTRAINT_NAME,CONSTRAINT_TYPE,ENFORCED FROM information_schema.table_constraints WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=?',$name);
        $actual=[];$wanted=[];foreach($constraints as $v){same($v['ENFORCED'],'YES','unit_enforced');$actual[$v['CONSTRAINT_NAME']]=$v['CONSTRAINT_TYPE'];}
        foreach($t['indexes'] as $key=>$v)if($v['unique'])$wanted[$key]=$key==='PRIMARY'?'PRIMARY KEY':'UNIQUE';
        foreach($t['fks'] as $key=>$v)$wanted[$key]='FOREIGN KEY';foreach($t['checks'] as $key=>$v)$wanted[$key]='CHECK';same($actual,$wanted,'unit_constraints:'.$name);
        $fk=rows($p,'SELECT k.CONSTRAINT_NAME,k.COLUMN_NAME,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,k.REFERENCED_TABLE_SCHEMA,r.DELETE_RULE,r.UPDATE_RULE,r.UNIQUE_CONSTRAINT_NAME FROM information_schema.key_column_usage k JOIN information_schema.referential_constraints r ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME AND r.TABLE_NAME=k.TABLE_NAME WHERE k.TABLE_SCHEMA=DATABASE() AND k.TABLE_NAME=? AND k.REFERENCED_TABLE_NAME IS NOT NULL ORDER BY k.CONSTRAINT_NAME,k.ORDINAL_POSITION',$name);
        $actual=[];foreach($fk as $v) {
            $key=$v['CONSTRAINT_NAME'];check(isset($t['fks'][$key]),'unexpected_unit_fk');$expected=$t['fks'][$key];
            same($v['REFERENCED_TABLE_SCHEMA'],'h29077_mosa2_test','unit_foreign_schema');
            same($v['DELETE_RULE'],'RESTRICT','unit_delete_rule');check(in_array($v['UPDATE_RULE'],['NO ACTION','RESTRICT'],true),'unit_update_rule');
            $target=$expected['targets']??[$expected['target']];$parentKeys=$schema[$expected['table']]['indexes'];
            check(isset($parentKeys[$v['UNIQUE_CONSTRAINT_NAME']])&&$parentKeys[$v['UNIQUE_CONSTRAINT_NAME']]['unique']&&$parentKeys[$v['UNIQUE_CONSTRAINT_NAME']]['columns']===$target,'unit_parent_key');
            $actual[$key]['columns'][]=$v['COLUMN_NAME'];$actual[$key]['table']=$v['REFERENCED_TABLE_NAME'];
            $actual[$key]['targets'][]=$v['REFERENCED_COLUMN_NAME'];$actual[$key]['delete']=$v['DELETE_RULE'];
        }
        $wanted=[];foreach($t['fks'] as $key=>$v)$wanted[$key]=['columns'=>$v['columns']??[$v['column']],'table'=>$v['table'],'targets'=>$v['targets']??[$v['target']],'delete'=>$v['delete']];
        same($actual,$wanted,'unit_fks:'.$name);
        compareShowForeignKeys($show,$wanted,$name);
        $checks=rows($p,'SELECT c.CONSTRAINT_NAME,c.CHECK_CLAUSE FROM information_schema.check_constraints c JOIN information_schema.table_constraints t ON t.CONSTRAINT_SCHEMA=c.CONSTRAINT_SCHEMA AND t.CONSTRAINT_NAME=c.CONSTRAINT_NAME WHERE t.TABLE_SCHEMA=DATABASE() AND t.TABLE_NAME=?',$name);
        $comparisons=[];foreach($checks as $v) {
            $key=$v['CONSTRAINT_NAME'];check(isset($t['checks'][$key]),'unexpected_unit_check');
            $comparison=compareCheck($name,$key,$t['checks'][$key],$v['CHECK_CLAUSE'],$show,true);$comparisons[$key]=$comparison;
            if(!$comparison['equal']&&$diagnosticsPath!==null)saveCheckFailure($diagnosticsPath,$comparison);
            check($comparison['equal'],'unit_check_expression:'.$key);
        }
        same(count($comparisons),count($t['checks']),'unit_check_count');
        $evidence[$name]=['show_create'=>$show,'table'=>$meta[0],'columns'=>$columns,'indexes'=>$indexes,'constraints'=>$constraints,'foreign_keys'=>$fk,'checks'=>$checks,'comparisons'=>$comparisons];
    }
    return ['counts'=>totals($schema),'metadata'=>$evidence];
}
function saveCheckFailure(string $path,array $comparison): void {\Mosa2\Phase2\save($path,$comparison);}
function showIdentifier(string $name): string {return qi($name);}
