<?php
declare(strict_types=1);
// Only the already guarded ephemeral service. No hosting config or password loading.
$backupStage='BACKUP_PHP_MODE_REJECTED';
try{
if(getenv('GITHUB_ACTIONS')!=='true'||getenv('MOSA2_ISOLATED_MYSQL')!=='1'||getenv('MOSA2_BACKUP_RESTORE_ISOLATED')!=='1')throw new RuntimeException();
$r=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
$backupStage='BACKUP_PHP_SCOPE_REJECTED';
if(!in_array($r['database'],['h29077_mosa2_test','mosa2_restore_isolated_a','mosa2_restore_isolated_b','mosa2_restore_isolated_fault'],true))throw new RuntimeException();
$backupStage='BACKUP_PHP_MODULE_REJECTED';
require dirname(__DIR__).'/scripts/market_collector/migration5_audit.php';
require dirname(__DIR__).'/scripts/market_collector/migration5_capture.php';
require dirname(__DIR__).'/api/current_read.php';
require_once dirname(__DIR__).'/api/observations_read.php';
$source=file_get_contents(dirname(__DIR__).'/scripts/phase3k/unit_schema.php');$source=substr($source,strpos($source,'function structure('));
preg_match_all('/rows\(\$p,\x27([^\x27]+)\x27,\$name\)/',$source,$m);
define('Mosa2\\CollectorMigration5\\METADATA_QUERIES',$m[1]);
$backupStage='BACKUP_PHP_CONNECTION_REJECTED';
$p=new PDO('mysql:host=127.0.0.1;port=3307;dbname='.$r['database'].';charset=utf8mb4','root','',
    [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_STRINGIFY_FETCHES=>true]);
$id=$p->query('SELECT DATABASE() AS db,VERSION() AS version,@@port AS port,@@server_uuid AS uuid,@@hostname AS hostname,@@event_scheduler AS scheduler')->fetch();
foreach(['db'=>$r['database'],'port'=>'3306','uuid'=>getenv('MOSA2_ISOLATED_SERVER_UUID'),'hostname'=>getenv('MOSA2_ISOLATED_SERVER_HOSTNAME'),'scheduler'=>'OFF'] as $key=>$expected){
    $backupStage='BACKUP_PHP_IDENTITY_'.strtoupper($key);if($id[$key]!==$expected)throw new RuntimeException();
}
$backupStage='BACKUP_PHP_VERSION_REJECTED';if(!str_starts_with($id['version'],'8.0.'))throw new RuntimeException();
$backupStage='BACKUP_PHP_TRANSACTION_REJECTED';
$p->exec("SET SESSION time_zone='+00:00'");$p->exec('SET SESSION max_execution_time=10000');$p->exec('SET SESSION TRANSACTION READ ONLY');
    $p->beginTransaction();
    $backupStage='BACKUP_PHP_VALIDATION_REJECTED';
    if($p->query('SELECT @@session.transaction_read_only')->fetchColumn()!=='1')throw new RuntimeException('fixture_read_only');
    $out=\Mosa2\CollectorMigration5\capture($p);
    \Mosa2\MarketLive\runtimeContract($p,['schema_version'=>$r['version'],'allow_current'=>true]);
    $p->rollBack();
    $out['current']=\Mosa2\MarketRead\read($p,['stale_seconds'=>1800],'2026-01-01 01:00:00.000000');
    $out['observations']=\Mosa2\ObservationRead\read($p,['stale_seconds'=>1800],'2026-01-01 01:00:00.000000');
    echo json_encode(['ok'=>true,'result'=>$out],JSON_THROW_ON_ERROR);
}catch(Throwable){echo json_encode(['ok'=>false,'code'=>$backupStage],JSON_THROW_ON_ERROR);}
finally{if(isset($p)&&$p->inTransaction())$p->rollBack();}
