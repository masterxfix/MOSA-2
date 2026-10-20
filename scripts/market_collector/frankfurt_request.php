<?php
/** Shared descriptor, copied unchanged from masterxfix/fixlab php/mosa_boerse_frankfurt.php
 * commit baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c, blob ead84889894fd3c1336e2259abb14b607446f366.
 * Public protocol constants; no account credentials. No network or database I/O. */
declare(strict_types=1);

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

$input=json_decode(stream_get_contents(STDIN),true,16,JSON_THROW_ON_ERROR);
echo json_encode(fixlabMosaFrankfurtRequest($input['isin'],'current',new DateTimeImmutable($input['instant'])),JSON_THROW_ON_ERROR);
