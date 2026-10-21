<?php
declare(strict_types=1);
namespace Mosa2\Phase3N;
require_once __DIR__.'/primitives.php';
use function Mosa2\MarketCore\{identity,decimal,utcTimestamp,compareDecimal,requireValue};
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
