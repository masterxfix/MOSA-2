<?php
declare(strict_types=1);
namespace Mosa2\CollectorSchema6;
use PDO;
use function Mosa2\Phase2\{check,same,splitSql};
require_once __DIR__.'/schema5.php';

/** Extend the existing restricted parser only for 0006's auto-increment BIGINTs. */
function extend(array $all): array {
    \Mosa2\CollectorSchema5\envelope(6);
    $sql=file_get_contents(dirname(__DIR__,2).'/docs/database/migrations/0006_fundamentals_and_payload_provenance.sql');
    $parts=splitSql(preg_replace('/^\s*--[^\n]*$/m','',$sql),';');
    same(array_pop($parts),'','schema6_semicolon');same(count($parts),5,'schema6_five_creates');
    $names=[];
    foreach($parts as $statement){
        check(preg_match('/\ACREATE TABLE (m2_[a-z_]+) \((.*)\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci\z/s',$statement,$m)===1,'schema6_create');
        $name=$m[1];check(!isset($all[$name]),'schema6_duplicate');$names[]=$name;
        $t=['columns'=>[],'indexes'=>[],'fks'=>[],'checks'=>[],'ddl'=>$statement];
        foreach(splitSql($m[2],',') as $line){
            if(preg_match('/\A([a-z_0-9]+) BIGINT UNSIGNED NOT NULL AUTO_INCREMENT\z/',$line,$col)){
                check(!isset($t['columns'][$col[1]]),'schema6_duplicate_column');
                $t['columns'][$col[1]]=['type'=>'bigint unsigned','nullable'=>'NO','extra'=>'auto_increment','collation'=>null,'charset'=>null,'default'=>null];
            }else \Mosa2\CollectorSchema5\definition($t,$line);
        }
        $all[$name]=$t;
    }
    same($names,\Mosa2\CollectorSchema5\FUNDAMENTALS,'schema6_five_tables');
    $names=array_keys($all);sort($names);same($names,\Mosa2\CollectorSchema5\envelope(6)['tables'],'schema6_exact_tables');
    return $all;
}
/** Runner/private runtime scratch only; no connection, DDL, DML, seed or activation. */
function schemas(): array {
    $envelope=\Mosa2\CollectorSchema5\envelope(6);
    $files=glob(dirname(__DIR__,2).'/docs/database/migrations/000[1-3]_*.sql');sort($files);
    same(count($files),3,'schema6_artifacts');
    $root=tempnam(sys_get_temp_dir(),'mosa2-schema6-');check($root!==false,'schema6_temp');
    check(unlink($root)&&mkdir($root,0700),'schema6_workdir');
    try{
        foreach($files as $i=>$file){
            $target=$root.'/'.sprintf('%04d',$i+1).'.sql';$out=fopen($target,'x');check($out!==false,'schema6_stage');
            try{$raw=file_get_contents($file);check($raw!==false&&fwrite($out,$raw)===strlen($raw),'schema6_write');}
            finally{fclose($out);}
            same(hash_file('sha256',$target),$envelope['digests'][$i],'schema6_staged_hash');
        }
        return \Mosa2\CollectorSchema5\schemas($root,6);
    }finally{
        for($i=1;$i<=3;$i++){$f=$root.'/'.sprintf('%04d',$i).'.sql';if(is_file($f))unlink($f);}
        rmdir($root);
    }
}
/** Shared exact metadata checker, including every old and new column/index/FK/CHECK. */
function database(PDO $p,array $allowedAdditiveTables=[]): array {
    return \Mosa2\Phase3K\structure($p,schemas(),null,$allowedAdditiveTables);
}
