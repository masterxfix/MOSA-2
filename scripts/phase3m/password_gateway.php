<?php
declare(strict_types=1);
namespace Mosa2\Phase3M;
use function Mosa2\Phase2\{check,same,save};
require_once __DIR__.'/live_seed.php';

function tokenValid(string $token,string $cookie,string $key,int $now): bool {
    if(!hash_equals($token,$cookie))return false;$parts=explode('.',$token);
    return count($parts)===3&&ctype_digit($parts[0])&&(int)$parts[0]>=$now-600&&(int)$parts[0]<=$now
        &&preg_match('/\A[a-f0-9]{64}\z/',$parts[1])===1
        &&hash_equals(hash_hmac('sha256',$parts[0].'.'.$parts[1],$key),$parts[2]);
}
function requestAllowed(array $server,array $config,int $now): bool {
    return ($server['HTTPS']??'')==='on'&&($server['HTTP_HOST']??'')==='mosa2-test.scharwerk.de'
        &&$config['host']==='mosa2-test.scharwerk.de'&&$config['expires']>=$now
        &&($server['QUERY_STRING']??'')===''
        &&in_array($server['REQUEST_METHOD']??'',['GET','POST'],true)
        &&(($server['REQUEST_METHOD']??'')!=='POST'||(($server['HTTP_ORIGIN']??'')==='https://mosa2-test.scharwerk.de'
            &&ctype_digit((string)($server['CONTENT_LENGTH']??''))&&(int)$server['CONTENT_LENGTH']<=4096));
}
function verifySources(string $root,array $config): void {
    check(realpath($root)===$root&&!is_link($root)&&(fileperms($root)&0077)===0,'gateway_private_root');
    $project=dirname($root,2);
    foreach($config['hashes'] as $name=>$hash) {
        check(preg_match('~\A(?:scripts/(?:phase2|phase3b|phase3k|phase3l|phase3m)/[a-z_0-9]+\.(?:php|py|sql|json)|docs/database/seeds/0001_market_units_v1\.json)\z~',$name)===1,'source_path');
        $path=$project.'/'.$name;
        check(is_file($path)&&!is_link($path)&&(fileperms($path)&0077)===0&&hash_file('sha256',$path)===$hash,'source_hash');
    }
    same(hash_file('sha256',$root.'/baseline.json'),BASELINE,'baseline_source');
    plan($root);same(\Mosa2\Phase3K\totals(\Mosa2\Phase3K\schemas($root)),
        ['tables'=>17,'columns'=>186,'primary'=>17,'unique'=>10,'secondary'=>39,'foreign_keys'=>36,'checks'=>37],'offline_schema');
}
function httpProof(string $root,string $method): void {
    $headers=headers_list();$has=function($needle)use($headers){foreach($headers as $header)if(stripos($header,$needle)!==false)return true;return false;};
    $proof=['https'=>($_SERVER['HTTPS']??'')==='on','method'=>$method,'no_store'=>$has('Cache-Control: no-store'),
        'noindex'=>$has('X-Robots-Tag: noindex'),'database_connections'=>0,'database_writes'=>0];
    if($method==='GET')$proof+=['secure'=>$has('; secure'),'httponly'=>$has('; HttpOnly'),'samesite_strict'=>$has('SameSite=Strict')];
    else $proof['origin_exact']=($_SERVER['HTTP_ORIGIN']??'')==='https://mosa2-test.scharwerk.de';
    save($root.'/http-'.$method.'.json',$proof);
}
function gateway(string $root): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);$password=null;
    header('Cache-Control: no-store');header('Referrer-Policy: same-origin');header('X-Content-Type-Options: nosniff');
    header('X-Robots-Tag: noindex, nofollow');header("Content-Security-Policy: default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
    header('Content-Type: text/html; charset=utf-8');
    try {
        $config=require $root.'/access.php';check(requestAllowed($_SERVER,$config,time()),'gateway_request');verifySources($root,$config);
        check(!is_file($root.'/started.lock')&&!is_file($root.'/report.json'),'already_started');
        if($_SERVER['REQUEST_METHOD']==='POST') {
            check(is_string($_POST['csrf']??null)&&is_string($_COOKIE['M2P3MCSRF']??null)
                &&tokenValid($_POST['csrf'],$_COOKIE['M2P3MCSRF'],$config['key'],time()),'csrf');
            if(($_POST['probe']??'')==='1'&&!isset($_POST['password'])) {
                httpProof($root,'POST');save($root.'/form-proof.json',['origin_csrf_probe'=>true,'source_hashes_verified'=>true,'database_connections'=>0,'database_writes'=>0]);
                unset($_POST);header('Location: '.$config['path'],true,303);return;
            }
            check(is_file($root.'/form-proof.json'),'form_probe_missing');
            $get=json_decode(file_get_contents($root.'/http-GET.json'),true,512,JSON_THROW_ON_ERROR);
            foreach(['https','no_store','noindex','secure','httponly','samesite_strict'] as $key)check(($get[$key]??false)===true,'http_proof');
            $password=$_POST['password']??null;unset($_POST);
            check(is_string($password)&&strlen($password)>=1&&strlen($password)<=1024,'password');
            set_time_limit(240);
            try{$result=run($root,$password);}finally{
                unset($password,$_POST);
                setcookie('M2P3MCSRF','',['expires'=>1,'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
                check(preg_match('~\A/phase3m-[a-z0-9-]+/\z~D',$config['path'])===1,'entry_path');
                check($config['entry']===dirname(dirname($root,2)).'/mosa2-test.scharwerk.de'.$config['path'].'index.php','entry_guard');
                check(!is_link($config['entry']),'entry_symlink');if(is_file($config['entry']))check(unlink($config['entry']),'entry_cleanup');
            }
            echo $result['ok']?'<h1>Vier Unit-Definitionen erfolgreich eingespielt</h1><p>Readbacks und Replay erfolgreich. Keine Produktion.</p>':
                '<h1>Phase-3M-Prüflauf gestoppt</h1><p>Kein Retry. Der private Bericht enthält den tatsächlichen Transaktionsstand.</p>';return;
        }
        $nonce=time().'.'.bin2hex(random_bytes(32));$token=$nonce.'.'.hash_hmac('sha256',$nonce,$config['key']);
        setcookie('M2P3MCSRF',$token,['expires'=>min(time()+600,$config['expires']),'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
        httpProof($root,'GET');
        echo '<h1>MOSA 2 – kontrollierter Unit-Seed-Insert Phase 3M</h1>';
        if(!is_file($root.'/form-proof.json'))echo '<p>Technische Vorprüfung: noch kein Passwort eingeben.</p><form method="post"><input type="hidden" name="csrf" value="'.$token.'"><input type="hidden" name="probe" value="1"><button>Geschützten Formularweg prüfen</button></form>';
        else echo '<p>Vier freigegebene Unit-Definitionen. Zuerst vollständiger Preflight und rollbackbarer Self-FK-Test. Das Passwort wird ausschließlich für Phase 3M im laufenden Prozess verwendet und nicht gespeichert.</p><form method="post" autocomplete="off"><input type="hidden" name="csrf" value="'.$token.'"><label>Test-DB-Passwort <input type="password" name="password" autocomplete="off" required maxlength="1024"></label><button>Kontrollierten Phase-3M-Testlauf starten</button></form>';
    }catch(\Throwable $error){unset($password,$_POST);http_response_code(403);echo '<h1>Zugriff oder Prüfung gestoppt</h1><p>Keine automatische Wiederholung. Keine Zugangsdaten gespeichert.</p>';}
}
if(PHP_SAPI==='fpm-fcgi'&&!defined('MOSA2_PHASE3M_LIBRARY_ONLY'))gateway(__DIR__);
