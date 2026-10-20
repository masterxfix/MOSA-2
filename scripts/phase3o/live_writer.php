<?php
declare(strict_types=1);
namespace Mosa2\Phase3O;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,qi,save,connection};
require_once __DIR__.'/state_integrity.php';

const CORE=['asset_id','source_id','route_id','currency','market_at','observed_at','price','bid','ask','volume'];
const UNITS=['unit_contract_version','quote_unit_key','quote_unit_version','quantity_basis_unit_key',
    'quantity_basis_unit_version','quantity_basis_amount','volume_unit_key','volume_unit_version'];
const CREATED='2001-01-01 00:00:02.000000';
const NS='phase3o-synthetic';

function byteValue(mixed $value): string {
    check(is_array($value)&&array_keys($value)===['$bytes']&&is_string($value['$bytes']),'byte_transport');
    $bytes=base64_decode($value['$bytes'],true);
    check(is_string($bytes)&&base64_encode($bytes)===$value['$bytes'],'canonical_base64');return $bytes;
}
function writerPlans(string $root,array $request,string $runtimePath): array {
    $project=dirname($root,2);$input=json_encode($request,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
    $process=proc_open(['python3',$project.'/scripts/phase3o/live_plan.py'],
        [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes,$project,
        ['PATH'=>$runtimePath,'PYTHONDONTWRITEBYTECODE'=>'1']);
    check(is_resource($process),'writer_process');
    check(fwrite($pipes[0],$input)===strlen($input),'writer_stdin');fclose($pipes[0]);
    $out=stream_get_contents($pipes[1]);$error=stream_get_contents($pipes[2]);
    fclose($pipes[1]);fclose($pipes[2]);$exit=proc_close($process);
    check($exit===0&&$error==='','writer_runtime');
    $reply=json_decode($out,true,512,JSON_THROW_ON_ERROR);
    check(($reply['ok']??false)===true&&is_array($reply['plans']??null),'writer_reply');
    same(count($reply['plans']),count($request['observations']),'writer_plan_count');return $reply['plans'];
}
function insertValues(array $plan,array $route,string $created=CREATED): array {
    same($plan['decision']??null,'INSERT','insert_decision');
    same($plan['observation_format_version']??null,2,'insert_format');
    same($plan['catalog_fingerprint']??null,\Mosa2\Phase3M\PACKAGE,'insert_catalog');
    $fields=array_merge(CORE,UNITS);$columns=array_merge($fields,['observation_format_version','dedupe_key','created_at']);
    same($plan['expected_db_columns']??null,$columns,'insert_columns');
    $values=$plan['db_values']??[];same(array_keys($values),$columns,'insert_value_columns');
    $canonical=byteValue($plan['canonical_bytes']);$key=byteValue($plan['dedupe_key']);
    same(strlen($key),32,'insert_key_length');same(hash('sha256',$canonical,true),$key,'insert_key_hash');
    check(str_starts_with($canonical,"mosa2-observation-v2\n"),'insert_domain');
    $payload=json_decode(substr($canonical,strlen("mosa2-observation-v2\n")),true,512,JSON_THROW_ON_ERROR);
    same(array_keys($payload),$fields,'insert_canonical_fields');same($payload,$plan['normalized'],'insert_payload');
    foreach($fields as $field){
        check($values[$field]===null||is_string($values[$field]),'insert_native_type');
        same($values[$field],$payload[$field],'insert_value');
    }
    same($values['observation_format_version'],2,'insert_marker');
    check(preg_match('/\A[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}\z/D',$created)===1,'insert_created_format');
    same($values['created_at'],$created,'insert_created');same(byteValue($values['dedupe_key']),$key,'insert_value_key');
    same($plan['route_binding']['matched_fields'],$route,'insert_route_snapshot');
    same($plan['route_binding']['format_version'],2,'insert_route_format');
    same($plan['route_binding']['route_revision'],$route['route_revision'],'insert_route_revision');
    same($plan['route_binding']['route_id'],$route['id'],'insert_route_id');
    foreach(['asset_id','source_id'] as $field)same($values[$field],$route[$field],'insert_identity');
    same($values['route_id'],$route['id'],'insert_route');
    foreach(UNITS as $field)same($values[$field],$route[$field],'insert_unit');
    $values['dedupe_key']=$key;return $values;
}
function executePlan(PDO $p,array $plan,array $route,string $created=CREATED): void {
    check($p->inTransaction(),'insert_transaction');$values=insertValues($plan,$route,$created);
    $q=$p->prepare('INSERT INTO m2_market_observations ('.implode(',',array_map(__NAMESPACE__.'\\column',array_keys($values))).') VALUES ('.implode(',',array_fill(0,count($values),'?')).')');
    $q->execute(array_values($values));same($q->rowCount(),1,'one_observation');
}
function column(string $value): string {return qi($value);}
function transactionState(): array {
    return array_fill_keys(['transaction_started','rollback_attempted','rollback_call_succeeded',
        'rollback_transaction_closed','post_rollback_readback_1_confirmed','post_rollback_readback_2_confirmed'],false);
}
function completeReport(array $report): bool {
    foreach(transactionState() as $key=>$unused)if(($report[$key]??false)!==true)return false;
    return !isset($report['failure'])&&!isset($report['readback_failure'])&&!isset($report['cleanup_failure'])
        &&($report['transaction']['observation_inserts']??0)===4&&($report['lock_released']??false);
}
function rollbackTransaction(PDO $p,callable $body,?array &$report=null): mixed {
    $report??=transactionState();
    check(!$p->inTransaction(),'outer_transaction');check($p->beginTransaction(),'transaction_begin');$report['transaction_started']=true;
    try{return $body();}finally{
        check($p->inTransaction(),'transaction_lost');$report['rollback_attempted']=true;
        try{$report['rollback_call_succeeded']=$p->rollBack();}
        finally{$report['rollback_transaction_closed']=!$p->inTransaction();}
        check($report['rollback_call_succeeded']&&$report['rollback_transaction_closed'],'rollback_failed');
    }
}
function preparedInsert(PDO $p,string $table,array $row): string {
    check($p->inTransaction(),'graph_transaction');
    check(in_array($table,['m2_entities','m2_assets','m2_sources','m2_asset_source_routes'],true),'graph_table');
    $q=$p->prepare('INSERT INTO '.qi($table).' ('.implode(',',array_map(__NAMESPACE__.'\\column',array_keys($row))).') VALUES ('.implode(',',array_fill(0,count($row),'?')).')');
    $q->execute(array_values($row));same($q->rowCount(),1,'graph_one');return $p->lastInsertId();
}
function requestFor(array $routes,array $observations,array $existing=[]): array {
    return ['routes'=>$routes,'observations'=>$observations,'existing'=>$existing,'created_at'=>CREATED,
        'format_version'=>2,'intent'=>'NEW_NATIVE_V2','representation'=>'native'];
}
function wireKey(string $key): array {same(strlen($key),32,'stored_key_length');return ['$bytes'=>base64_encode($key)];}
function graph(PDO $p,array $unitRows): array {
    $source=preparedInsert($p,'m2_sources',['source_key'=>NS.'-source','source_type'=>'synthetic',
        'display_name'=>NS.' source','base_url'=>null,'enabled'=>0,'created_at'=>CREATED,'updated_at'=>CREATED]);
    $routes=[];$observations=[];
    foreach($unitRows as $i=>$unit){
        $name=NS.'-'.($i+1);
        $entity=preparedInsert($p,'m2_entities',['entity_type'=>'synthetic','canonical_name'=>$name,'status'=>'active','created_at'=>CREATED,'updated_at'=>CREATED]);
        preparedInsert($p,'m2_assets',['entity_id'=>$entity,'asset_class'=>'synthetic','display_name'=>$name,'base_currency'=>null,'status'=>'active','created_at'=>CREATED,'updated_at'=>CREATED]);
        $binding=['unit_contract_version'=>$unit['unit_contract_version'],'quote_unit_key'=>$unit['unit_key'],
            'quote_unit_version'=>$unit['unit_version'],'quantity_basis_unit_key'=>null,'quantity_basis_unit_version'=>null,
            'quantity_basis_amount'=>null,'volume_unit_key'=>null,'volume_unit_version'=>null];
        $id=preparedInsert($p,'m2_asset_source_routes',['asset_id'=>$entity,'source_id'=>$source,'route_type'=>NS,
            'external_key'=>$name,'priority'=>1,'enabled'=>0,'created_at'=>CREATED,'updated_at'=>CREATED,'route_revision'=>'1']+$binding);
        $q=$p->prepare('SELECT id,asset_id,source_id,route_revision,'.implode(',',array_map(__NAMESPACE__.'\\column',UNITS)).' FROM m2_asset_source_routes WHERE id=?');$q->execute([$id]);$route=$q->fetch();
        foreach($route as &$v)if($v!==null)$v=(string)$v;unset($v);
        same($route,['id'=>$id,'asset_id'=>$entity,'source_id'=>$source,'route_revision'=>'1']+$binding,'graph_readback');
        $routes[]=['format_version'=>2,'route'=>$route];
        $observations[]=['asset_id'=>$entity,'source_id'=>$source,'route_id'=>$id,'currency'=>$unit['monetary_currency_code'],
            'market_at'=>'2001-01-01 00:00:00','observed_at'=>'2001-01-01 00:00:01','price'=>'42.125','bid'=>null,'ask'=>null,'volume'=>null]+$binding;
    }
    return requestFor($routes,$observations);
}
function transactionProof(PDO $p,string $root,array $units,string $phpCli,array &$report): array {
    return rollbackTransaction($p,function()use($p,$root,$units,$phpCli){
        $request=graph($p,$units);$plans=writerPlans($root,$request,$phpCli);$snapshots=[];$proof=[];
        foreach($plans as $i=>$plan){
            executePlan($p,$plan,$request['routes'][$i]['route']);
            $q=$p->prepare('SELECT * FROM m2_market_observations WHERE id=?');$q->execute([$p->lastInsertId()]);$row=$q->fetch();
            same((int)$row['observation_format_version'],2,'readback_format');
            same($row['dedupe_key'],byteValue($plan['dedupe_key']),'readback_key');
            same($row['created_at'],CREATED,'readback_created');$payload=[];
            foreach(array_merge(CORE,UNITS) as $field)$payload[$field]=$row[$field]===null?null:(string)$row[$field];
            same($payload,$plan['normalized'],'readback_values');
            $snapshots[]=['format_version'=>2,'payload'=>$payload,'dedupe_key'=>wireKey($row['dedupe_key'])];
            $single=requestFor([$request['routes'][$i]],[$payload],[$snapshots[$i]]);
            $duplicate=writerPlans($root,$single,$phpCli)[0];same($duplicate['decision'],'DUPLICATE_UNCHANGED','duplicate');
            same($duplicate['canonical_bytes'],$plan['canonical_bytes'],'canonical_parity');same($duplicate['dedupe_key'],$plan['dedupe_key'],'dedupe_parity');
            $conflict=$single;$conflict['existing'][0]['payload']['price']='99.0000000000';
            same(writerPlans($root,$conflict,$phpCli)[0]['decision'],'CONFLICT','conflict');
            $proof[]=['unit'=>$payload['quote_unit_key'],'insert'=>true,'readback'=>true,'canonical_parity'=>true,'dedupe_parity'=>true,'duplicate'=>true,'conflict'=>true];
        }
        $rejects=[];
        foreach(['route_unit','point_currency','gbx_currency','legacy_route','volume','quantity','derived'] as $case){
            $index=0;foreach($snapshots as $i=>$s){if(($case==='point_currency'&&$s['payload']['currency']===null)||($case==='gbx_currency'&&$s['payload']['quote_unit_key']==='GBX'))$index=$i;}
            $req=requestFor([$request['routes'][$index]],[$snapshots[$index]['payload']],[$snapshots[$index]]);
            if($case==='route_unit')foreach(['quote_unit_key','quote_unit_version'] as $f)$req['routes'][0]['route'][$f]=$snapshots[($index+1)%4]['payload'][$f];
            if($case==='point_currency')$req['observations'][0]['currency']='EUR';
            if($case==='gbx_currency')$req['observations'][0]['currency']='GBX';
            if($case==='legacy_route'){$req['routes'][0]['format_version']=1;foreach(UNITS as $f)$req['routes'][0]['route'][$f]=null;}
            if($case==='volume')$req['observations'][0]['volume']='1';
            if($case==='quantity')$req['observations'][0]['quantity_basis_unit_key']=$req['observations'][0]['quote_unit_key'];
            if($case==='derived')$req['representation']='derived';
            same(writerPlans($root,$req,$phpCli)[0]['decision'],'REJECT','reject:'.$case);$rejects[$case]=true;
        }
        save($root.'/in-transaction.json',['plans'=>$plans,'snapshots'=>$snapshots,'proof'=>$proof,'rejects'=>$rejects]);
        return ['units'=>$proof,'rejects'=>$rejects,'synthetic_inserts'=>17,'observation_inserts'=>4];
    },$report);
}
function run(string $root,string $password): array {
    $config=require $root.'/access.php';$report=['ok'=>false,'stage'=>'start']+transactionState();$p=null;$locked=false;$baseline=null;
    $lock=fopen($root.'/started.lock','x');check($lock!==false&&flock($lock,LOCK_EX|LOCK_NB),'one_shot_lock');chmod($root.'/started.lock',0600);
    try {
        requireCapability($root,$config);
        $p=connection($password);$report['stage']='baseline';$baseline=checkedState($p,$root,historicalState($root));
        save($root.'/baseline-live.json',$baseline);$report['baseline_hash']=stateHash($baseline);
        $report['structural_counter_tables']=count(\Mosa2\Phase3M\counterColumns($baseline['structure']));
        $q=$p->prepare('SELECT GET_LOCK(?,0)');$q->execute(['mosa2_phase3o_synthetic']);$locked=(int)$q->fetchColumn()===1;check($locked,'live_lock');
        requireCapability($root,$config);
        $report['stage']='transaction';$report['transaction']=transactionProof($p,$root,$baseline['units'],$config['runtime_path'],$report);
    }catch(Throwable $e){$report['failure']=\Mosa2\Phase3K\safeError($e);}
    finally {
        // No rollback retry: the transaction helper owns the single attempt.
        try{if($locked){$q=$p->prepare('SELECT RELEASE_LOCK(?)');$q->execute(['mosa2_phase3o_synthetic']);$report['lock_released']=(int)$q->fetchColumn()===1;}}
        catch(Throwable $e){$report['cleanup_failure']=\Mosa2\Phase3K\safeError($e);}
        $p=null;
        if($baseline!==null){
            try{
                foreach([1,2] as $i){
                    $read=connection($password);
                    try{$state=checkedState($read,$root,$baseline);}finally{$read=null;}
                    same(stateHash($state),$report['baseline_hash'],'post_readback_hash');
                    save($root.'/readback-'.$i.'.json',$state);$report['readback_hashes'][]=stateHash($state);
                    $report['post_rollback_readback_'.$i.'_confirmed']=true;
                }
            }catch(Throwable $e){$report['readback_failure']=\Mosa2\Phase3K\safeError($e);}
        }
        unset($password);
        $report['ok']=completeReport($report);
        $report['stage']=$report['ok']?'complete':'stopped';save($root.'/report.json',$report);flock($lock,LOCK_UN);fclose($lock);
    }
    return $report;
}
