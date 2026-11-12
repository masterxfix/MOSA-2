<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/market_collector/mosa_tick.php';

function marketTickSame(mixed $expected,mixed $actual,string $case): void {
    if($expected!==$actual)throw new RuntimeException($case.': '.json_encode([$expected,$actual]));
}
$providers=\Mosa2\MosaMarket\SOURCES;
marketTickSame(['lang_schwarz','tradegate_bsx'],array_keys($providers),'single generic source registry');
marketTickSame(['lang_schwarz_search','lang_schwarz_page'],$providers['lang_schwarz']['requests'],'L&S requests');
marketTickSame(['tradegate_quote'],$providers['tradegate_bsx']['requests'],'Tradegate requests');
marketTickSame('tradegate_bsx',$providers['tradegate_bsx']['venue'],'Tradegate venue');
$isin='SE0000115446';
$tradegate='https://www.tradegatebsx.com/orderbuch.php?isin='.$isin;
marketTickSame(true,\Mosa2\IsinQuote\sourceAllowed(['request_key'=>'tradegate_quote','url'=>$tradegate],$isin),'approved Tradegate host');
marketTickSame(false,\Mosa2\IsinQuote\sourceAllowed(['request_key'=>'tradegate_quote','url'=>$tradegate], 'NO0010081235'),'cross-ISIN rejection');
marketTickSame(false,\Mosa2\IsinQuote\sourceAllowed(['request_key'=>'tradegate_quote','url'=>'https://example.org/orderbuch.php?isin='.$isin],$isin),'unapproved host rejection');
$quote=static function(string $key,string $provider,float $bid,float $ask,int $age): array {
    return ['source_key'=>$key,'provider_key'=>$provider,'provider_label'=>$provider,
        'venue_label'=>$provider,'data_type'=>'quote','available'=>true,'bid'=>$bid,'ask'=>$ask,
        'mid'=>($bid+$ask)/2,'currency'=>'EUR','quoted_at'=>'2026-11-12T11:00:00+00:00',
        'freshness'=>'fresh','age_seconds'=>$age];
};
$ls=$quote('lang_schwarz_quote','lang_schwarz',100.00,100.30,3);
$tg=$quote('tradegate_quote','tradegate_bsx',100.10,100.20,5);
$result=\fixlabMosaMarketQuoteRouter(['lang_schwarz_quote'=>$ls,'tradegate_quote'=>$tg]);
marketTickSame('tradegate_bsx',$result['selected_quote']['provider_key']??null,'narrower-spread provider selected');
$tg['available']=false;
$result=\fixlabMosaMarketQuoteRouter(['lang_schwarz_quote'=>$ls,'tradegate_quote'=>$tg]);
marketTickSame('lang_schwarz',$result['selected_quote']['provider_key']??null,'Tradegate outage falls back to L&S');
$ls['available']=false;
$result=\fixlabMosaMarketQuoteRouter(['lang_schwarz_quote'=>$ls,'tradegate_quote'=>$tg]);
marketTickSame(null,$result['selected_quote'],'no fictitious price when both unavailable');
echo "PASS 10/10 scheduled M2 source cases\n";
