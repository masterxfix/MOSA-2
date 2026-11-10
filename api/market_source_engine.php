<?php
declare(strict_types=1);
/**
 * Vendored read-only source-comparison core from masterxfix/fixlab.
 * Original functions: php/mosa_market_source_lab.php, php/mosa_boerse_frankfurt.php,
 * php/mosa_market_quote_router.php and Yahoo identity selector from
 * php/mosa_market_identity.php. No database/storage dependencies or globals are loaded.
 * MOSA 2's API wrapper applies host restrictions and publishes only validated quote facts.
 */
const FIXLAB_MOSA_FRANKFURT_PROVIDER='boerse_frankfurt_api';
const FIXLAB_MOSA_FRANKFURT_MIC='XFRA';
const FIXLAB_MOSA_FRANKFURT_CURRENCY='EUR';
const FIXLAB_MOSA_FRANKFURT_TIMEZONE='Europe/Berlin';
const FIXLAB_MOSA_FRANKFURT_BASE_URL='https://api.live.deutsche-boerse.com/v1';
const FIXLAB_MOSA_FRANKFURT_TRACE_SALT='af5a8d16eb5dc49f8a72b26fd9185475c7a';

function fixlabMosaFrankfurtLocalTime(?DateTimeImmutable $now=null):DateTimeImmutable
{
    return ($now??new DateTimeImmutable('now',new DateTimeZone(FIXLAB_MOSA_FRANKFURT_TIMEZONE)))->setTimezone(new DateTimeZone(FIXLAB_MOSA_FRANKFURT_TIMEZONE));
}

function fixlabMosaFrankfurtHeaders(string $url,?DateTimeImmutable $now=null):array
{
    $local=fixlabMosaFrankfurtLocalTime($now);$clientDate=$local->format('Y-m-d\TH:i:sP');
    return ['Accept: application/json','Client-Date: '.$clientDate,'X-Client-TraceId: '.md5($clientDate.$url.FIXLAB_MOSA_FRANKFURT_TRACE_SALT),'X-Security: '.md5($local->format('YmdHi')),'User-Agent: FixLab-MOSA-Frankfurt/1.0'];
}

function fixlabMosaFrankfurtRequest(string $isin,string $profile='current',?DateTimeImmutable $now=null):array
{
    $isin=strtoupper(trim($isin));if(preg_match('/^[A-Z0-9]{12}$/D',$isin)!==1||!in_array($profile,['current','rich','intraday','daily','backfill'],true))return[];
    $local=fixlabMosaFrankfurtLocalTime($now);
    if(in_array($profile,['current','rich'],true)){
        $url=FIXLAB_MOSA_FRANKFURT_BASE_URL.'/data/price_information/single?isin='.rawurlencode($isin).'&mic='.FIXLAB_MOSA_FRANKFURT_MIC;
        return ['request_key'=>'frankfurt_price_'.$isin,'endpoint_family'=>'frankfurt_price_information','url'=>$url,'headers'=>fixlabMosaFrankfurtHeaders($url,$local),'role'=>'price_information','series'=>'snapshot'];
    }
    $resolution=$profile==='intraday'?'M':($profile==='backfill'?'D':'H');
    $from=match($profile){'intraday'=>$local->setTime(0,0),'daily'=>$local->modify('-40 days')->setTime(0,0),default=>$local->modify('-5 years')->setTime(0,0)};
    $query=http_build_query(['resolution'=>$resolution,'from'=>$from->getTimestamp(),'to'=>$local->getTimestamp(),'symbols'=>FIXLAB_MOSA_FRANKFURT_MIC.':'.$isin,'adjustment'=>'','keepNaN'=>$profile==='intraday'?'false':'true'],'','&',PHP_QUERY_RFC3986);
    $url=FIXLAB_MOSA_FRANKFURT_BASE_URL.'/tradingview/lightweight/history/single?'.$query;
    return ['request_key'=>'frankfurt_history_'.$profile.'_'.$isin,'endpoint_family'=>'frankfurt_history','url'=>$url,'headers'=>fixlabMosaFrankfurtHeaders($url,$local),'role'=>'history','series'=>$profile==='intraday'?'intraday':'history'];
}

function fixlabMosaFrankfurtSnapshotValid(mixed $payload,string $isin):bool
{
    return is_array($payload)&&($payload['isin']??null)===strtoupper(trim($isin))&&($payload['mic']??null)===FIXLAB_MOSA_FRANKFURT_MIC&&($payload['currency']['originalValue']??null)===FIXLAB_MOSA_FRANKFURT_CURRENCY&&is_numeric($payload['lastPrice']??null)&&is_string($payload['timestampLastPrice']??null);
}

const FIXLAB_MOSA_MARKET_QUOTE_ROUTER_VERSION='mosa_market_quote_router_v1';
const FIXLAB_MOSA_MARKET_ETF_SHADOW_VERSION='mosa_market_etf_shadow_v1';

function fixlabMosaMarketQuoteRouterBase():array
{
    return [
        'contract_version'=>FIXLAB_MOSA_MARKET_QUOTE_ROUTER_VERSION,
        'mode'=>'shadow',
        'ok'=>false,
        'recommended_source_key'=>null,
        'selected_quote'=>null,
        'decision_code'=>'no_eligible_quote',
        'decision_label'=>'Keine geeignete vollständige Offerte verfügbar.',
        'candidates'=>[],
    ];
}

function fixlabMosaMarketQuoteRouterCandidate(string $sourceKey,array $source):array
{
    $candidate=[
        'source_key'=>$sourceKey,
        'provider_key'=>is_string($source['provider_key']??null)?trim($source['provider_key']):'',
        'provider_label'=>is_string($source['provider_label']??null)?trim($source['provider_label']):'',
        'venue_label'=>is_string($source['venue_label']??null)?trim($source['venue_label']):'',
        'freshness'=>is_string($source['freshness']??null)?$source['freshness']:'unavailable',
        'freshness_rank'=>0,
        'bid'=>is_numeric($source['bid']??null)?(float)$source['bid']:null,
        'ask'=>is_numeric($source['ask']??null)?(float)$source['ask']:null,
        'mid'=>is_numeric($source['mid']??null)?(float)$source['mid']:null,
        'spread'=>null,
        'spread_bps'=>null,
        'currency'=>is_string($source['currency']??null)?strtoupper(trim($source['currency'])):'',
        'quoted_at'=>is_string($source['quoted_at']??null)?trim($source['quoted_at']):'',
        'age_seconds'=>is_int($source['age_seconds']??null)?$source['age_seconds']:null,
        'eligible'=>false,
        'exclusion_code'=>null,
    ];
    $candidate['freshness_rank']=$candidate['freshness']==='fresh'?2:($candidate['freshness']==='aging'?1:0);
    $validTime=false;if($candidate['quoted_at']!==''){try{new DateTimeImmutable($candidate['quoted_at']);$validTime=true;}catch(Throwable){}}
    $valid=($source['source_key']??null)===$sourceKey&&($source['data_type']??null)==='quote'&&($source['available']??false)===true
        &&$candidate['provider_key']!==''&&$candidate['provider_label']!==''&&$candidate['venue_label']!==''
        &&is_float($candidate['bid'])&&is_float($candidate['ask'])&&is_float($candidate['mid'])
        &&$candidate['bid']>0&&$candidate['ask']>0&&$candidate['mid']>0&&$candidate['ask']>=$candidate['bid']
        &&preg_match('/^[A-Z]{3}$/D',$candidate['currency'])===1&&$validTime
        &&is_int($candidate['age_seconds'])&&$candidate['age_seconds']>=0&&$candidate['freshness_rank']>0;
    if(!$valid){$candidate['exclusion_code']='quote_incomplete_or_invalid';return $candidate;}
    $candidate['spread']=$candidate['ask']-$candidate['bid'];
    $candidate['spread_bps']=$candidate['spread']/$candidate['mid']*10000;
    $candidate['eligible']=true;
    return $candidate;
}

function fixlabMosaMarketQuoteRouter(array $sources):array
{
    $result=fixlabMosaMarketQuoteRouterBase();
    foreach($sources as$key=>$source)if(is_string($key)&&is_array($source)&&($source['data_type']??null)==='quote')$result['candidates'][$key]=fixlabMosaMarketQuoteRouterCandidate($key,$source);
    $eligible=array_values(array_filter($result['candidates'],static fn(array$candidate):bool=>$candidate['eligible']===true));
    if($eligible===[])return $result;
    $currencies=array_values(array_unique(array_column($eligible,'currency')));
    if(count($currencies)!==1){$result['decision_code']='currency_mismatch';$result['decision_label']='Die vollständigen Offerten haben unterschiedliche Währungen; die Simulation entscheidet nicht.';return $result;}
    usort($eligible,static function(array$left,array$right):int{
        if($left['freshness_rank']!==$right['freshness_rank'])return $right['freshness_rank']<=>$left['freshness_rank'];
        $spreadDifference=$left['spread_bps']-$right['spread_bps'];if(abs($spreadDifference)>0.000000001)return $spreadDifference<0?-1:1;
        if($left['age_seconds']!==$right['age_seconds'])return $left['age_seconds']<=>$right['age_seconds'];
        return strcmp($left['source_key'],$right['source_key']);
    });
    $winner=$eligible[0];$runnerUp=$eligible[1]??null;$code='only_eligible_source';
    if(is_array($runnerUp)){
        if($winner['freshness_rank']>$runnerUp['freshness_rank'])$code='fresher_quote';
        elseif(abs($winner['spread_bps']-$runnerUp['spread_bps'])>0.000000001)$code='narrower_relative_spread';
        elseif($winner['age_seconds']<$runnerUp['age_seconds'])$code='younger_quote';
        else$code='stable_source_key';
    }
    $reason=match($code){
        'only_eligible_source'=>'einzige vollständige geeignete Offerte',
        'fresher_quote'=>'höhere Aktualitätsklasse als die Alternative',
        'narrower_relative_spread'=>'kleinerer relativer Spread ('.number_format($winner['spread_bps'],1,',','.').' Basispunkte)',
        'younger_quote'=>'jüngerer Quellenzeitpunkt bei gleichem Spread',
        default=>'stabile technische Reihenfolge bei Gleichstand',
    };
    $result['ok']=true;$result['recommended_source_key']=$winner['source_key'];$result['decision_code']=$code;$result['decision_label']=$winner['provider_label'].' empfohlen: '.$reason.'.';
    $result['selected_quote']=[
        'source_key'=>$winner['source_key'],'provider_key'=>$winner['provider_key'],'provider_label'=>$winner['provider_label'],'venue_label'=>$winner['venue_label'],
        'bid'=>$winner['bid'],'ask'=>$winner['ask'],'mid'=>$winner['mid'],'spread'=>$winner['spread'],'spread_bps'=>$winner['spread_bps'],
        'currency'=>$winner['currency'],'quoted_at'=>$winner['quoted_at'],'age_seconds'=>$winner['age_seconds'],'freshness'=>$winner['freshness'],
    ];
    return $result;
}

function fixlabMosaMarketEtfShadowCandidate(string $expectedIsin,string $sourceKey,array $source):array
{
    $reasons=[];$isin=is_string($source['isin']??null)?strtoupper(trim($source['isin'])):'';$bid=is_numeric($source['bid']??null)?(float)$source['bid']:null;$ask=is_numeric($source['ask']??null)?(float)$source['ask']:null;$currency=is_string($source['currency']??null)?strtoupper(trim($source['currency'])):'';$quotedAt=is_string($source['quoted_at']??null)?trim($source['quoted_at']):'';$age=is_int($source['age_seconds']??null)?$source['age_seconds']:null;$freshness=is_string($source['freshness']??null)?$source['freshness']:'unavailable';
    if(($source['source_key']??null)!==$sourceKey)$reasons[]='source_key_mismatch';
    if(($source['data_type']??null)!=='quote')$reasons[]='not_quote';
    if(($source['available']??false)!==true)$reasons[]='source_unavailable';
    if($isin!==$expectedIsin)$reasons[]='isin_mismatch';
    if($bid===null||!is_finite($bid)||$bid<=0)$reasons[]='bid_invalid';
    if($ask===null||!is_finite($ask)||$ask<=0)$reasons[]='ask_invalid';
    if($bid!==null&&$ask!==null&&$bid>$ask)$reasons[]='bid_above_ask';
    if($currency!=='EUR')$reasons[]='currency_not_eur';
    $validTime=false;if($quotedAt!==''){try{new DateTimeImmutable($quotedAt);$validTime=true;}catch(Throwable){}}
    if(!$validTime)$reasons[]='quoted_at_invalid';
    if($age===null||$age<0)$reasons[]='age_invalid';
    if(!in_array($freshness,['fresh','aging'],true))$reasons[]='quote_stale';
    $mid=$reasons===[]?($bid+$ask)/2:null;$spread=$mid!==null?$ask-$bid:null;$spreadPercent=$mid!==null&&$mid>0?$spread/$mid*100:null;
    return ['source_key'=>$sourceKey,'provider_label'=>is_string($source['provider_label']??null)?trim($source['provider_label']):$sourceKey,'isin'=>$isin,'eligible'=>$reasons===[],'rejection_reasons'=>$reasons,'bid'=>$bid,'ask'=>$ask,'mid'=>$mid,'spread'=>$spread,'spread_percent'=>$spreadPercent,'currency'=>$currency,'quoted_at'=>$quotedAt,'age_seconds'=>$age,'freshness'=>$freshness];
}

function fixlabMosaMarketEtfShadowSelection(string $isin,array $sources,?DateTimeImmutable $now=null):array
{
    $now=($now??new DateTimeImmutable('now',new DateTimeZone('UTC')))->setTimezone(new DateTimeZone('UTC'));$berlin=$now->setTimezone(new DateTimeZone('Europe/Berlin'));$minutes=(int)$berlin->format('G')*60+(int)$berlin->format('i');$marketStatus=$minutes>=480&&$minutes<1320?'market_open':'market_closed';
    $result=['contract_version'=>FIXLAB_MOSA_MARKET_ETF_SHADOW_VERSION,'mode'=>'etf_shadow','ok'=>false,'selected_source_key'=>null,'selected_role'=>null,'selected_quote'=>null,'control_source_key'=>null,'control_quote'=>null,'mid_deviation_percent'=>null,'confirmation_status'=>'unavailable','spread_quality'=>'unavailable','price_quality'=>'unavailable','market_status'=>$marketStatus,'automatic_release'=>false,'candidates'=>[],'rejected_candidates'=>[]];
    foreach(['tradegate_quote','lang_schwarz_quote']as$key){$candidate=fixlabMosaMarketEtfShadowCandidate($isin,$key,is_array($sources[$key]??null)?$sources[$key]:[]);$result['candidates'][$key]=$candidate;if(!$candidate['eligible'])$result['rejected_candidates'][$key]=$candidate['rejection_reasons'];}
    $tradegate=$result['candidates']['tradegate_quote'];$langSchwarz=$result['candidates']['lang_schwarz_quote'];$selected=$tradegate['eligible']?$tradegate:($langSchwarz['eligible']?$langSchwarz:null);if(!is_array($selected))return $result;
    $primary=$selected['source_key']==='tradegate_quote';$control=$primary?$langSchwarz:$tradegate;$result['ok']=true;$result['selected_source_key']=$selected['source_key'];$result['selected_role']=$primary?'primary':'fallback';$result['selected_quote']=$selected;$result['control_source_key']=$control['source_key'];$result['control_quote']=$control['eligible']?$control:null;
    $spread=(float)$selected['spread_percent'];$result['spread_quality']=$spread<=.25?'tight':($spread<=1?'elevated':'wide');$result['price_quality']=$result['spread_quality']==='wide'?'indicative':'validated_mid';
    if($tradegate['eligible']&&$langSchwarz['eligible']){$basis=((float)$tradegate['mid']+(float)$langSchwarz['mid'])/2;$deviation=$basis>0?abs((float)$tradegate['mid']-(float)$langSchwarz['mid'])/$basis*100:null;$result['mid_deviation_percent']=$deviation;$result['confirmation_status']=$deviation===null?'unavailable':($deviation<=.10?'confirmed':($deviation<=.25?'warning':'conflict'));}else$result['confirmation_status']='single_source';
    $result['automatic_release']=$marketStatus==='market_open'&&$result['confirmation_status']!=='conflict';return $result;
}

function fixlabMosaMarketCountryProfiles():array
{
    return [
        'AU'=>['label'=>'Australien','exchanges'=>['ASX'],'suffixes'=>['.AX'],'currency'=>'AUD','timezone'=>'Australia/Sydney'],
        'CA'=>['label'=>'Kanada','exchanges'=>['TOR','VAN','CNQ'],'suffixes'=>['.TO','.V','.CN'],'currency'=>'CAD','timezone'=>'America/Toronto'],
        'CH'=>['label'=>'Schweiz','exchanges'=>['EBS'],'suffixes'=>['.SW'],'currency'=>'CHF','timezone'=>'Europe/Zurich'],
        'CN'=>['label'=>'China','exchanges'=>['HKG','SHH','SHZ'],'suffixes'=>['.HK','.SS','.SZ'],'currency'=>null,'timezone'=>null],
        'DE'=>['label'=>'Deutschland','exchanges'=>['GER'],'suffixes'=>['.DE'],'currency'=>'EUR','timezone'=>'Europe/Berlin'],
        'DK'=>['label'=>'Dänemark','exchanges'=>['CPH'],'suffixes'=>['.CO'],'currency'=>'DKK','timezone'=>'Europe/Copenhagen'],
        'ES'=>['label'=>'Spanien','exchanges'=>['MCE'],'suffixes'=>['.MC'],'currency'=>'EUR','timezone'=>'Europe/Madrid'],
        'FI'=>['label'=>'Finnland','exchanges'=>['HEL'],'suffixes'=>['.HE'],'currency'=>'EUR','timezone'=>'Europe/Helsinki'],
        'FR'=>['label'=>'Frankreich','exchanges'=>['PAR'],'suffixes'=>['.PA'],'currency'=>'EUR','timezone'=>'Europe/Paris'],
        'GB'=>['label'=>'Großbritannien','exchanges'=>['LSE'],'suffixes'=>['.L'],'currency'=>'GBP','timezone'=>'Europe/London'],
        'HK'=>['label'=>'Hongkong','exchanges'=>['HKG'],'suffixes'=>['.HK'],'currency'=>'HKD','timezone'=>'Asia/Hong_Kong'],
        'IE'=>['label'=>'Irland','exchanges'=>['ISE'],'suffixes'=>['.IR'],'currency'=>'EUR','timezone'=>'Europe/Dublin'],
        'IT'=>['label'=>'Italien','exchanges'=>['MIL'],'suffixes'=>['.MI'],'currency'=>'EUR','timezone'=>'Europe/Rome'],
        'JP'=>['label'=>'Japan','exchanges'=>['JPX'],'suffixes'=>['.T'],'currency'=>'JPY','timezone'=>'Asia/Tokyo'],
        'NL'=>['label'=>'Niederlande','exchanges'=>['AMS'],'suffixes'=>['.AS'],'currency'=>'EUR','timezone'=>'Europe/Amsterdam'],
        'NO'=>['label'=>'Norwegen','exchanges'=>['OSL'],'suffixes'=>['.OL'],'currency'=>'NOK','timezone'=>'Europe/Oslo'],
        'SE'=>['label'=>'Schweden','exchanges'=>['STO'],'suffixes'=>['.ST'],'currency'=>'SEK','timezone'=>'Europe/Stockholm'],
        'US'=>['label'=>'USA','exchanges'=>['NMS','NGM','NCM','NYQ','ASE'],'suffixes'=>[''],'currency'=>'USD','timezone'=>'America/New_York'],
    ];
}

function fixlabMosaMarketIdentityCountryCode(string $isin):?string
{
    if(!fixlabMosaMarketSourceLabIsinValid($isin))return null;$code=substr($isin,0,2);return isset(fixlabMosaMarketCountryProfiles()[$code])?$code:null;
}

function fixlabMosaMarketYahooCandidateScore(array $candidate,string $isin):int
{
    $country=fixlabMosaMarketIdentityCountryCode($isin);$profile=$country!==null?(fixlabMosaMarketCountryProfiles()[$country]??null):null;
    $exchange=strtoupper(trim((string)($candidate['exchange']??'')));$symbol=strtoupper(trim((string)($candidate['symbol']??'')));$currency=strtoupper(trim((string)($candidate['currency']??'')));$score=0;
    if(is_array($profile)){
        if(in_array($exchange,$profile['exchanges'],true))$score+=100;
        foreach($profile['suffixes']as$suffix){if($suffix===''&&!str_contains($symbol,'.')){$score+=45;break;}if($suffix!==''&&str_ends_with($symbol,$suffix)){$score+=45;break;}}
        if(is_string($profile['currency'])&&$currency===$profile['currency'])$score+=15;
    }
    if(($candidate['isYahooFinance']??false)===true)$score+=5;
    if(in_array($exchange,['PNK','OBB'],true))$score-=40;
    return $score;
}

function fixlabMosaMarketSelectYahooCandidate(array $candidates,string $isin):?array
{
    $valid=[];foreach($candidates as$candidate){if(!is_array($candidate)||isset($candidate['isin'])&&strtoupper((string)$candidate['isin'])!==$isin)continue;$symbol=trim((string)($candidate['symbol']??''));$type=strtoupper(trim((string)($candidate['quoteType']??$candidate['typeDisp']??'')));if($symbol===''||!in_array($type,['EQUITY','ETF','MUTUALFUND','STOCK'],true))continue;$candidate['_score']=fixlabMosaMarketYahooCandidateScore($candidate,$isin);$valid[]=$candidate;}
    if($valid===[])return null;usort($valid,static function(array$a,array$b):int{$score=($b['_score']??0)<=>($a['_score']??0);return$score!==0?$score:strcmp((string)$a['symbol']."\0".(string)($a['exchange']??''),(string)$b['symbol']."\0".(string)($b['exchange']??''));});$selected=$valid[0];unset($selected['_score']);return$selected;
}


const FIXLAB_MOSA_MARKET_SOURCE_LAB_VERSION='mosa_market_source_lab_v8';
const FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER='market_source_comparison';
const FIXLAB_MOSA_MARKET_SOURCE_LAB_MAX_RESPONSE_BYTES=2000000;
const FIXLAB_MOSA_MARKET_SOURCE_LAB_FRESH_SECONDS=120;
const FIXLAB_MOSA_MARKET_SOURCE_LAB_AGING_SECONDS=300;
const FIXLAB_MOSA_MARKET_SOURCE_LAB_INDICATOR_STATUS_RULES=[
    'current_seconds'=>180,
    'stale_overrun_seconds'=>600,
    'sources'=>[
        'dax'=>[
            'yahoo_market_indicator'=>['expected_delay_seconds'=>900,'timezone'=>'Europe/Berlin','sessions'=>[1=>[['09:00','17:30']],2=>[['09:00','17:30']],3=>[['09:00','17:30']],4=>[['09:00','17:30']],5=>[['09:00','17:30']]]],
            'tradegate_dax_indicator'=>['expected_delay_seconds'=>0,'timezone'=>'Europe/Berlin','sessions'=>[1=>[['07:30','22:00']],2=>[['07:30','22:00']],3=>[['07:30','22:00']],4=>[['07:30','22:00']],5=>[['07:30','22:00']]]],
        ],
        'sp500'=>['yahoo_market_indicator'=>['expected_delay_seconds'=>0,'timezone'=>'America/New_York','sessions'=>[1=>[['09:30','16:00']],2=>[['09:30','16:00']],3=>[['09:30','16:00']],4=>[['09:30','16:00']],5=>[['09:30','16:00']]]]],
        'nikkei225'=>['yahoo_market_indicator'=>['expected_delay_seconds'=>900,'timezone'=>'Asia/Tokyo','sessions'=>[1=>[['09:00','11:30'],['12:30','15:30']],2=>[['09:00','11:30'],['12:30','15:30']],3=>[['09:00','11:30'],['12:30','15:30']],4=>[['09:00','11:30'],['12:30','15:30']],5=>[['09:00','11:30'],['12:30','15:30']]]]],
        'gold'=>['yahoo_market_indicator'=>['expected_delay_seconds'=>600,'timezone'=>'America/New_York','sessions'=>[1=>[['00:00','17:00'],['18:00','24:00']],2=>[['00:00','17:00'],['18:00','24:00']],3=>[['00:00','17:00'],['18:00','24:00']],4=>[['00:00','17:00'],['18:00','24:00']],5=>[['00:00','17:00']],7=>[['18:00','24:00']]]]],
        'brent'=>['yahoo_market_indicator'=>['expected_delay_seconds'=>600,'timezone'=>'Europe/London','sessions'=>[1=>[['01:00','23:00']],2=>[['01:00','23:00']],3=>[['01:00','23:00']],4=>[['01:00','23:00']],5=>[['01:00','23:00']]]]],
    ],
];

function fixlabMosaMarketSourceLabSource(string $key,string $provider,string $providerLabel,string $venue,string $type):array
{
    return [
        'source_key'=>$key,'provider_key'=>$provider,'provider_label'=>$providerLabel,'venue_label'=>$venue,'data_type'=>$type,'isin'=>null,
        'available'=>false,'price'=>null,'currency'=>null,'quoted_at'=>null,'age_seconds'=>null,'freshness'=>'unavailable',
        'bid'=>null,'ask'=>null,'mid'=>null,'spread'=>null,'spread_percent'=>null,'bid_size'=>null,'ask_size'=>null,'reported_mid'=>null,'trade_size'=>null,'unit_label'=>null,
        'previous_close'=>null,'day_high'=>null,'day_low'=>null,'volume'=>null,'symbol'=>null,'exchange_code'=>null,
        'telemetry'=>['request_count'=>0,'failed_request_count'=>0,'latency_ms'=>null,'response_bytes'=>0],'error_code'=>null,
    ];
}

function fixlabMosaMarketSourceLabBase(string $isin=''):array
{
    return [
        'contract_version'=>FIXLAB_MOSA_MARKET_SOURCE_LAB_VERSION,'mode'=>'read_only','ok'=>false,'status'=>'not_run','instrument_key'=>$isin,'asset_type'=>'security',
        'provider_key'=>FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER,'provider_label'=>'L&S · Tradegate BSX · Börse Frankfurt · Yahoo Heimatmarkt','isin'=>$isin,
        'instrument'=>['isin'=>$isin,'name'=>null,'wkn'=>null,'instrument_id'=>null,'market_id'=>null],'instrument_type'=>'unknown','instrument_type_source'=>null,'instrument_type_verified_at'=>null,'requested_at'=>null,
        'sources'=>[
            'lang_schwarz_quote'=>fixlabMosaMarketSourceLabSource('lang_schwarz_quote','lang_schwarz','Lang & Schwarz','L&S TradeCenter','quote'),
            'tradegate_quote'=>fixlabMosaMarketSourceLabSource('tradegate_quote','tradegate_bsx','Tradegate BSX','Tradegate BSX','quote'),
            'lang_schwarz_trade'=>fixlabMosaMarketSourceLabSource('lang_schwarz_trade','lang_schwarz','Lang & Schwarz','L&S TradeCenter','last_trade'),
            'tradegate_trade'=>fixlabMosaMarketSourceLabSource('tradegate_trade','tradegate_bsx','Tradegate BSX','Tradegate BSX','last_trade'),
            'boerse_frankfurt_trade'=>fixlabMosaMarketSourceLabSource('boerse_frankfurt_trade',FIXLAB_MOSA_FRANKFURT_PROVIDER,'Börse Frankfurt','Frankfurt · XFRA','last_trade'),
            'yahoo_home_market'=>fixlabMosaMarketSourceLabSource('yahoo_home_market','yahoo_finance_chart','Yahoo Finance','Heimatmarkt','market_snapshot'),
        ],
        'mosa_quote_candidate'=>null,'requests'=>[],'raw_responses'=>[],'errors'=>[],'warnings'=>[],'external_fetch_executed'=>false,
        'database_connected'=>false,'sql_executed'=>false,'write_actions_executed'=>false,'state_written'=>false,
    ];
}

function fixlabMosaMarketSourceLabNormalizeIsin(mixed $value):string{return is_string($value)?strtoupper(trim($value)):'';}

function fixlabMosaMarketSourceLabIsinValid(string $isin):bool
{
    if(preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D',$isin)!==1)return false;$digits='';foreach(str_split($isin)as$character)$digits.=ctype_digit($character)?$character:(string)(ord($character)-55);
    $sum=0;$double=false;for($index=strlen($digits)-1;$index>=0;$index--){$digit=(int)$digits[$index];if($double){$digit*=2;if($digit>9)$digit-=9;}$sum+=$digit;$double=!$double;}return $sum%10===0;
}

function fixlabMosaMarketSourceLabEtfSelection(mixed $store,int $userId):array
{
    if($userId<1||!is_array($store)||!is_array($store['references']??null)||!array_is_list($store['references']))return ['status'=>'invalid','items'=>[]];
    $items=[];foreach($store['references']as$record){if(!is_array($record)||($record['user_id']??null)!==$userId||($record['asset_type']??null)!=='etf')continue;$isin=$record['isin']??null;$name=$record['object_name']??null;$wkn=$record['wkn']??null;if(!is_string($isin)||!fixlabMosaMarketSourceLabIsinValid($isin)||($record['object_key']??null)!==$isin||!is_string($name)||trim($name)===''||($wkn!==null&&!is_string($wkn)))continue;$items[]=['asset_type'=>'etf','object_key'=>$isin,'name'=>trim($name),'isin'=>$isin,'wkn'=>$wkn===null?null:trim($wkn)];}
    usort($items,static fn(array$left,array$right):int=>strnatcasecmp($left['name'].' '.$left['isin'],$right['name'].' '.$right['isin']));return ['status'=>$items===[]?'empty':'available','items'=>$items];
}

function fixlabMosaMarketSourceLabIndicators():array
{
    return [
        'dax'=>['key'=>'dax','name'=>'DAX','asset_key'=>'market_indicator_dax','yahoo_symbol'=>'^GDAXI','venue_label'=>'Deutscher Markt','unit_label'=>'Punkte','unit_key'=>'points','reference_type'=>'index_reference','tradegate_index'=>'DE000A1EXRV0'],
        'sp500'=>['key'=>'sp500','name'=>'S&P 500','asset_key'=>'market_indicator_sp500','yahoo_symbol'=>'^GSPC','venue_label'=>'US-Markt','unit_label'=>'Punkte','unit_key'=>'points','reference_type'=>'index_reference','tradegate_index'=>null],
        'nikkei225'=>['key'=>'nikkei225','name'=>'Nikkei 225','asset_key'=>'market_indicator_nikkei225','yahoo_symbol'=>'^N225','venue_label'=>'Japanischer Markt','unit_label'=>'Punkte','unit_key'=>'points','reference_type'=>'index_reference','tradegate_index'=>null],
        'gold'=>['key'=>'gold','name'=>'Gold','asset_key'=>'market_indicator_gold_future','yahoo_symbol'=>'GC=F','venue_label'=>'COMEX','unit_label'=>'USD je Feinunze','unit_key'=>'usd_per_troy_ounce','reference_type'=>'future_reference','tradegate_index'=>null],
        'brent'=>['key'=>'brent','name'=>'Brent Öl','asset_key'=>'market_indicator_brent_future','yahoo_symbol'=>'BZ=F','venue_label'=>'ICE Futures Europe','unit_label'=>'USD je Barrel','unit_key'=>'usd_per_barrel','reference_type'=>'future_reference','tradegate_index'=>null],
    ];
}

function fixlabMosaMarketSourceLabIndicator(mixed $key):?array
{
    if(!is_string($key))return null;$normalized=strtolower(trim($key));$indicators=fixlabMosaMarketSourceLabIndicators();return $indicators[$normalized]??null;
}

function fixlabMosaMarketSourceLabIndicatorBase(array $indicator):array
{
    $key=$indicator['key'];$sources=['yahoo_market_indicator'=>fixlabMosaMarketSourceLabSource('yahoo_market_indicator','yahoo_finance_chart','Yahoo Finance',(string)$indicator['venue_label'],'market_indicator')];
    if(is_string($indicator['tradegate_index']??null))$sources['tradegate_dax_indicator']=fixlabMosaMarketSourceLabSource('tradegate_dax_indicator','tradegate_bsx','Tradegate BSX DAX-Indikator','Tradegate BSX','market_indicator');
    return [
        'contract_version'=>FIXLAB_MOSA_MARKET_SOURCE_LAB_VERSION,'mode'=>'read_only','ok'=>false,'status'=>'not_run','instrument_key'=>$key,'asset_type'=>'market_indicator',
        'provider_key'=>FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER,'provider_label'=>'Direkte Marktindikatoren','isin'=>'',
        'instrument'=>['key'=>$key,'name'=>$indicator['name'],'symbol'=>$indicator['yahoo_symbol'],'asset_type'=>'market_indicator'],'requested_at'=>null,'sources'=>$sources,
        'mosa_quote_candidate'=>null,'requests'=>[],'raw_responses'=>[],'errors'=>[],'warnings'=>[],'external_fetch_executed'=>false,
        'database_connected'=>false,'sql_executed'=>false,'write_actions_executed'=>false,'state_written'=>false,
    ];
}

function fixlabMosaMarketSourceLabIndicatorRequests(array $indicator):array
{
    $symbol=(string)($indicator['yahoo_symbol']??'');if($symbol==='')return[];$requests=['yahoo_market_indicator'=>fixlabMosaMarketSourceLabRequest('yahoo_market_indicator','Yahoo Marktindikator','https://query1.finance.yahoo.com/v8/finance/chart/'.rawurlencode($symbol).'?range=1d&interval=1d&includePrePost=false',['Accept: application/json','User-Agent: FixLab-MOSA-Market-Source-Lab/2.0'])];
    if(is_string($indicator['tradegate_index']??null)){$index=$indicator['tradegate_index'];$requests['tradegate_dax_indicator']=fixlabMosaMarketSourceLabRequest('tradegate_dax_indicator','Tradegate BSX DAX-Indikator','https://www.tradegatebsx.com/indizes.php?index='.rawurlencode($index).'&lang=de',['Accept: text/html,application/xhtml+xml','Referer: https://www.tradegatebsx.com/','User-Agent: FixLab-MOSA-Market-Source-Lab/2.0']);}return$requests;
}

function fixlabMosaMarketSourceLabRequest(string $key,string $type,string $url,array $headers):array
{
    $parts=parse_url($url);$parameters=[];if(is_array($parts)&&is_string($parts['query']??null))parse_str($parts['query'],$parameters);
    return ['request_key'=>$key,'request_type'=>$type,'endpoint_host'=>is_array($parts)?(string)($parts['host']??''):'','endpoint_path'=>is_array($parts)?(string)($parts['path']??''):'','parameters'=>$parameters,'url'=>$url,'headers'=>$headers];
}

function fixlabMosaMarketSourceLabLsRequest(string $key,string $type,string $path,array $parameters=[]):array
{
    $query=http_build_query($parameters,'','&',PHP_QUERY_RFC3986);$url='https://www.ls-tc.de'.$path.($query===''?'':'?'.$query);
    $request=fixlabMosaMarketSourceLabRequest($key,$type,$url,['Accept: '.($key==='lang_schwarz_page'?'text/html,application/xhtml+xml':'application/json'),'Referer: https://www.ls-tc.de/de/','User-Agent: FixLab-MOSA-Market-Source-Lab/2.0']);if($key==='lang_schwarz_page')$request['follow_redirects']=true;return $request;
}

function fixlabMosaMarketSourceLabTradegateRequest(string $key,string $type,string $path,string $isin):array
{
    return fixlabMosaMarketSourceLabRequest($key,$type,'https://www.tradegatebsx.com'.$path.'?isin='.rawurlencode($isin),['Accept: text/html,application/xhtml+xml','Referer: https://www.tradegatebsx.com/','User-Agent: FixLab-MOSA-Market-Source-Lab/2.0']);
}

function fixlabMosaMarketSourceLabLiveTransport(array $request):array
{
    if(!function_exists('curl_init'))return ['body'=>'','http_status'=>null,'latency_ms'=>null,'error_code'=>'curl_unavailable'];$handle=curl_init($request['url']);if($handle===false)return ['body'=>'','http_status'=>null,'latency_ms'=>null,'error_code'=>'curl_init_failed'];
    $options=[CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_CONNECTTIMEOUT=>5,CURLOPT_TIMEOUT=>12,CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_HTTPHEADER=>$request['headers']];if(($request['follow_redirects']??false)===true){$options[CURLOPT_FOLLOWLOCATION]=true;$options[CURLOPT_MAXREDIRS]=2;if(defined('CURLOPT_REDIR_PROTOCOLS')&&defined('CURLPROTO_HTTPS'))$options[constant('CURLOPT_REDIR_PROTOCOLS')]=constant('CURLPROTO_HTTPS');}curl_setopt_array($handle,$options);
    $retryAfter=null;
    curl_setopt($handle,CURLOPT_HEADERFUNCTION,static function($handle,string $line)use(&$retryAfter):int{
        if(str_starts_with(strtolower($line),'retry-after:'))$retryAfter=trim(substr($line,12,128));
        return strlen($line);
    });
    $started=hrtime(true);$body=curl_exec($handle);$latency=max(0,(int)round((hrtime(true)-$started)/1000000));$status=(int)curl_getinfo($handle,CURLINFO_RESPONSE_CODE);$curlError=curl_errno($handle);curl_close($handle);if(!is_string($body))$body='';
    if(strlen($body)>FIXLAB_MOSA_MARKET_SOURCE_LAB_MAX_RESPONSE_BYTES)return ['body'=>'','http_status'=>$status>0?$status:null,'latency_ms'=>$latency,'error_code'=>'response_too_large'];return ['body'=>$body,'http_status'=>$status>0?$status:null,'latency_ms'=>$latency,'error_code'=>$curlError===0?null:'transport_error','retry_after'=>$retryAfter];
}

function fixlabMosaMarketSourceLabExecute(array $request,callable $transport,bool $expectsJson=true):array
{
    try{$raw=$transport($request);if(!is_array($raw))$raw=[];}catch(Throwable){$raw=['body'=>'','http_status'=>null,'latency_ms'=>null,'error_code'=>'transport_exception'];}
    $body=is_string($raw['body']??null)?$raw['body']:'';if(strlen($body)>FIXLAB_MOSA_MARKET_SOURCE_LAB_MAX_RESPONSE_BYTES)$raw=['body'=>'','http_status'=>$raw['http_status']??null,'latency_ms'=>$raw['latency_ms']??null,'error_code'=>'response_too_large'];
    $body=is_string($raw['body']??null)?$raw['body']:'';$http=is_int($raw['http_status']??null)?$raw['http_status']:null;$error=is_string($raw['error_code']??null)?$raw['error_code']:null;$decoded=$expectsJson?json_decode($body,true):null;
    if($error===null&&($http===null||$http<200||$http>=300))$error='http_status_invalid';if($error===null&&$expectsJson&&!is_array($decoded))$error='json_invalid';if($error===null&&!$expectsJson&&$body==='')$error='empty_response';
    return ['ok'=>$error===null,'http_status'=>$http,'latency_ms'=>is_int($raw['latency_ms']??null)?$raw['latency_ms']:null,'response_bytes'=>strlen($body),'error_code'=>$error,'json'=>is_array($decoded)?$decoded:null,'body'=>$body];
}

function fixlabMosaMarketSourceLabPublicRequest(array $request,array $response):array
{
    return ['request_key'=>$request['request_key'],'request_type'=>$request['request_type'],'endpoint_host'=>$request['endpoint_host'],'endpoint_path'=>$request['endpoint_path'],'parameters'=>$request['parameters'],'http_status'=>$response['http_status'],'latency_ms'=>$response['latency_ms'],'response_bytes'=>$response['response_bytes'],'error_code'=>$response['error_code']];
}

function fixlabMosaMarketSourceLabRawResponse(array $response,bool $json):array{return ['http_status'=>$response['http_status'],'content_type'=>$json?'application/json':'text/html','body'=>$response['body']];}
function fixlabMosaMarketSourceLabRows(mixed $json):array{if(!is_array($json))return [];if(array_is_list($json))return $json;foreach(['data','results','items']as$key)if(is_array($json[$key]??null))return $json[$key];return [];}

function fixlabMosaMarketSourceLabInstrument(array $rows,string $isin):?array
{
    $matches=[];foreach($rows as$row)if(is_array($row)&&($row['isin']??null)===$isin)$matches[]=$row;if($matches===[])return null;usort($matches,static function(array$left,array$right):int{$stock=static fn(array$row):bool=>($row['categorySymbol']??null)==='STK'||in_array(strtolower((string)($row['categoryName']??'')),['aktie','stock'],true);return(int)$stock($right)<=>(int)$stock($left);});
    $row=$matches[0];$id=$row['instrumentId']??$row['id']??null;return is_numeric($id)&&(int)$id>0?['id'=>(int)$id,'row'=>$row]:null;
}

function fixlabMosaMarketSourceLabTypeLabel(mixed $value):?string
{
    if(!is_string($value))return null;$normalized=strtolower(trim(preg_replace('/\s+/u',' ',str_replace(['_','-'],' ',$value))??''));
    return match($normalized){
        'stk','stock','aktie','aktien'=>'stock',
        'etf'=>'etf',
        'fnd','fund','fonds','mutualfund','mutual fund'=>'fund',
        'bond','bonds','anleihe','anleihen','certificate','certificates','zertifikat','zertifikate','warrant','warrants','optionsschein','optionsscheine','option','optionen','etc','etn','note','notes'=>'other',
        default=>null,
    };
}

function fixlabMosaMarketSourceLabTypeLink(mixed $value):?string
{
    if(!is_string($value))return null;$link=trim($value);
    return match(true){
        preg_match('~^/de/aktie/[1-9][0-9]*$~D',$link)===1=>'stock',
        preg_match('~^/de/etf/[1-9][0-9]*$~D',$link)===1=>'etf',
        preg_match('~^/de/(?:fonds|fund)/[1-9][0-9]*$~D',$link)===1=>'fund',
        preg_match('~^/de/(?:anleihe|anleihen|certificate|certificates|zertifikat|zertifikate|warrant|warrants|optionsschein|optionsscheine|option|optionen|etc|etn|note|notes)/[1-9][0-9]*$~D',$link)===1=>'other',
        default=>null,
    };
}

function fixlabMosaMarketSourceLabClassifyInstruments(array $rows,string $isin,DateTimeImmutable $verifiedAt):array
{
    $matches=array_values(array_filter($rows,static fn(mixed $row):bool=>is_array($row)&&($row['isin']??null)===$isin));
    if($matches===[])return ['instrument_type'=>'unknown','instrument_type_source'=>null,'instrument_type_verified_at'=>null];
    $types=[];$unresolved=false;$conflict=false;
    foreach($matches as $row){
        $evidence=[];
        foreach([fixlabMosaMarketSourceLabTypeLabel($row['categorySymbol']??null),fixlabMosaMarketSourceLabTypeLabel($row['categoryName']??null),fixlabMosaMarketSourceLabTypeLink($row['link']??null)] as $type)if($type!==null)$evidence[$type]=true;
        if(count($evidence)>1){$conflict=true;continue;}
        if($evidence===[]){$unresolved=true;continue;}
        $types[]=array_key_first($evidence);
    }
    $types=array_values(array_unique($types));
    if($conflict||count($types)>1)return ['instrument_type'=>'unknown','instrument_type_source'=>'lang_schwarz_conflict','instrument_type_verified_at'=>null];
    if($unresolved||count($types)!==1)return ['instrument_type'=>'unknown','instrument_type_source'=>null,'instrument_type_verified_at'=>null];
    return ['instrument_type'=>$types[0],'instrument_type_source'=>'lang_schwarz','instrument_type_verified_at'=>$verifiedAt->format(DateTimeInterface::ATOM)];
}

function fixlabMosaMarketSourceLabInstrumentPath(array $instrument):?string
{
    $id=$instrument['id']??null;$row=is_array($instrument['row']??null)?$instrument['row']:[];if(!is_int($id)||$id<1)return null;$link=is_string($row['link']??null)?trim($row['link']):'';
    if(preg_match('#^/de/(?:aktie|etf)/'.preg_quote((string)$id,'#').'$#D',$link)===1)return $link;
    $category=strtoupper(trim((string)($row['categorySymbol']??'')));$categoryName=strtolower(trim((string)($row['categoryName']??'')));return $category==='STK'||in_array($categoryName,['aktie','stock'],true)?'/de/aktie/'.$id:null;
}

function fixlabMosaMarketSourceLabFirstText(array $row,array $keys):?string{foreach($keys as$key){$value=$row[$key]??null;if(is_string($value)&&trim($value)!=='')return trim($value);}return null;}
function fixlabMosaMarketSourceLabHtmlText(string $value):string{return trim(preg_replace('/\s+/u',' ',html_entity_decode(strip_tags($value),ENT_QUOTES|ENT_HTML5,'UTF-8'))??'');}
function fixlabMosaMarketSourceLabHtmlField(string $html,string $field):?string{$quoted=preg_quote($field,'/');return preg_match('/<[^>]*\bfield=["\']'.$quoted.'["\'][^>]*>(.*?)<\/[^>]+>/is',$html,$match)===1?fixlabMosaMarketSourceLabHtmlText($match[1]):null;}
function fixlabMosaMarketSourceLabHtmlId(string $html,string $id):?string{$quoted=preg_quote($id,'/');return preg_match('/<([a-z0-9]+)\b(?=[^>]*\bid=["\']'.$quoted.'["\'])[^>]*>(.*?)<\/\1>/is',$html,$match)===1?fixlabMosaMarketSourceLabHtmlText($match[2]):null;}

function fixlabMosaMarketSourceLabHtmlItemField(string $html,int $instrumentId,int $marketId,string $field):?string
{
    $item=preg_quote($instrumentId.'@'.$marketId,'/');$field=preg_quote($field,'/');$pattern='/<([a-z0-9]+)\b(?=[^>]*\bitem=["\']'.$item.'["\'])(?=[^>]*\bfield=["\']'.$field.'["\'])[^>]*>(.*?)<\/\1>/is';return preg_match($pattern,$html,$match)===1?fixlabMosaMarketSourceLabHtmlText($match[2]):null;
}

function fixlabMosaMarketSourceLabTradegateCells(string $row):array
{
    preg_match_all('/<t[hd]\b[^>]*>(.*?)<\/t[hd]>/is',$row,$matches);return array_values(array_map('fixlabMosaMarketSourceLabHtmlText',$matches[1]??[]));
}

function fixlabMosaMarketSourceLabTradegateRow(string $html,string $label):?string
{
    preg_match_all('/<tr\b[^>]*>(.*?)<\/tr>/is',$html,$rows);foreach($rows[1]??[]as$row){$cells=fixlabMosaMarketSourceLabTradegateCells($row);if(count($cells)>1&&strcasecmp($cells[0],$label)===0)return $cells[1];}return null;
}

function fixlabMosaMarketSourceLabTradegateColumn(string $html,string $label):?string
{
    preg_match_all('/<tr\b[^>]*>(.*?)<\/tr>/is',$html,$rows);$wanted=null;foreach($rows[1]??[]as$row){$cells=fixlabMosaMarketSourceLabTradegateCells($row);if($wanted!==null){return array_key_exists($wanted,$cells)?$cells[$wanted]:null;}$index=array_search($label,$cells,true);if($index!==false)$wanted=$index;}return null;
}

function fixlabMosaMarketSourceLabTradegateCurrency(string $html):?string
{
    $currency=strtoupper((string)(fixlabMosaMarketSourceLabTradegateColumn($html,'Handelswährung')??''));if(preg_match('/^[A-Z]{3}$/D',$currency)===1)return $currency;$text=fixlabMosaMarketSourceLabHtmlText($html);return preg_match('/\bKurse in ([A-Z]{3})\b/u',$text,$match)===1?$match[1]:null;
}

function fixlabMosaMarketSourceLabTradegateDateTime(?string $date,?string $clock,DateTimeImmutable $requestedAt):?string
{
    if($date===null||$clock===null||preg_match('/^\d{2}\.\d{2}\.\d{4}$/D',trim($date))!==1||preg_match('/^\d{2}:\d{2}:\d{2}(?:[,.]\d{1,6})?$/D',trim($clock))!==1)return null;$clock=str_replace(',','.',trim($clock));if(!str_contains($clock,'.'))$clock.='.000000';else{[$whole,$fraction]=explode('.',$clock,2);$clock=$whole.'.'.str_pad(substr($fraction,0,6),6,'0');}$value=trim($date).' '.$clock;$local=DateTimeImmutable::createFromFormat('!d.m.Y H:i:s.u',$value,new DateTimeZone('Europe/Berlin'));if(!$local instanceof DateTimeImmutable||$local->format('d.m.Y H:i:s.u')!==$value||$local>$requestedAt->setTimezone(new DateTimeZone('Europe/Berlin'))->modify('+2 minutes'))return null;return $local->setTimezone(new DateTimeZone('UTC'))->format(DateTimeInterface::ATOM);
}

function fixlabMosaMarketSourceLabTradegateUpdatedAt(string $html,DateTimeImmutable $requestedAt):?string
{
    $text=fixlabMosaMarketSourceLabHtmlText($html);return preg_match('/Letzte Aktualisierung:\s*(\d{2}\.\d{2}\.\d{4})\s*@\s*(\d{2}:\d{2}:\d{2})/u',$text,$match)===1?fixlabMosaMarketSourceLabTradegateDateTime($match[1],$match[2],$requestedAt):null;
}

function fixlabMosaMarketSourceLabTradegateTrades(string $html,DateTimeImmutable $requestedAt):array
{
    $base=['available'=>false,'last'=>null,'last_at'=>null,'size'=>null,'count'=>0];preg_match_all('/<tr\b[^>]*>(.*?)<\/tr>/is',$html,$rows);$trades=[];foreach($rows[1]??[]as$row){$cells=fixlabMosaMarketSourceLabTradegateCells($row);if(count($cells)<5)continue;$time=fixlabMosaMarketSourceLabTradegateDateTime($cells[0],$cells[1],$requestedAt);$price=fixlabMosaMarketSourceLabPrice($cells[array_key_last($cells)]);if($time===null||$price===null)continue;$trades[]=['price'=>$price,'time'=>$time,'size'=>fixlabMosaMarketSourceLabSize($cells[2])];}if($trades===[])return $base;usort($trades,static fn(array$left,array$right):int=>strcmp($left['time'],$right['time']));$last=$trades[array_key_last($trades)];return ['available'=>true,'last'=>$last['price'],'last_at'=>$last['time'],'size'=>$last['size'],'count'=>count($trades)];
}

function fixlabMosaMarketSourceLabPrice(string $value):?float
{
    $value=preg_replace('/[^0-9,\.\-]/u','',fixlabMosaMarketSourceLabHtmlText($value))??'';if($value==='')return null;if(str_contains($value,',')&&str_contains($value,'.')){$comma=strrpos($value,',');$dot=strrpos($value,'.');$value=$comma>$dot?str_replace(',','.',str_replace('.','',$value)):str_replace(',','',$value);}elseif(str_contains($value,','))$value=str_replace(',','.',$value);return is_numeric($value)&&(float)$value>0?(float)$value:null;
}

function fixlabMosaMarketSourceLabSize(?string $value):?int{if($value===null)return null;$digits=preg_replace('/[^0-9]/','',$value)??'';return $digits!==''&&(int)$digits>0?(int)$digits:null;}

function fixlabMosaMarketSourceLabUtc(mixed $value):?string
{
    try{if(is_numeric($value)){$seconds=(int)$value;if($seconds>20000000000)$seconds=intdiv($seconds,1000);if($seconds<1)return null;$time=new DateTimeImmutable('@'.$seconds);}elseif(is_string($value)&&trim($value)!=='')$time=new DateTimeImmutable($value);else return null;return $time->setTimezone(new DateTimeZone('UTC'))->format(DateTimeInterface::ATOM);}catch(Throwable){return null;}
}

function fixlabMosaMarketSourceLabLsDatedQuote(?string $value,DateTimeImmutable $requestedAt):?string
{
    if($value===null||preg_match('/^(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)$/D',trim($value),$parts)!==1)return null;
    return fixlabMosaMarketSourceLabTradegateDateTime($parts[1],$parts[2],$requestedAt);
}
function fixlabMosaMarketSourceLabAgeSeconds(mixed $value,DateTimeImmutable $requestedAt):?int{if(!is_string($value)||$value==='')return null;try{$quotedAt=new DateTimeImmutable($value);}catch(Throwable){return null;}return max(0,$requestedAt->getTimestamp()-$quotedAt->getTimestamp());}
function fixlabMosaMarketSourceLabQuoteQuality(mixed $value,DateTimeImmutable $requestedAt):array{$age=fixlabMosaMarketSourceLabAgeSeconds($value,$requestedAt);if($age===null)return ['status'=>'unavailable','age_seconds'=>null];if($age<=FIXLAB_MOSA_MARKET_SOURCE_LAB_FRESH_SECONDS)return ['status'=>'fresh','age_seconds'=>$age];if($age<=FIXLAB_MOSA_MARKET_SOURCE_LAB_AGING_SECONDS)return ['status'=>'aging','age_seconds'=>$age];return ['status'=>'stale','age_seconds'=>$age];}

function fixlabMosaMarketSourceLabIndicatorRule(string $indicatorKey,string $sourceKey):?array
{
    $rule=FIXLAB_MOSA_MARKET_SOURCE_LAB_INDICATOR_STATUS_RULES['sources'][$indicatorKey][$sourceKey]??null;return is_array($rule)?$rule:null;
}

function fixlabMosaMarketSourceLabClockSeconds(string $clock):?int
{
    if(preg_match('/^(\d{2}):(\d{2})$/D',$clock,$parts)!==1)return null;$hours=(int)$parts[1];$minutes=(int)$parts[2];if($hours===24&&$minutes===0)return 86400;if($hours>23||$minutes>59)return null;return $hours*3600+$minutes*60;
}

function fixlabMosaMarketSourceLabIndicatorMarketOpen(array $rule,DateTimeImmutable $requestedAt):bool
{
    try{$local=$requestedAt->setTimezone(new DateTimeZone((string)($rule['timezone']??'')));}catch(Throwable){return false;}$sessions=$rule['sessions'][(int)$local->format('N')]??[];$second=(int)$local->format('H')*3600+(int)$local->format('i')*60+(int)$local->format('s');foreach($sessions as$session){if(!is_array($session)||count($session)!==2)continue;$start=fixlabMosaMarketSourceLabClockSeconds((string)$session[0]);$end=fixlabMosaMarketSourceLabClockSeconds((string)$session[1]);if($start!==null&&$end!==null&&$second>=$start&&$second<$end)return true;}return false;
}

function fixlabMosaMarketSourceLabIndicatorQuality(string $indicatorKey,string $sourceKey,mixed $value,DateTimeImmutable $requestedAt):array
{
    $age=fixlabMosaMarketSourceLabAgeSeconds($value,$requestedAt);$rule=fixlabMosaMarketSourceLabIndicatorRule($indicatorKey,$sourceKey);try{$quotedAt=is_string($value)?new DateTimeImmutable($value):null;}catch(Throwable){$quotedAt=null;}if($age===null||$rule===null||!$quotedAt instanceof DateTimeImmutable||$quotedAt>$requestedAt->modify('+2 minutes'))return ['status'=>'unavailable','age_seconds'=>$age,'market_open'=>false];$marketOpen=fixlabMosaMarketSourceLabIndicatorMarketOpen($rule,$requestedAt);if(!$marketOpen)return ['status'=>'market_closed','age_seconds'=>$age,'market_open'=>false];$currentSeconds=(int)FIXLAB_MOSA_MARKET_SOURCE_LAB_INDICATOR_STATUS_RULES['current_seconds'];$expectedDelay=max(0,(int)($rule['expected_delay_seconds']??0));$staleAfter=max($currentSeconds,$expectedDelay+(int)FIXLAB_MOSA_MARKET_SOURCE_LAB_INDICATOR_STATUS_RULES['stale_overrun_seconds']);if($expectedDelay===0&&$age<=$currentSeconds)$status='current';elseif($age<=$staleAfter)$status='delayed';else$status='stale';return ['status'=>$status,'age_seconds'=>$age,'market_open'=>true];
}

function fixlabMosaMarketSourceLabTrades(string $html,int $instrumentId,int $marketId,DateTimeImmutable $requestedAt):array
{
    $base=['available'=>false,'last'=>null,'last_at'=>null,'count'=>0];if($html===''||!str_contains($html,'item="'.$instrumentId.'@'.$marketId.'"')||!str_contains($html,'data-type="trades"'))return $base;$zone=new DateTimeZone('Europe/Berlin');$localRequest=$requestedAt->setTimezone($zone);preg_match_all('/<tr\b[^>]*>(.*?)<\/tr>/is',$html,$rows);$trades=[];$currency=null;
    foreach($rows[1]??[]as$row){$clock=fixlabMosaMarketSourceLabHtmlField($row,'tradeTime');$rawPrice=fixlabMosaMarketSourceLabHtmlField($row,'tradeWithCurrencySymbol');if($clock===null||$rawPrice===null||preg_match('/^(\d{2})\.(\d{2})\.\s*(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?$/D',$clock,$parts)!==1)continue;$year=$localRequest->format('Y');$month=$parts[2]!==''?$parts[2]:$localRequest->format('m');$day=$parts[1]!==''?$parts[1]:$localRequest->format('d');$micros=str_pad($parts[6]??'',6,'0');$local=DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u',$year.'-'.$month.'-'.$day.' '.$parts[3].':'.$parts[4].':'.$parts[5].'.'.$micros,$zone);if($local instanceof DateTimeImmutable&&$parts[1]!==''&&$local>$localRequest->modify('+1 day'))$local=$local->modify('-1 year');$price=fixlabMosaMarketSourceLabPrice($rawPrice);if(!$local instanceof DateTimeImmutable||$price===null||$local>$localRequest->modify('+2 minutes'))continue;if(str_contains($rawPrice,'€')||preg_match('/\bEUR\b/i',$rawPrice)===1)$currency='EUR';$trades[]=['price'=>$price,'time'=>$local];}
    if($trades===[])return $base;usort($trades,static fn(array$left,array$right):int=>$left['time']<=>$right['time']);$last=$trades[array_key_last($trades)];return ['available'=>true,'last'=>$last['price'],'last_at'=>$last['time']->setTimezone(new DateTimeZone('UTC'))->format(DateTimeInterface::ATOM),'currency'=>$currency,'count'=>count($trades)];
}

function fixlabMosaMarketSourceLabTelemetry(array $responses,array $keys):array
{
    $count=0;$failed=0;$latencies=[];$bytes=0;foreach($keys as$key){$response=$responses[$key]??null;if(!is_array($response))continue;$count++;if(($response['ok']??false)!==true)$failed++;if(is_int($response['latency_ms']??null))$latencies[]=$response['latency_ms'];if(is_int($response['response_bytes']??null))$bytes+=$response['response_bytes'];}return ['request_count'=>$count,'failed_request_count'=>$failed,'latency_ms'=>$latencies===[]?null:max($latencies),'response_bytes'=>$bytes];
}

function fixlabMosaMarketSourceLabNumeric(array $row,string $key):int|float|null{$value=$row[$key]??null;return is_numeric($value)?0+$value:null;}

function fixlabMosaMarketSourceLabFinalizeSource(array $source,DateTimeImmutable $now,bool $classifyFreshness=true):array
{
    $source['age_seconds']=fixlabMosaMarketSourceLabAgeSeconds($source['quoted_at'],$now);$source['spread_percent']=is_numeric($source['spread']??null)&&is_numeric($source['mid']??null)&&(float)$source['mid']>0?(float)$source['spread']/(float)$source['mid']*100:null;if($classifyFreshness){$quality=fixlabMosaMarketSourceLabQuoteQuality($source['quoted_at'],$now);$source['freshness']=$quality['status'];}else$source['freshness']=$source['available']?'not_applicable':'unavailable';return $source;
}

function fixlabMosaMarketSourceLabFinalizeIndicatorSource(array $source,string $indicatorKey,string $sourceKey,DateTimeImmutable $now):array
{
    $source=fixlabMosaMarketSourceLabFinalizeSource($source,$now,false);$rule=fixlabMosaMarketSourceLabIndicatorRule($indicatorKey,$sourceKey);$quality=fixlabMosaMarketSourceLabIndicatorQuality($indicatorKey,$sourceKey,$source['quoted_at'],$now);$source['freshness']=$source['available']?$quality['status']:'unavailable';$source['market_open']=$quality['market_open'];$source['market_timezone']=$rule['timezone']??null;$source['expected_delay_seconds']=$rule['expected_delay_seconds']??null;return $source;
}

function fixlabMosaMarketSourceLabSnapshot(array $result):array
{
    $requests=is_array($result['requests']??null)?$result['requests']:[];$latencies=[];$responseBytes=0;$failedRequests=0;foreach($requests as$request){if(!is_array($request))continue;if(is_int($request['latency_ms']??null))$latencies[]=$request['latency_ms'];if(is_int($request['response_bytes']??null))$responseBytes+=$request['response_bytes'];if(($request['error_code']??null)!==null)$failedRequests++;}
    $snapshot=['contract_version'=>$result['contract_version']??FIXLAB_MOSA_MARKET_SOURCE_LAB_VERSION,'mode'=>'read_only_comparison_snapshot','ok'=>($result['ok']??false)===true,'status'=>$result['status']??'failed','provider_key'=>$result['provider_key']??FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER,'instrument_key'=>$result['instrument_key']??($result['isin']??''),'asset_type'=>$result['asset_type']??'security','isin'=>$result['isin']??'','instrument'=>$result['instrument']??[],'requested_at'=>$result['requested_at']??null,'sources'=>$result['sources']??[],'mosa_quote_candidate'=>is_array($result['mosa_quote_candidate']??null)?$result['mosa_quote_candidate']:null,'telemetry'=>['request_count'=>count($requests),'failed_request_count'=>$failedRequests,'max_latency_ms'=>$latencies===[]?null:max($latencies),'response_bytes'=>$responseBytes],'errors'=>array_values(array_filter($result['errors']??[],'is_string')),'warnings'=>array_values(array_filter($result['warnings']??[],'is_string')),'safety'=>['database_connected'=>($result['database_connected']??false)===true,'sql_executed'=>($result['sql_executed']??false)===true,'write_actions_executed'=>($result['write_actions_executed']??false)===true,'state_written'=>($result['state_written']??false)===true]];
    if(($result['asset_type']??null)==='market_indicator')$snapshot['raw_responses']=is_array($result['raw_responses']??null)?$result['raw_responses']:[];return $snapshot;
}

function fixlabMosaMarketSourceLabQuoteCandidate(string $isin,array $sources,string $assetType='stock',?DateTimeImmutable $now=null):?array
{
    if($assetType==='etf')return fixlabMosaMarketEtfShadowSelection($isin,$sources,$now);return $isin==='DE0005936124'?fixlabMosaMarketQuoteRouter($sources):null;
}

function fixlabMosaMarketSourceLabErrorMessage(string $code):string
{
    return match($code){'isin_invalid'=>'Bitte eine gültige ISIN eingeben.','market_indicator_invalid'=>'Dieser Marktindikator ist nicht freigegeben.','provider_invalid'=>'Dieser Laborvergleich ist nicht verfügbar.','request_invalid'=>'Ungültige Laboranfrage.','csrf_invalid'=>'Die Sitzung ist abgelaufen.','no_market_values'=>'Keine der Vergleichsquellen hat einen Marktwert geliefert.',default=>'Die Abfrage konnte nicht vollständig ausgewertet werden.'};
}

function fixlabRunMosaMarketSourceIndicatorLab(mixed $indicatorKey,mixed $provider=FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER,?callable $transport=null,?DateTimeImmutable $now=null):array
{
    $indicator=fixlabMosaMarketSourceLabIndicator($indicatorKey);$fallback=['key'=>is_string($indicatorKey)?strtolower(trim($indicatorKey)):'','name'=>null,'yahoo_symbol'=>null,'venue_label'=>'Markt','unit_label'=>null,'tradegate_index'=>null];$result=fixlabMosaMarketSourceLabIndicatorBase($indicator??$fallback);$now=($now??new DateTimeImmutable('now',new DateTimeZone('UTC')))->setTimezone(new DateTimeZone('UTC'));$result['requested_at']=$now->format(DateTimeInterface::ATOM);
    if($indicator===null)return array_replace($result,['status'=>'invalid_input','errors'=>['market_indicator_invalid']]);if($provider!==FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER)return array_replace($result,['status'=>'invalid_input','errors'=>['provider_invalid']]);$transport??='fixlabMosaMarketSourceLabLiveTransport';$responses=[];
    $symbol=(string)$indicator['yahoo_symbol'];$indicatorRequests=fixlabMosaMarketSourceLabIndicatorRequests($indicator);$yahooRequest=$indicatorRequests['yahoo_market_indicator'];$responses['yahoo_market_indicator']=fixlabMosaMarketSourceLabExecute($yahooRequest,$transport);$result['external_fetch_executed']=true;$result['requests'][]=fixlabMosaMarketSourceLabPublicRequest($yahooRequest,$responses['yahoo_market_indicator']);$result['raw_responses']['yahoo_market_indicator']=fixlabMosaMarketSourceLabRawResponse($responses['yahoo_market_indicator'],true);$yahoo=$result['sources']['yahoo_market_indicator'];$chart=$responses['yahoo_market_indicator']['json']['chart']['result'][0]??null;$meta=is_array($chart)&&is_array($chart['meta']??null)?$chart['meta']:null;$rawCurrency=is_array($meta)&&is_string($meta['currency']??null)?trim($meta['currency']):'';$currency=strtoupper($rawCurrency);if(preg_match('/^[A-Z]{3}$/D',$currency)!==1)$currency=null;
    if($responses['yahoo_market_indicator']['ok']&&is_array($meta)&&($meta['symbol']??null)===$symbol&&is_numeric($meta['regularMarketPrice']??null)&&fixlabMosaMarketSourceLabUtc($meta['regularMarketTime']??null)!==null){$yahoo['available']=true;$yahoo['price']=0+$meta['regularMarketPrice'];$yahoo['currency']=$currency;$yahoo['quoted_at']=fixlabMosaMarketSourceLabUtc($meta['regularMarketTime']);$yahoo['previous_close']=fixlabMosaMarketSourceLabNumeric($meta,'chartPreviousClose')??fixlabMosaMarketSourceLabNumeric($meta,'previousClose');$yahoo['day_high']=fixlabMosaMarketSourceLabNumeric($meta,'regularMarketDayHigh');$yahoo['day_low']=fixlabMosaMarketSourceLabNumeric($meta,'regularMarketDayLow');$yahoo['volume']=fixlabMosaMarketSourceLabNumeric($meta,'regularMarketVolume');$yahoo['venue_label']=fixlabMosaMarketSourceLabFirstText($meta,['fullExchangeName','exchangeName'])??$indicator['venue_label'];$yahoo['exchange_code']=fixlabMosaMarketSourceLabFirstText($meta,['exchangeName']);$yahoo['symbol']=$symbol;$yahoo['unit_label']=$indicator['unit_label'];}else$yahoo['error_code']=$responses['yahoo_market_indicator']['error_code']??'yahoo_indicator_not_delivered';$yahoo['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['yahoo_market_indicator']);$result['sources']['yahoo_market_indicator']=fixlabMosaMarketSourceLabFinalizeIndicatorSource($yahoo,(string)$indicator['key'],'yahoo_market_indicator',$now);
    if(is_string($indicator['tradegate_index']??null)){$index=$indicator['tradegate_index'];$tradegateRequest=$indicatorRequests['tradegate_dax_indicator'];$responses['tradegate_dax_indicator']=fixlabMosaMarketSourceLabExecute($tradegateRequest,$transport,false);$result['requests'][]=fixlabMosaMarketSourceLabPublicRequest($tradegateRequest,$responses['tradegate_dax_indicator']);$result['raw_responses']['tradegate_dax_indicator']=fixlabMosaMarketSourceLabRawResponse($responses['tradegate_dax_indicator'],false);$tradegate=$result['sources']['tradegate_dax_indicator'];$html=$responses['tradegate_dax_indicator']['ok']?$responses['tradegate_dax_indicator']['body']:'';$tradegate['price']=fixlabMosaMarketSourceLabPrice((string)(fixlabMosaMarketSourceLabHtmlId($html,'points_'.$index)??''));$tradegate['previous_close']=fixlabMosaMarketSourceLabPrice((string)(fixlabMosaMarketSourceLabHtmlId($html,'close_'.$index)??''));$tradegate['day_high']=fixlabMosaMarketSourceLabPrice((string)(fixlabMosaMarketSourceLabHtmlId($html,'high_'.$index)??''));$tradegate['day_low']=fixlabMosaMarketSourceLabPrice((string)(fixlabMosaMarketSourceLabHtmlId($html,'low_'.$index)??''));$tradegate['quoted_at']=fixlabMosaMarketSourceLabTradegateDateTime(fixlabMosaMarketSourceLabHtmlId($html,'rt_datum'),fixlabMosaMarketSourceLabHtmlId($html,'rt_zeit'),$now);$tradegate['symbol']=$index;$tradegate['exchange_code']='TRADEGATE_BSX';$tradegate['unit_label']='Punkte';$tradegate['available']=is_numeric($tradegate['price'])&&is_string($tradegate['quoted_at']);$tradegate['error_code']=$tradegate['available']?null:($responses['tradegate_dax_indicator']['error_code']??'tradegate_dax_indicator_not_delivered');$tradegate['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['tradegate_dax_indicator']);$result['sources']['tradegate_dax_indicator']=fixlabMosaMarketSourceLabFinalizeIndicatorSource($tradegate,(string)$indicator['key'],'tradegate_dax_indicator',$now);}
    $available=0;foreach($result['sources']as$key=>$source){if(($source['available']??false)===true)$available++;else$result['warnings'][]=$key.':'.($source['error_code']??'not_available');}if($available===0)$result['errors'][]='no_market_values';$result['ok']=$available>0;$result['status']=$available===count($result['sources'])?'completed':($available>0?'partial':'failed');return $result;
}

function fixlabRunMosaMarketSourceLab(mixed $isin,mixed $provider=FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER,?callable $transport=null,?DateTimeImmutable $now=null,string $assetType='stock'):array
{
    $normalized=fixlabMosaMarketSourceLabNormalizeIsin($isin);$result=fixlabMosaMarketSourceLabBase($normalized);$now=($now??new DateTimeImmutable('now',new DateTimeZone('UTC')))->setTimezone(new DateTimeZone('UTC'));$result['requested_at']=$now->format(DateTimeInterface::ATOM);
    if(!in_array($assetType,['stock','etf'],true))return array_replace($result,['status'=>'invalid_input','errors'=>['asset_type_invalid']]);$result['asset_type']=$assetType;if(!fixlabMosaMarketSourceLabIsinValid($normalized))return array_replace($result,['status'=>'invalid_input','errors'=>['isin_invalid']]);if($provider!==FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER)return array_replace($result,['status'=>'invalid_input','errors'=>['provider_invalid']]);$transport??='fixlabMosaMarketSourceLabLiveTransport';$responses=[];

    $searchRequest=fixlabMosaMarketSourceLabLsRequest('lang_schwarz_search','L&S Instrumentensuche','/_rpc/json/.lstc/instrument/search/main',['q'=>$normalized,'localeId'=>2]);$responses['lang_schwarz_search']=fixlabMosaMarketSourceLabExecute($searchRequest,$transport);$result['external_fetch_executed']=true;$result['requests'][]=fixlabMosaMarketSourceLabPublicRequest($searchRequest,$responses['lang_schwarz_search']);$result['raw_responses']['lang_schwarz_search']=fixlabMosaMarketSourceLabRawResponse($responses['lang_schwarz_search'],true);
    $searchRows=fixlabMosaMarketSourceLabRows($responses['lang_schwarz_search']['json']);$result=array_replace($result,fixlabMosaMarketSourceLabClassifyInstruments($searchRows,$normalized,$now));$instrument=$responses['lang_schwarz_search']['ok']?fixlabMosaMarketSourceLabInstrument($searchRows,$normalized):null;$instrumentId=null;$marketId=1;
    if($instrument!==null&&fixlabMosaMarketSourceLabInstrumentPath($instrument)!==null){$row=$instrument['row'];$instrumentId=$instrument['id'];$marketRaw=$row['marketId']??1;$marketId=is_numeric($marketRaw)&&(int)$marketRaw>0?(int)$marketRaw:1;$result['instrument']=['isin'=>$normalized,'name'=>fixlabMosaMarketSourceLabFirstText($row,['name','displayName','displayname','instrumentName','securityName','nameLong','nameShort','label']),'wkn'=>fixlabMosaMarketSourceLabFirstText($row,['wkn','WKN']),'instrument_id'=>$instrumentId,'market_id'=>$marketId];
        $pageRequest=fixlabMosaMarketSourceLabLsRequest('lang_schwarz_page','L&S Offerte und Handelskurse',(string)fixlabMosaMarketSourceLabInstrumentPath($instrument));$responses['lang_schwarz_page']=fixlabMosaMarketSourceLabExecute($pageRequest,$transport,false);$result['requests'][]=fixlabMosaMarketSourceLabPublicRequest($pageRequest,$responses['lang_schwarz_page']);$result['raw_responses']['lang_schwarz_page']=fixlabMosaMarketSourceLabRawResponse($responses['lang_schwarz_page'],false);
        $result['sources']['lang_schwarz_quote']['isin']=$normalized;
        $html=$responses['lang_schwarz_page']['ok']?$responses['lang_schwarz_page']['body']:'';$quote=$result['sources']['lang_schwarz_quote'];$rawBid=fixlabMosaMarketSourceLabHtmlItemField($html,$instrumentId,$marketId,'bid');$rawAsk=fixlabMosaMarketSourceLabHtmlItemField($html,$instrumentId,$marketId,'ask');$rawMid=fixlabMosaMarketSourceLabHtmlItemField($html,$instrumentId,$marketId,'mid');$quote['bid']=$rawBid===null?null:fixlabMosaMarketSourceLabPrice($rawBid);$quote['ask']=$rawAsk===null?null:fixlabMosaMarketSourceLabPrice($rawAsk);$quote['reported_mid']=$rawMid===null?null:fixlabMosaMarketSourceLabPrice($rawMid);$quote['mid']=is_numeric($quote['bid'])&&is_numeric($quote['ask'])?((float)$quote['bid']+(float)$quote['ask'])/2:$quote['reported_mid'];$quote['spread']=is_numeric($quote['bid'])&&is_numeric($quote['ask'])&&(float)$quote['ask']>=(float)$quote['bid']?(float)$quote['ask']-(float)$quote['bid']:null;$quote['bid_size']=fixlabMosaMarketSourceLabSize(fixlabMosaMarketSourceLabHtmlItemField($html,$instrumentId,$marketId,'bidSize'));$quote['ask_size']=fixlabMosaMarketSourceLabSize(fixlabMosaMarketSourceLabHtmlItemField($html,$instrumentId,$marketId,'askSize'));$quote['quoted_at']=fixlabMosaMarketSourceLabLsDatedQuote(fixlabMosaMarketSourceLabHtmlItemField($html,$instrumentId,$marketId,'midTime'),$now);$quote['currency']='EUR';$quote['price']=$quote['mid'];$quote['available']=is_numeric($quote['bid'])&&is_numeric($quote['ask'])&&(float)$quote['ask']>=(float)$quote['bid']&&is_string($quote['quoted_at']);$quote['error_code']=$quote['available']?null:($responses['lang_schwarz_page']['error_code']??'quote_not_delivered');$quote['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['lang_schwarz_search','lang_schwarz_page']);$result['sources']['lang_schwarz_quote']=fixlabMosaMarketSourceLabFinalizeSource($quote,$now);
        if(is_numeric($quote['reported_mid'])&&is_numeric($quote['mid'])&&abs((float)$quote['reported_mid']-(float)$quote['mid'])>0.000001)$result['warnings'][]='lang_schwarz_mid_mismatch';
        $trade=$result['sources']['lang_schwarz_trade'];$parsedTrades=fixlabMosaMarketSourceLabTrades($html,$instrumentId,$marketId,$now);$trade['available']=($parsedTrades['available']??false)===true;$trade['price']=$parsedTrades['last']??null;$trade['quoted_at']=$parsedTrades['last_at']??null;$trade['currency']=$parsedTrades['currency']??$quote['currency'];$trade['error_code']=$trade['available']?null:($responses['lang_schwarz_page']['error_code']??'trade_not_delivered');$trade['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['lang_schwarz_search','lang_schwarz_page']);$result['sources']['lang_schwarz_trade']=fixlabMosaMarketSourceLabFinalizeSource($trade,$now,false);
    }else{foreach(['lang_schwarz_quote','lang_schwarz_trade']as$key){$result['sources'][$key]['error_code']=$responses['lang_schwarz_search']['ok']?'instrument_not_found':($responses['lang_schwarz_search']['error_code']??'search_unreachable');$result['sources'][$key]['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['lang_schwarz_search']);}}

    $tradegateQuoteRequest=fixlabMosaMarketSourceLabTradegateRequest('tradegate_quote','Tradegate BSX · Offerte','/orderbuch.php',$normalized);$responses['tradegate_quote']=fixlabMosaMarketSourceLabExecute($tradegateQuoteRequest,$transport,false);$result['requests'][]=fixlabMosaMarketSourceLabPublicRequest($tradegateQuoteRequest,$responses['tradegate_quote']);$result['raw_responses']['tradegate_quote']=fixlabMosaMarketSourceLabRawResponse($responses['tradegate_quote'],false);$tradegateQuote=$result['sources']['tradegate_quote'];$tradegateQuoteHtml=$responses['tradegate_quote']['ok']?$responses['tradegate_quote']['body']:'';$tradegateIsin=strtoupper((string)(fixlabMosaMarketSourceLabTradegateColumn($tradegateQuoteHtml,'ISIN')??''));$tradegateCurrency=fixlabMosaMarketSourceLabTradegateCurrency($tradegateQuoteHtml);
    $tradegateQuote['isin']=$tradegateIsin;
    $tradegateQuote['bid']=fixlabMosaMarketSourceLabPrice((string)(fixlabMosaMarketSourceLabTradegateRow($tradegateQuoteHtml,'Bid')??''));$tradegateQuote['ask']=fixlabMosaMarketSourceLabPrice((string)(fixlabMosaMarketSourceLabTradegateRow($tradegateQuoteHtml,'Ask')??''));$tradegateQuote['mid']=is_numeric($tradegateQuote['bid'])&&is_numeric($tradegateQuote['ask'])?((float)$tradegateQuote['bid']+(float)$tradegateQuote['ask'])/2:null;$tradegateQuote['spread']=is_numeric($tradegateQuote['bid'])&&is_numeric($tradegateQuote['ask'])&&(float)$tradegateQuote['ask']>=(float)$tradegateQuote['bid']?(float)$tradegateQuote['ask']-(float)$tradegateQuote['bid']:null;$tradegateQuote['bid_size']=fixlabMosaMarketSourceLabSize(fixlabMosaMarketSourceLabTradegateRow($tradegateQuoteHtml,'Bid Size'));$tradegateQuote['ask_size']=fixlabMosaMarketSourceLabSize(fixlabMosaMarketSourceLabTradegateRow($tradegateQuoteHtml,'Ask Size'));$tradegateQuote['day_high']=fixlabMosaMarketSourceLabPrice((string)(fixlabMosaMarketSourceLabTradegateRow($tradegateQuoteHtml,'High')??''));$tradegateQuote['day_low']=fixlabMosaMarketSourceLabPrice((string)(fixlabMosaMarketSourceLabTradegateRow($tradegateQuoteHtml,'Low')??''));$tradegateQuote['volume']=fixlabMosaMarketSourceLabSize(fixlabMosaMarketSourceLabTradegateRow($tradegateQuoteHtml,'Stück'));$tradegateQuote['quoted_at']=fixlabMosaMarketSourceLabTradegateUpdatedAt($tradegateQuoteHtml,$now);$tradegateQuote['currency']=$tradegateCurrency;$tradegateQuote['price']=$tradegateQuote['mid'];$tradegateQuote['available']=$tradegateIsin===$normalized&&is_numeric($tradegateQuote['bid'])&&is_numeric($tradegateQuote['ask'])&&(float)$tradegateQuote['ask']>=(float)$tradegateQuote['bid']&&$tradegateCurrency!==null&&is_string($tradegateQuote['quoted_at']);$tradegateQuote['error_code']=$tradegateQuote['available']?null:($responses['tradegate_quote']['error_code']??'tradegate_quote_not_delivered');$tradegateQuote['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['tradegate_quote']);$result['sources']['tradegate_quote']=fixlabMosaMarketSourceLabFinalizeSource($tradegateQuote,$now);

    $tradegateTradeRequest=fixlabMosaMarketSourceLabTradegateRequest('tradegate_trade','Tradegate BSX · letzter Handel','/orderbuch_umsaetze.php',$normalized);$responses['tradegate_trade']=fixlabMosaMarketSourceLabExecute($tradegateTradeRequest,$transport,false);$result['requests'][]=fixlabMosaMarketSourceLabPublicRequest($tradegateTradeRequest,$responses['tradegate_trade']);$result['raw_responses']['tradegate_trade']=fixlabMosaMarketSourceLabRawResponse($responses['tradegate_trade'],false);$tradegateTrade=$result['sources']['tradegate_trade'];$tradegateTradeHtml=$responses['tradegate_trade']['ok']?$responses['tradegate_trade']['body']:'';$parsedTradegateTrades=fixlabMosaMarketSourceLabTradegateTrades($tradegateTradeHtml,$now);$tradegateTradeCurrency=$tradegateCurrency??fixlabMosaMarketSourceLabTradegateCurrency($tradegateTradeHtml);$tradegateTrade['available']=($parsedTradegateTrades['available']??false)===true&&$tradegateTradeCurrency!==null;$tradegateTrade['price']=$parsedTradegateTrades['last']??null;$tradegateTrade['quoted_at']=$parsedTradegateTrades['last_at']??null;$tradegateTrade['trade_size']=$parsedTradegateTrades['size']??null;$tradegateTrade['currency']=$tradegateTradeCurrency;$tradegateTrade['error_code']=$tradegateTrade['available']?null:($responses['tradegate_trade']['error_code']??'tradegate_trade_not_delivered');$tradegateTrade['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['tradegate_trade']);$result['sources']['tradegate_trade']=fixlabMosaMarketSourceLabFinalizeSource($tradegateTrade,$now,false);

    $frankfurtDefinition=fixlabMosaFrankfurtRequest($normalized,'current',$now);$frankfurtRequest=fixlabMosaMarketSourceLabRequest('boerse_frankfurt_trade','Börse Frankfurt · letzter Handel',(string)($frankfurtDefinition['url']??''),is_array($frankfurtDefinition['headers']??null)?$frankfurtDefinition['headers']:[]);$responses['boerse_frankfurt_trade']=fixlabMosaMarketSourceLabExecute($frankfurtRequest,$transport);$result['requests'][]=fixlabMosaMarketSourceLabPublicRequest($frankfurtRequest,$responses['boerse_frankfurt_trade']);$result['raw_responses']['boerse_frankfurt_trade']=fixlabMosaMarketSourceLabRawResponse($responses['boerse_frankfurt_trade'],true);$frankfurt=$result['sources']['boerse_frankfurt_trade'];$payload=$responses['boerse_frankfurt_trade']['json'];
    if($responses['boerse_frankfurt_trade']['ok']&&fixlabMosaFrankfurtSnapshotValid($payload,$normalized)){$frankfurt['available']=true;$frankfurt['price']=0+$payload['lastPrice'];$frankfurt['currency']='EUR';$frankfurt['quoted_at']=fixlabMosaMarketSourceLabUtc($payload['timestampLastPrice']);$frankfurt['previous_close']=fixlabMosaMarketSourceLabNumeric($payload,'closingPricePrevTradingDay');$frankfurt['day_high']=fixlabMosaMarketSourceLabNumeric($payload,'dayHigh');$frankfurt['day_low']=fixlabMosaMarketSourceLabNumeric($payload,'dayLow');$frankfurt['volume']=fixlabMosaMarketSourceLabNumeric($payload,'turnoverInPieces');}else$frankfurt['error_code']=$responses['boerse_frankfurt_trade']['error_code']??'frankfurt_not_delivered';$frankfurt['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['boerse_frankfurt_trade']);$result['sources']['boerse_frankfurt_trade']=fixlabMosaMarketSourceLabFinalizeSource($frankfurt,$now,false);

    $yahooSearchRequest=fixlabMosaMarketSourceLabRequest('yahoo_home_search','Yahoo Heimatmarkt-Suche','https://query1.finance.yahoo.com/v1/finance/search?q='.rawurlencode($normalized).'&quotesCount=10&newsCount=0',['Accept: application/json','User-Agent: FixLab-MOSA-Market-Source-Lab/2.0']);$responses['yahoo_home_search']=fixlabMosaMarketSourceLabExecute($yahooSearchRequest,$transport);$result['requests'][]=fixlabMosaMarketSourceLabPublicRequest($yahooSearchRequest,$responses['yahoo_home_search']);$result['raw_responses']['yahoo_home_search']=fixlabMosaMarketSourceLabRawResponse($responses['yahoo_home_search'],true);$yahoo=$result['sources']['yahoo_home_market'];$selected=$responses['yahoo_home_search']['ok']&&is_array($responses['yahoo_home_search']['json']['quotes']??null)?fixlabMosaMarketSelectYahooCandidate($responses['yahoo_home_search']['json']['quotes'],$normalized):null;
    if(is_array($selected)){$symbol=trim((string)($selected['symbol']??''));$exchange=trim((string)($selected['exchange']??$selected['exchDisp']??''));$venue=fixlabMosaMarketSourceLabFirstText($selected,['longExchangeName','exchDisp','exchange']);$yahoo['symbol']=$symbol;$yahoo['exchange_code']=$exchange!==''?$exchange:null;$yahoo['venue_label']=$venue??'Heimatmarkt';$yahooRequest=fixlabMosaMarketSourceLabRequest('yahoo_home_market','Yahoo Heimatmarkt-Snapshot','https://query1.finance.yahoo.com/v8/finance/chart/'.rawurlencode($symbol).'?range=1d&interval=1d&includePrePost=false',['Accept: application/json','User-Agent: FixLab-MOSA-Market-Source-Lab/2.0']);$responses['yahoo_home_market']=fixlabMosaMarketSourceLabExecute($yahooRequest,$transport);$result['requests'][]=fixlabMosaMarketSourceLabPublicRequest($yahooRequest,$responses['yahoo_home_market']);$result['raw_responses']['yahoo_home_market']=fixlabMosaMarketSourceLabRawResponse($responses['yahoo_home_market'],true);$chart=$responses['yahoo_home_market']['json']['chart']['result'][0]??null;$meta=is_array($chart)&&is_array($chart['meta']??null)?$chart['meta']:null;$rawCurrency=is_array($meta)&&is_string($meta['currency']??null)?trim($meta['currency']):'';$currency=in_array($rawCurrency,['GBp','GBX'],true)?'GBX':strtoupper($rawCurrency);if(preg_match('/^[A-Z]{3}$/D',$currency)!==1)$currency=null;
        if($responses['yahoo_home_market']['ok']&&is_array($meta)&&($meta['symbol']??null)===$symbol&&$currency!==null&&is_numeric($meta['regularMarketPrice']??null)&&fixlabMosaMarketSourceLabUtc($meta['regularMarketTime']??null)!==null){$yahoo['available']=true;$yahoo['price']=0+$meta['regularMarketPrice'];$yahoo['currency']=$currency;$yahoo['quoted_at']=fixlabMosaMarketSourceLabUtc($meta['regularMarketTime']);$yahoo['previous_close']=fixlabMosaMarketSourceLabNumeric($meta,'chartPreviousClose');$yahoo['day_high']=fixlabMosaMarketSourceLabNumeric($meta,'regularMarketDayHigh');$yahoo['day_low']=fixlabMosaMarketSourceLabNumeric($meta,'regularMarketDayLow');$yahoo['volume']=fixlabMosaMarketSourceLabNumeric($meta,'regularMarketVolume');}else$yahoo['error_code']=$responses['yahoo_home_market']['error_code']??'yahoo_snapshot_not_delivered';
        $yahoo['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['yahoo_home_search','yahoo_home_market']);if($result['instrument']['name']===null)$result['instrument']['name']=fixlabMosaMarketSourceLabFirstText($selected,['longname','shortname','name']);
    }else{$yahoo['error_code']=$responses['yahoo_home_search']['error_code']??'home_market_not_found';$yahoo['telemetry']=fixlabMosaMarketSourceLabTelemetry($responses,['yahoo_home_search']);}
    $result['sources']['yahoo_home_market']=fixlabMosaMarketSourceLabFinalizeSource($yahoo,$now);

    $result['mosa_quote_candidate']=fixlabMosaMarketSourceLabQuoteCandidate($normalized,$result['sources'],$assetType,$now);
    $available=0;foreach($result['sources']as$key=>$source){if(($source['available']??false)===true)$available++;else$result['warnings'][]=$key.':'.($source['error_code']??'not_available');}$result['warnings']=array_values(array_unique($result['warnings']));if($available===0)$result['errors'][]='no_market_values';$result['ok']=$available>0;$result['status']=$available===count($result['sources'])?'completed':($available>0?'partial':'failed');return $result;
}
