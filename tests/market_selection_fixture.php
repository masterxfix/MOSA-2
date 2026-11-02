<?php
require dirname(__DIR__).'/scripts/market_collector/selection.php';
$input=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
try { echo json_encode(['ok'=>true,'result'=>\Mosa2\MarketSelection\select($input['assets']??[],$input['identifiers']??[],$input['routes']??[],$input['currents']??[],$input['observations']??[],$input['now']??'',(int)($input['stale_seconds']??1800),(int)($input['max_assets']??1000))],JSON_THROW_ON_ERROR); }
catch(\Throwable $e){ echo json_encode(['ok'=>false,'error'=>$e->getMessage()],JSON_THROW_ON_ERROR); }
