<?php
declare(strict_types=1);
namespace Mosa2\Schema6Apply;
use PDO;
use function Mosa2\Phase2\{check,same,qi,connection};
require_once __DIR__.'/market_collector/schema6.php';
require_once __DIR__.'/market_collector/schema6_prepare.php';

const EXECUTION='MOSA2-SCHEMA6-20261101-01';
function event(string $stage,array $facts=[]): void {
    echo json_encode(['stage'=>$stage]+$facts,JSON_THROW_ON_ERROR)."\n";flush();
}
function ledger(PDO $p,int $version): void {
    $e=\Mosa2\CollectorSchema5\envelope($version);
    $rows=$p->query('SELECT version,migration_key,HEX(checksum) AS checksum FROM m2_schema_migrations ORDER BY version LIMIT 7')->fetchAll();
    same(count($rows),$version,'ledger_count');
    $files=glob(dirname(__DIR__).'/docs/database/migrations/000[1-6]_*.sql');sort($files);
    foreach($rows as $i=>$row){
        same((string)$row['version'],$e['versions'][$i],'ledger_version');
        same($row['migration_key'],basename($files[$i],'.sql'),'ledger_key');
        same(strtolower($row['checksum']),$e['digests'][$i],'ledger_hash');
    }
}
function addLedger(PDO $p,int $version): void {
    $e=\Mosa2\CollectorSchema5\envelope($version);
    $files=glob(dirname(__DIR__).'/docs/database/migrations/000'.$version.'_*.sql');same(count($files),1,'artifact');
    $q=$p->prepare('INSERT INTO m2_schema_migrations (version,migration_key,checksum,applied_at) VALUES (?,?,?,UTC_TIMESTAMP(6))');
    check($q->execute([$version,basename($files[0],'.sql'),hex2bin($e['digests'][$version-1])]),'ledger_insert');
}
/** Lossless, bounded fingerprints: binary/decimal/time/null preserved; no row output. */
function fingerprints(PDO $p,bool $after=false): array {
    $out=[];
    foreach(\Mosa2\CollectorSchema5\envelope(4)['tables'] as $table){
        $where=$after?match($table){
            'm2_schema_migrations'=>' WHERE version<=4',
            'm2_jobs'=>" WHERE job_key<>'collector_reservations_v1'",
            'm2_module_state'=>" WHERE module_key<>'collector_reservations'",default=>''}:'';
        $rows=$p->query('SELECT * FROM '.qi($table).$where.' LIMIT 129')->fetchAll(PDO::FETCH_ASSOC);
        check(count($rows)<=128,'row_bound');$encoded=[];
        foreach($rows as $row){$values=[];foreach($row as $key=>$value)$values[$key]=$value===null?null:bin2hex((string)$value);
            $text=json_encode($values,JSON_THROW_ON_ERROR);check(strlen($text)<=1048576,'row_bytes');$encoded[]=$text;}
        sort($encoded,SORT_STRING);$out[$table]=['count'=>count($rows),'sha256'=>hash('sha256',json_encode($encoded,JSON_THROW_ON_ERROR))];
    }
    same($out['m2_market_current']['count'],5,'current_count');same($out['m2_market_observations']['count'],28,'observations_count');
    foreach(['m2_jobs','m2_job_runs','m2_module_state'] as $t)same($out[$t]['count'],0,'initial_jobs');
    return $out;
}
function quiet(PDO $p): void {
    same((int)$p->query('SELECT COUNT(*) FROM m2_jobs WHERE enabled<>0')->fetchColumn(),0,'enabled_jobs');
    same((int)$p->query("SELECT COUNT(*) FROM m2_job_runs WHERE status='running'")->fetchColumn(),0,'running_jobs');
    same((int)$p->query('SELECT COUNT(*) FROM information_schema.processlist WHERE DB=DATABASE() AND ID<>CONNECTION_ID()')->fetchColumn(),0,'other_test_sessions');
}
function provenance(PDO $p): void {
    $now=gmdate('Y-m-d H:i:s').'.000000';$published=\Mosa2\CurrentRead\published($p,$now,900);$observations=[];
    $q=$p->prepare('SELECT id,'.implode(',',\Mosa2\ObservationRead\FIELDS).',observation_format_version,HEX(dedupe_key) AS dedupe_hex FROM m2_market_observations WHERE asset_id=? AND source_id=? ORDER BY market_at DESC,id DESC LIMIT 101');
    foreach($published as $entry){$r=$entry['route'];$q->execute([$r['asset_id'],$r['source_id']]);
        $observations[]=\Mosa2\ObservationRead\latest($q->fetchAll(PDO::FETCH_ASSOC),$r,$r['isin'],$now,900);}
    \Mosa2\Schema6Prepare\publications($published,$observations);
}
/** Sequential DDL with explicit uncertain-step reporting; never retry or repair. */
function migrate(PDO $p,array $schema,callable $verify,callable $notify): void {
    $five=\Mosa2\CollectorSchema5\statements();
    foreach(array_slice($five,0,5) as $i=>$sql){$notify('DDL5_'.($i+1).'_START');$p->exec($sql);$notify('DDL5_'.($i+1).'_CONFIRMED');}
    $notify('BOOTSTRAP5_START');check($p->beginTransaction(),'begin5');
    foreach(array_slice($five,5) as $sql)$p->exec($sql);
    addLedger($p,5);check($p->commit(),'commit5');$notify('BOOTSTRAP5_CONFIRMED');
    $verify(5);$notify('SCHEMA5_PASS');
    foreach(\Mosa2\CollectorSchema5\FUNDAMENTALS as $i=>$name){$notify('DDL6_'.($i+1).'_START');$p->exec($schema[$name]['ddl']);$notify('DDL6_'.($i+1).'_CONFIRMED');}
    $verify(0); // full structure before recording ledger 6
    $notify('LEDGER6_START');check($p->beginTransaction(),'begin6');addLedger($p,6);check($p->commit(),'commit6');$notify('LEDGER6_CONFIRMED');
    $verify(6);$notify('SCHEMA6_PASS');
}
function main(): int {
    ini_set('display_errors','0');ini_set('log_errors','0');$stage='INPUT';$p=null;$read=null;$started=false;
    try{
        $input=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);
        same($input['execution']??null,EXECUTION,'execution');same($input['attempt']??null,'1','attempt');same($input['run_number']??null,'1','run_number');
        check(preg_match('/\A[0-9a-f]{40}\z/',$input['commit']??'')===1,'commit');
        $stage='ARTIFACTS';$schema=\Mosa2\CollectorSchema6\schemas();$schema4=array_intersect_key($schema,array_flip(\Mosa2\CollectorSchema5\envelope(4)['tables']));
        $schema5=array_intersect_key($schema,array_flip(\Mosa2\CollectorSchema5\envelope(5)['tables']));
        $stage='IDENTITY_AND_RIGHTS';$p=connection($input['password'],'127.0.0.1',$input['port']);
        \Mosa2\Phase2\preflight($p,false); // exact schema-only ALL PRIVILEGES, global USAGE only
        $stage='LOCKS';
        foreach(['m2-schema6-apply','m2-current-migration-4','m2-current-refresh','m2-collector-scheduler'] as $lock){
            $q=$p->prepare('SELECT GET_LOCK(?,0)');$q->execute([$lock]);same((int)$q->fetchColumn(),1,'busy');}
        $stage='PREFLIGHT';$p->exec('SET SESSION MAX_EXECUTION_TIME=3000');$p->exec('SET TRANSACTION READ ONLY');check($p->beginTransaction(),'begin_preflight');
        \Mosa2\Phase3K\structure($p,$schema4);ledger($p,4);quiet($p);provenance($p);$before=fingerprints($p);
        check($p->commit(),'end_preflight');
        event('PREFLIGHT_PASS',['schema'=>4,'tables'=>17,'ledger'=>'PASS','mysql'=>'8.0.26-16','ddl_insert_rights'=>'PASS','fingerprints'=>$before]);
        $stage='IMMEDIATE_RECHECK';quiet($p);same(fingerprints($p),$before,'baseline_changed');
        $verify=static function(int $v)use($p,$schema,$schema5){
            \Mosa2\Phase3K\structure($p,$v===5?$schema5:$schema);ledger($p,$v===0?5:$v);\Mosa2\CollectorSchema5\lockedDatabase($p);
        };
        $notify=static function(string $s)use(&$stage){$stage=$s;event($s);};
        $started=true;migrate($p,$schema,$verify,$notify);
        $stage='INDEPENDENT_POSTCHECK';
        $originalId=(int)$p->query('SELECT CONNECTION_ID()')->fetchColumn();
        $read=connection($input['password'],'127.0.0.1',$input['port']);unset($input['password']);
        check((int)$read->query('SELECT CONNECTION_ID()')->fetchColumn()!==$originalId,'independent');
        $read->exec('SET SESSION MAX_EXECUTION_TIME=3000');$read->exec('SET TRANSACTION READ ONLY');check($read->beginTransaction(),'begin_postcheck');
        \Mosa2\Phase3K\structure($read,$schema);ledger($read,6);\Mosa2\CollectorSchema5\lockedDatabase($read);
        same(fingerprints($read,true),$before,'old_data_changed');provenance($read);
        foreach(\Mosa2\CollectorSchema5\FUNDAMENTALS as $table)same((int)$read->query('SELECT COUNT(*) FROM '.qi($table))->fetchColumn(),0,'fundamentals_empty');
        same((int)$read->query('SELECT COUNT(*) FROM m2_jobs WHERE enabled<>0')->fetchColumn(),0,'scheduler_disabled');
        check($read->commit(),'end_postcheck');
        event('SUCCESS',['schema_before'=>4,'schema_after'=>6,'tables_before'=>17,'tables_after'=>26,'ledger'=>'PASS','current_unchanged'=>true,'observations_unchanged'=>true,'old_data_unchanged'=>true,'provenance_chains'=>5,'fundamentals_empty'=>true,'collector_locked'=>true,'independent_connection'=>true]);
        return 0;
    }catch(\Throwable){event('STOP',['at'=>$stage,'outcome'=>$started?'PARTIAL_OR_UNKNOWN':'NO_SCHEMA_WRITES']);return 1;}
    finally{$read=null;$p=null;} // disconnect; no explicit rollback/retry/repair claims
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)exit(main());
