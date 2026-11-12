<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/market_collector/mosa_tick.php';
use function Mosa2\MarketSources\{catalog,scheduled,providerOf,choose};

function sameValue(mixed $expected,mixed $actual,string $case):void {
    if($expected!==$actual)throw new RuntimeException($case.': '.json_encode([$expected,$actual]));
}
$n=0;
$all=catalog();$active=scheduled();
sameValue(['lang_schwarz','tradegate_bsx','boerse_frankfurt_api','yahoo_finance_chart','twelve_data','eodhd'],array_keys($all),'one source catalog');$n++;
sameValue(['lang_schwarz','tradegate_bsx','boerse_frankfurt_api'],array_keys($active),'scheduled sources');$n++;
sameValue(['lang_schwarz','tradegate_bsx','boerse_frankfurt_api','twelve_data'],array_keys(\Mosa2\MarketSources\scheduled(true)),'private entitlement adds generic international source');$n++;
sameValue(['lang_schwarz','tradegate_bsx','boerse_frankfurt_api','eodhd'],array_keys(\Mosa2\MarketSources\scheduled(false,true)),'only separately entitled delayed provider joins shared collector');$n++;
sameValue(false,$all['yahoo_finance_chart']['scheduled'],'no unauthorized Yahoo automation');$n++;
sameValue('boerse_frankfurt_api',providerOf('boerse_frankfurt_trade'),'shared Frankfurt key');$n++;
sameValue(['tradegate_quote','tradegate_trade'],$active['tradegate_bsx']['requests'],'shared Tradegate request keys');$n++;
sameValue('tradegate_quote',\Mosa2\MarketSources\singlePreview()['tradegate']['request_key'],'manual Tradegate uses shared provider catalog');$n++;
sameValue('boerse_frankfurt_trade',\Mosa2\MarketSources\singlePreview()['frankfurt']['request_key'],'manual Frankfurt uses shared provider catalog');$n++;
sameValue(false,str_contains(file_get_contents(dirname(__DIR__).'/api/isin_quote.php'),'const SOURCES ='),'no duplicate PHP preview provider array');$n++;
sameValue(false,str_contains(file_get_contents(dirname(__DIR__).'/assets/js/isin_quotes.js'),'const providers ='),'no duplicate browser provider array');$n++;
$isin='SE0000115446';
$tradegate='https://www.tradegatebsx.com/orderbuch.php?isin='.$isin;
sameValue(true,\Mosa2\IsinQuote\sourceAllowed(['request_key'=>'tradegate_quote','url'=>$tradegate],$isin),'approved Tradegate host');$n++;
sameValue(false,\Mosa2\IsinQuote\sourceAllowed(['request_key'=>'tradegate_quote','url'=>$tradegate],'NO0010081235'),'wrong ISIN');$n++;
sameValue(false,\Mosa2\IsinQuote\sourceAllowed(['request_key'=>'tradegate_quote','url'=>'https://example.org/orderbuch.php?isin='.$isin],$isin),'foreign host');$n++;
sameValue(true,\Mosa2\IsinQuote\sourceAllowed(['request_key'=>'boerse_frankfurt_trade','url'=>'https://api.live.deutsche-boerse.com/v1/data/price_information/single?isin='.$isin.'&mic=XFRA'],$isin),'Frankfurt scope');$n++;
sameValue(false,\Mosa2\IsinQuote\sourceAllowed(['request_key'=>'boerse_frankfurt_trade','url'=>'https://api.live.deutsche-boerse.com/v1/data/price_information/single?isin='.$isin.'&mic=XETR'],$isin),'Frankfurt MIC scope');$n++;
$now=new DateTimeImmutable('2026-11-12T12:04:07+00:00');
$ts='2026-11-12T12:04:04+00:00';
$captured=['lang_schwarz_page'=>'2026-11-12 12:04:05.000000','tradegate_quote'=>'2026-11-12 12:04:05.000000',
    'tradegate_trade'=>'2026-11-12 12:04:05.000000','boerse_frankfurt_trade'=>'2026-11-12 12:04:05.000000'];
$quote=static fn(string $key,string $provider,float $bid,float $ask):array=>[
    'source_key'=>$key,'provider_key'=>$provider,'provider_label'=>$provider,'venue_label'=>$provider,'data_type'=>'quote',
    'available'=>true,'isin'=>$isin,'currency'=>'EUR','bid'=>$bid,'ask'=>$ask,'mid'=>($bid+$ask)/2,
    'quoted_at'=>$ts,'freshness'=>'fresh','age_seconds'=>3];
$ls=$quote('lang_schwarz_quote','lang_schwarz',5.40,5.60);
$tg=$quote('tradegate_quote','tradegate_bsx',5.49,5.51);
$lab=['sources'=>['lang_schwarz_quote'=>$ls,'tradegate_quote'=>$tg]];
foreach(['stock','fund','other','unknown'] as $kind) {
    $fact=choose($lab,$isin,$kind,$active,$captured,$now);
    sameValue('tradegate_bsx',$fact['provider']??null,'generic '.$kind.' selection');$n++;
    sameValue('5.5',$fact['price']??null,'generic '.$kind.' midpoint');$n++;
}
$etf=choose($lab,$isin,'etf',$active,$captured,$now);
sameValue('tradegate_bsx',$etf['provider']??null,'MOSA ETF class-wide policy');$n++;
$ls['available']=false;$tg['available']=false;
$frankfurt=['source_key'=>'boerse_frankfurt_trade','provider_key'=>'boerse_frankfurt_api','data_type'=>'last_trade',
    'available'=>true,'currency'=>'EUR','price'=>5.52,'quoted_at'=>$ts,'age_seconds'=>3];
$lab=['sources'=>['lang_schwarz_quote'=>$ls,'tradegate_quote'=>$tg,'boerse_frankfurt_trade'=>$frankfurt]];
$fact=choose($lab,$isin,'stock',$active,$captured,$now);
sameValue('boerse_frankfurt_api',$fact['provider']??null,'Frankfurt fallback');$n++;
sameValue([null,null],[$fact['bid']??null,$fact['ask']??null],'last trade never invented midpoint');$n++;
$frankfurt['currency']='USD';
$lab['sources']['boerse_frankfurt_trade']=$frankfurt;
sameValue(null,choose($lab,$isin,'stock',$active,$captured,$now),'no fictitious FX conversion');$n++;
$frankfurt['currency']='EUR';$frankfurt['quoted_at']='2026-11-12T11:00:00Z';
$lab['sources']['boerse_frankfurt_trade']=$frankfurt;
sameValue(null,choose($lab,$isin,'stock',$active,$captured,$now),'stale trade not current');$n++;
$frankfurt['quoted_at']=$ts;$lab['sources']['boerse_frankfurt_trade']=$frankfurt;
$onlyLS=['lang_schwarz'=>$active['lang_schwarz']];
sameValue(null,choose($lab,$isin,'stock',$onlyLS,$captured,$now),'disabled provider does not leak');$n++;
$lab['sources']['tradegate_quote']['available']=true;
$lab['sources']['tradegate_quote']['isin']='NO0010081235';
sameValue(null,choose($lab,$isin,'etf',$active,$captured,$now),'ETF ISIN guard');$n++;
$lab['sources']['boerse_frankfurt_trade']['quoted_at']='2026-11-12T12:04:07+00:00';
sameValue(null,choose($lab,$isin,'stock',$active,$captured,$now),'market timestamp after provider receipt');$n++;
$engine=file_get_contents(dirname(__DIR__).'/api/market_source_engine.php');
$tick=file_get_contents(dirname(__DIR__).'/scripts/market_collector/mosa_tick.php');
sameValue(false,str_contains($engine,"return \$isin==='DE0005936124'"),'remove one-ISIN pilot switch');$n++;
sameValue(false,str_contains($tick,'const SOURCES='),'no second scheduled source list');$n++;
sameValue(true,str_contains($tick,'a.asset_class AS asset_class'),'asset classification taken from catalog');$n++;
sameValue('etf',\Mosa2\MarketSources\resolvedType('unknown',['instrument_type'=>'etf','instrument_type_source'=>'lang_schwarz']),'verified unclassified ETF');$n++;
sameValue('fund',\Mosa2\MarketSources\resolvedType('unknown',['instrument_type'=>'fund','instrument_type_source'=>'lang_schwarz']),'verified unclassified fund');$n++;
sameValue('unknown',\Mosa2\MarketSources\resolvedType('unknown',['instrument_type'=>'etf','instrument_type_source'=>'lang_schwarz_conflict']),'conflicting class stays unknown');$n++;
sameValue('etf',\Mosa2\MarketSources\resolvedType('etf',[]),'declared ETF remains authoritative');$n++;
sameValue('unknown',\Mosa2\MarketSources\resolvedType('unknown',[]),'unclassified identity remains unknown');$n++;
// Exact-ISIN identity enrichment uses the same successful provider responses.
// No name is accepted from an unrelated ISIN, blocked source, or conflicting type.
$identityIsin='SE0000115446';
$tradegateHtml='<table><tr><th>Name</th><th>ISIN</th></tr><tr><td>General Example Holdings AB</td><td>'.$identityIsin.'</td></tr></table>';
$identityLab=[
    'instrument_type'=>'stock','instrument_type_source'=>'lang_schwarz',
    'instrument'=>['isin'=>$identityIsin,'name'=>'GENERAL EXAMPLE'],
    'sources'=>['tradegate_quote'=>['isin'=>$identityIsin]],
    'raw_responses'=>['tradegate_quote'=>['http_status'=>200,'body'=>$tradegateHtml]],
];
$identity=\Mosa2\MarketSources\identityEvidence($identityLab,$identityIsin,$active);
sameValue('General Example Holdings AB',$identity['name'],'trusted full name from matching Tradegate');$n++;
sameValue('tradegate_bsx',$identity['name_source'],'explicit name origin');$n++;
sameValue('equity',$identity['asset_class'],'verified stock class is equity in M2');$n++;
sameValue('lang_schwarz',$identity['class_source'],'verified type provenance');$n++;
sameValue(['name'=>'General Example Holdings AB','asset_class'=>'equity'],
    \Mosa2\MarketSources\identityPatch($identityIsin,$identityIsin,'unknown',$identity),'fills only unknowns');$n++;
sameValue(['name'=>'Manual Preferred Name','asset_class'=>'etf'],
    \Mosa2\MarketSources\identityPatch($identityIsin,'Manual Preferred Name','etf',$identity),'preserves existing curated name and class');$n++;
sameValue(['name'=>'General Example Holdings AB','asset_class'=>'etf'],
    \Mosa2\MarketSources\identityPatch($identityIsin,$identityIsin,'etf',$identity),'does not overwrite existing class');$n++;
$other=$identityLab;
$other['raw_responses']['tradegate_quote']['body']=str_replace($identityIsin,'NO0010081235',$tradegateHtml);
sameValue('GENERAL EXAMPLE',\Mosa2\MarketSources\identityEvidence($other,$identityIsin,$active)['name'],'reject mismatched Tradegate ISIN');$n++;
$other=$identityLab;$other['raw_responses']['tradegate_quote']['http_status']=503;
sameValue('GENERAL EXAMPLE',\Mosa2\MarketSources\identityEvidence($other,$identityIsin,$active)['name'],'reject unsuccessful provider fetch');$n++;
$onlyLs=['lang_schwarz'=>$active['lang_schwarz']];
sameValue('GENERAL EXAMPLE',\Mosa2\MarketSources\identityEvidence($identityLab,$identityIsin,$onlyLs)['name'],'disabled Tradegate cannot supply names');$n++;
$other=$identityLab;$other['instrument_type']='etf';
sameValue('etf',\Mosa2\MarketSources\identityEvidence($other,$identityIsin,$active)['asset_class'],'ETF classified from same search');$n++;
$other=$identityLab;$other['instrument_type_source']='lang_schwarz_conflict';
sameValue(null,\Mosa2\MarketSources\identityEvidence($other,$identityIsin,$active)['asset_class'],'ambiguous class never persisted');$n++;
$other=$identityLab;$other['instrument']['name']='<script>spoof</script>';
$other['raw_responses']['tradegate_quote']['http_status']=503;
sameValue(null,\Mosa2\MarketSources\identityEvidence($other,$identityIsin,$active)['name'],'unsafe names rejected');$n++;
sameValue(['name'=>$identityIsin,'asset_class'=>'unknown'],
    \Mosa2\MarketSources\identityPatch($identityIsin,$identityIsin,'unknown',['name'=>null,'asset_class'=>null]),
    'no evidence means no metadata guess');$n++;
sameValue(false,str_contains(file_get_contents(dirname(__DIR__).'/scripts/market_collector/mosa_tick.php'),'UPDATE m2_entities'),
    'stable ISIN entity identity never renamed');$n++;

sameValue(true,str_contains($tick,"check(\$saved!==false,'identity_readback')"),
    'M2 identity writer uses a boolean check instead of mismatched equality arity');$n++;
// Native currencies are accepted only with a frozen, physically seeded M2 unit.
// GBX is a quote unit of GBP, never a synthetic ISO currency or FX rate.
$nativeRows=[
    ['unit_key'=>'EUR','unit_version'=>1,'status'=>'frozen','monetary_currency_code'=>'EUR'],
    ['unit_key'=>'GBP','unit_version'=>1,'status'=>'frozen','monetary_currency_code'=>'GBP'],
    ['unit_key'=>'GBX','unit_version'=>1,'status'=>'frozen','monetary_currency_code'=>'GBP'],
    ['unit_key'=>'POINT','unit_version'=>1,'status'=>'frozen','monetary_currency_code'=>null],
    ['unit_key'=>'USD','unit_version'=>1,'status'=>'draft','monetary_currency_code'=>'USD'],
];
$native=\Mosa2\MarketSources\unitRegistry($nativeRows);
sameValue(['EUR','GBP','GBX'],array_keys($native),'only frozen monetary units');$n++;
sameValue('GBP',$native['GBX']['currency'],'GBX denominated in GBP');$n++;
$nativeQuote=$quote('tradegate_quote','tradegate_bsx',500.0,504.0);
$nativeQuote['currency']='GBP';
$onlyTradegate=['tradegate_bsx'=>$active['tradegate_bsx']];
$nativeLab=['sources'=>['tradegate_quote'=>$nativeQuote]];
$nativeFact=choose($nativeLab,$isin,'stock',$onlyTradegate,$captured,$now,$native);
sameValue('GBP',$nativeFact['currency']??null,'native GBP currency');$n++;
sameValue('GBP',$nativeFact['quote_unit_key']??null,'native GBP unit route');$n++;
sameValue('502',$nativeFact['price']??null,'native price preserved without synthetic FX');$n++;
$nativeQuote['currency']='GBX';$nativeLab['sources']['tradegate_quote']=$nativeQuote;
$gbxFact=choose($nativeLab,$isin,'stock',$onlyTradegate,$captured,$now,$native);
sameValue('GBP',$gbxFact['currency']??null,'GBX monetary currency is GBP');$n++;
sameValue('GBX',$gbxFact['quote_unit_key']??null,'GBX native quote unit remains explicit');$n++;
sameValue('502',$gbxFact['price']??null,'no silent pence to pounds rewrite');$n++;
$nativeQuote['currency']='USD';$nativeLab['sources']['tradegate_quote']=$nativeQuote;
sameValue(null,choose($nativeLab,$isin,'stock',$onlyTradegate,$captured,$now,$native),
    'unseeded USD is rejected rather than mislabeled EUR');$n++;
$nativeQuote['currency']='GBp';$nativeLab['sources']['tradegate_quote']=$nativeQuote;
sameValue(null,choose($nativeLab,$isin,'stock',$onlyTradegate,$captured,$now,$native),
    'ambiguous pence notation cannot be silently uppercased to GBP');$n++;
$nativeQuote['currency']='EUR';$nativeLab['sources']['tradegate_quote']=$nativeQuote;
sameValue('EUR',choose($nativeLab,$isin,'stock',$onlyTradegate,$captured,$now,$native)['currency']??null,
    'old EUR quote path unchanged');$n++;
$both=$nativeLab;
$both['sources']['lang_schwarz_quote']=$quote('lang_schwarz_quote','lang_schwarz',4.0,6.0);
$both['sources']['tradegate_quote']['currency']='GBP';
$cross=choose($both,$isin,'stock',$active,$captured,$now,$native);
sameValue(true,in_array($cross['currency']??null,['EUR','GBP'],true),
    'independent currency groups are routed without comparing their prices');$n++;
$unavailableUnitRows=[['unit_key'=>'GBP','unit_version'=>1,'status'=>'draft','monetary_currency_code'=>'GBP']];
sameValue([], \Mosa2\MarketSources\unitRegistry($unavailableUnitRows),
    'unfrozen DB units never reach Current');$n++;
foreach(['fund','other'] as $kind){
    $q=['canonical_name'=>$isin,'display_name'=>$isin,'asset_class'=>$kind,
       'identifier_type'=>'isin','identifier_value'=>$isin,'normalized_value'=>$isin,
       'scope_key'=>'','is_primary'=>1];
    sameValue($kind,\Mosa2\MarketIdentity\qualifiedIdentity($q)['asset_class'],
        'general asset identity class '.$kind);$n++;
}
echo 'PASS '.$n.'/'.$n." unified M2 market source scenarios\n";
