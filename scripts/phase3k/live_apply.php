<?php
declare(strict_types=1);
namespace Mosa2\Phase3K;
use PDO;
use PDOException;
use Throwable;
use function Mosa2\Phase2\{check,same,qi,connection,preflight,save};
require_once __DIR__.'/unit_schema.php';

const COUNTS=['m2_entities'=>7,'m2_sources'=>4,'m2_relationships'=>0,'m2_files'=>0,
    'm2_events'=>0,'m2_jobs'=>0,'m2_job_runs'=>0,'m2_assets'=>7,'m2_asset_identifiers'=>7,
    'm2_asset_source_routes'=>8,'m2_schema_migrations'=>2,'m2_sync_checkpoints'=>5,
    'm2_module_state'=>0,'m2_market_current'=>0,'m2_market_observations'=>8,'m2_market_bars'=>0];

function jsonBytes(array $value): string {return json_encode($value,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);}
function dataHash(array $value): string {return hash('sha256',jsonBytes($value));}
function privateFile(string $path,string $bytes): string {
    check(!file_exists($path)&&!is_link($path),'private_file_exists');
    $handle=fopen($path,'x');check($handle!==false,'private_file_open');
    try {check(fwrite($handle,$bytes)===strlen($bytes)&&fflush($handle),'private_file_write');}
    finally {fclose($handle);}
    check(chmod($path,0600)&&hash_file('sha256',$path)===hash('sha256',$bytes),'private_file_verify');
    return hash('sha256',$bytes);
}
function ledger(PDO $p,int $count,?array $before=null): array {
    $r=$p->query('SELECT version,migration_key,LOWER(HEX(checksum)) AS checksum,applied_at FROM m2_schema_migrations ORDER BY version')->fetchAll();
    same(count($r),$count,'unit_ledger_count');
    $keys=['0001_core_asset_identity','0002_market_current_history','0003_market_units'];
    $hashes=[\Mosa2\Phase2\DIGEST,\Mosa2\Phase3B\DIGEST,DIGEST];
    foreach($r as $i=>$row) {
        same((int)$row['version'],$i+1,'unit_ledger_version');same($row['migration_key'],$keys[$i],'unit_ledger_key');
        same($row['checksum'],$hashes[$i],'unit_ledger_hash');
        check((bool)preg_match('/\A\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}\z/',$row['applied_at']),'unit_ledger_time');
    }
    if($before!==null)same(array_slice($r,0,2),$before,'old_ledger_changed');return $r;
}
function snapshot(PDO $p,array $schema,bool $ledgerThree=false): array {
    $result=[];
    foreach($schema as $name=>$t) {
        $select=[];foreach($t['columns'] as $key=>$c)$select[]=($c['type']==='binary(32)'?'HEX('.qi($key).')':qi($key)).' AS '.qi($key);
        $sql='SELECT '.implode(',',$select).' FROM '.qi($name);
        if($name==='m2_schema_migrations'&&$ledgerThree)$sql.=' WHERE version<=2';
        $sql.=' ORDER BY '.implode(',',array_map(__NAMESPACE__.'\\showIdentifier',$t['indexes']['PRIMARY']['columns']));
        $result[$name]=$p->query($sql)->fetchAll();
        same(count($result[$name]),COUNTS[$name],'row_count:'.$name);
    }
    $isin=array_filter($result['m2_asset_identifiers'],fn($v)=>$v['identifier_type']==='isin'&&$v['scope_key']===''&&(int)$v['is_primary']===1);
    same(count($isin),7,'primary_global_isin_count');return $result;
}
function addedValues(PDO $p,array $base,array $expected): void {
    foreach($expected as $name=>$t) {
        if($name==='m2_units'){same((int)$p->query('SELECT COUNT(*) FROM m2_units')->fetchColumn(),0,'unit_catalog_not_empty');continue;}
        $added=array_diff_key($t['columns'],$base[$name]['columns']);if(!$added)continue;
        $wrong=[];foreach($added as $field=>$unused)$wrong[]=qi($field).($field==='route_revision'?'<>1':' IS NOT NULL');
        same((int)$p->query('SELECT COUNT(*) FROM '.qi($name).' WHERE '.implode(' OR ',$wrong))->fetchColumn(),0,'legacy_added_values:'.$name);
    }
}
function autoIncrements(array $structure): array {
    $r=[];foreach($structure['metadata'] as $name=>$v)$r[$name]=$v['table']['AUTO_INCREMENT'];return $r;
}
function sessionState(PDO $p): array {
    return ['qualified'=>preflight($p,false),'server'=>$p->query('SELECT @@global.sql_mode AS sql_mode,@@global.time_zone AS time_zone,@@character_set_server AS charset,@@collation_server AS collation')->fetch()];
}
function state(PDO $p,array $schema,array $base,bool $ledgerThree=false,?string $diagnosticsPath=null): array {
    $environment=sessionState($p);$structure=structure($p,$schema,$diagnosticsPath);$data=snapshot($p,$base,$ledgerThree);
    addedValues($p,$base,$schema);
    return ['environment'=>$environment,'structure'=>$structure,'rows'=>$data,'row_hash'=>dataHash($data),'auto_increment'=>autoIncrements($structure)];
}
function preserve(array $before,array $after): void {
    same($after['environment'],$before['environment'],'server_session_grants_changed');
    same($after['rows'],$before['rows'],'legacy_rows_changed');same($after['row_hash'],$before['row_hash'],'legacy_hash_changed');
}
function restoreArtifact(PDO $p,array $before,array $base): string {
    // A complete private export for an explicitly authorized EMPTY isolated target.
    // No DROP, USE, credential, disabling of FKs, or automatic restore execution.
    $sql="-- Phase 3K pre-state; restore ONLY to a separately authorized empty isolated target.\n";
    foreach($base as $name=>$t)$sql.=$before['structure']['metadata'][$name]['show_create'].";\n";
    foreach($base as $name=>$t)foreach($before['rows'][$name] as $row) {
        $values=[];foreach($row as $key=>$value)$values[]=$value===null?'NULL':($t['columns'][$key]['type']==='binary(32)'?"UNHEX('".$value."')":"CONVERT(UNHEX('".bin2hex((string)$value)."') USING utf8mb4)");
        $sql.='INSERT INTO '.qi($name).' ('.implode(',',array_map(__NAMESPACE__.'\\showIdentifier',array_keys($row))).') VALUES ('.implode(',',$values).");\n";
    }return $sql;
}
function reject(PDO $p,string $sql,int $errno,string $constraint,array &$results): void {
    try {$p->exec($sql);}catch(PDOException $error) {
        same((int)($error->errorInfo[1]??0),$errno,'unit_probe_errno');
        check(str_contains((string)($error->errorInfo[2]??''),$constraint),'unit_probe_constraint');
        check($p->inTransaction(),'unit_probe_transaction');$results[]=['constraint'=>$constraint,'errno'=>$errno,'rejected'=>true];return;
    }throw new \RuntimeException('unit_probe_accepted');
}
function practical(PDO $p,array $before): array {
    $r=[];$p->beginTransaction();
    try {
        $q=$p->prepare('INSERT INTO m2_units (unit_key,unit_version,unit_contract_version,dimension_key,base_unit_key,base_unit_version,monetary_currency_code,scale_numerator,scale_denominator,definition_sha256,status,created_at) VALUES (?,1,?,?,?,?,?,1,?,?,\'frozen\',UTC_TIMESTAMP(6))');
        foreach([['TEST_BASE','monetary','TEST_BASE','GBP',1],['TEST_MINOR','monetary','TEST_BASE','GBP',100],['TEST_POINT','index_point','TEST_POINT',null,1],['TEST_COUNT','quantity','TEST_COUNT',null,1]] as [$key,$dimension,$base,$currency,$denominator])
            $q->execute([$key,'mosa2-market-unit-v1',$dimension,$base,1,$currency,$denominator,hash('sha256','phase3k-synthetic-'.$key,true)]);
        same((int)$p->query('SELECT COUNT(*) FROM m2_units')->fetchColumn(),4,'synthetic_units');
        $r['valid_units']=['base_1_1'=>true,'minor_1_100'=>true,'point_currency_null'=>true,'quantity'=>true];
        $negative=[];
        reject($p,"UPDATE m2_units SET scale_denominator=0 WHERE unit_key='TEST_MINOR'",3819,'ck_units_scale',$negative);
        reject($p,"UPDATE m2_units SET unit_version=0 WHERE unit_key='TEST_MINOR'",3819,'ck_units_versions',$negative);
        $observation=$before['rows']['m2_market_observations'][0];$route=(int)$observation['route_id'];$id=(int)$observation['id'];
        $contract="'mosa2-market-unit-v1'";
        $p->exec("UPDATE m2_asset_source_routes SET unit_contract_version=$contract,quote_unit_key='TEST_BASE',quote_unit_version=1 WHERE id=$route");
        same((int)$p->query("SELECT COUNT(*) FROM m2_asset_source_routes WHERE id=$route AND quote_unit_key='TEST_BASE' AND quote_unit_version=1")->fetchColumn(),1,'valid_route_binding');
        reject($p,"UPDATE m2_asset_source_routes SET quote_unit_key='TEST_UNKNOWN' WHERE id=$route",1452,'fk_routes_quote_unit',$negative);
        reject($p,"UPDATE m2_asset_source_routes SET quote_unit_version=NULL WHERE id=$route",3819,'ck_routes_units',$negative);
        reject($p,"UPDATE m2_asset_source_routes SET quantity_basis_unit_key='TEST_COUNT' WHERE id=$route",3819,'ck_routes_quantity',$negative);
        foreach(['0','-0.00000001'] as $amount)
            reject($p,"UPDATE m2_asset_source_routes SET quantity_basis_unit_key='TEST_COUNT',quantity_basis_unit_version=1,quantity_basis_amount=$amount WHERE id=$route",3819,'ck_routes_quantity',$negative);
        reject($p,"UPDATE m2_asset_source_routes SET route_revision=0 WHERE id=$route",3819,'ck_routes_revision',$negative);
        $volume=$observation['volume']===null?'NULL':"'TEST_COUNT'";$version=$observation['volume']===null?'NULL':'1';
        $p->exec("UPDATE m2_asset_source_routes SET volume_unit_key=$volume,volume_unit_version=$version WHERE id=$route");
        $p->exec("UPDATE m2_market_observations SET observation_format_version=2,unit_contract_version=$contract,quote_unit_key='TEST_BASE',quote_unit_version=1,currency='GBP',volume_unit_key=$volume,volume_unit_version=$version WHERE id=$id");
        same((int)$p->query("SELECT COUNT(*) FROM m2_market_observations o JOIN m2_asset_source_routes r ON r.id=o.route_id WHERE o.id=$id AND o.quote_unit_key=r.quote_unit_key AND o.quote_unit_version=r.quote_unit_version AND o.unit_contract_version=r.unit_contract_version AND o.volume_unit_key<=>r.volume_unit_key AND o.volume_unit_version<=>r.volume_unit_version")->fetchColumn(),1,'valid_observation_binding');
        reject($p,"UPDATE m2_market_observations SET quote_unit_key=NULL WHERE id=$id",3819,'ck_market_observations_units',$negative);
        reject($p,"UPDATE m2_market_observations SET observation_format_version=NULL,unit_contract_version=NULL,quote_unit_key=NULL,quote_unit_version=NULL,volume_unit_key=NULL,volume_unit_version=NULL,currency=NULL WHERE id=$id",3819,'ck_market_observations_units',$negative);
        $r['negative']=$negative;$r['route_observation_binding']=true;
    } finally {if($p->inTransaction())$p->rollBack();}
    $r['rolled_back']=true;return $r;
}
function safeError(Throwable $error): array {
    return $error instanceof PDOException?['kind'=>'database','errno'=>(int)($error->errorInfo[1]??0)]:
        ['kind'=>'guard','reason'=>preg_match('/\A[a-z_0-9:]+\z/',$error->getMessage())?$error->getMessage():'internal_error'];
}
function applyStatements(array $parts,callable $before,callable $execute,callable $after,int $start=0): void {
    same(count($parts),5,'apply_five_statements');
    check($start>=0&&$start<5,'apply_start');
    foreach($parts as $i=>$sql) {if($i<$start)continue;$before($i);$execute($sql,$i);$after($i);}
}
function resumeStatements(array $parts,callable $before,callable $execute,callable $after): void {
    // The first three atomic DDLs are historical facts, never replay them.
    applyStatements($parts,$before,$execute,$after,3);
}
function originalEvidence(string $root): array {
    $report=json_decode(file_get_contents($root.'/original-report.json'),true,512,JSON_THROW_ON_ERROR);
    same($report['migration_sha256'],DIGEST,'resume_original_digest');
    same([$report['ok'],$report['stage'],$report['failure'],$report['restore_ready']],
        [false,'ddl_1',['kind'=>'guard','reason'=>'show_fk:m2_units'],true],'resume_original_stop');
    same(count($report['ddl']),1,'resume_original_ddl_count');
    same([$report['ddl'][0]['table'],$report['ddl'][0]['status'],$report['ddl'][0]['sha256']],
        ['m2_units','executing',hash('sha256',statements(file_get_contents($root.'/0003.sql'))[0])],'resume_original_ddl');
    foreach(['original-pre-state.json'=>'pre_state_sha256','original-restore.sql'=>'restore_sha256'] as $file=>$key)
        check(hash_file('sha256',$root.'/'.$file)===$report[$key],'resume_original_artifact_hash');
    $before=json_decode(file_get_contents($root.'/original-pre-state.json'),true,512,JSON_THROW_ON_ERROR);
    same($before['structure']['counts'],totals(schemas($root,0)),'resume_original_counts');
    same($before['row_hash'],dataHash($before['rows']),'resume_original_row_hash');
    same(count($before['ledger']),2,'resume_original_ledger');
    return $before;
}
function priorEvidence(string $root): array {
    $original=originalEvidence($root);
    $report=json_decode(file_get_contents($root.'/prior-report.json'),true,512,JSON_THROW_ON_ERROR);
    same($report['migration_sha256'],DIGEST,'resume_prior_digest');
    same([$report['ok'],$report['stage'],$report['failure'],$report['restore_ready'],$report['resume_from_ddl']],
        [false,'ddl_3',['kind'=>'guard','reason'=>'unit_check_expression:ck_market_observations_volume'],true,2],'resume_prior_stop');
    same(array_keys($report['ddl']),[1,2],'resume_prior_ddl_set');
    $parts=statements(file_get_contents($root.'/0003.sql'));
    foreach([1=>'validated',2=>'executing'] as $i=>$status)
        same([$report['ddl'][$i]['table'],$report['ddl'][$i]['status'],$report['ddl'][$i]['sha256']],
            [ORDER[$i],$status,hash('sha256',$parts[$i])],'resume_prior_ddl');
    foreach(['prior-pre-state.json'=>'pre_state_sha256','prior-restore.sql'=>'restore_sha256'] as $file=>$key)
        check(hash_file('sha256',$root.'/'.$file)===$report[$key],'resume_prior_artifact_hash');
    $before=json_decode(file_get_contents($root.'/prior-pre-state.json'),true,512,JSON_THROW_ON_ERROR);
    same($before['structure']['counts'],totals(schemas($root,1)),'resume_prior_counts');
    preserve($original,$before);same($before['ledger'],$original['ledger'],'resume_prior_ledger');
    return $original;
}
function run(string $root,string $password): array {
    umask(0077);$resolved=realpath($root);
    check($resolved!==false&&$resolved===$root&&!is_link($root)&&(fileperms($root)&0077)===0,'unit_private_root');
    check(is_file($root.'/form-proof.json')&&!file_exists($root.'/report.json'),'unit_form_proof');
    $marker=fopen($root.'/started.lock','x');check($marker!==false,'unit_already_attempted');fclose($marker);
    $report=['ok'=>false,'migration_sha256'=>DIGEST,'started_at_utc'=>gmdate('c'),'ddl'=>[],'stage'=>'resume_preflight','resume_from_ddl'=>4];$p=null;
    $persist=function()use($root,&$report){save($root.'/report.json',$report);};$persist();
    try {
        $base=schemas($root,0);$parts=statements(file_get_contents($root.'/0003.sql'));
        same(totals($base),['tables'=>16,'columns'=>140,'primary'=>16,'unique'=>9,'secondary'=>26,'foreign_keys'=>23,'checks'=>19],'baseline_totals');
        same(totals(schemas($root)),['tables'=>17,'columns'=>186,'primary'=>17,'unique'=>10,'secondary'=>39,'foreign_keys'=>36,'checks'=>37],'final_totals');
        $original=priorEvidence($root);$resumeSchema=schemas($root,3);
        $p=connection($password);same((int)$p->query("SELECT GET_LOCK('mosa2-phase3k-0003',0)")->fetchColumn(),1,'unit_lock');
        $applyId=$p->query('SELECT CONNECTION_ID()')->fetchColumn();
        // Only the exact post-DDL-3 schema is accepted. Reject any part of
        // DDL 4/5, missing/extra objects, nonempty units or changed legacy data.
        $before=state($p,$resumeSchema,$base,false,$root.'/check-failure.json');preserve($original,$before);
        $oldLedger=ledger($p,2,$original['ledger']);
        $report['resume_preflight']=['ddl_1_3_correct'=>true,'unit_rows'=>0,'legacy_matches_original'=>true,
            'ddl_4_5_absent'=>true,'ledger_versions'=>[1,2],'counts'=>$before['structure']['counts']];
        foreach([['source_id','route_type','external_key'],['asset_id','source_id','route_type']] as $columns) {
            $seen=[];foreach($before['rows']['m2_asset_source_routes'] as $row) {
                $key=jsonBytes(array_map(fn($column)=>$row[$column],$columns));
                check(!isset($seen[$key]),'route_revision_conflict');$seen[$key]=true;
            }
        }
        $before['ledger']=$oldLedger;
        $preBytes=jsonBytes($before);$report['pre_state_sha256']=privateFile($root.'/pre-state.json',$preBytes);
        $exportBefore=$before;$exportBefore['rows']['m2_units']=[];
        $restore=restoreArtifact($p,$exportBefore,$resumeSchema);$report['restore_sha256']=privateFile($root.'/restore-pre-state.sql',$restore);
        $restoreParts=\Mosa2\Phase2\splitSql(preg_replace('/^--[^\n]*$/m','',$restore),';');same(array_pop($restoreParts),'','restore_semicolon');
        same(count($restoreParts),17+array_sum(COUNTS),'restore_complete_statement_count');
        foreach(array_values($resumeSchema) as $i=>$unused)check(str_starts_with($restoreParts[$i],'CREATE TABLE '),'restore_schema_order');
        foreach(array_slice($restoreParts,17) as $part)check(str_starts_with($part,'INSERT INTO '),'restore_data_only');
        $report['restore_ready']=hash_file('sha256',$root.'/pre-state.json')===$report['pre_state_sha256']&&hash_file('sha256',$root.'/restore-pre-state.sql')===$report['restore_sha256'];check($report['restore_ready'],'restore_not_ready');
        privateFile($root.'/restore-plan.json',jsonBytes(['complete_tables'=>17,'complete_rows'=>array_sum(COUNTS),
            'restore_sha256'=>$report['restore_sha256'],'pre_state_sha256'=>$report['pre_state_sha256'],
            'requires'=>'Separate authorization, same qualified runtime, strict/UTC, empty isolated target, FK dependency order, independent readback; no automatic destructive preparation or restore',
            'restore_executed'=>false]));
        $report['preflight_counts']=$before['structure']['counts'];$report['preflight_rows']=array_map('count',$before['rows']);$persist();
        resumeStatements($parts,function(int $i)use($p,$root,$base,$before,$oldLedger,&$report,$persist) {
            // Recheck before each nonrollbackable DDL; never retry or repair.
            $pre=state($p,schemas($root,$i),$base,false,$root.'/check-failure.json');preserve($before,$pre);ledger($p,2,$oldLedger);
            $report['stage']='ddl_'.($i+1);$report['ddl'][$i]=['table'=>ORDER[$i],'status'=>'executing'];$persist();
        },function(string $sql,int $i)use($p,&$report,$persist) {
            $report['ddl'][$i]['sha256']=hash('sha256',$sql);$persist();$p->exec($sql);
        },function(int $i)use($p,$root,$base,$before,$oldLedger,&$report,$persist) {
            $post=state($p,schemas($root,$i+1),$base,false,$root.'/check-failure.json');preserve($before,$post);ledger($p,2,$oldLedger);
            privateFile($root.'/after-ddl-'.($i+1).'.json',jsonBytes($post));
            $report['ddl'][$i]['status']='validated';$report['ddl'][$i]['counts']=$post['structure']['counts'];$persist();
        });
        $report['stage']='constraint_tests';$persist();$report['practical']=practical($p,$before);
        $post=state($p,schemas($root),$base,false,$root.'/check-failure.json');preserve($before,$post);ledger($p,2,$oldLedger);
        $report['post_state_sha256']=privateFile($root.'/post-state-before-ledger.json',jsonBytes($post));
        $report['auto_increment_before']=$before['auto_increment'];$report['auto_increment_after']=$post['auto_increment'];
        $report['stage']='ledger_transaction';$persist();
        $p->beginTransaction();
        try {
            $q=$p->prepare("INSERT INTO m2_schema_migrations (version,migration_key,checksum,applied_at) VALUES (3,'0003_market_units',?,UTC_TIMESTAMP(6))");$q->execute([hex2bin(DIGEST)]);
            $report['ledger_before_commit']=ledger($p,3,$oldLedger);$p->commit();
        }catch(Throwable $error){if($p->inTransaction())$p->rollBack();throw $error;}
        $report['stage']='independent_readback';$persist();$finals=[];$ids=[$applyId];
        for($n=1;$n<=2;$n++) {
            $independent=connection($password);$ids[]=$independent->query('SELECT CONNECTION_ID()')->fetchColumn();
            $end=state($independent,schemas($root),$base,true,$root.'/check-failure.json');preserve($before,$end);
            $end['ledger']=ledger($independent,3,$oldLedger);$independent=null;
            $finals[]=$end;$report['end_state_sha256_'.$n]=privateFile($root.'/end-state-'.$n.'.json',jsonBytes($end));
        }
        same(count(array_unique($ids)),3,'independent_connections');same($finals[0],$finals[1],'independent_state_changed');
        same($report['end_state_sha256_1'],$report['end_state_sha256_2'],'end_hash_changed');
        $report['counts']=$finals[1]['structure']['counts'];$report['ledger']=$finals[1]['ledger'];
        $report['legacy_unchanged']=true;$report['independent_readbacks']=2;$report['unit_rows']=0;
        $report['ok']=true;$report['stage']='complete';
    } catch(Throwable $error) {
        if($p instanceof PDO&&$p->inTransaction())$p->rollBack();
        $report['failure']=safeError($error);
        // Capture actual partial state without issuing any further DDL or ledger write.
        if($p instanceof PDO)try {
            $partial=[];foreach(\Mosa2\Phase2\tables($p) as $name)
                $partial[$name]=$p->query('SHOW CREATE TABLE '.qi($name))->fetch(PDO::FETCH_NUM)[1];
            privateFile($root.'/partial-schema.json',jsonBytes($partial));
        }catch(Throwable $unused){$report['partial_capture_failed']=true;}
    } finally {
        if($p instanceof PDO)try{$p->query("SELECT RELEASE_LOCK('mosa2-phase3k-0003')");}catch(Throwable $unused){}
        $p=null;unset($password);$report['finished_at_utc']=gmdate('c');$persist();
    }
    return $report;
}
