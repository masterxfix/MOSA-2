<?php
declare(strict_types=1);
// Synthetic service only. No production credential, hostname, launcher or provider.
if(getenv('GITHUB_ACTIONS')!=='true'||getenv('MOSA2_ISOLATED_MYSQL')!=='1')exit(2);
require dirname(__DIR__).'/scripts/market_current/refresh.php';
require_once dirname(__DIR__).'/scripts/market_collector/runtime_persistence.php';
$p=new PDO('mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4','root','',
    [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_STRINGIFY_FETCHES=>true]);
$id=$p->query('SELECT DATABASE() AS db,VERSION() AS version,@@port AS port')->fetch();
if($id['db']!=='h29077_mosa2_test'||!str_starts_with($id['version'],'8.0.')||$id['port']!=='3306')exit(2);
$r=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);$requests=0;
try{
    $contract=\Mosa2\MarketCurrent\stateContract($r['config']);
    $capture=static fn(PDO $db)=>\Mosa2\MarketLive\snapshot($db,$contract);
    $before=$capture($p);
    $runtime=\Mosa2\MarketLive\runtimeContract($p,$contract);
    if($r['operation']==='contract')$out=['tables'=>count($before),'ledger'=>count($runtime['m2_schema_migrations'])];
    elseif($r['operation']==='collector'){
        // The real runtime path owns its preflight. The fake callback is a tripwire, never a transport.
        $out=\Mosa2\MarketLive\runtimeRun('SYNTHETIC',['state_contract'=>$contract],['identity'=>['identifier_type'=>'isin','normalized_value'=>'SYNTHETIC']],
            static fn()=>$p,static function()use(&$requests){$requests++;throw new RuntimeException('provider_forbidden');},
            static function(PDO $db,array $m,array $c){\Mosa2\MarketLive\runtimeContract($db,$c);\Mosa2\CollectorSchema5\acquisitionAllowed($c);throw new RuntimeException('synthetic_schema4_no_provider');});
    }elseif($r['operation']==='current'){
        $now='2026-01-01 01:00:00.000000';$approvals=[];
        // Explicit synthetic approval, generated only inside this guarded fixture.
        foreach($r['routes'] as $route){
            $item=\Mosa2\MarketCurrent\inputs($p,[['route_id'=>$route]],$now)[0];$bound=$item['route'];ksort($bound);
            $approvals[]=['route_id'=>$route,'route_sha256'=>hash('sha256',json_encode($bound,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR)),
                'approved_at'=>$now,'allow_disabled_projection'=>$r['allow_disabled']??false];
        }
        $config=['python'=>$r['python'],'project'=>dirname(__DIR__),'runtime_path'=>getenv('PATH')];
        $reader=static fn(PDO $db,string $clock)=>\Mosa2\MarketCurrent\inputs($db,$approvals,$clock);
        $planner=static fn($items)=>\Mosa2\MarketCurrent\plans($config,$items);
        $result=\Mosa2\MarketCurrent\transaction($p,$reader,$planner,$capture);
        // Different physical PDO connection; actual independent readback and planner replay.
        $read=new PDO('mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4','root','',
            [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_STRINGIFY_FETCHES=>true]);
        $read->exec('SET SESSION TRANSACTION READ ONLY');$read->beginTransaction();
        if($read->query('SELECT @@session.transaction_read_only')->fetchColumn()!=='1')throw new RuntimeException('fixture_readonly');
        try{$verified=\Mosa2\MarketCurrent\verifyReadback($result,$capture($read),$planner($reader($read,$now)));}
        finally{$read->rollBack();}
        $out=['decisions'=>$result['decisions'],'readback'=>$verified['readback'],'replay'=>'UNCHANGED','unchanged'=>$before===$capture($p)];
    }else throw new RuntimeException('fixture_operation');
    echo json_encode(['ok'=>true,'result'=>$out,'provider_requests'=>$requests],JSON_THROW_ON_ERROR);
}catch(Throwable $e){echo json_encode(['ok'=>false,'code'=>$e instanceof PDOException?'database_contract_rejected':$e->getMessage(),'provider_requests'=>$requests],JSON_THROW_ON_ERROR);}
finally{if($p->inTransaction())$p->rollBack();}
