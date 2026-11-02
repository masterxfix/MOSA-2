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
/** Only called when this script is directly requested as the HTTP endpoint. */
function main(): void {
    ini_set('display_errors','0');ini_set('log_errors','0');
    header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store, private');
    header('X-Content-Type-Options: nosniff');header('Referrer-Policy: no-referrer');
    if (($_SERVER['REQUEST_METHOD']??'')!=='POST') {http_response_code(405);header('Allow: POST');echo '{"status":"error","code":"METHOD_NOT_ALLOWED"}';return;}
    $host=$_SERVER['HTTP_HOST']??'';
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
        if (!isset(SOURCES[$provider])) fail('SOURCE_UNSUPPORTED');
        // The user explicitly starts one provider GET per button activation; short session limit prevents accidental loops.
        session_name('MOSA2_ISIN');session_set_cookie_params(['secure'=>true,'httponly'=>true,'samesite'=>'Strict','path'=>'/']);
        if (!session_start()) fail('SESSION_UNAVAILABLE');
        $key=$code.':'.$provider;$now=microtime(true);
        if ($now-($_SESSION['quote_at'][$key]??0)<3.0) {session_write_close();http_response_code(429);echo '{"status":"error","code":"TOO_FREQUENT"}';return;}
        $_SESSION['quote_at'][$key]=$now;session_write_close();
        echo json_encode(preview($code,$provider),JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);
    }catch(QuoteFailure $error){
        http_response_code(in_array($error->getMessage(),['INVALID_ISIN','INVALID_REQUEST','SOURCE_UNSUPPORTED'],true)?400:502);
        echo json_encode(['status'=>'error','code'=>$error->getMessage()]);
    }catch(Throwable){http_response_code(502);echo '{"status":"error","code":"SOURCE_UNAVAILABLE"}';}
}
if (realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__) main();
