<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/market_collector/mosa_tick.php';

use function Mosa2\MarketInternational\TwelveData\{authorization,request,source,nextBudget};
use function Mosa2\MarketSources\{allowed,catalog,scheduled,choose};

function equalIntl(mixed $expected,mixed $actual,string $label):void {
    if($expected!==$actual)throw new RuntimeException($label.': '.json_encode([$expected,$actual]));
}
$n=0;
$isin='JP3633400001';
equalIntl(false,catalog()['twelve_data']['scheduled'],'no unentitled automatic source');$n++;
equalIntl(false,isset(scheduled()['twelve_data']),'default scheduled catalog has no international GET');$n++;
equalIntl(false,isset(scheduled(true)['twelve_data']),'provider remains excluded despite old entitlement flag');$n++;
equalIntl('2741.25',\Mosa2\IsinQuote\asPrice('2741.2500000000'),'native exact decimal string preserves digits');$n++;
equalIntl('0.0000000001',\Mosa2\IsinQuote\asPrice('0.0000000001'),'one tenth-billionth native unit is not rounded to zero');$n++;
equalIntl(null,\Mosa2\IsinQuote\asPrice('2741.25e0'),'exponent input rejected');$n++;
equalIntl(null,\Mosa2\IsinQuote\asPrice('0.0000000000'),'zero-priced quote rejected');$n++;
$token='dev-only-test-token-12345';
$req=request($isin,$token);
equalIntl('https://api.twelvedata.com/quote?isin='.$isin,$req['url'],'exact ISIN-only quote request');$n++;
equalIntl('twelve_data_quote',$req['request_key'],'canonical request key');$n++;
equalIntl(false,str_contains($req['url'],$token),'secret is not in request URL');$n++;
equalIntl(true,in_array('Authorization: apikey '.$token,$req['headers'],true),'secret only in private header');$n++;
equalIntl(false,$req['follow_redirects'],'redirects forbidden');$n++;
equalIntl(false,allowed($req,$isin),'excluded provider URL must never enter shared HTTP transport');$n++;
equalIntl(false,allowed($req,'AU000000DRO2'),'bound to requested ISIN');$n++;
$redirect=$req;$redirect['url']='https://evil.test/quote?isin='.$isin;
equalIntl(false,allowed($redirect,$isin),'foreign host never accepted');$n++;
$swap=$req;$swap['url']='https://api.twelvedata.com/quote?symbol=TM';
equalIntl(false,allowed($swap,$isin),'no unverified ticker lookup');$n++;
$now=new DateTimeImmutable('2026-11-12T12:04:07Z');
$stamp=(new DateTimeImmutable('2026-11-12T12:04:05Z'))->getTimestamp();
$quote=[
    'symbol'=>'7203','name'=>'Toyota Motor Corp','currency'=>'JPY','mic_code'=>'XTKS',
    'close'=>'2741.25','last_quote_at'=>$stamp,'timestamp'=>$stamp,
    'is_market_open'=>true,
];
$row=source($isin,$quote,$now);
equalIntl(true,$row['available'],'native source ready');$n++;
equalIntl('JPY',$row['currency'],'native Japanese quote');$n++;
equalIntl('XTKS',$row['venue_label'],'verified exchange MIC');$n++;
equalIntl('XTKS',$row['venue_key'],'physical route uses verified MIC');$n++;
equalIntl('2741.25',$row['price'],'no FX price rewrite');$n++;
equalIntl('last_trade',$row['data_type'],'market observation kind');$n++;
equalIntl('2026-11-12T12:04:05+00:00',$row['quoted_at'],'source UTC time');$n++;
equalIntl($isin,$row['isin'],'request ISIN remains bound');$n++;
$tdRegistry=['twelve_data'=>catalog()['twelve_data']+['id'=>'91']];
$units=['JPY'=>['quote_unit_key'=>'JPY','quote_unit_version'=>'1','currency'=>'JPY']];
$selected=choose(['sources'=>['twelve_data_quote'=>$row]],$isin,'stock',
    $tdRegistry,['twelve_data_quote'=>'2026-11-12 12:04:06.000000'],$now,$units);
equalIntl('JPY',$selected['currency']??null,'native currency in shared M2 writer');$n++;
equalIntl('JPY',$selected['quote_unit_key']??null,'physical JPY route derived from approved unit');$n++;
equalIntl('2741.25',$selected['price']??null,'complete native source observation');$n++;
equalIntl('twelve_data',$selected['provider']??null,'one provider within common writer');$n++;
equalIntl('XTKS',$selected['venue_key']??null,'verified native venue travels with selected quote');$n++;
// A German EUR midpoint can be newer than a valid native-market trade.
// Native exchange quotes must still win, regardless of ISIN or asset class.
$eurSource=[
    'source_key'=>'tradegate_quote','provider_key'=>'tradegate_bsx',
    'venue_key'=>'tradegate_bsx','available'=>true,'isin'=>$isin,
    'provider_label'=>'Tradegate BSX','venue_label'=>'Tradegate BSX',
    'freshness'=>'fresh','age_seconds'=>1,
    'currency'=>'EUR','data_type'=>'quote','mid'=>'100.00',
    'bid'=>'99.90','ask'=>'100.10','quoted_at'=>'2026-11-12T12:04:06+00:00',
];
$combinedRegistry=$tdRegistry+['tradegate_bsx'=>catalog()['tradegate_bsx']+['id'=>'92']];
$combinedUnits=$units+['EUR'=>['quote_unit_key'=>'EUR','quote_unit_version'=>'1','currency'=>'EUR']];
$combinedCaptured=['twelve_data_quote'=>'2026-11-12 12:04:06.000000',
    'tradegate_quote'=>'2026-11-12 12:04:07.000000'];
$combinedLab=['sources'=>['tradegate_quote'=>$eurSource,'twelve_data_quote'=>$row]];
$primaryStock=choose($combinedLab,$isin,'stock',$combinedRegistry,$combinedCaptured,$now,$combinedUnits);
equalIntl('twelve_data',$primaryStock['provider']??null,'verified native MIC outranks German EUR stock quote');$n++;
equalIntl('JPY',$primaryStock['currency']??null,'no EUR relabel of selected stock quote');$n++;
$primaryEtf=choose($combinedLab,$isin,'etf',$combinedRegistry,$combinedCaptured,$now,$combinedUnits);
equalIntl('twelve_data',$primaryEtf['provider']??null,'verified native MIC outranks German ETF quotation');$n++;
$withoutMic=$row;$withoutMic['venue_key']='international_isin';
$withoutMicLab=['sources'=>['tradegate_quote'=>$eurSource,'twelve_data_quote'=>$withoutMic]];
$euroFallback=choose($withoutMicLab,$isin,'stock',$combinedRegistry,$combinedCaptured,$now,$combinedUnits);
equalIntl('tradegate_bsx',$euroFallback['provider']??null,'unverified native exchange falls back to EUR');$n++;
$staleNative=$row;$staleNative['quoted_at']='2026-11-12T11:04:05+00:00';
$staleNativeLab=['sources'=>['tradegate_quote'=>$eurSource,'twelve_data_quote'=>$staleNative]];
$staleFallback=choose($staleNativeLab,$isin,'stock',$combinedRegistry,$combinedCaptured,$now,$combinedUnits);
equalIntl('tradegate_bsx',$staleFallback['provider']??null,'stale native quote falls back to EUR');$n++;
$etfSelected=choose(['sources'=>['twelve_data_quote'=>$row]],$isin,'etf',
    $tdRegistry,['twelve_data_quote'=>'2026-11-12 12:04:06.000000'],$now,$units);
equalIntl('JPY',$etfSelected['currency']??null,'generic ETF supports independently validated native quote');$n++;
$asiaTrading=new DateTimeImmutable('2026-11-12T02:00:05Z');
$asiaPayload=$quote;$asiaPayload['last_quote_at']=(new DateTimeImmutable('2026-11-12T02:00:03Z'))->getTimestamp();
$asiaPayload['timestamp']=$asiaPayload['last_quote_at'];
$asiaQuote=source($isin,$asiaPayload,$asiaTrading);
$asiaFact=choose(['sources'=>['twelve_data_quote'=>$asiaQuote]],$isin,'etf',$tdRegistry,
    ['twelve_data_quote'=>'2026-11-12 02:00:04.000000'],$asiaTrading,$units);
equalIntl('JPY',$asiaFact['currency']??null,'Tokyo-morning ETF quote works during Berlin night');$n++;
equalIntl('XTKS',$asiaFact['venue_key']??null,'Asia-hours ETF retains exact venue');$n++;

equalIntl(null,choose(['sources'=>['twelve_data_quote'=>$row]],$isin,'stock',
    $tdRegistry,['twelve_data_quote'=>'2026-11-12 12:04:06.000000'],$now,
    ['EUR'=>['quote_unit_key'=>'EUR','quote_unit_version'=>'1','currency'=>'EUR']]),
    'no unseeded currency as EUR');$n++;
$corrupt=$quote;$corrupt['isin']='AU000000DRO2';
equalIntl(false,source($isin,$corrupt,$now)['available'],'source ISIN echo mismatch');$n++;
$corrupt=$quote;$corrupt['currency']='XXX';
equalIntl(false,source($isin,$corrupt,$now)['available'],'pseudo currency rejected');$n++;
$corrupt=$quote;$corrupt['close']='-0.01';
equalIntl(false,source($isin,$corrupt,$now)['available'],'negative quote rejected');$n++;
$corrupt=$quote;$corrupt['last_quote_at']=$now->getTimestamp()+10;
equalIntl(false,source($isin,$corrupt,$now)['available'],'future source time rejected');$n++;
$corrupt=$quote;$corrupt['status']='error';
equalIntl(false,source($isin,$corrupt,$now)['available'],'vendor entitlement error cannot be a price');$n++;
$corrupt=$quote;$corrupt['mic_code']='<>bad';$corrupt['exchange']='Tokyo Stock Exchange';
equalIntl('Tokyo Stock Exchange',source($isin,$corrupt,$now)['venue_label'],'non-MIC market name is validated');$n++;
equalIntl('international_isin',source($isin,$corrupt,$now)['venue_key'],'non-MIC fallback does not invent exchange identity');$n++;
$corrupt=$quote;$corrupt['mic_code']='<>bad';$corrupt['exchange']='<script>';
equalIntl('Internationale Börse',source($isin,$corrupt,$now)['venue_label'],'no HTML source injection');$n++;
$stale=source($isin,$quote,new DateTimeImmutable('2026-11-12T13:00:00Z'));
equalIntl(null,choose(['sources'=>['twelve_data_quote'=>$stale]],$isin,'stock',
    $tdRegistry,['twelve_data_quote'=>'2026-11-12 13:00:00.000000'],
    new DateTimeImmutable('2026-11-12T13:00:00Z'),$units),
    'market closure must not create invented fresh quotes');$n++;
equalIntl('2026-11-12|1',nextBudget(null,'2026-11-12',3),'first UTC daily reservation');$n++;
equalIntl('2026-11-12|3',nextBudget('2026-11-12|2','2026-11-12',3),'last quota credit');$n++;
equalIntl(null,nextBudget('2026-11-12|3','2026-11-12',3),'daily cap stops further GET');$n++;
equalIntl('2026-11-13|1',nextBudget('2026-11-12|3','2026-11-13',3),'UTC daily rollover');$n++;
equalIntl(null,nextBudget('2026-11-12 12:04|2','2026-11-12 12:04',2),'per-minute cap');$n++;
equalIntl('2026-11-12 12:05|1',nextBudget('2026-11-12 12:04|2','2026-11-12 12:05',2),
    'per-minute quota resets');$n++;
$failed=false;
try{nextBudget('2026-11-12|NaN','2026-11-12',3);}catch(InvalidArgumentException){$failed=true;}
equalIntl(true,$failed,'corrupted quota fails closed');$n++;
$root=sys_get_temp_dir().'/m2-provider-offline-'.bin2hex(random_bytes(7));
$dir=$root.'/mosa2-market-twelvedata-private';
if(!mkdir($dir,0700,true))throw new RuntimeException('cannot create offline test root');
try{
    equalIntl(null,authorization($root),'provider disabled if private config absent');$n++;
    $path=$dir.'/access.php';
    $payload=['enabled'=>true,'market_data_rights_confirmed'=>true,'isin_addon_confirmed'=>true,
        'api_key'=>$token,'max_daily_requests'=>50,'max_minute_requests'=>2];
    file_put_contents($path,'<?php return '.var_export($payload,true).';');
    chmod($path,0600);
    equalIntl($token,authorization($root)['api_key']??null,'strict private entitlement enables provider');$n++;
    chmod($path,0644);
    $permissionBlocked=false;
    try{authorization($root);}catch(InvalidArgumentException){$permissionBlocked=true;}
    equalIntl(true,$permissionBlocked,'world-readable credential file is rejected');$n++;
    chmod($path,0600);$payload['isin_addon_confirmed']=false;
    file_put_contents($path,'<?php return '.var_export($payload,true).';');
    equalIntl(null,authorization($root),'missing ISIN add-on disables all provider requests');$n++;
}finally{if(is_file($dir.'/access.php'))unlink($dir.'/access.php');rmdir($dir);rmdir($root);}
echo 'PASS '.$n.'/'.$n." optional global ISIN/native currency, rights, quota and secret safety checks\n";
