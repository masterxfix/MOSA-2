<?php
declare(strict_types=1);
namespace Mosa2\Phase3M;
use PDO;
use PDOException;
use Throwable;
use function Mosa2\Phase2\{check,same,qi,connection,save};
require_once __DIR__.'/../phase3k/live_apply.php';
require_once __DIR__.'/state_integrity.php';

const PACKAGE='b66df6f972ad13c05c3f34c604088c0281dcd9f0ff4bafad45b9600aa2b747ee';
const BASELINE='783921f878fb5e4dc40c1baf68381dfb11ab8c8f07df9bd9273a7b3596ca9938';
const FIELDS=['unit_key','unit_version','unit_contract_version','dimension_key','base_unit_key',
    'base_unit_version','monetary_currency_code','scale_numerator','scale_denominator','status'];

function offline(string $root,array $args=[]): array {
    $process=proc_open(array_merge(['python3',$root.'/unit_seed.py'],$args),
        [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes);
    check(is_resource($process),'python_start');fclose($pipes[0]);
    $out=stream_get_contents($pipes[1],65536);$error=stream_get_contents($pipes[2],16384);
    fclose($pipes[1]);fclose($pipes[2]);$code=proc_close($process);
    check($code===0&&$error==='','offline_validator_failed');
    $result=json_decode($out,true,512,JSON_THROW_ON_ERROR);same($result['package_sha256'],PACKAGE,'package_digest');
    return $result;
}

function plan(string $root): array {
    $proof=offline($root);$plan=json_decode(file_get_contents($root.'/plan.json'),true,512,JSON_THROW_ON_ERROR);
    same($plan['plan_format'],'mosa2-unit-insert-plan-v1','plan_format');same($plan['package_sha256'],PACKAGE,'plan_package');
    same(count($plan['definitions']),4,'four_units');
    same(array_column($plan['definitions'],'definition_sha256'),$proof['definition_hashes'],'plan_hashes');
    same(array_map(fn($r)=>$r['unit_key'].'@'.$r['unit_version'],$plan['definitions']),$proof['insert_order'],'plan_order');
    foreach($plan['definitions'] as $i=>$row) {
        $bytes=$plan['canonical_definitions'][$i];same(hash('sha256',$bytes),$row['definition_sha256'],'canonical_digest');
        check(str_starts_with($bytes,"mosa2-unit-definition-v1\n"),'definition_domain');
        $canonical=json_decode(substr($bytes,strlen("mosa2-unit-definition-v1\n")),true,512,JSON_THROW_ON_ERROR);
        same(array_keys($canonical),FIELDS,'canonical_fields');
        foreach(FIELDS as $field)same($row[$field],$canonical[$field],'plan_semantics');
    }
    return $plan;
}

function readUnits(PDO $p): array {
    $columns=array_map(__NAMESPACE__.'\\identifier',FIELDS);
    $columns[]='LOWER(HEX(definition_sha256)) AS definition_sha256';$columns[]='created_at';
    $rows=$p->query('SELECT '.implode(',',$columns).' FROM m2_units ORDER BY unit_key,unit_version')->fetchAll();
    foreach($rows as &$row)foreach(['unit_version','base_unit_version','scale_numerator','scale_denominator'] as $field)$row[$field]=(string)$row[$field];
    unset($row);return $rows;
}
function identifier(string $value): string {return qi($value);}

function legacyState(PDO $p,string $root,int $unitCount,array $baseline): array {
    $state=captureState($p,$root);
    // Capture precedes every guard; counters are diagnostic, never historical identity.
    compareState($baseline,$state,$unitCount);
    \Mosa2\Phase3K\ledger($p,3);return $state;
}

function insertOne(PDO $p,array $row,string $created): void {
    $columns=array_merge(FIELDS,['definition_sha256','created_at']);$values=[];
    foreach(FIELDS as $field)$values[]=$row[$field];
    $hash=hex2bin($row['definition_sha256']);check(is_string($hash)&&strlen($hash)===32,'binary_hash');
    $values[]=$hash;$values[]=$created;
    $q=$p->prepare('INSERT INTO m2_units ('.implode(',',array_map(__NAMESPACE__.'\\identifier',$columns)).') VALUES ('.implode(',',array_fill(0,count($columns),'?')).')');
    $q->execute($values);same($q->rowCount(),1,'one_unit_insert');
}

function selfFk(PDO $p,array $probes,string $created): array {
    same(count($probes),2,'two_probes');$p->beginTransaction();
    try {
        foreach($probes as $row)insertOne($p,$row,$created);
        same(count(readUnits($p)),2,'probe_units');
        $bad=$probes[1];$bad['unit_key']='SEED_PROBE_INVALID';$bad['base_unit_key']='SEED_PROBE_MISSING';
        $rejected=false;
        try{insertOne($p,$bad,$created);}catch(PDOException $e){
            same((int)($e->errorInfo[1]??0),1452,'probe_fk_errno');
            check(str_contains((string)($e->errorInfo[2]??''),'fk_units_base'),'probe_fk_name');$rejected=true;
        }
        check($rejected&&$p->inTransaction(),'probe_invalid_fk_not_rejected');
    } finally {if($p->inTransaction())$p->rollBack();}
    return ['self_base'=>true,'dependent_fk'=>true,'checks_accept'=>true,'invalid_base_rejected'=>true,'rolled_back'=>true];
}

function compareReadback(string $root,array $rows,string $created,string $file): array {
    \Mosa2\Phase3K\privateFile($root.'/'.$file,\Mosa2\Phase3K\jsonBytes($rows));
    $result=offline($root,['--readback',$root.'/'.$file,'--created-at',$created]);
    same([$result['unit_rows'],$result['replay']['duplicates'],$result['replay']['inserts'],
        $result['replay']['updates'],$result['replay']['conflicts']],[4,4,0,0,0],'readback_replay');return $result;
}

function applyTransaction(PDO $p,array $definitions,string $created,callable $before,callable $readback): void {
    same(count($definitions),4,'transaction_four_units');$p->beginTransaction();
    try {
        $p->query('SELECT unit_key,unit_version FROM m2_units FOR UPDATE')->fetchAll();
        foreach($definitions as $i=>$row){$before($i);insertOne($p,$row,$created);}
        $readback();check($p->commit(),'commit_failed');
    }catch(Throwable $error){if($p->inTransaction())$p->rollBack();throw $error;}
}

function run(string $root,string $password): array {
    umask(0077);check(realpath($root)===$root&&!is_link($root)&&(fileperms($root)&0077)===0,'private_root');
    check(is_file($root.'/form-proof.json')&&!file_exists($root.'/report.json'),'form_proof');
    $marker=fopen($root.'/started.lock','x');check($marker!==false,'already_attempted');fclose($marker);
    $report=['ok'=>false,'commit_requested'=>false,'commit_confirmed'=>false,'package_sha256'=>PACKAGE,'stage'=>'offline','unit_rows_before'=>null];$p=null;
    $persist=function()use($root,&$report){save($root.'/report.json',$report);};$persist();
    try {
        $plan=plan($root);same(hash_file('sha256',$root.'/baseline.json'),BASELINE,'baseline_hash');
        $baseline=json_decode(file_get_contents($root.'/baseline.json'),true,512,JSON_THROW_ON_ERROR);
        $classification=json_decode(file_get_contents($root.'/diagnosis.json'),true,512,JSON_THROW_ON_ERROR);
        check(in_array($classification['classification'],['CHECKER_BASELINE_BUG','METADATA_ONLY_DRIFT'],true),'classification_required');
        $report['classification']=$classification['classification'];$report['affected_tables']=$classification['affected_tables'];
        $report['counter_reset']=false;
        $report['stage']='live_preflight';$persist();$p=connection($password);
        same((int)$p->query("SELECT GET_LOCK('mosa2-unit-seeds-v1',0)")->fetchColumn(),1,'seed_lock');
        $ids=[$p->query('SELECT CONNECTION_ID()')->fetchColumn()];
        $before=legacyState($p,$root,0,$baseline);$report['unit_rows_before']=0;
        \Mosa2\Phase3K\privateFile($root.'/pre-state.json',\Mosa2\Phase3K\jsonBytes($before));
        $report['stage']='self_fk_precheck';$persist();
        $report['self_fk']=selfFk($p,$plan['synthetic_probe'],'2000-01-01 00:00:00.000000');
        $independent=connection($password);$ids[]=$independent->query('SELECT CONNECTION_ID()')->fetchColumn();
        legacyState($independent,$root,0,$baseline);$independent=null;$report['rollback_independent_empty']=true;
        // The package timestamp is created exactly once, after the successful probe.
        $created=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');
        $report['created_at']=$created;
        \Mosa2\Phase3K\privateFile($root.'/resolved-insert.json',\Mosa2\Phase3K\jsonBytes(['package_sha256'=>PACKAGE,'created_at'=>$created,'definitions'=>$plan['definitions']]));
        $report['stage']='normative_transaction';$persist();
        applyTransaction($p,$plan['definitions'],$created,
            function(int $i)use($p,$root,$baseline){legacyState($p,$root,$i,$baseline);},
            function()use($p,$root,$created,$baseline,&$report,$persist){
                $report['before_commit']=compareReadback($root,readUnits($p),$created,'before-commit-units.json');
                legacyState($p,$root,4,$baseline);$report['commit_requested']=true;$persist();
            });
        $report['commit_confirmed']=true;$persist();
        $report['stage']='independent_readbacks';$persist();$readbacks=[];
        for($n=1;$n<=2;$n++) {
            $independent=connection($password);$ids[]=$independent->query('SELECT CONNECTION_ID()')->fetchColumn();
            $state=legacyState($independent,$root,4,$baseline);$units=readUnits($independent);
            $verified=compareReadback($root,$units,$created,'readback-'.$n.'-units.json');
            $state['units']=$units;$readbacks[]=$state;
            $report['readback_sha256_'.$n]=\Mosa2\Phase3K\privateFile($root.'/readback-'.$n.'.json',\Mosa2\Phase3K\jsonBytes($state));
            $report['stable_readback_sha256_'.$n]=\Mosa2\Phase3K\dataHash(stableState($state)+['units'=>$units]);
            if($n===1)$report['replay']=$verified['replay'];$independent=null;
        }
        same(count(array_unique($ids)),4,'independent_connections');
        same($readbacks[0]['units'],$readbacks[1]['units'],'readbacks_differ');
        \Mosa2\Phase3K\preserve($readbacks[0],$readbacks[1]);
        same(stableState($readbacks[0]),stableState($readbacks[1]),'stable_state_changed');
        same($report['stable_readback_sha256_1'],$report['stable_readback_sha256_2'],'stable_readback_hashes_differ');
        $report['ok']=true;$report['stage']='complete';$report['unit_rows_after']=4;
        $report['legacy_unchanged']=true;$report['ledger_versions']=[1,2,3];$report['current']=0;$report['bars']=0;
    } catch(Throwable $error){
        if($p instanceof PDO&&$p->inTransaction())$p->rollBack();$report['failure']=\Mosa2\Phase3K\safeError($error);
    } finally {
        if($p instanceof PDO)try{$p->query("SELECT RELEASE_LOCK('mosa2-unit-seeds-v1')");}catch(Throwable $unused){}
        $p=null;unset($password);$report['finished_at_utc']=gmdate('c');$persist();
    }
    return $report;
}
