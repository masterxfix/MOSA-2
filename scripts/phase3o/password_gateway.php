<?php
declare(strict_types=1);
namespace Mosa2\Phase3O;
use function Mosa2\Phase2\{check,same,save};
require_once __DIR__.'/capability.php';
defined('MOSA2_PHASE3M_LIBRARY_ONLY')||define('MOSA2_PHASE3M_LIBRARY_ONLY',true);
require_once __DIR__.'/../phase3m/password_gateway.php';

function gateway(string $root): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);$password=null;
    header('Cache-Control: no-store');header('Referrer-Policy: same-origin');header('X-Content-Type-Options: nosniff');
    header('X-Robots-Tag: noindex, nofollow');header("Content-Security-Policy: default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
    header('Content-Type: text/html; charset=utf-8');
    try {
        $config=require $root.'/access.php';
        check(\Mosa2\Phase3M\requestAllowed($_SERVER,$config,time()),'gateway_request');requireCapability($root,$config);
        check(!is_file($root.'/started.lock')&&!is_file($root.'/report.json'),'already_started');
        if($_SERVER['REQUEST_METHOD']==='POST'){
            check(is_string($_POST['csrf']??null)&&is_string($_COOKIE['M2P3OCSRF']??null)
                &&\Mosa2\Phase3M\tokenValid($_POST['csrf'],$_COOKIE['M2P3OCSRF'],$config['key'],time()),'csrf');
            if(($_POST['probe']??'')==='1'&&!isset($_POST['password'])){
                \Mosa2\Phase3M\httpProof($root,'POST');
                save($root.'/form-proof.json',['origin_csrf_probe'=>true,'source_hashes_verified'=>true,'database_connections'=>0,'database_writes'=>0,'writer_runs'=>0]);
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
                setcookie('M2P3OCSRF','',['expires'=>1,'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
                check($config['path']==='/phase3o-a1579b/','entry_path');
                check(str_ends_with($config['entry'],'/mosa2-test.scharwerk.de'.$config['path'].'index.php')&&!is_link($config['entry']),'entry_guard');
                if(is_file($config['entry']))check(unlink($config['entry']),'entry_cleanup');
            }
            echo $result['ok']?'<h1>Phase 3O erfolgreich geprüft und zurückgerollt</h1><p>Vier synthetische Writerpfade, zwei unabhängige Readbacks. Keine Produktion.</p>':
                '<h1>Phase-3O-Prüflauf gestoppt</h1><p>Keine automatische Wiederholung. Der private Bericht enthält den tatsächlichen Prüfstand.</p>';return;
        }
        $nonce=time().'.'.bin2hex(random_bytes(32));$token=$nonce.'.'.hash_hmac('sha256',$nonce,$config['key']);
        setcookie('M2P3OCSRF',$token,['expires'=>min(time()+600,$config['expires']),'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
        \Mosa2\Phase3M\httpProof($root,'GET');
        echo '<h1>MOSA 2 – kontrollierter Observation-v2-Test Phase 3O</h1>';
        if(!is_file($root.'/form-proof.json'))echo '<p>Technische Vorprüfung: noch kein Passwort eingeben.</p><form method="post"><input type="hidden" name="csrf" value="'.$token.'"><input type="hidden" name="probe" value="1"><button>Geschützten Formularweg prüfen</button></form>';
        else echo '<p>Vier synthetische Unittypen in einer Testtransaktion mit vollständigem Rollback. Das Passwort wird nur für diesen Testlauf verwendet und nicht gespeichert.</p><form method="post" autocomplete="off"><input type="hidden" name="csrf" value="'.$token.'"><label>Test-DB-Passwort <input type="password" name="password" autocomplete="off" required maxlength="1024"></label><button>Kontrollierten Phase-3O-Testlauf starten</button></form>';
    }catch(\Throwable $e){unset($password,$_POST);http_response_code(403);echo '<h1>Zugriff oder Prüfung gestoppt</h1><p>Keine automatische Wiederholung. Keine Zugangsdaten gespeichert.</p>';}
}
if(PHP_SAPI==='fpm-fcgi'&&!defined('MOSA2_PHASE3O_LIBRARY_ONLY'))gateway(__DIR__);
