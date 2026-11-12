<?php
declare(strict_types=1);
require dirname(__DIR__).'/api/market_sources.php';
use function Mosa2\MarketSources\{catalog,scheduled,providerOf,allowed};
$active=['lang_schwarz','tradegate_bsx','boerse_frankfurt_api'];
foreach([[false,false],[true,false],[false,true],[true,true]] as [$a,$b]){
    if(array_keys(scheduled($a,$b))!==$active)throw new RuntimeException('Excluded provider activated by old auth flag');
}
foreach(['twelve_data','eodhd'] as $p) {
    if((catalog()[$p]['status']??null)!=='excluded')
        throw new RuntimeException('Missing exclusion marker: '.$p);
}
foreach(['twelve_data_quote','eodhd_search','eodhd_exchange','eodhd_delayed'] as $key){
    if(providerOf($key)!==null)throw new RuntimeException('Excluded providerOf: '.$key);
    if(allowed(['request_key'=>$key,'url'=>'https://api.twelvedata.com/quote?isin=NO0010081235'],'NO0010081235'))
        throw new RuntimeException('Excluded source accepted');
}
$collector=file_get_contents(dirname(__DIR__).'/scripts/market_collector/mosa_tick.php');
if(!str_contains($collector,'$international=null;')||!str_contains($collector,'$eodhd=null;'))
    throw new RuntimeException('Excluded providers not disabled in collector');
echo "PASS 2 permanently excluded market API providers, no entitlement escape, three existing sources unchanged\n";
