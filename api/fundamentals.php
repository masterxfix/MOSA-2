<?php
declare(strict_types=1);
require_once __DIR__.'/fundamentals_read.php';
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
if(($_SERVER['REQUEST_METHOD']??'GET')!=='GET'){http_response_code(405);header('Allow: GET');echo '{"status":"error"}';exit;}
$isin=$_GET['isin']??null;
if($isin!==null&&(!is_string($isin)||preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D',$isin)!==1)){http_response_code(400);echo '{"status":"error","message":"Ungültige ISIN."}';exit;}
try{
    $path=dirname(__DIR__,2).'/mosa2-market-read-private/access.php';
    if(!is_file($path)||is_link($path)||(fileperms($path)&0077)!==0)throw new RuntimeException('private_config');
    $config=require $path;
    $pdo=new PDO($config['dsn'],$config['user'],$config['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_EMULATE_PREPARES=>false,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>3]);
    unset($config['password']);
    $asOf=(new DateTimeImmutable('now',new DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');
    $result=\Mosa2\FundamentalsRead\read($pdo,$isin,$asOf);$pdo=null;
    echo json_encode($result,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
}catch(Throwable $error){
    if($error instanceof RuntimeException&&$error->getMessage()==='fundamentals_not_found'){http_response_code(404);echo '{"status":"error","message":"Unternehmen nicht gefunden."}';exit;}
    http_response_code(503);echo '{"status":"error","message":"Fundamentaldaten sind gerade nicht verfügbar."}';
}
