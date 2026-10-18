<?php
declare(strict_types=1);
const MOSA2_HISTORY_PROFILE='history100000_v1';
require __DIR__.'/backup.php';
use function Mosa2\Phase1B\{ensure,connect};
use function Mosa2\History10000\{saveState,validateState,tableNames,build,cleanup};
use function Mosa2\BackupRestore\{validatePair,restoreConnect,snapshot,comparison,exportBackup,importBackup,functional};
ini_set('display_errors','0');
set_error_handler(static function(){throw new RuntimeException('runtime_warning');});
$source=null;$restore=null;$state=null;$lock=null;
try {
    ensure(PHP_SAPI==='cli'&&($argv[1]??'')==='--run','explicit_cli_required');
    $action=$argv[2]??'';ensure(in_array($action,['--backup','--restore','--cleanup','--reset-failed-restore'],true),'unknown_action');
    $root=dirname(__DIR__);ensure(!is_link($root)&&(fileperms($root)&0077)===0,'private_root');
    $target=require $root.'/phase1b/target.php';$access=require $root.'/access.php';$rt=$access['restore'];
    validatePair($target,$rt);
    foreach([$root.'/phase1b/secret.php',$root.'/restore-secret.php'] as $p)ensure(is_file($p)&&!is_link($p)&&(fileperms($p)&0077)===0,'private_secret');
    $source=connect($target,require $root.'/phase1b/secret.php');
    $restore=restoreConnect($target,$rt,require $root.'/restore-secret.php');
    $lock=fopen($root.'/backup.lock','c');ensure($lock!==false&&chmod($root.'/backup.lock',0600)&&flock($lock,LOCK_EX|LOCK_NB),'backup_lock');
    $path=$root.'/dataset.json';$reportPath=$root.'/backup-report.json';$backupPath=$root.'/synthetic-backup.jsonl';
    $deadline=microtime(true)+120;set_time_limit(150);
    if($action==='--backup') {
        ensure(tableNames($source)===[]&&tableNames($restore)===[],'both_targets_must_be_empty');
        ensure(!file_exists($path)&&!file_exists($reportPath),'backup_already_started');
        $built=build($source,$path,$deadline);
        $state=json_decode(file_get_contents($path),true,32,JSON_THROW_ON_ERROR);validateState($state);
        $before=snapshot($source,$state,$deadline);
        $backup=exportBackup($source,$state,$before,$backupPath,$deadline);
        $report=['ok'=>true,'stage'=>'backed_up','at_berlin'=>(new DateTimeImmutable('now',new DateTimeZone('Europe/Berlin')))->format(DATE_ATOM),'runtime'=>PHP_VERSION,'build'=>$built,'before'=>$before,'backup'=>$backup];
        saveState($reportPath,$report);
        echo json_encode(['ok'=>true,'stage'=>'backed_up','counts'=>$before['counts'],'integrity'=>$before['integrity'],'backup'=>$backup],JSON_THROW_ON_ERROR),PHP_EOL;
    } else {
        ensure(is_file($path)&&!is_link($path),'manifest_missing');
        $state=json_decode(file_get_contents($path),true,32,JSON_THROW_ON_ERROR);validateState($state);
        if($action==='--reset-failed-restore') {
            $report=json_decode(file_get_contents($reportPath),true,32,JSON_THROW_ON_ERROR);
            ensure($report['stage']==='backed_up'&&file_exists($root.'/restore-started'),'failed_restore_required');
            comparison($report['before'],snapshot($source,$state,$deadline));
            $restoreState=$state;
            $reset=cleanup($restore,$restoreState,$root.'/restore-reset.json',$deadline);
            ensure($reset['remaining_table_count']===0,'reset_not_empty');
            ensure(unlink($root.'/restore-started'),'reset_reservation');
            $report['corrected_restore_attempts']=(int)($report['corrected_restore_attempts']??0)+1;
            saveState($reportPath,$report);
            echo json_encode(['ok'=>true,'stage'=>'restore_target_reset','source_unchanged'=>true,'target_tables'=>0]),PHP_EOL;
        } elseif($action==='--restore') {
            $report=json_decode(file_get_contents($reportPath),true,32,JSON_THROW_ON_ERROR);
            ensure($report['stage']==='backed_up'&&!file_exists($root.'/restore-started'),'restore_already_started');
            comparison($report['before'],snapshot($source,$state,$deadline));
            ensure(tableNames($restore)===[],'restore_not_empty');
            $reservation=fopen($root.'/restore-started','x');ensure($reservation!==false,'restore_reservation');fclose($reservation);chmod($root.'/restore-started',0600);
            $report['restore']=importBackup($restore,$state,$report['before'],$backupPath,$report['backup'],$deadline);
            $report['stage']='restored';saveState($reportPath,$report);
            $report['after']=snapshot($restore,$state,$deadline);
            $report['comparison']=comparison($report['before'],$report['after']);
            $report['source_unchanged']=comparison($report['before'],snapshot($source,$state,$deadline));
            $report['functional']=functional($restore,$state);
            $report['stage']='verified';$report['verified_at_berlin']=(new DateTimeImmutable('now',new DateTimeZone('Europe/Berlin')))->format(DATE_ATOM);
            saveState($reportPath,$report);
            echo json_encode(['ok'=>true,'stage'=>'verified','restore'=>$report['restore'],'comparison'=>$report['comparison'],'source_unchanged'=>$report['source_unchanged'],'functional'=>$report['functional'],'at_berlin'=>$report['verified_at_berlin']],JSON_THROW_ON_ERROR),PHP_EOL;
        } else {
            $report=json_decode(file_get_contents($reportPath),true,32,JSON_THROW_ON_ERROR);
            ensure($report['stage']==='verified','successful_verification_required');
            $restoreState=$state;
            $r=cleanup($restore,$restoreState,$root.'/restore-cleanup.json',$deadline);
            $s=cleanup($source,$state,$path,$deadline);
            $report['cleanup']=['source'=>$s,'restore'=>$r];$report['stage']='tables_cleaned';
            saveState($reportPath,$report);
            echo json_encode(['ok'=>true,'stage'=>'tables_cleaned','cleanup'=>$report['cleanup']],JSON_THROW_ON_ERROR),PHP_EOL;
        }
    }
} catch(Throwable $e) {
    $failure=['ok'=>false,'code'=>$e instanceof Mosa2\Phase1B\Failure?$e->getMessage():'backup_operation_failed'];
    foreach([$source,$restore] as $pdo)if($pdo instanceof PDO&&$pdo->inTransaction())$pdo->rollBack();
    // Keep the manifest and backup for deliberate recovery; never drop unproven tables.
    echo json_encode($failure,JSON_THROW_ON_ERROR),PHP_EOL;exit(1);
} finally {if(is_resource($lock)){flock($lock,LOCK_UN);fclose($lock);}}
