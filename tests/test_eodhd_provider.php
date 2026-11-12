<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/market_collector/mosa_tick.php';
use function Mosa2\MarketInternational\Eodhd\{authorization,request,approvedRequest,resolve,source,validTicker};
use function Mosa2\MarketSources\{allowed,catalog,scheduled,choose};
$n=0;
$assert=static function(mixed $expected,mixed $actual,string $label)use(&$n):void {
    if($expected!==$actual)throw new RuntimeException($label);
    $n++;
};
$isin='AU000000DRO2';
$token='m2-test-no-real-token-123456789';
$assert(false,isset(scheduled()['eodhd']),'private provider disabled by default');
$assert(false,isset(scheduled(false,true)['eodhd']),'excluded provider cannot reenter registry through old entitlement');
$search=request('eodhd_search',$isin,$token);
$assert(false,allowed($search,$isin),'excluded provider ISIN search rejected');
$assert(true,approvedRequest($search,'eodhd_search',$isin,$token),'exact private search/token binding');
$assert(false,allowed($search,'NO0010081235'),'search not usable for other ISIN');
$evil=$search;$evil['url']=str_replace('https://eodhd.com/','https://evil.example/',$search['url']);
$assert(false,allowed($evil,$isin),'no host spoofing');
$assert(false,str_contains($search['request_type'],$token),'no key in request label');
$exchangeReq=request('eodhd_exchange','',$token);
$assert(false,allowed($exchangeReq,$isin),'excluded provider exchange metadata rejected');
$quoteReq=request('eodhd_delayed','DRO.AU',$token);
$assert(false,allowed($quoteReq,$isin),'excluded provider quote rejected');
$assert(false,validTicker('DRO.AU@evil.com'),'foreign URL prohibited');
$assert(false,approvedRequest($quoteReq,'eodhd_delayed','OTHER.AU',$token),'ticker binding enforced');
$results=[
 ['Code'=>'DRO','Exchange'=>'F','Name'=>'DroneShield','Type'=>'Common Stock',
  'Country'=>'Germany','Currency'=>'EUR','ISIN'=>$isin,'isPrimary'=>false],
 ['Code'=>'DRO','Exchange'=>'AU','Name'=>'DroneShield','Type'=>'Common Stock',
  'Country'=>'Australia','Currency'=>'AUD','ISIN'=>$isin,'isPrimary'=>true],
 ['Code'=>'WRONG','Exchange'=>'AU','Currency'=>'AUD','ISIN'=>'AU000000BAD1','isPrimary'=>true],
];
$exchanges=[
 ['Name'=>'Frankfurt Exchange','Code'=>'F','OperatingMIC'=>'XFRA','Currency'=>'EUR'],
 ['Name'=>'Australian Securities Exchange','Code'=>'AU','OperatingMIC'=>'XASX','Currency'=>'AUD'],
];
$route=resolve($isin,$results,$exchanges);
$assert('DRO.AU',$route['ticker']??null,'primary ticker from exact ISIN only');
$assert('AUD',$route['currency']??null,'original Australian currency');
$assert('XASX',$route['mic']??null,'real provider MIC');
$assert($isin,$route['isin']??null,'ISIN retained in route');
$bad=$results;$bad[1]['ISIN']='AU000000BAD1';
$assert('DRO.F',resolve($isin,$bad,$exchanges)['ticker']??null,'unique exact fallback when no primary');
$double=$results;$double[0]['isPrimary']=true;
$assert(null,resolve($isin,$double,$exchanges),'ambiguous primary fails closed');
$multipleMic=$exchanges;$multipleMic[1]['OperatingMIC']='XASX, XAS2';
$assert('DRO.F',resolve($isin,$results,$multipleMic)['ticker']??null,'ambiguous MIC never chosen');
$now=new DateTimeImmutable('2026-11-12T12:00:00Z');
$stamp=$now->getTimestamp()-1100;
$quote=['code'=>'DRO.AU','timestamp'=>$stamp,'close'=>1.42,'volume'=>230000];
$s=source($isin,$route,$quote,$now);
$assert(true,$s['available'],'15-20 minute delayed native price available');
$assert('AUD',$s['currency'],'native Australian unit');
$assert('XASX',$s['venue_key'],'physical route identity');
$assert('1.42',$s['price'],'numeric close preserved');
$assert((new DateTimeImmutable('@'.$stamp))->format('Y-m-d H:i:s'),
    (new DateTimeImmutable($s['quoted_at']))->format('Y-m-d H:i:s'),'actual delayed market time not clock time');
$registry=['eodhd'=>catalog()['eodhd']+['id'=>'42'],
           'tradegate_bsx'=>catalog()['tradegate_bsx']+['id'=>'43']];
$captured=['eodhd_delayed'=>'2026-11-12 12:00:00.000000',
           'tradegate_quote'=>'2026-11-12 12:00:00.000000'];
$units=['AUD'=>['quote_unit_key'=>'AUD','quote_unit_version'=>'1','currency'=>'AUD'],
        'EUR'=>['quote_unit_key'=>'EUR','quote_unit_version'=>'1','currency'=>'EUR']];
$eur=['source_key'=>'tradegate_quote','provider_key'=>'tradegate_bsx','provider_label'=>'Tradegate',
      'venue_label'=>'Tradegate BSX','isin'=>$isin,'available'=>true,'freshness'=>'fresh',
      'age_seconds'=>0,'data_type'=>'quote','currency'=>'EUR','bid'=>0.79,'ask'=>0.81,'mid'=>0.80,
      'quoted_at'=>'2026-11-12T12:00:00+00:00'];
$lab=['sources'=>['tradegate_quote'=>$eur,'eodhd_delayed'=>$s]];
foreach(['stock','etf'] as $assetClass){
    $winner=choose($lab,$isin,$assetClass,$registry,$captured,$now,$units);
    $assert('eodhd',$winner['provider']??null,'native priority for '.$assetClass);
    $assert('AUD',$winner['currency']??null,'no EUR rewrite '.$assetClass);
    $assert('XASX',$winner['venue_key']??null,'physical MIC '.$assetClass);
}
$stale=$quote;$stale['timestamp']=$now->getTimestamp()-1801;
$assert(false,source($isin,$route,$stale,$now)['available'],'stale delayed quote not freshened');
$badCode=$quote;$badCode['code']='OTHER.AU';
$assert(false,source($isin,$route,$badCode,$now)['available'],'ticker echo mismatch blocked');
$badPrice=$quote;$badPrice['close']=-2;
$assert(false,source($isin,$route,$badPrice,$now)['available'],'negative price blocked');
$badFuture=$quote;$badFuture['timestamp']=$now->getTimestamp()+10;
$assert(false,source($isin,$route,$badFuture,$now)['available'],'future market timestamp blocked');
$eurFallback=choose(['sources'=>['tradegate_quote'=>$eur,'eodhd_delayed'=>source($isin,$route,$stale,$now)]],
    $isin,'stock',$registry,$captured,$now,$units);
$assert('tradegate_bsx',$eurFallback['provider']??null,'stale native quote falls back to EUR');
$root=sys_get_temp_dir().'/m2eodhd-'.bin2hex(random_bytes(6));
$dir=$root.'/mosa2-market-eodhd-private';
mkdir($dir,0700,true);
try {
    $assert(null,authorization($root),'missing licence file means no HTTP requests');
    $cfg=['enabled'=>true,'personal_or_internal_rights_confirmed'=>true,
          'private_display_only'=>true,'api_token'=>$token,
          'max_daily_requests'=>20,'max_minute_requests'=>2];
    $file=$dir.'/access.php';file_put_contents($file,'<?php return '.var_export($cfg,true).';');chmod($file,0600);
    $assert($token,authorization($root)['api_token']??null,'private approved account');
    chmod($file,0644);$refused=false;
    try{authorization($root);}catch(InvalidArgumentException){$refused=true;}
    $assert(true,$refused,'readable secret file refused');
    chmod($file,0600);$cfg['private_display_only']=false;
    file_put_contents($file,'<?php return '.var_export($cfg,true).';');
    $assert(null,authorization($root),'public display not licensed');
}finally{if(is_file($dir.'/access.php'))unlink($dir.'/access.php');rmdir($dir);rmdir($root);}
echo 'PASS '.$n.'/'.$n." licensed generic ISIN->MIC delayed price and native priority checks\n";
