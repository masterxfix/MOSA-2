<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/market_collector/actions_acceptance.php';

function checkNative(bool $pass,string $name):void {
    if(!$pass)throw new RuntimeException('native route '.$name);
}
$isin='SE0000115446';$total=0;
$state=[
    'm2_entities'=>[['id'=>'1','entity_type'=>'asset','canonical_name'=>$isin,'status'=>'active']],
    'm2_assets'=>[['entity_id'=>'1','asset_class'=>'equity','display_name'=>$isin,'base_currency'=>null,'status'=>'active']],
    'm2_asset_identifiers'=>[['id'=>'3','asset_id'=>'1','identifier_type'=>'isin','identifier_value'=>$isin,
        'normalized_value'=>$isin,'scope_key'=>'','is_primary'=>'1','source_id'=>null,'valid_from'=>null,'valid_to'=>null]],
    'm2_sources'=>[
        ['id'=>'2','source_key'=>'provider:tradegate_bsx','source_type'=>'market_data','enabled'=>'1'],
        ['id'=>'5','source_key'=>'provider:twelve_data','source_type'=>'market_data','enabled'=>'1'],
    ],
    'm2_asset_source_routes'=>[],
    'm2_units'=>[
        ['unit_key'=>'EUR','unit_version'=>'1','status'=>'frozen','unit_contract_version'=>'mosa2-market-unit-v1','monetary_currency_code'=>'EUR'],
        ['unit_key'=>'GBP','unit_version'=>'1','status'=>'frozen','unit_contract_version'=>'mosa2-market-unit-v1','monetary_currency_code'=>'GBP'],
        ['unit_key'=>'GBX','unit_version'=>'1','status'=>'frozen','unit_contract_version'=>'mosa2-market-unit-v1','monetary_currency_code'=>'GBP'],
        ['unit_key'=>'USD','unit_version'=>'1','status'=>'frozen','unit_contract_version'=>'mosa2-market-unit-v1','monetary_currency_code'=>'USD'],
        ['unit_key'=>'JPY','unit_version'=>'1','status'=>'frozen','unit_contract_version'=>'mosa2-market-unit-v1','monetary_currency_code'=>'JPY'],
    ],
];
$provider=['source_key'=>'tradegate_bsx','reference_key'=>'tradegate_bsx','venue_key'=>'tradegate_bsx',
    'family'=>'mosa_live_quote','reference'=>'verified exact ISIN test quote',
    'provider_key'=>'tradegate_bsx','adapter_module'=>'m2_market_observation','adapter_class'=>'MarketObservation'];
foreach([['EUR','EUR'],['GBP','GBP'],['GBX','GBP'],['USD','USD'],['JPY','JPY']] as [$unit,$money]){
    $manifest=\Mosa2\MarketAcceptance\quoteManifest($state,
        ['isin'=>$isin,'name'=>$isin,'quote_unit_key'=>$unit,'currency'=>$money],$provider);
    checkNative($manifest['unit_binding']['quote_unit_key']===$unit,'native unit binding '.$unit);$total++;
    checkNative($manifest['route_evidence']['row']['currency']===$money,'money denomination '.$unit);$total++;
    checkNative($manifest['policy']==='ONBOARD_NEW_ROUTE','route revision without reusing wrong unit');$total++;
}
$internationalProvider=[
    'source_key'=>'twelve_data','reference_key'=>'twelve_data','venue_key'=>'XTKS',
    'family'=>'mosa_live_quote','reference'=>'exact-ISIN licensed quote with verified XTKS MIC',
    'provider_key'=>'twelve_data','adapter_module'=>'m2_market_observation','adapter_class'=>'MarketObservation',
];
$foreignManifest=\Mosa2\MarketAcceptance\quoteManifest($state,
    ['isin'=>$isin,'name'=>$isin,'quote_unit_key'=>'JPY','currency'=>'JPY'],$internationalProvider);
checkNative($foreignManifest['identity']['normalized_value']===$isin,'international route exact ISIN');$total++;
checkNative($foreignManifest['route_evidence']['row']['venue_key']==='XTKS','international route verified MIC');$total++;
checkNative($foreignManifest['unit_binding']['quote_unit_key']==='JPY','international route native JPY unit');$total++;
checkNative($foreignManifest['policy']==='ONBOARD_NEW_ROUTE','same universal onboarding plan');$total++;
foreach(['fund','other'] as $type){
    $new=$state;$new['m2_assets'][0]['asset_class']=$type;
    $m=\Mosa2\MarketAcceptance\quoteManifest($new,
        ['isin'=>$isin,'name'=>$isin,'quote_unit_key'=>'EUR','currency'=>'EUR'],$provider);
    checkNative($m['identity']['asset_class']===$type,'generic '.$type.' identity');$total++;
}
foreach([['AUD','AUD'],['GBX','GBX']] as [$unit,$money]){
    try {
        \Mosa2\MarketAcceptance\quoteManifest($state,['isin'=>$isin,'name'=>$isin,
            'quote_unit_key'=>$unit,'currency'=>$money],$provider);
        throw new RuntimeException('invalid native denomination accepted');
    }catch(RuntimeException|InvalidArgumentException $error){
        checkNative($error->getMessage()!=='invalid native denomination accepted','reject unsupported/wrong unit');
        $total++;
    }
}
echo 'PASS '.$total.'/'.$total." physical native-currency route planning and generic asset classes\n";
