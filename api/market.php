<?php
declare(strict_types=1);
require_once __DIR__.'/read_model.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
if(($_SERVER['REQUEST_METHOD']??'GET')!=='GET'){http_response_code(405);header('Allow: GET');echo '{"status":"error"}';exit;}
try{
    // Fixed subscription-private location, outside every public document root.
    $path=dirname(__DIR__,2).'/mosa2-market-read-private/access.php';
    if(!is_file($path)||is_link($path)||(fileperms($path)&0077)!==0)throw new RuntimeException('private_config');
    $config=require $path;
    $pdo=new PDO($config['dsn'],$config['user'],$config['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>3]);
    unset($config['password']);
    $result=\Mosa2\MarketRead\read($pdo,$config,(new DateTimeImmutable('now',new DateTimeZone('UTC')))->format('Y-m-d H:i:s.u'));
    $pdo=null;echo json_encode($result,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);
}catch(Throwable $error){http_response_code(503);echo '{"status":"error","message":"Marktdaten sind gerade nicht verfügbar."}';}
