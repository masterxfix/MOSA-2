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
if($host!=='mosa2-test.scharwerk.de'||strtolower((string)($_SERVER['SERVER_NAME']??''))!=='mosa2-test.scharwerk.de')
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
        ||($input['action']??null)!=='purge'
        ||!is_string($input['isin']??null)||!is_string($input['csrf']??null)
        ||!hash_equals($csrf,$input['csrf']))answer(403,['status'=>'error','code'=>'INVALID_ACTION']);
    $code=\Mosa2\MarketRegistry\isin($input['isin']);
    // The writer config is provisioned *privately* by the Dogado deployment, never by a web request.
    $path=dirname(__DIR__,2).'/mosa2-market-write-private/access.php';
    if(!is_file($path)||is_link($path)||(fileperms($path)&0077)!==0)
        answer(503,['status'=>'error','code'=>'WRITER_NOT_CONFIGURED']);
    $config=require $path;
    if(!is_array($config)||!isset($config['dsn'],$config['user'],$config['password']))
        answer(503,['status'=>'error','code'=>'WRITER_NOT_CONFIGURED']);
    $db=new \PDO($config['dsn'],$config['user'],$config['password'],
        [\PDO::ATTR_ERRMODE=>\PDO::ERRMODE_EXCEPTION,
         \PDO::ATTR_EMULATE_PREPARES=>false,\PDO::ATTR_DEFAULT_FETCH_MODE=>\PDO::FETCH_ASSOC,
         \PDO::ATTR_TIMEOUT=>3]);
    unset($config);
    if((string)$db->query('SELECT DATABASE()')->fetchColumn()!=='h29077_mosa2_test')
        answer(503,['status'=>'error','code'=>'WRONG_DATABASE']);
    $result=\Mosa2\MarketRegistry\purge($db,$code);
    $db=null;
    // Committed deletes are never reported as verified until an independent SELECT-only readback.
    answer(200,$result+['readback'=>'pending']);
}catch(\Throwable $e){
    answer(in_array($e->getMessage(),['COLLECTOR_BUSY','COLLECTOR_NOT_IDLE','ASSET_HAS_PENDING_WORK'],true)?409:503,
        ['status'=>'error','code'=>'PURGE_UNAVAILABLE']);
}
