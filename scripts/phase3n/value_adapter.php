<?php
declare(strict_types=1);
namespace Mosa2\Phase3N;
require_once __DIR__.'/../phase3c/market_flow.php';
use function Mosa2\Phase3C\{identity,decimal,utcTimestamp,compareDecimal,requireValue};

// Local stdio adapter only. Reuse v1 primitives without changing v1 or inventing
// a monetary currency for a nonmonetary observation. No persistence capability.
function values(array $input): array {
    $row=[];
    foreach(['asset_id','source_id','route_id'] as $field)$row[$field]=identity($input[$field]);
    $currency=$input['currency'];
    requireValue($currency===null||(is_string($currency)&&preg_match('/\A[A-Z]{3}\z/D',$currency)===1),'currency');
    $row['currency']=$currency;
    foreach(['market_at','observed_at'] as $field)$row[$field]=utcTimestamp($input[$field]);
    foreach(['price','bid','ask'] as $field)$row[$field]=decimal($input[$field],28,10,$field!=='price');
    $row['volume']=decimal($input['volume'],32,8,true);
    requireValue(compareDecimal($row['price'],'0.0000000000')>0,'price');
    requireValue($row['bid']===null||$row['ask']===null||compareDecimal($row['bid'],$row['ask'])<=0,'bid_ask');
    return $row;
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    try {
        $request=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
        $result=match($request['operation']) {
            'values'=>values($request['row']),
            'legacy'=>['row'=>\Mosa2\Phase3C\normalizeObservation($request['row']),
                'canonical'=>\Mosa2\Phase3C\canonicalObservation($request['row']),
                'dedupe_hex'=>bin2hex(\Mosa2\Phase3C\dedupeKey($request['row']))],
            'timestamp'=>utcTimestamp($request['value']),
            'identity'=>identity($request['value']),
            default=>throw new \InvalidArgumentException('operation'),
        };
        echo json_encode(['ok'=>true,'result'=>$result],JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);
    }catch(\Throwable $error){echo json_encode(['ok'=>false,'reason'=>$error->getMessage()],JSON_THROW_ON_ERROR);}
}
