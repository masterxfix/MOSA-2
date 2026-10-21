<?php
declare(strict_types=1);
require dirname(__DIR__).'/scripts/market_collector/live_batch.php';
$in=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);$calls=[];$events=[];
try {
    if(isset($in['dogado_source']))eval($in['dogado_source']);
    if(($in['action']??'')==='outcome_guard'){
        echo json_encode(['before'=>\Mosa2\DogadoBatch\exceptionOutcome(false),'after'=>\Mosa2\DogadoBatch\exceptionOutcome(true)]);exit;
    }
    if(($in['action']??'')==='qualify'){
        $qualified=\Mosa2\DogadoBatch\qualify($in['state'],$in['selection'],static fn($state,$s)=>$in['qualified_manifests'][$s['isin']]);
        echo json_encode(['ok'=>true,'qualified_count'=>count($qualified),'calls'=>[]]);exit;
    }
    $config=['public_root'=>$in['public_root']];
    if(($in['action']??'')==='invalid_run')$report=\Mosa2\MarketBatch\run($in['private_root'],'unused',$config,$in['entries']);
    else {
        $prepared=\Mosa2\MarketBatch\prepare($in['private_root'],$in['public_root'],$in['entries']);
        $coordinator=isset($in['dogado_source'])?'Mosa2\\DogadoBatch\\coordinate':'Mosa2\\MarketBatch\\execute';
        $report=$coordinator($prepared,static function($entry)use(&$calls,&$events,$in){
            $position=count($calls);$calls[]=$entry['manifest']['identity']['normalized_value'];$events[]='start:'.$position;
            $outcome=$in['outcomes'][$position]??[];
            if($outcome['throw']??false)throw new RuntimeException('synthetic runner exception');
            $result=['ok'=>true,'committed'=>true,'provider_requests'=>1,'database_connections'=>2,'policy'=>'USE_EXISTING_ROUTE',
                'asset_plan'=>'EXISTING_MATCH','route_plan'=>'EXISTING_MATCH','writer'=>'INSERT','replay'=>'DUPLICATE_UNCHANGED','readback'=>'PASS',
                'deltas'=>['m2_entities'=>0,'m2_assets'=>0,'m2_asset_identifiers'=>0,'m2_asset_source_routes'=>0,'m2_market_observations'=>1],
                'private_evidence'=>['plan'=>['source'=>['decision'=>'EXISTING_MATCH']]]];
            $events[]='finish:'.$position;return array_replace($result,$outcome);
        });
    }
    echo json_encode(['ok'=>true,'batch'=>$report,'calls'=>$calls,'events'=>$events],JSON_THROW_ON_ERROR);
}catch(Throwable $e){echo json_encode(['ok'=>false,'error'=>$e->getMessage(),'calls'=>$calls,'events'=>$events],JSON_THROW_ON_ERROR);}
