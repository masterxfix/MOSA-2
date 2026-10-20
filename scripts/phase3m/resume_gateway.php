<?php
declare(strict_types=1);
namespace Mosa2\Phase3M\Resume;
define('MOSA2_PHASE3M_LIBRARY_ONLY',true);
require_once __DIR__.'/password_gateway.php';
require_once __DIR__.'/state_integrity.php';
use function Mosa2\Phase2\{check,same,save,connection};
use function Mosa2\Phase3M\{requestAllowed,tokenValid,verifySources,httpProof,diagnose};

function continueAfterDiagnosis(string $root,string $password,array $config): array {
    $lock=fopen($root.'/diagnosis.lock','x');check($lock!==false,'diagnosis_already_attempted');fclose($lock);
    $p=null;
    try {
        $baseline=json_decode(file_get_contents($root.'/baseline.json'),true,512,JSON_THROW_ON_ERROR);
        $p=connection($password);$classification=diagnose($p,$root,$baseline);$p=null;
        check(in_array($classification['classification'],['CHECKER_BASELINE_BUG','METADATA_ONLY_DRIFT'],true),'continuation_classification');
        save($root.'/control-status.json',['stage'=>'awaiting_tested_fix','classification'=>$classification['classification'],'database_writes'=>0]);
        // Password remains only in this request's memory. A tested source update
        // must be delivered through the existing authenticated Plesk text path.
        $deadline=time()+300;
        while(!is_file($root.'/continue-ready.json')&&time()<$deadline)usleep(250000);
        check(is_file($root.'/continue-ready.json'),'tested_fix_missing');
        $ready=json_decode(file_get_contents($root.'/continue-ready.json'),true,512,JSON_THROW_ON_ERROR);
        same($ready['classification_sha256'],hash_file('sha256',$root.'/diagnosis.json'),'classification_binding');
        same($ready['tests_passed'],true,'tests_missing');
        same(array_keys($ready['hashes']),array_keys($config['hashes']),'source_set_changed');
        foreach($ready['hashes'] as $name=>$hash){
            if($name!=='scripts/phase3m/live_seed.php')same($hash,$config['hashes'][$name],'unexpected_source_update');
            $file=dirname($root,2).'/'.$name;check(!is_link($file)&&hash_file('sha256',$file)===$hash,'tested_source_hash');
        }
        $process=proc_open(['/opt/plesk/php/8.4/bin/php',$root.'/continuation_worker.php'],
            [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes);
        check(is_resource($process),'worker_start');check(fwrite($pipes[0],$password)===strlen($password),'worker_password_pipe');fclose($pipes[0]);
        unset($password);$out=stream_get_contents($pipes[1]);$err=stream_get_contents($pipes[2]);fclose($pipes[1]);fclose($pipes[2]);
        check(proc_close($process)===0&&$err==='','worker_failed');
        $result=json_decode($out,true,512,JSON_THROW_ON_ERROR);save($root.'/control-status.json',['stage'=>$result['stage'],'ok'=>$result['ok']]);return $result;
    }catch(\Throwable $error){
        if($p instanceof \PDO&&$p->inTransaction())$p->rollBack();$p=null;
        $reason=\Mosa2\Phase3K\safeError($error);
        $dataReasons=['legacy_rows_changed','legacy_hash_changed','ledger_changed','structure_changed','unit_count','counter_table_set'];
        $kind=in_array($error->getMessage(),$dataReasons,true)?'DATA_CHANGE':'EVIDENCE_INSUFFICIENT';
        if(!is_file($root.'/diagnosis.json'))save($root.'/diagnosis.json',['classification'=>$kind,'failure'=>$reason,'database_writes'=>0]);
        save($root.'/control-status.json',['stage'=>'stopped','failure'=>$reason,'database_writes'=>0]);return ['ok'=>false,'stage'=>'stopped'];
    }finally{unset($password);}
}
function gateway(string $root): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);$password=null;
    header('Cache-Control: no-store');header('Referrer-Policy: same-origin');header('X-Content-Type-Options: nosniff');
    header('X-Robots-Tag: noindex, nofollow');header("Content-Security-Policy: default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
    header('Content-Type: text/html; charset=utf-8');
    try {
        $config=require $root.'/access.php';check(requestAllowed($_SERVER,$config,time()),'request');verifySources($root,$config);
        check(!is_file($root.'/diagnosis.lock'),'already_started');
        if($_SERVER['REQUEST_METHOD']==='POST'){
            check(is_string($_POST['csrf']??null)&&is_string($_COOKIE['M2P3MCSRF']??null)
                &&tokenValid($_POST['csrf'],$_COOKIE['M2P3MCSRF'],$config['key'],time()),'csrf');
            if(($_POST['probe']??'')==='1'&&!isset($_POST['password'])){
                httpProof($root,'POST');save($root.'/form-proof.json',['origin_csrf_probe'=>true,'database_connections'=>0,'database_writes'=>0]);
                unset($_POST);header('Location: '.$config['path'],true,303);return;
            }
            check(is_file($root.'/form-proof.json'),'probe_missing');
            $get=json_decode(file_get_contents($root.'/http-GET.json'),true,512,JSON_THROW_ON_ERROR);
            foreach(['https','no_store','noindex','secure','httponly','samesite_strict'] as $key)check(($get[$key]??false)===true,'http_proof');
            $password=$_POST['password']??null;unset($_POST);check(is_string($password)&&strlen($password)>0&&strlen($password)<=1024,'password');
            set_time_limit(480);
            try{$result=continueAfterDiagnosis($root,$password,$config);}finally{
                unset($password,$_POST);setcookie('M2P3MCSRF','',['expires'=>1,'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
                $entry=dirname(dirname($root,2)).'/mosa2-test.scharwerk.de/phase3m-resume-a157c2/index.php';
                same($config['entry'],$entry,'entry_guard');check(!is_link($entry),'entry_link');if(is_file($entry))check(unlink($entry),'entry_remove');
            }
            echo $result['ok']?'<h1>Phase 3M erfolgreich abgeschlossen</h1><p>Vier Units, Readbacks und Replay bestätigt. Kein Counter-Reset.</p>':
                '<h1>Phase-3M-Fortsetzung gestoppt</h1><p>Keine automatische Wiederholung. Privater Diagnosebericht gesichert.</p>';return;
        }
        $nonce=time().'.'.bin2hex(random_bytes(32));$token=$nonce.'.'.hash_hmac('sha256',$nonce,$config['key']);
        setcookie('M2P3MCSRF',$token,['expires'=>min(time()+600,$config['expires']),'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);httpProof($root,'GET');
        echo '<h1>MOSA 2 – AUTO_INCREMENT-Diagnose und Phase-3M-Fortsetzung</h1>';
        if(!is_file($root.'/form-proof.json'))echo '<p>Noch kein Passwort eingeben.</p><form method="post"><input type="hidden" name="csrf" value="'.$token.'"><input type="hidden" name="probe" value="1"><button>Geschützten Formularweg prüfen</button></form>';
        else echo '<p>Zuerst ausschließlich read-only: Rows, PKs, Ledger, Units und Betriebsmetadaten. Fortsetzung nur bei bewiesener Metadatenabweichung, geprüftem Guardfix und grünen Tests. Das Passwort bleibt ausschließlich im laufenden Prozess und wird nicht gespeichert.</p><form method="post" autocomplete="off"><input type="hidden" name="csrf" value="'.$token.'"><label>Test-DB-Passwort <input type="password" name="password" autocomplete="off" required maxlength="1024"></label><button>Read-only Diagnose und freigegebene Fortsetzung starten</button></form>';
    }catch(\Throwable $error){unset($password,$_POST);http_response_code(403);echo '<h1>Zugriff oder Prüfung gestoppt</h1>';}
}
if(PHP_SAPI==='fpm-fcgi')gateway(__DIR__);
