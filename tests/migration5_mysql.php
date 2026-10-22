<?php
declare(strict_types=1);
// Destructive synthetic fixtures are never reachable through a Dogado connection.
if(getenv('GITHUB_ACTIONS')!=='true'||getenv('MOSA2_ISOLATED_MYSQL')!=='1')exit(2);
require dirname(__DIR__).'/scripts/market_collector/migration5_audit.php';
require dirname(__DIR__).'/scripts/market_collector/migration5_capture.php';
require dirname(__DIR__).'/api/current_read.php';
require_once dirname(__DIR__).'/api/observations_read.php';
require_once dirname(__DIR__).'/scripts/market_current/preview_read.php';
$source=file_get_contents(dirname(__DIR__).'/scripts/phase3k/unit_schema.php');$source=substr($source,strpos($source,'function structure('));
preg_match_all('/rows\(\$p,\x27([^\x27]+)\x27,\$name\)/',$source,$m);
define('Mosa2\\CollectorMigration5\\METADATA_QUERIES',$m[1]);
$p=new PDO('mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4','root','',
    [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_STRINGIFY_FETCHES=>true]);
$id=$p->query('SELECT DATABASE() AS db,VERSION() AS version,@@port AS port')->fetch();
if($id['db']!=='h29077_mosa2_test'||!str_starts_with($id['version'],'8.0.')||$id['port']!=='3306')exit(2);
$request=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
$p->exec('SET SESSION TRANSACTION READ ONLY');
if($request['operation']!=='current')$p->beginTransaction();
try{
    if($request['operation']==='capture')$out=\Mosa2\CollectorMigration5\capture($p);
    elseif($request['operation']==='wire')$out=\Mosa2\CurrentPreview\gather($p,'2026-01-01 01:00:00.000000')+['migration5'=>\Mosa2\CollectorMigration5\packed($p)];
    elseif($request['operation']==='contracts'){
        $contract=['schema_version'=>$request['version'],'allow_current'=>true];
        $out=['snapshot'=>\Mosa2\MarketLive\snapshot($p,$contract),'runtime'=>\Mosa2\MarketLive\runtimeContract($p,$contract)];
    }elseif($request['operation']==='current')$out=['current'=>\Mosa2\MarketRead\read($p,['stale_seconds'=>1800],'2026-01-01 01:00:00.000000'),
        'observations'=>\Mosa2\ObservationRead\read($p,['stale_seconds'=>1800],'2026-01-01 01:00:00.000000')];
    else throw new RuntimeException('fixture_operation');
    echo json_encode(['ok'=>true,'result'=>$out],JSON_THROW_ON_ERROR);
}catch(Throwable $e){echo json_encode(['ok'=>false,'code'=>$e->getMessage()],JSON_THROW_ON_ERROR);}
finally{if($p->inTransaction())$p->rollBack();}
