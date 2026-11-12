<?php
declare(strict_types=1);
namespace Mosa2\ProviderLab;

require_once __DIR__.'/market_source_engine.php';
require_once __DIR__.'/market_sources.php';

use DateTimeImmutable;
use DateTimeZone;
use DOMDocument;
use DOMElement;
use DOMXPath;
use Throwable;

/**
 * Read-only diagnostic of the five existing M2 requests to three active providers.
 * No PDO, database calls, raw payload publishing, cache or independent provider list.
 * The M2 catalog enforces the same ISIN/host/path guard as the collector.
 */
const MAX_RAW_FIELDS = 1100;
const MAX_FIELD_LENGTH = 360;

function safeText(mixed $value):string {
    if ($value===null) return '(null)';
    if (is_bool($value)) return $value?'true':'false';
    if (!is_scalar($value)) return '(verschachtelt)';
    $text=(string)$value;
    $text=trim(preg_replace('/[\x00-\x1F\x7F]/u',' ',$text)??'');
    if (strlen($text)>MAX_FIELD_LENGTH) {
        $text=substr($text,0,MAX_FIELD_LENGTH).' … [gekürzt]';
    }
    return $text;
}
function appendField(array &$out,string $path,mixed $value):void {
    if(count($out)>=MAX_RAW_FIELDS)return;
    if(preg_match('/(?:password|passwd|secret|api[_-]?key|access[_-]?token|authorization|cookie|csrf|session|credential)/i',$path))return;
    $out[]=['field'=>substr($path,0,220),'value'=>safeText($value)];
}
function flattenJson(mixed $value,string $path,array &$rows,int $depth=0):void {
    if(count($rows)>=MAX_RAW_FIELDS)return;
    if($depth>=12){appendField($rows,$path,'[Tiefe begrenzt]');return;}
    if(is_array($value)){
        if($value===[]){appendField($rows,$path,'[]');return;}
        foreach($value as $key=>$part){
            if(count($rows)>=MAX_RAW_FIELDS)break;
            if(is_string($key)&&preg_match('/(?:password|passwd|secret|api[_-]?key|access[_-]?token|authorization|cookie|csrf|session|credential)/i',$key))continue;
            $label=is_int($key)?'['.$key.']':'.'.preg_replace('/[^a-zA-Z0-9_-]/','_',(string)$key);
            flattenJson($part,$path.$label,$rows,$depth+1);
        }
        return;
    }
    appendField($rows,$path,$value);
}
function htmlInventory(string $body,string $prefix,array &$rows):void {
    if(!class_exists(DOMDocument::class))return;
    $prev=libxml_use_internal_errors(true);
    try{
        $dom=new DOMDocument('1.0','UTF-8');
        if(!$dom->loadHTML('<?xml encoding="utf-8" ?>'.$body,LIBXML_NONET|LIBXML_NOWARNING|LIBXML_NOERROR))return;
        $xp=new DOMXPath($dom);
        // L&S field/item values, plus comparable attributed fields from other providers.
        foreach($xp->query('//*[@field]')?:[] as $node){
            if(!$node instanceof DOMElement)continue;
            $field=$node->getAttribute('field');$item=$node->getAttribute('item');
            $name=$prefix.'.field.'.preg_replace('/[^a-zA-Z0-9_.-]/','_',$field);
            if($item!=='')$name.='[item='.$item.']';
            $value=trim(preg_replace('/\s+/u',' ',$node->textContent)??'');
            if($value!=='')appendField($rows,$name,$value);
        }
        // Surface *all* meaningful visible table rows, not a hard-coded field list.
        $index=0;
        foreach($xp->query('//tr')?:[] as $tr){
            $cells=[];
            foreach($tr->childNodes as $child)if($child instanceof DOMElement
                &&in_array(strtolower($child->tagName),['td','th'],true)){
                $value=trim(preg_replace('/\s+/u',' ',$child->textContent)??'');
                if($value!=='')$cells[]=$value;
            }
            if(count($cells)<2)continue;
            $index++;
            if(count($cells)===2)appendField($rows,$prefix.'.table.'.$index.'.'.$cells[0],$cells[1]);
            else foreach($cells as $i=>$value)appendField($rows,$prefix.'.table.'.$index.'.column_'.($i+1),$value);
            if(count($rows)>=MAX_RAW_FIELDS)break;
        }
        foreach($xp->query('//h1|//h2')?:[] as $headline){
            $value=trim(preg_replace('/\s+/u',' ',$headline->textContent)??'');
            if($value!=='')appendField($rows,$prefix.'.heading',$value);
        }
    } finally {libxml_clear_errors();libxml_use_internal_errors($prev);}
}
function rawInventory(array $raw,string $key):array {
    $rows=[];$body=$raw['body']??'';
    if(!is_string($body)||$body==='')return ['fields'=>[],'truncated'=>false,'bytes'=>0];
    $json=($raw['content_type']??'')==='application/json';
    if($json){
        try{$data=json_decode($body,true,32,JSON_THROW_ON_ERROR|JSON_BIGINT_AS_STRING);
            flattenJson($data,$key,$rows);
        }catch(\JsonException){/* error status remains in the request summary */ }
    }else htmlInventory($body,$key,$rows);
    return ['fields'=>$rows,'truncated'=>count($rows)>=MAX_RAW_FIELDS,'bytes'=>strlen($body)];
}
function inspect(string $input,?callable $transport=null,?DateTimeImmutable $now=null):array {
    $isin=strtoupper(trim($input));
    if(!\fixlabMosaMarketSourceLabIsinValid($isin))throw new \InvalidArgumentException('INVALID_ISIN');
    $now??=new DateTimeImmutable('now',new DateTimeZone('UTC'));
    $requestsSent=[];
    $guarded=static function(array $request)use($isin,$transport,&$requestsSent):array {
        if(!\Mosa2\MarketSources\allowed($request,$isin)) {
            return ['body'=>'','http_status'=>null,'error_code'=>'provider_not_approved'];
        }
        $requestsSent[]=$request['request_key'];
        return ($transport??'fixlabMosaMarketSourceLabLiveTransport')($request);
    };
    $lab=\fixlabRunMosaMarketSourceLab($isin,\FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER,
        $guarded,$now,'unknown',static fn(?string $clock,DateTimeImmutable $at)=>
            \fixlabMosaMarketSourceLabLsDatedQuote($clock,$at)
                ??\fixlabMosaMarketSourceLabLocalClock($clock,$at));
    $providers=[];
    foreach(\Mosa2\MarketSources\scheduled() as $key=>$definition){
        $requests=[];$fields=[];$rawFields=[];$truncated=[];
        foreach($definition['requests'] as $requestKey){
            foreach($lab['requests']??[] as $request)if(($request['request_key']??null)===$requestKey){
                $requests[]=['key'=>$requestKey,
                    'http_status'=>$request['http_status']??null,
                    'latency_ms'=>$request['latency_ms']??null,
                    'response_bytes'=>$request['response_bytes']??null,
                    'error_code'=>$request['error_code']??null];
                break;
            }
            $sourceRaw=$lab['raw_responses'][$requestKey]??[];
            $inventory=rawInventory($sourceRaw,$requestKey);
            foreach($inventory['fields'] as $row)$rawFields[]=$row;
            if($inventory['truncated'])$truncated[]=$requestKey;
        }
        foreach($lab['sources']??[] as $sourceKey=>$source){
            if(\Mosa2\MarketSources\providerOf($sourceKey)!==$key||!is_array($source))continue;
            foreach($source as $field=>$value){
                if($field==='telemetry'||is_array($value))continue;
                $fields[]=['field'=>$field,'role'=>$sourceKey,'value'=>safeText($value)];
            }
        }
        $providers[]=[
            'key'=>$key,'name'=>$definition['name'],'venue'=>$definition['venue'],
            'requests'=>$requests,'fields'=>$fields,'raw_fields'=>$rawFields,
            'raw_fields_truncated'=>$truncated,
        ];
    }
    return [
        'status'=>'ok','isin'=>$isin,'requested_at'=>$lab['requested_at']??null,
        'identity'=>[
            'name'=>$lab['instrument']['name']??null,'wkn'=>$lab['instrument']['wkn']??null,
            'instrument_id'=>$lab['instrument']['instrument_id']??null,
            'market_id'=>$lab['instrument']['market_id']??null,
            'instrument_type'=>$lab['instrument_type']??'unknown',
            'type_source'=>$lab['instrument_type_source']??null,
        ],
        'request_count'=>count($requestsSent),'providers'=>$providers,
        'storage'=>'none',
    ];
}
function respond(int $status,array $body):never {
    http_response_code($status);
    echo json_encode($body,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_INVALID_UTF8_SUBSTITUTE);
    exit;
}
function main():void {
    ini_set('display_errors','0');ini_set('log_errors','0');
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store, private');
    header('X-Content-Type-Options: nosniff');header('Referrer-Policy: no-referrer');
    $host=strtolower(explode(':',(string)($_SERVER['HTTP_HOST']??''),2)[0]);
    if(($_SERVER['HTTPS']??'')!=='on'||$host!=='mosa2-test.scharwerk.de'
        ||strtolower((string)($_SERVER['SERVER_NAME']??''))!=='mosa2-test.scharwerk.de')
        respond(403,['status'=>'error','code'=>'TESTSITE_ONLY']);
    if(($_SERVER['REQUEST_METHOD']??'')!=='POST')respond(405,['status'=>'error','code'=>'METHOD_NOT_ALLOWED']);
    if(!is_string($_SERVER['REMOTE_USER']??null)||$_SERVER['REMOTE_USER']==='')
        respond(401,['status'=>'error','code'=>'AUTH_REQUIRED']);
    if(($_SERVER['HTTP_ORIGIN']??'')!=='https://mosa2-test.scharwerk.de'
        ||($_SERVER['HTTP_X_REQUESTED_WITH']??'')!=='XMLHttpRequest'
        ||($_SERVER['HTTP_X_MOSA2_QUOTE_INTENT']??'')!=='manual'
        ||(isset($_SERVER['HTTP_SEC_FETCH_SITE'])&&!in_array($_SERVER['HTTP_SEC_FETCH_SITE'],['same-origin','none'],true))
        ||strtolower(trim(explode(';',(string)($_SERVER['CONTENT_TYPE']??''),2)[0]))!=='application/json')
        respond(403,['status'=>'error','code'=>'ORIGIN_DENIED']);
    if((int)($_SERVER['CONTENT_LENGTH']??0)>256)respond(413,['status'=>'error','code'=>'REQUEST_TOO_LARGE']);
    try{
        $input=json_decode((string)file_get_contents('php://input',false,null,0,257),
            true,4,JSON_THROW_ON_ERROR);
        if(!is_array($input)||array_keys($input)!==['isin']||!is_string($input['isin'])
            ||!\fixlabMosaMarketSourceLabIsinValid(strtoupper(trim($input['isin']))))
            respond(422,['status'=>'error','code'=>'INVALID_ISIN']);
        $isin=strtoupper(trim($input['isin']));
        session_name('M2ProviderLab');
        if(!session_start(['use_strict_mode'=>1,'use_only_cookies'=>1,'cookie_secure'=>true,
            'cookie_httponly'=>true,'cookie_samesite'=>'Strict',
            'cookie_path'=>'/api/market_provider_lab.php']))
            respond(503,['status'=>'error','code'=>'SESSION_UNAVAILABLE']);
        $at=microtime(true);
        if($at-($_SESSION['at']??0)<12){
            session_write_close();respond(429,['status'=>'error','code'=>'WAIT_BEFORE_RETRY']);
        }
        $_SESSION['at']=$at;
        session_write_close();
        respond(200,inspect($isin));
    }catch(Throwable){
        respond(502,['status'=>'error','code'=>'SOURCE_LAB_UNAVAILABLE']);
    }finally{
        if(session_status()===PHP_SESSION_ACTIVE)session_write_close();
    }
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)main();
