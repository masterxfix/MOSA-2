<?php
declare(strict_types=1);
namespace Mosa2\MarketSources;

use DateTimeImmutable;
use DateTimeZone;

/** One M2 source catalog shared by preview and scheduled market collection.
 * The parsers, timestamps and quote ranking remain the vendored MOSA core.
 * This module has no MOSA runtime dependency and no database capability.
 */
function catalog():array {
    return [
        'lang_schwarz'=>[
            'name'=>'Lang & Schwarz','venue'=>'lang_schwarz_tradecenter','url'=>'https://www.ls-tc.de/de/',
            'requests'=>['lang_schwarz_search','lang_schwarz_page'],'scheduled'=>true,
        ],
        'tradegate_bsx'=>[
            'name'=>'Tradegate BSX','venue'=>'tradegate_bsx','url'=>'https://www.tradegatebsx.com/',
            'requests'=>['tradegate_quote','tradegate_trade'],'scheduled'=>true,
        ],
        'boerse_frankfurt_api'=>[
            'name'=>'Börse Frankfurt','venue'=>'boerse_frankfurt','url'=>'https://api.live.deutsche-boerse.com/v1/',
            'requests'=>['boerse_frankfurt_trade'],'scheduled'=>true,
        ],
        'yahoo_finance_chart'=>[
            'name'=>'Yahoo Finance','venue'=>'home_market','url'=>'https://query1.finance.yahoo.com/',
            'requests'=>['yahoo_home_search','yahoo_home_market'],
            // Automated use remains forbidden until its source rights are confirmed.
            'scheduled'=>false,
        ],
    ];
}
function scheduled():array {
    return array_filter(catalog(),static fn(array $p):bool=>$p['scheduled']===true);
}
function providerOf(string $key):?string {
    foreach(catalog() as $name=>$provider)if(in_array($key,$provider['requests'],true))return $name;
    return null;
}
/** Exact HTTPS host, path, and ISIN binding: used in both M2 acquisition entrypoints. */
function allowed(array $request,string $isin):bool {
    $key=$request['request_key']??null;$url=$request['url']??null;
    if(!is_string($key)||!is_string($url)||strlen($url)>500||providerOf($key)===null)return false;
    $p=parse_url($url);
    if(!is_array($p)||($p['scheme']??null)!=='https'||isset($p['user'])||isset($p['pass'])
        ||isset($p['fragment'])||($p['port']??443)!==443)return false;
    $host=$p['host']??'';$path=$p['path']??'';
    return match($key) {
        'lang_schwarz_search'=>$url==='https://www.ls-tc.de/_rpc/json/.lstc/instrument/search/main?q='.$isin.'&localeId=2',
        'lang_schwarz_page'=>$host==='www.ls-tc.de'
            &&preg_match('~^/de/(aktie|etf)/[1-9][0-9]{0,18}$~D',$path)===1&&!isset($p['query']),
        'tradegate_quote'=>$url==='https://www.tradegatebsx.com/orderbuch.php?isin='.$isin,
        'tradegate_trade'=>$url==='https://www.tradegatebsx.com/orderbuch_umsaetze.php?isin='.$isin,
        'boerse_frankfurt_trade'=>$url==='https://api.live.deutsche-boerse.com/v1/data/price_information/single?isin='.$isin.'&mic=XFRA',
        'yahoo_home_search'=>$url==='https://query1.finance.yahoo.com/v1/finance/search?q='.$isin.'&quotesCount=10&newsCount=0',
        'yahoo_home_market'=>$host==='query1.finance.yahoo.com'
            &&preg_match('~^/v8/finance/chart/[a-zA-Z0-9._%=-]{1,128}$~D',$path)===1
            &&($p['query']??null)==='range=1d&interval=1d&includePrePost=false',
        default=>false,
    };
}
/** Apply MOSA's verified source classification when an M2 registration is still unknown.
 * No ISIN allowlist or asset-specific collector; unverified/conflicting types remain unknown.
 */
function resolvedType(string $assetClass,array $lab):string {
    $type=match($assetClass){'equity'=>'stock','etf'=>'etf','fund'=>'fund','other'=>'other',default=>'unknown'};
    if($type!=='unknown')return $type;
    if(($lab['instrument_type_source']??null)!=='lang_schwarz')return 'unknown';
    $found=$lab['instrument_type']??null;
    return in_array($found,['stock','etf','fund','other'],true)?$found:'unknown';
}
/** Return the same validated M2 writer fact for every asset and provider. */
function fact(array $source,string $key,string $isin,array $registry,array $captured,
              DateTimeImmutable $now,int $maxAge):?array {
    $provider=$source['provider_key']??null;
    if(!is_string($provider)||!isset($registry[$provider])
        ||($source['available']??false)!==true||($source['source_key']??null)!==$key
        ||($source['currency']??null)!=='EUR'
        ||(isset($source['isin'])&&$source['isin']!==$isin))return null;
    $observed=null;
    foreach($registry[$provider]['requests'] as $requestKey)
        if(isset($captured[$requestKey]))$observed=$captured[$requestKey];
    $price=\Mosa2\IsinQuote\asPrice(($source['data_type']??null)==='quote'?$source['mid']??null:$source['price']??null);
    if($observed===null||$price===null||!is_string($source['quoted_at']??null))return null;
    try {
        $market=(new DateTimeImmutable($source['quoted_at']))->setTimezone(new DateTimeZone('UTC'));
        $received=(new DateTimeImmutable($observed,new DateTimeZone('UTC')))->setTimezone(new DateTimeZone('UTC'));
        $age=$now->getTimestamp()-$market->getTimestamp();
    }catch(\Throwable){return null;}
    if($market>$received||$market>$now||$age<0||$age>$maxAge)return null;
    $quote=($source['data_type']??null)==='quote';
    if($quote&&(!is_numeric($source['bid']??null)||!is_numeric($source['ask']??null)
        ||(float)$source['ask']<(float)$source['bid']))return null;
    return [
        'provider'=>$provider,'market_at'=>$market->format('Y-m-d H:i:s.u'),
        'observed_at'=>$received->format('Y-m-d H:i:s.u'),'currency'=>'EUR','price'=>$price,
        'bid'=>$quote?\Mosa2\IsinQuote\asPrice($source['bid']):null,
        'ask'=>$quote?\Mosa2\IsinQuote\asPrice($source['ask']):null,
        'volume'=>null,
    ];
}
/**
 * Prefer MOSA's production complete-quote router and class-wide ETF rule.
 * Qualify a last trade only when no eligible midpoint exists. Never forge FX
 * conversion or invent bid/ask. All decisions are independent of the ISIN.
 */
function choose(array $lab,string $isin,string $assetType,array $registry,array $captured,
                DateTimeImmutable $now):?array {
    $sources=is_array($lab['sources']??null)?$lab['sources']:[];
    if($assetType==='etf') {
        $etf=\fixlabMosaMarketEtfShadowSelection($isin,$sources,$now);
        if(($etf['automatic_release']??false)!==true)return null;
        $key=$etf['selected_source_key'];
        return is_string($key)&&isset($sources[$key])
            ?fact($sources[$key],$key,$isin,$registry,$captured,$now,300):null;
    }
    $router=\fixlabMosaMarketQuoteRouter($sources);
    $key=$router['selected_quote']['source_key']??null;
    if(is_string($key)&&isset($sources[$key])) {
        $selected=fact($sources[$key],$key,$isin,$registry,$captured,$now,300);
        if($selected!==null)return $selected;
    }
    $alternatives=[];
    foreach(['lang_schwarz_trade','tradegate_trade','boerse_frankfurt_trade','yahoo_home_market'] as $key) {
        if(!isset($sources[$key])||!in_array($sources[$key]['data_type']??null,['last_trade','market_snapshot'],true))continue;
        // Tradegate trades require the same validated ISIN as its quote page.
        if($key==='tradegate_trade'&&($sources['tradegate_quote']['isin']??null)!==$isin)continue;
        $v=fact($sources[$key],$key,$isin,$registry,$captured,$now,300);
        if($v!==null)$alternatives[]=$v;
    }
    usort($alternatives,static fn(array $a,array $b):int=>strcmp($b['market_at'],$a['market_at'])?:strcmp($a['provider'],$b['provider']));
    return $alternatives[0]??null;
}
