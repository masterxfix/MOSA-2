<?php
declare(strict_types=1);
namespace Mosa2\Schema6Prepare;
use PDO;
use function Mosa2\Phase2\{check,same,qi};
require_once __DIR__.'/schema5.php';
require_once __DIR__.'/tradegate_manifest.php';
require_once dirname(__DIR__,2).'/api/current_read.php';
require_once dirname(__DIR__,2).'/api/observations_read.php';

/** Preserve exact historical envelopes; this is not a schema6 runtime opt-in. */
function ledger(array $rows,string $root): void {
    $contract=\Mosa2\CollectorSchema5\envelope(4);
    same(count($rows),4,'prepare_ledger_count');
    $files=glob($root.'/docs/database/migrations/000[1-4]_*.sql');sort($files);
    same(count($files),4,'prepare_artifacts');
    foreach($rows as $i=>$row){
        same((string)$row['version'],$contract['versions'][$i],'prepare_ledger_version');
        same($row['migration_key'],basename($files[$i],'.sql'),'prepare_ledger_key');
        same(strtolower($row['checksum']),$contract['digests'][$i],'prepare_ledger_checksum');
        same(hash_file('sha256',$files[$i]),$contract['digests'][$i],'prepare_artifact_checksum');
    }
}
/** A momentary process list cannot establish whole-export write/DDL quiescence. */
function exportGate(array $objects,array $rights,array $processes): array {
    $blockers=['WRITE_DDL_QUIESCENCE_NOT_PROVEN','LIVE_BACKUP_ADAPTER_ISOLATED_ONLY','OFF_HOST_KEY_CUSTODY_NOT_PROVEN'];
    if(($objects['complete_object_visibility']??null)!=='JA')$blockers[]='OBJECT_VISIBILITY_NOT_PROVEN';
    if(($objects['objects']['ROUTINE']['visible_count']??-1)!==0)$blockers[]='ROUTINES_UNSUPPORTED';
    foreach(['SELECT','SHOW VIEW','TRIGGER','EVENT'] as $right)if(($rights[$right]??false)!==true)$blockers[]='EXPORT_SCHEMA_RIGHT_MISSING';
    if(count($processes)>0)$blockers[]='OTHER_TEST_DATABASE_SESSIONS_VISIBLE';
    return ['status'=>'BLOCKED_BEFORE_EXPORT','blockers'=>array_values(array_unique($blockers)),
        'writer_visibility'=>($rights['PROCESS']??false)?'GLOBAL_RIGHT_SCHEMA_FILTERED':'CURRENT_ACCOUNT_ONLY',
        'whole_export_quiescence'=>'NOT_PROVEN','exports'=>0,'restores'=>0];
}
/** Only public identity/status and one-way baseline fingerprints leave the process. */
function publications(array $published,array $observations): array {
    same(count($published),5,'prepare_published_count');same(count($observations),5,'prepare_observation_count');
    $out=[];
    foreach($published as $i=>$entry){
        $r=$entry['route'];$o=$observations[$i];
        same($r['source_key'],\Mosa2\TradegateQuote\SOURCE_VALUES['source_key'],'prepare_tradegate_source');
        same($o['isin'],$r['isin'],'prepare_observation_identity');
        check(in_array($entry['item']['status'],['stored','stale'],true)&&in_array($o['status'],['stored','stale'],true),'prepare_stored_prices');
        foreach(['price','currency','market_at','observed_at'] as $key)same($entry['item'][$key],$o[$key],'prepare_current_observation_match');
        $out[]=['name'=>$r['display_name'],'isin'=>$r['isin'],'source'=>'TRADEGATE_XGAT_MID',
            'current'=>'VALID','observation'=>'VALID','provenance'=>'PASS','age_status'=>$o['status'],
            'route_enabled'=>$r['enabled'],
            'baseline_sha256'=>hash('sha256',\Mosa2\ObservationRead\canonical(['current'=>$entry,'observation'=>$o]))];
    }
    return $out;
}
/** Called only inside the already authenticated, verified READ ONLY transaction. */
function inspect(PDO $p,string $root,array $permissions): array {
    check($p->inTransaction()&&(string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn()==='1','prepare_readonly');
    $p->exec('SET SESSION MAX_EXECUTION_TIME=3000');
    $tables=$p->query('SELECT TABLE_NAME,ENGINE,DATA_LENGTH,INDEX_LENGTH,AUTO_INCREMENT FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME LIMIT 28')->fetchAll(PDO::FETCH_ASSOC);
    same(array_column($tables,'TABLE_NAME'),\Mosa2\CollectorSchema5\envelope(4)['tables'],'prepare_exact_schema4');
    $schema=\Mosa2\Phase3K\structure($p,\Mosa2\CollectorSchema5\schemas($root,4));
    $rows=$p->query('SELECT version,migration_key,HEX(checksum) AS checksum,applied_at FROM m2_schema_migrations ORDER BY version LIMIT 7')->fetchAll(PDO::FETCH_ASSOC);
    ledger($rows,$root);
    $counts=[];$bytes=0;
    foreach($tables as $table){
        same($table['ENGINE'],'InnoDB','prepare_innodb');
        $counts[$table['TABLE_NAME']]=(string)$p->query('SELECT /*+ MAX_EXECUTION_TIME(3000) */ COUNT(*) FROM '.qi($table['TABLE_NAME']))->fetchColumn();
        $bytes+=(int)$table['DATA_LENGTH']+(int)$table['INDEX_LENGTH'];
    }
    $now=gmdate('Y-m-d H:i:s').'.000000';
    $published=\Mosa2\CurrentRead\published($p,$now,900);$observations=[];
    $q=$p->prepare('SELECT /*+ MAX_EXECUTION_TIME(1500) */ id,'.implode(',',\Mosa2\ObservationRead\FIELDS).',observation_format_version,HEX(dedupe_key) AS dedupe_hex FROM m2_market_observations WHERE asset_id=? AND source_id=? ORDER BY market_at DESC,id DESC LIMIT 101');
    foreach($published as $entry){$r=$entry['route'];$q->execute([$r['asset_id'],$r['source_id']]);
        $observations[]=\Mosa2\ObservationRead\latest($q->fetchAll(PDO::FETCH_ASSOC),$r,$r['isin'],$now,900);}
    $public=publications($published,$observations);
    $processes=$p->query('SELECT COMMAND,STATE FROM information_schema.processlist WHERE DB=DATABASE() AND ID<>CONNECTION_ID() LIMIT 33')->fetchAll(PDO::FETCH_ASSOC);
    check(count($processes)<=32,'prepare_process_bound');
    $jobs=$p->query("SELECT COUNT(*) FROM m2_jobs WHERE enabled=1")->fetchColumn();
    $runs=$p->query("SELECT COUNT(*) FROM m2_job_runs WHERE status='running'")->fetchColumn();
    $locks=[];foreach(['m2-current-refresh','m2-collector-live-batch'] as $name){
        $q=$p->prepare('SELECT IS_USED_LOCK(?) IS NOT NULL');$q->execute([$name]);$locks[$name]=(bool)$q->fetchColumn();}
    check($p->inTransaction(),'prepare_transaction_lost');
    return ['status'=>'SCHEMA6_PREPARE_INVENTORY_PASS','schema_version'=>4,'table_count'=>count($tables),
        'exact_structure'=>'PASS','ledger_checksums'=>'PASS','migration5_6_objects'=>'ABSENT',
        'table_rows'=>$counts,'allocated_table_bytes_estimate'=>$bytes,'all_innodb'=>true,
        'metadata_baseline_sha256'=>hash('sha256',\Mosa2\ObservationRead\canonical(['schema'=>$schema,'tables'=>$tables,'ledger'=>$rows])),
        'published'=>$public,'other_schema_sessions_visible'=>count($processes),
        'enabled_jobs'=>(string)$jobs,'running_jobs'=>(string)$runs,'named_locks_in_use'=>$locks,
        'collector_activity'=>'ONLY_DB_JOB_AND_NAMED_LOCK_SIGNALS_NOT_OS_PROOF',
        'backup'=>exportGate($permissions,$permissions['rights'],$processes),
        'runtime_schema6'=>'NOT_COMPATIBLE_EXACT_SCHEMA4_5_CONTRACTS',
        'db_mutations'=>0,'provider_requests'=>0,'deployments'=>0];
}
