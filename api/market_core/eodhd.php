<?php
declare(strict_types=1);
namespace Mosa2\MarketInternational\Eodhd;

use DateTimeImmutable;
use DateTimeZone;
use InvalidArgumentException;
use PDO;

/**
 * Licensed, delayed global quotes, resolved by exact ISIN.
 * Runs only inside the existing M2 minute collector. No ticker/ISIN lists.
 * Search results bind ISIN -> vendor ticker + original currency. The vendor
 * exchanges list binds vendor exchange -> exactly one physical operating MIC.
 * Unknown identity, exchange or currency never becomes a fabricated quote.
 */
function authorization(string $root):?array {
    $path=$root.'/mosa2-market-eodhd-private/access.php';
    if(!is_file($path))return null;
    if(is_link($path)||realpath($path)!==$path||(fileperms($path)&0077)!==0)
        throw new InvalidArgumentException('eodhd_config_permissions');
    $cfg=require $path;
    if(!is_array($cfg)||($cfg['enabled']??null)!==true
       ||($cfg['personal_or_internal_rights_confirmed']??null)!==true
       ||($cfg['private_display_only']??null)!==true)return null;
    $token=$cfg['api_token']??null;
    $daily=$cfg['max_daily_requests']??null;
    $minute=$cfg['max_minute_requests']??null;
    if(!is_string($token)||preg_match('/^[A-Za-z0-9_-]{12,128}$/D',$token)!==1
       ||!is_int($daily)||$daily<1||$daily>100000
       ||!is_int($minute)||$minute<1||$minute>1000)
        throw new InvalidArgumentException('eodhd_config_invalid');
    return ['api_token'=>$token,'max_daily_requests'=>$daily,'max_minute_requests'=>$minute];
}
function validIsin(string $isin):bool {
    return preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D',$isin)===1;
}
function validTicker(string $ticker):bool {
    return preg_match('/^[A-Za-z0-9][A-Za-z0-9._-]{1,40}\.[A-Za-z0-9]{1,10}$/D',$ticker)===1;
}
function request(string $kind,string $value,string $token):array {
    if(preg_match('/^[A-Za-z0-9_-]{4,128}$/D',$token)!==1)
        throw new InvalidArgumentException('eodhd_token_invalid');
    $path=match($kind) {
        'eodhd_search'=>validIsin($value)?'/search/'.$value:null,
        'eodhd_exchange'=>'/exchanges-list/',
        'eodhd_delayed'=>validTicker($value)?'/real-time/'.$value:null,
        default=>null
    };
    if($path===null)throw new InvalidArgumentException('eodhd_request_invalid');
    $suffix=$kind==='eodhd_search'?'&limit=100':'';
    return ['request_key'=>$kind,'request_type'=>'EODHD private delayed API',
        'url'=>'https://eodhd.com/api'.$path.'?api_token='.$token.'&fmt=json'.$suffix,
        'headers'=>['Accept: application/json'],'follow_redirects'=>false];
}
function approvedRequest(array $request,string $kind,string $value,string $token):bool {
    try {
        $expected=selfRequest($kind,$value,$token);
        return ($request['request_key']??null)===$kind
            &&($request['url']??null)===$expected['url']
            &&($request['follow_redirects']??true)===false;
    }catch(\Throwable){return false;}
}
function selfRequest(string $kind,string $value,string $token):array {
    return request($kind,$value,$token);
}
/** Resolve only exact-ISIN results, never a guessed ticker or country-code heuristic. */
function resolve(string $isin,mixed $search,mixed $exchanges):?array {
    if(!validIsin($isin)||!is_array($search)||!array_is_list($search)
       ||!is_array($exchanges)||!array_is_list($exchanges))return null;
    $candidates=[];
    foreach($search as $entry) {
        if(!is_array($entry)||($entry['ISIN']??null)!==$isin)continue;
        $ticker=$entry['Code']??null;
        $exchange=$entry['Exchange']??null;
        $unit=$entry['Currency']??null;
        if(!is_string($ticker)||!is_string($exchange)||!is_string($unit)
           ||preg_match('/^[A-Za-z0-9._-]{1,32}$/D',$ticker)!==1
           ||preg_match('/^[A-Za-z0-9]{1,10}$/D',$exchange)!==1
           ||preg_match('/^[A-Z]{3}$/D',$unit)!==1||$unit==='XXX')continue;
        $symbol=$ticker.'.'.$exchange;
        if(!validTicker($symbol))continue;
        // MIC comes from actual provider exchange metadata, not the ISIN prefix.
        $matching=array_values(array_filter($exchanges,static fn($e)=>
            is_array($e)&&($e['Code']??null)===$exchange));
        if(count($matching)!==1)continue;
        $mics=$matching[0]['OperatingMIC']??null;
        if(!is_string($mics)||preg_match('/^[A-Z0-9]{4}$/D',$mics)!==1)continue;
        $name=$matching[0]['Name']??null;
        if(!is_string($name)||!preg_match('/^[\p{L}\p{N} ._\/()-]{2,70}$/uD',$name))
            $name=$exchange;
        $candidates[]=['isin'=>$isin,'ticker'=>$symbol,'currency'=>$unit,
            'mic'=>$mics,'venue_label'=>$name,'primary'=>($entry['isPrimary']??null)===true];
    }
    $primary=array_values(array_filter($candidates,static fn($c)=>$c['primary']));
    $selection=count($primary)===1?$primary:(count($primary)===0&&count($candidates)===1?$candidates:[]);
    if(count($selection)!==1)return null; // Ambiguous multiple primary listings fail closed.
    $route=$selection[0];
    unset($route['primary']);
    return $route;
}
function source(string $isin,array $route,mixed $payload,DateTimeImmutable $now):array {
    $unavailable=['source_key'=>'eodhd_delayed','provider_key'=>'eodhd',
        'provider_label'=>'EODHD · 15–20 Min. verzögert','venue_label'=>'Unbekannt',
        'venue_key'=>'unknown','data_type'=>'last_trade','isin'=>$isin,'available'=>false,
        'price'=>null,'currency'=>null,'quoted_at'=>null];
    if(!validIsin($isin)||($route['isin']??null)!==$isin
       ||!is_array($payload)||array_is_list($payload))return $unavailable;
    $ticker=$route['ticker']??null;$mic=$route['mic']??null;$unit=$route['currency']??null;
    if(!is_string($ticker)||!validTicker($ticker)
        ||!is_string($mic)||preg_match('/^[A-Z0-9]{4}$/D',$mic)!==1
        ||!is_string($unit)||preg_match('/^[A-Z]{3}$/D',$unit)!==1
        ||($payload['code']??null)!==$ticker)return $unavailable;
    $price=$payload['close']??null;
    if(!is_string($price)&&!is_int($price)&&!is_float($price))return $unavailable;
    $value=(string)$price;
    if(!preg_match('/^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,10})?$/D',$value)
        ||(float)$value<=0)return $unavailable;
    $ts=$payload['timestamp']??null;
    if(!is_int($ts)||$ts<=0||$ts>$now->getTimestamp()+1)return $unavailable;
    // Delayed source: real event timestamp remains unchanged, never stamped "now".
    $age=$now->getTimestamp()-$ts;
    if($age>1800)return $unavailable;
    return array_replace($unavailable,['available'=>true,'venue_label'=>$route['venue_label']??$mic,
        'venue_key'=>$mic,'price'=>$value,'currency'=>$unit,
        'quoted_at'=>(new DateTimeImmutable('@'.$ts))->setTimezone(new DateTimeZone('UTC'))->format(DATE_ATOM)]);
}
/** Persist a positive, verifiable identity once; never store API tokens. */
function cachedRoute(PDO $db,string $id,string $isin,DateTimeImmutable $now):?array {
    $q=$db->prepare("SELECT cursor_value FROM m2_sync_checkpoints WHERE source_id=?
        AND stream_key=?");
    $q->execute([$id,'eodhd_route_v1_'.$isin]);
    $raw=$q->fetchColumn();
    if(!is_string($raw)||strlen($raw)>512)return null;
    $route=json_decode($raw,true);
    if(!is_array($route)||($route['isin']??null)!==$isin
       ||!validTicker((string)($route['ticker']??''))
       ||!preg_match('/^[A-Z0-9]{4}$/D',(string)($route['mic']??''))
       ||!preg_match('/^[A-Z]{3}$/D',(string)($route['currency']??''))
       ||!is_int($route['cached_at']??null)
       ||($route['cached_at']??0)>$now->getTimestamp()
       ||$now->getTimestamp()-$route['cached_at']>14*86400)return null;
    return $route;
}
function saveRoute(PDO $db,string $id,string $isin,array $route,DateTimeImmutable $now):void {
    if(($route['isin']??null)!==$isin||!validTicker((string)($route['ticker']??''))
       ||!preg_match('/^[A-Z0-9]{4}$/D',(string)($route['mic']??''))
       ||!preg_match('/^[A-Z]{3}$/D',(string)($route['currency']??'')))
        throw new InvalidArgumentException('eodhd_route_invalid');
    $data=$route+['cached_at'=>$now->getTimestamp()];
    $json=json_encode($data,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);
    if(strlen($json)>512)throw new InvalidArgumentException('eodhd_route_too_long');
    $q=$db->prepare("INSERT INTO m2_sync_checkpoints
        (source_id,stream_key,cursor_value,watermark_at,updated_at)
        VALUES (?,?,?,NULL,UTC_TIMESTAMP(6))
        ON DUPLICATE KEY UPDATE cursor_value=VALUES(cursor_value),updated_at=UTC_TIMESTAMP(6)");
    $q->execute([$id,'eodhd_route_v1_'.$isin,$json]);
}
/** Every attempted HTTP request consumes one credit; concurrency under M2 scheduler. */
function reserve(PDO $db,string $sourceId,array $cfg,DateTimeImmutable $now):bool {
    if(!ctype_digit($sourceId)||$sourceId==='0')throw new InvalidArgumentException('eodhd_source_id');
    require_once __DIR__.'/twelve_data.php';
    $windows=[
        'eodhd_day_budget'=>[$now->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d'),$cfg['max_daily_requests']],
        'eodhd_minute_budget'=>[$now->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i'),$cfg['max_minute_requests']]
    ];
    if($db->inTransaction())throw new InvalidArgumentException('eodhd_transaction_active');
    $db->beginTransaction();
    try {
        $next=[];
        $read=$db->prepare("SELECT cursor_value FROM m2_sync_checkpoints
            WHERE source_id=? AND stream_key=? FOR UPDATE");
        foreach($windows as $stream=>[$slot,$max]){
            $read->execute([$sourceId,$stream]);
            $v=\Mosa2\MarketInternational\TwelveData\nextBudget($read->fetchColumn(),$slot,$max);
            if($v===null){$db->rollBack();return false;}
            $next[$stream]=$v;
        }
        $upsert=$db->prepare("INSERT INTO m2_sync_checkpoints
            (source_id,stream_key,cursor_value,watermark_at,updated_at)
            VALUES (?,?,?,NULL,UTC_TIMESTAMP(6))
            ON DUPLICATE KEY UPDATE cursor_value=VALUES(cursor_value),updated_at=UTC_TIMESTAMP(6)");
        foreach($next as $stream=>$value)$upsert->execute([$sourceId,$stream,$value]);
        if(!$db->commit())throw new InvalidArgumentException('eodhd_budget_commit_failed');
        return true;
    }finally{if($db->inTransaction())$db->rollBack();}
}
