<?php
declare(strict_types=1);
require dirname(__DIR__,2).'/api/isin_quote.php';
use function Mosa2\IsinQuote\{previewAll,sourceAllowed,sourceRecord};
function assertSameValue(mixed $actual,mixed $expected,string $label):void {
    if($actual!==$expected)throw new RuntimeException($label.' '.json_encode([$actual,$expected]));
}
$code='DE000A0JBPG2';
$quote='<!doctype html><html><body><h2>PNE AG</h2><table><tr><th>ISIN</th><th>Handelswährung</th></tr><tr><td>DE000A0JBPG2</td><td>EUR</td></tr><tr><td>Bid</td><td>5,44</td></tr><tr><td>Ask</td><td>5,56</td></tr></table><p>Letzte Aktualisierung: 02.11.2026 @ 15:02:00</p></body></html>';
$lsSearch=json_encode(['data'=>[['isin'=>$code,'instrumentId'=>123456,'marketId'=>1,'categorySymbol'=>'STK','link'=>'/de/aktie/123456','name'=>'PNE AG']]]);
$lsPage='<div item="123456@1" field="bid">5,40</div><div item="123456@1" field="ask">5,60</div><div item="123456@1" field="midTime">15:03:00</div><div item="123456@1" data-type="trades"><table><tr><td field="tradeTime">02.11. 15:04:00</td><td field="tradeWithCurrencySymbol">5,52 €</td></tr></table></div>';
$trade='<table><tr><td>02.11.2026</td><td>15:05:00</td><td>250</td><td>XGAT</td><td>5,54</td></tr></table>';
$frankfurt=json_encode(['isin'=>$code,'mic'=>'XFRA','currency'=>['originalValue'=>'EUR'],'lastPrice'=>5.58,'timestampLastPrice'=>'2026-11-02T15:06:00+01:00']);
$search=json_encode(['quotes'=>[['symbol'=>'PNE.DE','quoteType'=>'EQUITY','exchange'=>'GER','longname'=>'PNE AG','currency'=>'EUR']]]);
$chart=json_encode(['chart'=>['error'=>null,'result'=>[['meta'=>[
    'symbol'=>'PNE.DE','currency'=>'EUR','regularMarketPrice'=>5.62,
    'regularMarketTime'=>(new DateTimeImmutable('2026-11-02T14:07:00Z'))->getTimestamp(),
    'fullExchangeName'=>'Xetra']]]]]);
$fixtures=['lang_schwarz_search'=>$lsSearch,'lang_schwarz_page'=>$lsPage,'tradegate_quote'=>$quote,
    'tradegate_trade'=>$trade,'boerse_frankfurt_trade'=>$frankfurt,
    'yahoo_home_search'=>$search,'yahoo_home_market'=>$chart];
$events=[];$requests=[];
$transport=static function(array $r)use($fixtures,&$requests):array{
    $requests[]=$r['request_key'];
    if(!array_key_exists($r['request_key'],$fixtures))throw new RuntimeException('unplanned provider');
    return ['body'=>$fixtures[$r['request_key']],'http_status'=>200,'latency_ms'=>1,'error_code'=>null];
};
$result=previewAll($code,static function(array $event)use(&$events):void{$events[]=$event;},$transport);
assertSameValue($result['isin'],$code,'isin');
assertSameValue($result['name'],'PNE AG','name');
assertSameValue($result['request_count'],7,'one shared comparison, seven HTTP GETs');
assertSameValue($requests,array_keys($fixtures),'request order');
assertSameValue(count($events),14,'one start+finish per request');
assertSameValue(count($result['records']),6,'six independent source facts');
$map=array_column($result['records'],null,'provider');
assertSameValue(array_keys($map),['lang_schwarz_quote','lang_schwarz_trade','tradegate_quote',
    'tradegate_trade','boerse_frankfurt_trade','yahoo_home_market'],'provider scopes');
assertSameValue($map['lang_schwarz_quote']['status'],'ok','ls quote');
assertSameValue($map['lang_schwarz_trade']['status'],'ok','ls trade');
assertSameValue($map['tradegate_quote']['status'],'ok','tradegate quote');
assertSameValue($map['tradegate_trade']['status'],'ok','tradegate trade');
assertSameValue($map['boerse_frankfurt_trade']['status'],'ok','frankfurt trade');
assertSameValue($map['yahoo_home_market']['status'],'ok','yahoo home');
assertSameValue($map['tradegate_quote']['price'],'5.5','tradegate mid price');
assertSameValue($map['yahoo_home_market']['currency'],'EUR','yahoo native currency');
assertSameValue($map['yahoo_home_market']['symbol'],'PNE.DE','yahoo native ticker');
assertSameValue($map['tradegate_trade']['quote_type'],'Letzter Handel','trade type');
assertSameValue($map['tradegate_quote']['quote_type'],'Mid (Geld/Brief)','mid type');
$bad=['request_key'=>'yahoo_home_market','url'=>'https://attacker.example/v8/finance/chart/PNE.DE?range=1d&interval=1d&includePrePost=false'];
assertSameValue(sourceAllowed($bad,$code),false,'reject foreign host');
$bad=['request_key'=>'lang_schwarz_page','url'=>'https://www.ls-tc.de/de/aktie/123456/../../secret'];
assertSameValue(sourceAllowed($bad,$code),false,'reject traversal');
$bad=['request_key'=>'yahoo_home_search','url'=>'https://query1.finance.yahoo.com/v1/finance/search?q=WRONG&quotesCount=10&newsCount=0'];
assertSameValue(sourceAllowed($bad,$code),false,'reject unrelated ISIN search');
// Failure of one source remains visible and does not erase the other five.
$transportFault=static function(array $req)use($fixtures):array{
    if($req['request_key']==='tradegate_trade')return ['body'=>'','http_status'=>503,'latency_ms'=>1,'error_code'=>'service_unavailable'];
    return ['body'=>$fixtures[$req['request_key']],'http_status'=>200,'latency_ms'=>1,'error_code'=>null];
};
$partial=previewAll($code,static function(array $event):void{},$transportFault);
$failed=array_column($partial['records'],null,'provider');
assertSameValue($failed['tradegate_trade']['status'],'error','tradegate error separate');
assertSameValue($failed['lang_schwarz_quote']['status'],'ok','other provider succeeds');
assertSameValue($failed['yahoo_home_market']['status'],'ok','yahoo independently succeeds');
echo "PASS all four MOSA providers / six quote types, 7 requests, partial errors\n";
