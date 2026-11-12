<?php
declare(strict_types=1);
namespace Mosa2\MarketInternational\TwelveData;

use DateTimeImmutable;
use DateTimeZone;
use InvalidArgumentException;
use PDO;
use Throwable;

/**
 * Optional international quote adapter inside the one M2 minute collector.
 * No additional scheduler, ISIN-specific lookup, proxy, or MOSA dependency.
 * Twelve Data /quote supports direct ISIN lookup when the ISIN add-on and
 * corresponding market-data rights are enabled on the account.
 *
 * This adapter is OFF unless a private owner-maintained file explicitly
 * confirms the entitlement and supplies bounded usage limits.
 */

/** Credentials must never be placed in a URL, log or repository. */
function authorization(string $vhostRoot):?array {
    $path=$vhostRoot.'/mosa2-market-twelvedata-private/access.php';
    if(!is_file($path))return null;
    if(is_link($path)||realpath($path)!==$path||(fileperms($path)&0077)!==0)
        throw new InvalidArgumentException('international_provider_config_permissions');
    $cfg=require $path;
    if(!is_array($cfg)||($cfg['enabled']??null)!==true
        ||($cfg['market_data_rights_confirmed']??null)!==true
        ||($cfg['isin_addon_confirmed']??null)!==true)return null;
    $key=$cfg['api_key']??null;
    $daily=$cfg['max_daily_requests']??null;
    $minute=$cfg['max_minute_requests']??null;
    if(!is_string($key)||preg_match('/^[A-Za-z0-9_-]{12,128}$/D',$key)!==1
        ||!is_int($daily)||$daily<1||$daily>100000
        ||!is_int($minute)||$minute<1||$minute>1000)
        throw new InvalidArgumentException('international_provider_config_invalid');
    return ['api_key'=>$key,'max_daily_requests'=>$daily,'max_minute_requests'=>$minute];
}
function request(string $isin,string $apiKey):array {
    if(preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D',$isin)!==1
        ||preg_match('/^[A-Za-z0-9_-]{12,128}$/D',$apiKey)!==1)
        throw new InvalidArgumentException('international_request_invalid');
    return [
        'request_key'=>'twelve_data_quote',
        'request_type'=>'Twelve Data · ISIN-Quote',
        'url'=>'https://api.twelvedata.com/quote?isin='.$isin,
        'headers'=>['Accept: application/json','Authorization: apikey '.$apiKey],
        'follow_redirects'=>false,
    ];
}
/** A missing or historical exchange timestamp is not a new live observation. */
function source(string $isin,mixed $payload,DateTimeImmutable $now):array {
    $unavailable=[
        'source_key'=>'twelve_data_quote','provider_key'=>'twelve_data',
        'provider_label'=>'Twelve Data','venue_label'=>'Internationale Börse',
        'data_type'=>'last_trade','isin'=>$isin,'available'=>false,
        'price'=>null,'currency'=>null,'quoted_at'=>null,
    ];
    if(preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D',$isin)!==1
        ||!is_array($payload)||array_is_list($payload)
        ||($payload['status']??null)==='error')return $unavailable;
    if(isset($payload['isin'])&&$payload['isin']!==$isin)return $unavailable;
    $currency=$payload['currency']??null;
    if(!is_string($currency)||preg_match('/^[A-Z]{3}$/D',$currency)!==1
        ||$currency==='XXX')return $unavailable;
    $price=$payload['close']??null;
    if(!is_string($price)&&!is_int($price)&&!is_float($price))return $unavailable;
    $price=(string)$price;
    if(preg_match('/^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,10})?$/D',$price)!==1
        ||(float)$price<=0)return $unavailable;
    $time=$payload['last_quote_at']??$payload['timestamp']??null;
    if(!is_int($time)||$time<=0)return $unavailable;
    $now=$now->setTimezone(new DateTimeZone('UTC'));
    if($time>$now->getTimestamp()+1)return $unavailable;
    $venue=$payload['mic_code']??null;
    if(!is_string($venue)||preg_match('/^[A-Z0-9]{4}$/D',$venue)!==1){
        $venue=$payload['exchange']??null;
        if(!is_string($venue)||!preg_match('/^[\p{L}\p{N} ._/-]{2,50}$/uD',$venue))
            $venue='Internationale Börse';
    }
    return array_replace($unavailable,[
        'available'=>true,'venue_label'=>$venue,'currency'=>$currency,
        'quoted_at'=>(new DateTimeImmutable('@'.$time))->setTimezone(new DateTimeZone('UTC'))->format(DATE_ATOM),
        'price'=>$price,'market_open'=>($payload['is_market_open']??null),
    ]);
}

/** Reservation counts attempted GETs even on HTTP errors; one shared M2 DB lock. */
function reserve(PDO $db,string $sourceId,array $cfg,DateTimeImmutable $now):bool {
    if(!ctype_digit($sourceId)||$sourceId==='0')throw new InvalidArgumentException('international_source_id');
    $windows=[
        'twelvedata_day_budget'=>[$now->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d'),$cfg['max_daily_requests']],
        'twelvedata_minute_budget'=>[$now->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i'),$cfg['max_minute_requests']],
    ];
    if($db->inTransaction())throw new InvalidArgumentException('international_transaction_active');
    $db->beginTransaction();
    try {
        $existing=[];
        $read=$db->prepare('SELECT cursor_value FROM m2_sync_checkpoints WHERE source_id=? AND stream_key=? FOR UPDATE');
        foreach($windows as $stream=>[$slot,$max]){
            $read->execute([$sourceId,$stream]);
            $old=$read->fetchColumn();
            $count=0;
            if(is_string($old)&&str_starts_with($old,$slot.'|')){
                $number=substr($old,strlen($slot)+1);
                if(!ctype_digit($number)||strlen($number)>7)throw new InvalidArgumentException('international_budget_corrupt');
                $count=(int)$number;
            }
            if($count>=$max){$db->rollBack();return false;}
            $existing[$stream]=[$slot,$count+1];
        }
        $upsert=$db->prepare("INSERT INTO m2_sync_checkpoints
            (source_id,stream_key,cursor_value,watermark_at,updated_at)
            VALUES (?,?,?,NULL,UTC_TIMESTAMP(6))
            ON DUPLICATE KEY UPDATE cursor_value=VALUES(cursor_value),updated_at=UTC_TIMESTAMP(6)");
        foreach($existing as $stream=>[$slot,$count])
            $upsert->execute([$sourceId,$stream,$slot.'|'.$count]);
        if(!$db->commit())throw new InvalidArgumentException('international_budget_commit_failed');
        return true;
    }finally{if($db->inTransaction())$db->rollBack();}
}
