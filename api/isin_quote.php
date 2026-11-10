<?php
declare(strict_types=1);
namespace Mosa2\IsinQuote;

use DateTimeImmutable;
use DateTimeZone;
use PDO;
use RuntimeException;
use Throwable;

/** Explicit, provider-neutral on-demand preview; no database/collector writes. */
const SOURCES = ['tradegate' => 'Tradegate BSX · Mid', 'frankfurt' => 'Börse Frankfurt · XFRA · Last'];
const MAX_BYTES = 2000000;

final class QuoteFailure extends RuntimeException {}
function fail(string $code): never { throw new QuoteFailure($code); }
function isin(string $input): string {
    $value = strtoupper(trim($input));
    if (!preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D', $value)) fail('INVALID_ISIN');
    return $value;
}
function decimal(string $input): string {
    if (!preg_match('/^[0-9.,\s\x{00A0}\x{202F}\x{2009}]+$/u', trim($input))) fail('INVALID_PRICE');
    $value = preg_replace('/[\x{00A0}\x{202F}\x{2009}\s]/u', '', trim($input));
    $value = preg_replace('/[^0-9,.]/', '', $value);
    if ($value === '' || strlen($value) > 40) fail('INVALID_PRICE');
    if (str_contains($value, ',') && str_contains($value, '.')) {
        $value = strrpos($value, ',') > strrpos($value, '.') ? str_replace(',', '.', str_replace('.', '', $value)) : str_replace(',', '', $value);
    } elseif (str_contains($value, ',')) $value = str_replace(',', '.', $value);
    if (!preg_match('/^[0-9]{1,18}(?:\.[0-9]{1,12})?$/D', $value)) fail('INVALID_PRICE');
    [$integer, $fraction] = array_pad(explode('.', $value, 2), 2, '');
    $integer = ltrim($integer, '0');
    if ($integer === '') $integer = '0';
    if ($integer === '0' && (int)($fraction ?: '0') === 0) fail('INVALID_PRICE');
    $fraction = rtrim($fraction, '0');
    return $integer . ($fraction === '' ? '' : '.' . $fraction);
}
/** Exact decimal midpoint without float rounding, bcmath, or binary conversion. */
function midpoint(string $a, string $b): string {
    $a = decimal($a);$b = decimal($b);
    [$ai,$af] = array_pad(explode('.', $a, 2), 2, '');
    [$bi,$bf] = array_pad(explode('.', $b, 2), 2, '');
    $scale = max(strlen($af), strlen($bf));
    $x = $ai . str_pad($af, $scale, '0');
    $y = $bi . str_pad($bf, $scale, '0');
    $width = max(strlen($x), strlen($y));
    $x = str_pad($x, $width, '0', STR_PAD_LEFT);
    $y = str_pad($y, $width, '0', STR_PAD_LEFT);
    $carry = 0;$sum = '';
    for ($i = $width-1; $i >= 0; --$i) {
        $digit = (int)$x[$i] + (int)$y[$i] + $carry;
        $sum = ($digit % 10) . $sum;$carry = intdiv($digit, 10);
    }
    if ($carry) $sum = (string)$carry . $sum;
    $half = '';$remainder = 0;
    foreach (str_split($sum) as $digit) {
        $value = $remainder * 10 + (int)$digit;
        $half .= (string)intdiv($value,2);$remainder = $value % 2;
    }
    $half = str_pad($half, $scale+1, '0', STR_PAD_LEFT);
    $int = substr($half,0,strlen($half)-$scale);
    $frac = $scale ? substr($half,-$scale) : '';
    if ($remainder) $frac .= '5';
    $frac=rtrim($frac,'0');
    return (ltrim($int,'0') ?: '0') . ($frac === '' ? '' : '.' . $frac);
}
function tdText(string $cell): string {
    return trim(preg_replace('/\s+/u', ' ', html_entity_decode(strip_tags($cell), ENT_QUOTES | ENT_HTML5, 'UTF-8')));
}
function rows(string $html): array {
    preg_match_all('~<tr\b[^>]*>(.*?)</tr\s*>~si', $html, $matches);
    if (count($matches[1]) > 2000) fail('INVALID_SOURCE');
    $rows=[];
    foreach ($matches[1] as $htmlRow) {
        preg_match_all('~<t[dh]\b[^>]*>(.*?)</t[dh]\s*>~si', $htmlRow, $cells);
        $rows[] = array_map(__NAMESPACE__.'\\tdText', $cells[1]);
    }
    return $rows;
}
function column(array $rows,string $label): ?string {
    foreach ($rows as $index=>$row) {
        $column = array_search($label,$row,true);
        if ($column !== false) return $rows[$index+1][$column] ?? null;
    }
    return null;
}
function rowValue(array $rows,string $label): ?string {
    foreach ($rows as $row) if (count($row)>1 && strcasecmp($row[0],$label)===0) return $row[1];
    return null;
}
function timeUtc(DateTimeImmutable $instant): string {
    if ($instant->getTimestamp() > time()+300) fail('FUTURE_MARKET_TIME');
    return $instant->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z');
}
function tradegate(string $html,string $code): array {
    if (strlen($html) > MAX_BYTES) fail('INVALID_SOURCE');
    $table = rows($html);
    // Same currency evidence as the qualified TradegateQuoteV1 adapter.
    $text=tdText(preg_replace('~<[^>]+>~',' ',$html));
    $currency=strtoupper((string)column($table,'Handelswährung'));
    if(!preg_match('/^[A-Z]{3}$/D',$currency))$currency=preg_match('/\bKurse in ([A-Z]{3})\b/u',$text,$unit)?$unit[1]:'';
    if (column($table,'ISIN') !== $code || $currency !== 'EUR') fail('NO_MATCHING_INSTRUMENT');
    $bid = rowValue($table,'Bid');$ask = rowValue($table,'Ask');
    if ($bid===null || $ask===null) fail('QUOTE_MISSING');
    $bid = decimal($bid);$ask = decimal($ask);
    $pair = static function(string $v): array { [$whole,$fraction] = array_pad(explode('.',$v,2),2,'');return [$whole,$fraction]; };
    [$ai,$af]=$pair($bid);[$bi,$bf]=$pair($ask);
    $scale=max(strlen($af),strlen($bf));
    $left=ltrim($ai.str_pad($af,$scale,'0'),'0') ?: '0';
    $right=ltrim($bi.str_pad($bf,$scale,'0'),'0') ?: '0';
    if (strlen($left)>strlen($right) || (strlen($left)===strlen($right) && strcmp($left,$right)>0)) fail('CROSSED_QUOTE');
    if (!preg_match('/Letzte\s+Aktualisierung:\s*(\d{2}\.\d{2}\.\d{4})\s*@\s*(\d{2}:\d{2}:\d{2})/ui',$text,$when)) fail('TIME_MISSING');
    $stamp=$when[1].' '.$when[2];
    $date=DateTimeImmutable::createFromFormat('!d.m.Y H:i:s',$stamp,new DateTimeZone('Europe/Berlin'));
    if (!$date || $date->format('d.m.Y H:i:s')!==$stamp) fail('INVALID_MARKET_TIME');
    $name=column($table,'Name');
    if ($name===null && preg_match_all('~<h[12]\b[^>]*>(.*?)</h[12]>~si',$html,$titles)) {
        foreach ($titles[1] as $heading) {
            $candidate = tdText($heading);
            if ($candidate!=='' && mbLength($candidate)<=160 && !preg_match('/^(Tradegate.*|Kurssuche|Aktien|Information)$/ui',$candidate)) { $name=$candidate; break; }
        }
    }
    return ['name'=>$name,'price'=>midpoint($bid,$ask),'bid'=>$bid,'ask'=>$ask,'currency'=>'EUR',
        'quote_type'=>'Mid (Geld/Brief)','market_at'=>timeUtc($date),'venue'=>'Tradegate BSX'];
}
function mbLength(string $value): int { return function_exists('mb_strlen') ? mb_strlen($value,'UTF-8') : strlen($value); }
function frankfurt(string $body,string $code): array {
    if (strlen($body)>MAX_BYTES) fail('INVALID_SOURCE');
    try{$data=json_decode($body,true,24,JSON_THROW_ON_ERROR);}catch(\JsonException){fail('SOURCE_INVALID_JSON');}
    if (!is_array($data) || ($data['isin']??null)!==$code || ($data['mic']??null)!=='XFRA' || ($data['currency']['originalValue']??null)!=='EUR') fail('NO_MATCHING_INSTRUMENT');
    $number=$data['lastPrice']??null;
    if (!is_int($number)&&!is_float($number)) fail('QUOTE_MISSING');
    $price=decimal((string)$number);
    $stamp=$data['timestampLastPrice']??null;
    if (!is_string($stamp) || !preg_match('/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)$/D',$stamp)) fail('TIME_MISSING');
    try{$date=new DateTimeImmutable($stamp);}catch(Throwable){fail('INVALID_MARKET_TIME');}
    $name=$data['name']??$data['instrumentName']??null;
    if (!is_string($name)||trim($name)===''||mbLength($name)>160)$name=null;
    return ['name'=>$name,'price'=>$price,'bid'=>null,'ask'=>null,'currency'=>'EUR',
        'quote_type'=>'Letzter Kurs','market_at'=>timeUtc($date),'venue'=>'Börse Frankfurt · XFRA'];
}
/** Existing MOSA Frankfurt descriptor constants, identical request semantics. */
function descriptor(string $code,string $provider): array {
    if ($provider==='tradegate') return ['url'=>'https://www.tradegatebsx.com/orderbuch.php?isin='.$code,
        'headers'=>['Accept: text/html,application/xhtml+xml','Referer: https://www.tradegatebsx.com/',
            'User-Agent: FixLab-MOSA-Market-Source-Lab/2.0']];
    if ($provider==='frankfurt') {
        $local=new DateTimeImmutable('now',new DateTimeZone('Europe/Berlin'));
        $date=$local->format('Y-m-d\TH:i:sP');
        $url='https://api.live.deutsche-boerse.com/v1/data/price_information/single?isin='.$code.'&mic=XFRA';
        return ['url'=>$url,'headers'=>['Accept: application/json','Client-Date: '.$date,
            'X-Client-TraceId: '.md5($date.$url.'af5a8d16eb5dc49f8a72b26fd9185475c7a'),
            'X-Security: '.md5($local->format('YmdHi')),
            'User-Agent: FixLab-MOSA-Frankfurt/1.0']];
    }
    fail('SOURCE_UNSUPPORTED');
}
/** Fixed HTTPS hosts only, no redirect, proxy, cookies, retry or authentication. */
function fetch(string $url,array $headers): string {
    if (!str_starts_with($url,'https://www.tradegatebsx.com/orderbuch.php?isin=') &&
        !str_starts_with($url,'https://api.live.deutsche-boerse.com/v1/data/price_information/single?isin=')) fail('SOURCE_UNSUPPORTED');
    $context=stream_context_create(['http'=>['method'=>'GET','timeout'=>8,'ignore_errors'=>true,
        'follow_location'=>0,'max_redirects'=>0,'header'=>implode("\r\n",$headers)],
        'ssl'=>['verify_peer'=>true,'verify_peer_name'=>true]]);
    $stream=@fopen($url,'rb',false,$context);
    if (!$stream) fail('SOURCE_UNAVAILABLE');
    try{
        $meta=stream_get_meta_data($stream);
        $responseHeaders=$meta['wrapper_data']??[];
        $status=preg_match('/^HTTP\/\S+\s+(\d{3})\b/',(string)($responseHeaders[0]??''),$m)?(int)$m[1]:0;
        if ($status!==200) fail('SOURCE_HTTP_'.$status);
        $body=stream_get_contents($stream,MAX_BYTES+1);
        if(stream_get_meta_data($stream)['timed_out']??false)fail('SOURCE_TIMEOUT');
        if (!is_string($body) || strlen($body)>MAX_BYTES) fail('SOURCE_TOO_LARGE');
        return $body;
    }finally{fclose($stream);}
}
/** Optional read-only name resolution for already registered assets. */
function registeredName(string $code): ?string {
    try{
        $path=dirname(__DIR__,2).'/mosa2-market-read-private/access.php';
        if (!is_file($path)||is_link($path)||(fileperms($path)&0077)!==0) return null;
        $config=require $path;
        $db=new PDO($config['dsn'],$config['user'],$config['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_EMULATE_PREPARES=>false,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>2]);
        $stmt=$db->prepare("SELECT a.display_name FROM m2_asset_identifiers i JOIN m2_assets a ON a.entity_id=i.asset_id WHERE i.identifier_type='isin' AND i.normalized_value=? AND i.scope_key='' AND i.is_primary=1 AND i.valid_to IS NULL LIMIT 2");
        $stmt->execute([$code]);$rows=$stmt->fetchAll();$db=null;
        return count($rows)===1 ? $rows[0]['display_name'] : null;
    }catch(Throwable){return null;}
}
function preview(string $code,string $provider,?callable $transport=null): array {
    $code=isin($code);
    if (!isset(SOURCES[$provider])) fail('SOURCE_UNSUPPORTED');
    $spec=descriptor($code,$provider);
    $body=($transport??__NAMESPACE__.'\\fetch')($spec['url'],$spec['headers']);
    $result=$provider==='tradegate'?tradegate($body,$code):frankfurt($body,$code);
    $name=registeredName($code)??$result['name']??null;
    $observed=(new DateTimeImmutable('now',new DateTimeZone('UTC')))->format('Y-m-d\TH:i:s\Z');
    $age=max(0,time()-(new DateTimeImmutable($result['market_at']))->getTimestamp());
    return ['status'=>'ok','isin'=>$code,'name'=>$name,'provider'=>$provider,'source'=>SOURCES[$provider],
        'url'=>$spec['url'],'captured_at'=>$observed,'age_seconds'=>$age,'stale'=>$age>1800]+$result;
}

/** Only the four established MOSA source providers and their documented endpoints. */
function sourceAllowed(array $request,string $code): bool {
    $key=$request['request_key']??null;$url=$request['url']??null;
    if (!is_string($key)||!is_string($url)||strlen($url)>500)return false;
    $parts=parse_url($url);
    if (!is_array($parts)||($parts['scheme']??null)!=='https'||(isset($parts['user'])||isset($parts['pass']))
        ||isset($parts['fragment'])||!in_array($parts['port']??443,[443],true))return false;
    $host=$parts['host']??'';$path=$parts['path']??'';
    return match($key) {
        'lang_schwarz_search' => $url==='https://www.ls-tc.de/_rpc/json/.lstc/instrument/search/main?q='.$code.'&localeId=2',
        'lang_schwarz_page' => $host==='www.ls-tc.de' && preg_match('~^/de/(aktie|etf)/[1-9][0-9]{0,18}$~D',$path)===1 && !isset($parts['query']),
        'tradegate_quote' => $url==='https://www.tradegatebsx.com/orderbuch.php?isin='.$code,
        'tradegate_trade' => $url==='https://www.tradegatebsx.com/orderbuch_umsaetze.php?isin='.$code,
        'boerse_frankfurt_trade' => $url==='https://api.live.deutsche-boerse.com/v1/data/price_information/single?isin='.$code.'&mic=XFRA',
        'yahoo_home_search' => $url==='https://query1.finance.yahoo.com/v1/finance/search?q='.$code.'&quotesCount=10&newsCount=0',
        'yahoo_home_market' => $host==='query1.finance.yahoo.com'
            && preg_match('~^/v8/finance/chart/[a-zA-Z0-9._%=-]{1,128}$~D',$path)===1
            && ($parts['query']??null)==='range=1d&interval=1d&includePrePost=false',
        default => false,
    };
}
/** A safe observable wrapper around the proven read-only MOSA source transport. */
function sourceTransport(array $request,string $code,callable $emit,?callable $transport=null): array {
    $key=is_string($request['request_key']??null)?$request['request_key']:'unknown';
    $title=is_string($request['request_type']??null)?$request['request_type']:$key;
    $emit(['event'=>'request','stage'=>'started','request_key'=>$key,'name'=>$title]);
    if (!sourceAllowed($request,$code)){
        $reply=['body'=>'','http_status'=>null,'latency_ms'=>0,'error_code'=>'source_rejected'];
    } elseif ($transport===null && str_starts_with($key,'yahoo_') && getenv('MOSA2_YAHOO_AUTOMATION_AUTHORIZED')!=='1') {
        $reply=['body'=>'','http_status'=>null,'latency_ms'=>0,'error_code'=>'provider_access_unconfirmed'];
    } elseif ($transport===null && ($_SESSION['quote_provider_retry_at'][parse_url($request['url'],PHP_URL_HOST)]??0)>time()) {
        $reply=['body'=>'','http_status'=>null,'latency_ms'=>0,'error_code'=>'provider_cooldown'];
    } else {
        // Seven descriptors mean at most seven external GETs, including L&S.
        // Do not silently spend extra requests or leave the approved host via redirects.
        $request['follow_redirects']=false;
        try{$reply=($transport??'fixlabMosaMarketSourceLabLiveTransport')($request);}
        catch(Throwable){$reply=['body'=>'','http_status'=>null,'latency_ms'=>null,'error_code'=>'transport_exception'];}
        if(!is_array($reply))$reply=['body'=>'','http_status'=>null,'latency_ms'=>null,'error_code'=>'transport_invalid'];
    }
    if ($transport===null && session_status()===PHP_SESSION_ACTIVE && ($reply['http_status']??null)===429) {
        // Stop requests to this host for the rest of the comparison and subsequent cycles.
        $retry=$reply['retry_after']??null;
        $now=time();
        $until=is_string($retry)&&ctype_digit($retry)?$now+min((float)$retry,31536000):
            (is_string($retry)?strtotime($retry):false);
        $_SESSION['quote_provider_retry_at'][parse_url($request['url'],PHP_URL_HOST)]=max($now+60,$until?:0);
    }
    $emit(['event'=>'request','stage'=>'finished','request_key'=>$key,'name'=>$title,
        'http_status'=>is_int($reply['http_status']??null)?$reply['http_status']:null,
        'duration_ms'=>is_int($reply['latency_ms']??null)?$reply['latency_ms']:null,
        'code'=>is_string($reply['error_code']??null)?$reply['error_code']:null]);
    return $reply;
}
function asPrice(mixed $price): ?string {
    if (!is_float($price)&&!is_int($price))return null;
    if (!is_finite((float)$price)||$price<=0||$price>=1000000000000000)return null;
    $value=rtrim(rtrim(sprintf('%.10f',(float)$price),'0'),'.');
    if ($value===''||!preg_match('/^[0-9]+(?:\.[0-9]+)?$/D',$value))return null;
    return $value;
}
function sourceRecord(string $key,array $source,string $code,string $captured): array {
    $label=is_string($source['provider_label']??null)?$source['provider_label']:$key;
    $venue=is_string($source['venue_label']??null)?$source['venue_label']:'—';
    $kind=match($key){
        'lang_schwarz_quote','tradegate_quote'=>'Mid (Geld/Brief)',
        'lang_schwarz_trade','tradegate_trade','boerse_frankfurt_trade'=>'Letzter Handel',
        'yahoo_home_market'=>'Heimatmarktkurs',
        default=>'Kurs'
    };
    $base=['provider'=>$key,'source'=>$label.' · '.$venue,'venue'=>$venue,'quote_type'=>$kind,
        'isin'=>$code,'captured_at'=>$captured];
    $price=asPrice($source['price']??null);
    $currency=$source['currency']??null;
    $quoted=$source['quoted_at']??null;
    if(($source['available']??false)!==true||$price===null
        ||!is_string($currency)||preg_match('/^[A-Z]{3}$/D',$currency)!==1
        ||!is_string($quoted)){
        $error=$source['error_code']??(($source['available']??false)===true?'invalid_quote':'quote_unavailable');
        if(!is_string($error)||preg_match('/^[a-z0-9_]{1,90}$/D',$error)!==1)$error='quote_unavailable';
        $missing=preg_match('/(?:not_delivered|not_found|_missing|^quote_unavailable$|^provider_access_unconfirmed$)/D',$error)===1;
        return $base+['status'=>$missing?'unavailable':'error','code'=>$error];
    }
    try{
        $market=new DateTimeImmutable($quoted);
        $received=new DateTimeImmutable($captured);
        if($market>$received)return $base+['status'=>'error','code'=>'market_time_future'];
        $stamp=$market->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s.u\Z');
    }catch(Throwable){return $base+['status'=>'error','code'=>'market_time_invalid'];}
    $age=$received->getTimestamp()-$market->getTimestamp();
    return $base+['status'=>'ok','price'=>$price,'currency'=>$currency==='GBX'?'GBP':$currency,'unit'=>$currency,'market_at'=>$stamp,
        'age_seconds'=>$age,'stale'=>$age>1800,
        'bid'=>asPrice($source['bid']??null),'ask'=>asPrice($source['ask']??null),
        'symbol'=>is_string($source['symbol']??null)?$source['symbol']:null];
}
/** Executes the unchanged MOSA core once; never writes to the database. */
function previewAll(string $input,callable $emit,?callable $transport=null,?DateTimeImmutable $now=null): array {
    $code=isin($input);
    require_once __DIR__.'/market_source_engine.php';
    $received=[];
    $lab=\fixlabRunMosaMarketSourceLab($code,\FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER,
        static function(array $request)use($code,$emit,$transport,$now,&$received):array{
            $reply=sourceTransport($request,$code,$emit,$transport);
            $received[$request['request_key']]=($now??new DateTimeImmutable())->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s.u\Z');
            return $reply;
        },$now);
    $captured=($now??new DateTimeImmutable())->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s.u\Z');
    $items=[];$success=0;
    foreach(['lang_schwarz_quote','lang_schwarz_trade','tradegate_quote','tradegate_trade',
        'boerse_frankfurt_trade','yahoo_home_market'] as $key){
        $source=$lab['sources'][$key]??[];
        $requestKey=match($key){
            'lang_schwarz_quote','lang_schwarz_trade'=>isset($received['lang_schwarz_page'])?'lang_schwarz_page':'lang_schwarz_search',
            'yahoo_home_market'=>isset($received[$key])?$key:'yahoo_home_search',
            default=>$key,
        };
        $result=sourceRecord($key,is_array($source)?$source:[],$code,$received[$requestKey]??$captured);
        if($result['status']==='ok')$success++;
        $items[]=$result;
    }
    $name=registeredName($code)??($lab['instrument']['name']??null);
    if (!is_string($name)||trim($name)===''||mbLength($name)>160)$name=null;
    return ['status'=>$success>0?'ok':'error','isin'=>$code,'name'=>$name,
        'instrument_type'=>in_array($lab['instrument_type']??null,['stock','etf','fund','other'],true)?$lab['instrument_type']:'unknown',
        'instrument_type_source'=>is_string($lab['instrument_type_source']??null)?$lab['instrument_type_source']:null,
        'instrument_type_verified_at'=>is_string($lab['instrument_type_verified_at']??null)?$lab['instrument_type_verified_at']:null,
        'captured_at'=>$captured,'success_count'=>$success,'records'=>$items,'request_count'=>count($lab['requests']??[])];
}
function emitStream(array $event): void {
    echo json_encode($event,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)."\n";
    if(function_exists('ob_flush')&&ob_get_level()>0)@ob_flush();
    flush();
}

/** Only called when this script is directly requested as the HTTP endpoint. */
function main(): void {
    ini_set('display_errors','0');ini_set('log_errors','0');
    header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store, private');
    header('X-Content-Type-Options: nosniff');header('Referrer-Policy: no-referrer');
    if (($_SERVER['REQUEST_METHOD']??'')!=='POST') {http_response_code(405);header('Allow: POST');echo '{"status":"error","code":"METHOD_NOT_ALLOWED"}';return;}
    $host=$_SERVER['HTTP_HOST']??'';
    // Older open tabs must not keep polling during the M2 testsite reset hold.
    $testsite=strtolower($_SERVER['SERVER_NAME']??'')==='mosa2-test.scharwerk.de' ||
        strtolower(explode(':',$host,2)[0])==='mosa2-test.scharwerk.de';
    if ($testsite && ($_SERVER['HTTP_X_MOSA2_QUOTE_INTENT']??'')!=='manual') {
        http_response_code(403);echo '{"status":"error","code":"MANUAL_QUOTE_REQUIRED"}';return;
    }
    if ($host==='' || (isset($_SERVER['HTTP_ORIGIN']) && $_SERVER['HTTP_ORIGIN']!=='https://'.$host)
        || (isset($_SERVER['HTTP_SEC_FETCH_SITE'])&&!in_array($_SERVER['HTTP_SEC_FETCH_SITE'],['same-origin','none'],true))
        || ($_SERVER['HTTP_X_REQUESTED_WITH']??'')!=='XMLHttpRequest'
        || !str_starts_with(strtolower($_SERVER['CONTENT_TYPE']??''),'application/json')) {
        http_response_code(403);echo '{"status":"error","code":"ORIGIN_DENIED"}';return;
    }
    try{
        $wire=file_get_contents('php://input',false,null,0,256);
        $payload=json_decode((string)$wire,true,4,JSON_THROW_ON_ERROR);
        if (!is_array($payload)||array_keys($payload)!==['isin','provider']||!is_string($payload['isin'])||!is_string($payload['provider'])) fail('INVALID_REQUEST');
        $code=isin($payload['isin']);$provider=$payload['provider'];
        if (!isset(SOURCES[$provider])&&$provider!=='all') fail('SOURCE_UNSUPPORTED');
        // The user explicitly starts one provider GET per button activation; short session limit prevents accidental loops.
        session_name('MOSA2_ISIN');session_set_cookie_params(['secure'=>true,'httponly'=>true,'samesite'=>'Strict','path'=>'/']);
        if (!session_start()) fail('SESSION_UNAVAILABLE');
        $key=$code.':'.$provider;$now=microtime(true);
        if ($now-($_SESSION['quote_at'][$key]??0)<3.0) {session_write_close();http_response_code(429);echo '{"status":"error","code":"TOO_FREQUENT"}';return;}
        $_SESSION['quote_at']=array_filter($_SESSION['quote_at']??[],static fn($stamp)=>$now-$stamp<3.0);
        $_SESSION['quote_at'][$key]=$now; // Hold the session lock across the sequential comparison.
        if($provider==='all'){
            header('Content-Type: application/x-ndjson; charset=utf-8');
            header('X-Accel-Buffering: no');
            emitStream(['event'=>'started','isin'=>$code]);
            try{
                $result=previewAll($code,__NAMESPACE__.'\\emitStream');
                emitStream(['event'=>'result','data'=>$result]);
            }catch(Throwable){emitStream(['event'=>'failure','code'=>'SOURCE_COMPARISON_FAILED']);}
            return;
        }
        echo json_encode(preview($code,$provider),JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);
    }catch(QuoteFailure $error){
        http_response_code(in_array($error->getMessage(),['INVALID_ISIN','INVALID_REQUEST','SOURCE_UNSUPPORTED'],true)?400:502);
        echo json_encode(['status'=>'error','code'=>$error->getMessage()]);
    }catch(Throwable){http_response_code(502);echo '{"status":"error","code":"SOURCE_UNAVAILABLE"}';}
    finally{if(session_status()===PHP_SESSION_ACTIVE)session_write_close();}
}
if (realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__) main();
