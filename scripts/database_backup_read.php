<?php
declare(strict_types=1);
namespace Mosa2\BackupRead;
require_once __DIR__.'/market_collector/migration5_audit.php';
require_once __DIR__.'/market_collector/migration5_capture.php';
require_once dirname(__DIR__).'/api/current_read.php';
require_once dirname(__DIR__).'/api/observations_read.php';
function evidence(\PDO $p,int $version,string $now='2026-01-01 01:00:00.000000'): array {
    \Mosa2\Phase2\check($version===4||$version===5,'backup_schema');
    $p->setAttribute(\PDO::ATTR_STRINGIFY_FETCHES,true); // Same evidence types across source and isolated readback.
    $source=file_get_contents(__DIR__.'/phase3k/unit_schema.php');$source=substr($source,strpos($source,'function structure('));
    preg_match_all('/rows\(\$p,\x27([^\x27]+)\x27,\$name\)/',$source,$m);
    \Mosa2\Phase2\same(count($m[1]),6,'backup_metadata');
    if(!defined('Mosa2\CollectorMigration5\METADATA_QUERIES'))define('Mosa2\CollectorMigration5\METADATA_QUERIES',$m[1]);
    $p->exec("SET SESSION time_zone='+00:00'");
    $p->exec('SET SESSION max_execution_time=10000');
    $p->exec('SET SESSION TRANSACTION READ ONLY');$p->beginTransaction();
    try {
        \Mosa2\Phase2\check((string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn()==='1','backup_readonly');
    $out=\Mosa2\CollectorMigration5\capture($p);
    \Mosa2\MarketLive\runtimeContract($p,['schema_version'=>$version,'allow_current'=>true]);
    $p->rollBack();
    $out['current']=\Mosa2\MarketRead\read($p,['stale_seconds'=>1800],$now);
    $out['observations']=\Mosa2\ObservationRead\read($p,['stale_seconds'=>1800],$now);

        return $out;
    }finally{if($p->inTransaction())$p->rollBack();}
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    ini_set('display_errors','0');ini_set('log_errors','0');
    try{
        $wire=stream_get_contents(STDIN,8193);\Mosa2\Phase2\check(strlen($wire)<=8192,'input');
        $in=json_decode($wire,true,32,JSON_THROW_ON_ERROR);
        $p=\Mosa2\Phase2\connection($in['password'],'127.0.0.1',$in['port']);unset($in['password'],$wire);
        echo json_encode(['ok'=>true,'result'=>evidence($p,4,$in['now'])],JSON_THROW_ON_ERROR);
    }catch(\Throwable){echo '{"ok":false,"code":"BACKUP_SOURCE_EVIDENCE_REJECTED"}';}
}