<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/api/market_provider_lab.php';
use function Mosa2\ProviderLab\{inspect,rawInventory};
function tSame(mixed $actual,mixed $expected,string $name):void {
    if($actual!==$expected)throw new RuntimeException($name.': '.json_encode([$actual,$expected]));
}
$isin='KYG9830T1067';
$now=new DateTimeImmutable('2026-11-12T19:00:00Z');
$raw=[
 'lang_schwarz_search'=>json_encode(['data'=>[
     ['isin'=>$isin,'instrumentId'=>23,'marketId'=>1,'categorySymbol'=>'STK',
      'link'=>'/de/aktie/23','name'=>'Testgesellschaft','wkn'=>'A0TEST','unbekanntesFeld'=>'sichtbar']]]),
 'lang_schwarz_page'=>'<div item="23@1" field="bid">12,00</div><div item="23@1" field="ask">12,50</div><div item="23@1" field="bidSize">100</div><div item="23@1" field="askSize">200</div><div item="23@1" field="midTime">12.11.2026 19:00:00</div>',
 'tradegate_quote'=>'<h2>Testgesellschaft</h2><table><tr><th>ISIN</th><th>Handelswährung</th></tr><tr><td>'.$isin.'</td><td>EUR</td></tr><tr><td>Bid</td><td>12,00</td></tr><tr><td>Ask</td><td>12,50</td></tr><tr><td>Bid Size</td><td>90</td></tr><tr><td>Ask Size</td><td>110</td></tr><tr><td>Stück</td><td>1234</td></tr></table><p>Letzte Aktualisierung: 12.11.2026 @ 18:59:00</p>',
 'tradegate_trade'=>'<table><tr><td>12.11.2026</td><td>18:59:00</td><td>50</td><td>XGAT</td><td>12,30</td></tr></table>',
 'boerse_frankfurt_trade'=>json_encode(['isin'=>$isin,'mic'=>'XFRA','currency'=>['originalValue'=>'EUR'],
     'lastPrice'=>12.35,'timestampLastPrice'=>'2026-11-12T18:58:00Z',
     'weeks52High'=>50,'weeks52Low'=>4.5,'marketCapitalization'=>1234567,
     'turnoverInEur'=>56789,'priceFixings'=>12,'extraUnlisted'=>777]),
];
$sent=[];
$transport=static function(array $request)use($raw,&$sent):array{
    $key=$request['request_key'];
    if(!isset($raw[$key]))throw new RuntimeException('Excluded provider was sent');
    $sent[]=$key;
    return ['body'=>$raw[$key],'http_status'=>200,'latency_ms'=>3,'error_code'=>null];
};
$result=inspect($isin,$transport,$now);
tSame($result['request_count'],5,'five approved requests');
tSame($sent,['lang_schwarz_search','lang_schwarz_page','tradegate_quote',
    'tradegate_trade','boerse_frankfurt_trade'],'Yahoo never sent');
tSame(count($result['providers']),3,'three providers');
tSame($result['storage'],'none','read only');
tSame($result['identity']['name'],'Testgesellschaft','exact ISIN resolved');
tSame($result['identity']['wkn'],'A0TEST','WKN from search');
$providers=array_column($result['providers'],null,'key');
$ls=$providers['lang_schwarz'];$tg=$providers['tradegate_bsx'];$fr=$providers['boerse_frankfurt_api'];
$flatten=static fn(array $rows):string=>json_encode($rows,JSON_UNESCAPED_UNICODE);
if(!str_contains($flatten($ls['fields']),'bid_size')||!str_contains($flatten($ls['fields']),'ask_size'))
    throw new RuntimeException('L&S bid/ask sizes lost');
if(!str_contains($flatten($ls['raw_fields']),'unbekanntesFeld'))
    throw new RuntimeException('unlisted L&S field lost');
if(!str_contains($flatten($tg['raw_fields']),'Bid Size')||!str_contains($flatten($tg['raw_fields']),'12,30'))
    throw new RuntimeException('Tradegate orderbook/trades missing');
foreach(['weeks52High','marketCapitalization','turnoverInEur','priceFixings','extraUnlisted'] as $field)
    if(!str_contains($flatten($fr['raw_fields']),$field))throw new RuntimeException('Frankfurt unknown field '.$field);
if(str_contains($flatten($result),'yahoo_home_market'))throw new RuntimeException('Yahoo leaked');
$partial=inspect($isin,static function(array $request)use($raw):array{
    $key=$request['request_key'];
    if($key==='tradegate_quote')return ['body'=>'','http_status'=>503,'latency_ms'=>4,'error_code'=>'provider_unavailable'];
    return ['body'=>$raw[$key],'http_status'=>200,'latency_ms'=>2,'error_code'=>null];
},$now);
$p=array_column($partial['providers'],null,'key');
tSame($p['tradegate_bsx']['requests'][0]['http_status'],503,'provider fault visible');
tSame($p['boerse_frankfurt_api']['requests'][0]['http_status'],200,'others still visible');
try{inspect('KYG9830T1066',$transport,$now);throw new RuntimeException('invalid accepted');}
catch(InvalidArgumentException $ok){}
$private=rawInventory(['body'=>json_encode(['bid'=>1,'secretToken'=>'shhhh','nested'=>['new_field'=>55]]) ,
    'content_type'=>'application/json'],'example');
if(str_contains($flatten($private),'shhhh'))throw new RuntimeException('secret field leaked');
if(!str_contains($flatten($private),'new_field'))throw new RuntimeException('unknown field omitted');
$source=file_get_contents(dirname(__DIR__).'/api/market_provider_lab.php');
foreach(['new PDO','mysqli','file_put_contents','m2_market_observations','m2_market_current'] as $forbidden)
    if(str_contains($source,$forbidden))throw new RuntimeException('storage code present');
echo "PASS provider lab: five read-only requests, exact ISIN, 3 providers, extra raw fields, partial failure, excluded Yahoo, no DB\n";
