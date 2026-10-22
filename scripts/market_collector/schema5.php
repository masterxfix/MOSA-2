<?php
declare(strict_types=1);
namespace Mosa2\CollectorSchema5;
use PDO;
use function Mosa2\Phase2\{check,same,splitSql};
require_once __DIR__.'/../market_current/migration.php';

require_once __DIR__.'/schema_contract.php';
function artifact(): string {return dirname(__DIR__,2).'/docs/database/migrations/0005_collector_reservations.sql';}
function statements(): array {
    $sql=file_get_contents(artifact());same(hash('sha256',$sql),DIGEST,'schema5_artifact');
    $parts=splitSql(preg_replace('/^\s*--[^\n]*$/m','',$sql),';');same(array_pop($parts),'','schema5_semicolon');
    same(count($parts),8,'schema5_eight_steps');return $parts;
}
/** Narrow extension for the unchanged 0005 DDL; rejects every unknown definition. */
function definition(array &$t,string $line): void {
    if(preg_match('/\A([a-z_0-9]+) (BIGINT UNSIGNED|INT UNSIGNED|TINYINT UNSIGNED|TINYINT|VARCHAR\(\d+\)|CHAR\(\d+\)|DATETIME\(6\)|DATE|JSON)(?: COLLATE ([a-z0-9_]+))? (NOT NULL|NULL)(?: DEFAULT (\d+|\x27[A-Z_]+\x27))?\z/',$line,$m)){
        check(!isset($t['columns'][$m[1]]),'schema5_duplicate_column');$text=str_starts_with($m[2],'VARCHAR')||str_starts_with($m[2],'CHAR(');
        $t['columns'][$m[1]]=['type'=>strtolower($m[2]),'nullable'=>$m[4]==='NULL'?'YES':'NO','extra'=>'',
            'collation'=>$text?($m[3]?:'utf8mb4_0900_ai_ci'):null,'charset'=>$text?'utf8mb4':null,'default'=>isset($m[5])?trim($m[5],"'"):null];return;
    }
    if(preg_match('/\ACONSTRAINT ([a-z_0-9]+) FOREIGN KEY \(([^()]+)\) REFERENCES (m2_[a-z_]+)\(([^()]+)\)\z/',$line,$m)){
        check(!isset($t['fks'][$m[1]]),'schema5_duplicate_fk');$t['fks'][$m[1]]=['columns'=>array_map('trim',explode(',',$m[2])),'table'=>$m[3],'targets'=>array_map('trim',explode(',',$m[4])),'delete'=>'NO ACTION'];return;
    }
    \Mosa2\Phase3K\definition($t,$line);
}
function schemas(string $root,int $version): array {
    $all=\Mosa2\MarketCurrentMigration\schemas($root);if($version===4)return $all;same($version,5,'schema5_version');
    foreach(array_slice(statements(),0,5) as $sql){
        if(preg_match('/\ACREATE TABLE (m2_[a-z_]+) \((.*)\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci\z/s',$sql,$m)){
            $name=$m[1];check(in_array($name,TABLES,true)&&!isset($all[$name]),'schema5_create');
            $all[$name]=['columns'=>[],'indexes'=>[],'fks'=>[],'checks'=>[],'ddl'=>$sql];$body=$m[2];
        }else{check(str_starts_with($sql,'ALTER TABLE m2_collector_state'),'schema5_alter');$name='m2_collector_state';$body=substr($sql,strlen('ALTER TABLE m2_collector_state'));}
        foreach(splitSql(trim($body),',') as $line)definition($all[$name],preg_replace('/^ADD /','',$line));
    }
    // MySQL creates these nonunique child indexes where no existing prefix covers an FK.
    foreach(TABLES as $name)foreach($all[$name]['fks'] as $key=>$fk){$covered=false;
        foreach($all[$name]['indexes'] as $index)if(array_slice($index['columns'],0,count($fk['columns']))===$fk['columns'])$covered=true;
        if(!$covered)$all[$name]['indexes'][$key]=['unique'=>false,'columns'=>$fk['columns']];
    }
    return $all;
}
