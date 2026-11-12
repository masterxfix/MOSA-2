<?php
declare(strict_types=1);
namespace Mosa2\MarketRegistryApi;

require_once __DIR__.'/market_registry_model.php';
ini_set('display_errors','0');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');

function answer(int $code,array $body): never {
    http_response_code($code);
    echo json_encode($body,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);
    exit;
}
$host=strtolower(explode(':',(string)($_SERVER['HTTP_HOST']??''),2)[0]);
if(($_SERVER['HTTPS']??'')!=='on'||$host!=='mosa2-test.scharwerk.de'||strtolower((string)($_SERVER['SERVER_NAME']??''))!=='mosa2-test.scharwerk.de')
    answer(403,['status'=>'error','code'=>'TESTSITE_ONLY']);
$method=$_SERVER['REQUEST_METHOD']??'';
if(!in_array($method,['GET','POST'],true)){header('Allow: GET, POST');answer(405,['status'=>'error']);}
$user=$_SERVER['REMOTE_USER']??null;
if(!is_string($user)||$user==='')answer(401,['status'=>'error','code'=>'AUTH_REQUIRED']);
session_name('M2MarketRegistry');
if(!session_start(['use_strict_mode'=>1,'use_only_cookies'=>1,'cookie_secure'=>true,
    'cookie_httponly'=>true,'cookie_samesite'=>'Strict','cookie_path'=>'/api/market_registry.php']))
    answer(503,['status'=>'error','code'=>'SESSION_UNAVAILABLE']);
$digest=hash('sha256',$user);
if(($_SESSION['owner']??null)!==$digest){
    if(!session_regenerate_id(true))answer(503,['status'=>'error','code'=>'SESSION_UNAVAILABLE']);
    $_SESSION=['owner'=>$digest,'csrf'=>bin2hex(random_bytes(32))];
}
$csrf=$_SESSION['csrf'];
session_write_close();
if($method==='GET')answer(200,['status'=>'ok','csrf'=>$csrf]);
if(($_SERVER['HTTP_ORIGIN']??'')!=='https://mosa2-test.scharwerk.de'
    ||($_SERVER['HTTP_X_REQUESTED_WITH']??'')!=='XMLHttpRequest'
    ||strtolower(trim(explode(';',(string)($_SERVER['CONTENT_TYPE']??''),2)[0]))!=='application/json')
    answer(403,['status'=>'error','code'=>'ORIGIN_INVALID']);
if((int)($_SERVER['CONTENT_LENGTH']??0)>2048)answer(413,['status'=>'error','code'=>'REQUEST_TOO_LARGE']);
$raw=file_get_contents('php://input',false,null,0,2049);
try {
    if(!is_string($raw)||strlen($raw)>2048)answer(413,['status'=>'error','code'=>'REQUEST_TOO_LARGE']);
    $input=json_decode($raw,true,8,JSON_THROW_ON_ERROR);
    if(!is_array($input)||array_keys($input)!==['action','isin','csrf']
        ||!in_array($input['action']??null,['register','purge','purge_all'],true)
        ||!is_string($input['isin']??null)||!is_string($input['csrf']??null)
        ||!hash_equals($csrf,$input['csrf']))answer(403,['status'=>'error','code'=>'INVALID_ACTION']);
    $action=$input['action'];
    $code=$action==='purge_all'?'':\Mosa2\MarketRegistry\isin($input['isin']);
    if($action==='purge_all' && $input['isin']!=='ALLE TEST-MARKTDATEN')
        answer(422,['status'=>'error','code'=>'CONFIRMATION_REQUIRED']);
    $root=dirname(__DIR__,2);
    $db=\Mosa2\MarketRegistry\connection('write',$root);
    $result=match($action){
        'register'=>\Mosa2\MarketRegistry\register($db,$code),
        'purge'=>\Mosa2\MarketRegistry\purge($db,$code),
        'purge_all'=>\Mosa2\MarketRegistry\purgeMarketData($db),
    };
    $db=null;
    try {
        $verified=\Mosa2\MarketRegistry\verify(\Mosa2\MarketRegistry\connection('read',$root),$action,$code,$result);
    } catch(\Throwable) {
        $verified=false;
    }
    answer(200,$result+['readback'=>$verified?'passed':'pending']);
}catch(\Throwable $error){
    $reason=$error->getMessage();
    $code=match($reason){
        'INVALID_ISIN'=>422,
        'COLLECTOR_BUSY','COLLECTOR_NOT_IDLE','ASSET_HAS_PENDING_WORK','INACTIVE_IDENTITY'=>409,
        default=>503,
    };
    answer($code,['status'=>'error','code'=>$code===503?'REGISTRY_UNAVAILABLE':$reason]);
}
