<?php
declare(strict_types=1);
namespace Mosa2\Phase3K;
use function Mosa2\Phase2\{check,same,save};
require_once __DIR__.'/live_apply.php';

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
    check(!is_link($root)&&(fileperms($root)&0077)===0,'gateway_private_root');
    foreach($config['hashes'] as $name=>$hash) {
        check(preg_match('~\A(?:phase2|phase3b|phase3k)/[a-z_0-9]+\.(?:php|sql)\z~',$name)===1,'gateway_source_name');
        $path=dirname($root).'/'.$name;
        check(is_file($path)&&!is_link($path)&&(fileperms($path)&0077)===0&&hash_file('sha256',$path)===$hash,'gateway_source_hash');
    }
    statements(file_get_contents($root.'/0003.sql'));
    same(totals(schemas($root)),['tables'=>17,'columns'=>186,'primary'=>17,'unique'=>10,'secondary'=>39,'foreign_keys'=>36,'checks'=>37],'gateway_offline_schema');
}
function gateway(string $root): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    header('Cache-Control: no-store');header('Referrer-Policy: same-origin');header('X-Content-Type-Options: nosniff');
    header('X-Robots-Tag: noindex, nofollow');header("Content-Security-Policy: default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
    header('Content-Type: text/html; charset=utf-8');$password=null;$config=null;
    try {
        $config=require $root.'/access.php';check(requestAllowed($_SERVER,$config,time()),'gateway_request');verifySources($root,$config);
        if(is_file($root.'/started.lock')){echo '<h1>Einmaliger Prüflauf bereits gestartet</h1><p>Keine Wiederholung möglich.</p>';return;}
        if($_SERVER['REQUEST_METHOD']==='POST') {
            check(is_string($_POST['csrf']??null)&&is_string($_COOKIE['M2P3KCSRF']??null)
                &&tokenValid($_POST['csrf'],$_COOKIE['M2P3KCSRF'],$config['key'],time()),'gateway_csrf');
            if(($_POST['probe']??'')==='1'&&!isset($_POST['password'])) {
                save($root.'/form-proof.json',['origin_csrf_probe'=>true,'database_connections'=>0,'ddl_statements'=>0,'schema_counts'=>totals(schemas($root)),'at_utc'=>gmdate('c')]);
                unset($_POST);header('Location: '.$config['path'],true,303);return;
            }
            check(is_file($root.'/form-proof.json'),'gateway_probe_missing');
            $password=$_POST['password']??null;unset($_POST);
            check(is_string($password)&&strlen($password)>=1&&strlen($password)<=1024,'gateway_password');
            set_time_limit(180);
            try {$result=run($root,$password);}
            finally {
                unset($password,$_POST);
                setcookie('M2P3KCSRF','',['expires'=>1,'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
                $entry=$config['entry'];
                check(str_ends_with($entry,'/mosa2-test.scharwerk.de/phase3k-a152ca/index.php')&&!is_link($entry),'gateway_entry_guard');
                if(is_file($entry))check(unlink($entry),'gateway_entry_cleanup');
            }
            echo $result['ok']?'<h1>Unit-Grundschema erfolgreich geprüft</h1><p>17 Tabellen, Ledger v3. Keine Unit-Seeds; acht Marktbeobachtungen erhalten. Keine Produktion.</p>':
                '<h1>Prüflauf gestoppt</h1><p>Kein Retry. Privater Teilzustand gesichert; keine weiteren DDLs.</p>';
            return;
        }
        $nonce=time().'.'.bin2hex(random_bytes(32));$token=$nonce.'.'.hash_hmac('sha256',$nonce,$config['key']);
        setcookie('M2P3KCSRF',$token,['expires'=>min(time()+600,$config['expires']),'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
        echo '<h1>MOSA 2 – kontrollierter Unit-Schema-Apply</h1>';
        if(!is_file($root.'/form-proof.json'))echo '<p>Technische Vorprüfung: noch kein Passwort eingeben.</p><form method="post"><input type="hidden" name="csrf" value="'.$token.'"><input type="hidden" name="probe" value="1"><button>Geschützten Formularweg prüfen</button></form>';
        else echo '<p>Das bestehende Passwort der isolierten Testdatenbank eingeben. Zuerst erfolgt ausschließlich ein read-only Struktur- und Legacyvergleich des exakten Teilzustands nach DDL 3 mit den privaten Originalbelegen. Nur bei vollständiger Übereinstimmung werden DDL 4 und 5 einmalig fortgesetzt. DDL 1–3 werden nicht erneut ausgeführt. Das Passwort wird ausschließlich im laufenden Prozess verwendet.</p><form method="post" autocomplete="off"><input type="hidden" name="csrf" value="'.$token.'"><label>Testdatenbank-Passwort <input type="password" name="password" autocomplete="off" required maxlength="1024"></label><button>Geprüfte Fortsetzung ab DDL 4 starten</button></form>';
    }catch(\Throwable $error) {
        unset($password,$_POST);http_response_code(403);
        echo '<h1>Zugriff oder Prüfung gestoppt</h1><p>Keine automatische Wiederholung. Keine Zugangsdaten gespeichert.</p>';
    }
}
if(PHP_SAPI==='fpm-fcgi')gateway(__DIR__);
