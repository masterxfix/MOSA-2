<?php
declare(strict_types=1);
require dirname(__DIR__).'/scripts/market_collector/tradegate_manifest.php';
$in=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
try{
    if($in['action']==='source')$out=\Mosa2\TradegateQuote\sourcePlan($in['sources'],$in['now']);
    elseif($in['action']==='manifest'){
        $manifest=\Mosa2\TradegateQuote\manifest($in['state'],$in['selection']);
        $out=['manifest'=>$manifest,'plan'=>\Mosa2\MarketLive\completePlan($in['state'],$manifest),
            'candidate'=>\Mosa2\Phase3D\candidate($manifest['route_evidence'])];
    }else throw new RuntimeException('unknown_test_action');
    echo json_encode(['ok'=>true,'result'=>$out],JSON_THROW_ON_ERROR);
}catch(Throwable $e){echo json_encode(['ok'=>false,'error'=>$e->getMessage()],JSON_THROW_ON_ERROR);}
