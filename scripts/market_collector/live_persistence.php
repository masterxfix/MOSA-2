<?php
declare(strict_types=1);
namespace Mosa2\MarketLive;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,qi,connection};
use function Mosa2\MarketIdentity\{planAssetIdentity,planMarketRoute,applyAssetIdentityPlan,applyMarketRoutePlan,matchFields};
require_once __DIR__.'/onboarding.php';
require_once __DIR__.'/../phase3o/live_writer.php';

function strings(array $row): array {foreach($row as &$v)if($v!==null)$v=(string)$v;unset($v);return $row;}
function snapshot(PDO $p,array $contract=[]): array {
    $tables=array_merge(\Mosa2\Phase2\TABLES,\Mosa2\Phase3B\MARKET,['m2_units']);sort($tables);
    same(\Mosa2\Phase2\tables($p),$tables,'table_set');$out=[];
    foreach($tables as $t){
        $cols=$p->query('SHOW COLUMNS FROM '.qi($t))->fetchAll();$select=[];
        foreach($cols as $c)$select[]=(str_starts_with(strtolower($c['Type']),'binary(')?'HEX('.qi($c['Field']).')':qi($c['Field'])).' AS '.qi($c['Field']);
        $keys=$p->query('SHOW KEYS FROM '.qi($t)." WHERE Key_name='PRIMARY'")->fetchAll();check($keys!==[],'primary_key');
        $out[$t]=array_map(__NAMESPACE__.'\\strings',$p->query('SELECT '.implode(',',$select).' FROM '.qi($t).' ORDER BY '.implode(',',array_map(static fn($k)=>qi($k['Column_name']),$keys)))->fetchAll());
    }
    if(($contract['allow_current']??false)!==true)same($out['m2_market_current'],[],'current_nonempty');same($out['m2_market_bars'],[],'bars_nonempty');
    $versions=['1','2','3'];
    if(($contract['schema_version']??3)===4)$versions[]='4';
    else same($contract['schema_version']??3,3,'schema_contract');
    same(count($out['m2_units']),4,'four_units');same(array_column($out['m2_schema_migrations'],'version'),$versions,'ledger_versions');
    $digests=[\Mosa2\Phase2\DIGEST,\Mosa2\Phase3B\DIGEST,\Mosa2\Phase3K\DIGEST];
    if(count($versions)===4)$digests[]=hash_file('sha256',dirname(__DIR__,2).'/docs/database/migrations/0004_current_observation_provenance.sql');
    foreach($out['m2_schema_migrations'] as $i=>$row)same(strtolower($row['checksum']),$digests[$i],'ledger_checksum');
    $seed=json_decode(file_get_contents(dirname(__DIR__,2).'/docs/database/seeds/0001_market_units_v1.json'),true,32,JSON_THROW_ON_ERROR);
    foreach($seed['definitions'] as $d){$rows=array_values(array_filter($out['m2_units'],static fn($r)=>$r['unit_key']===$d['unit_key']&&$r['unit_version']===$d['unit_version']));same(count($rows),1,'seed_binding');
        foreach($d as $k=>$v)if($k!=='definition_reference')check(array_key_exists($k,$rows[0])&&($k==='definition_sha256'?strtolower($rows[0][$k])===$v:$rows[0][$k]===$v),'seed_definition');}
    return $out;
}
function completePlan(array $state,array $m): array {
    $policy=$m['policy']??'ONBOARD_NEW_ROUTE';check(in_array($policy,['ONBOARD_NEW_ROUTE','USE_EXISTING_ROUTE'],true),'live_policy');
    $asset=planAssetIdentity($state,$m['identity']);check($asset['decision']!=='CONFLICT','asset_plan_conflict');
    if($policy==='USE_EXISTING_ROUTE')same($asset['decision'],'EXISTING_MATCH','existing_asset_required');
    $c=\Mosa2\Phase3D\candidate($m['route_evidence']);$key=$c['proposed_source_key'];
    $sources=array_values(array_filter($state['m2_sources'],static fn($r)=>$r['source_key']===$key));same(count($sources),1,'qualified_source');
    check(matchFields($sources[0],['source_type'=>'market_data','enabled'=>1]),'source_semantics');
    same($m['identity']['normalized_value'],$m['route_evidence']['row']['isin'],'asset_route_identity');
    same($m['instrument'],$m['identity']['normalized_value'],'request_identity');
    $unit=$m['unit_binding'];$unitRows=array_values(array_filter($state['m2_units'],static fn($r)=>matchFields($r,['unit_key'=>$unit['quote_unit_key'],'unit_version'=>$unit['quote_unit_version'],'unit_contract_version'=>$unit['unit_contract_version']])));same(count($unitRows),1,'quote_unit_exists');
    same($unitRows[0]['monetary_currency_code'],$m['route_evidence']['row']['currency'],'quote_currency');
    $qualified=['asset_id'=>$asset['asset_id'],'source_id'=>$sources[0]['id'],'route_type'=>'quote','priority'=>0,'enabled'=>0,'evidence'=>$m['route_evidence']];
    $route=planMarketRoute($state['m2_asset_source_routes'],$qualified,$unit);
    same($route['decision'],$policy==='USE_EXISTING_ROUTE'?'EXISTING_MATCH':'CREATE_REVISION','policy_route_required');
    return ['policy'=>$policy,'asset'=>$asset,'source'=>['decision'=>'EXISTING_MATCH','source_id'=>$sources[0]['id']],
        'qualified_route'=>$qualified,'route'=>$route,'unit_binding'=>$unit,
        'provider_request'=>['adapter_module'=>$m['adapter_module'],'adapter_class'=>$m['adapter_class'],'instrument'=>$m['instrument'],'count'=>1],
        'writer_path'=>'Collector/Adapter/Normalizer/Phase3N INSERT; stored DUPLICATE_UNCHANGED',
        'deltas'=>$asset['deltas']+['m2_asset_source_routes'=>$policy==='USE_EXISTING_ROUTE'?0:1,'m2_market_observations'=>1]];
}
function bridge(array $config,array $request): array {
    $p=proc_open([$config['python'],$config['project'].'/scripts/market_collector/live_bridge.py'],[0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes,$config['project'],
        ['PATH'=>$config['runtime_path'],'PYTHONDONTWRITEBYTECODE'=>'1']);check(is_resource($p),'bridge_process');
    $wire=json_encode($request,JSON_THROW_ON_ERROR);check(fwrite($pipes[0],$wire)===strlen($wire),'bridge_input');fclose($pipes[0]);
    $out=stream_get_contents($pipes[1]);$err=stream_get_contents($pipes[2]);fclose($pipes[1]);fclose($pipes[2]);same(proc_close($p),0,'bridge_exit');same($err,'','bridge_stderr');
    $reply=json_decode($out,true,512,JSON_THROW_ON_ERROR);check(($reply['ok']??false)===true,'bridge_'.$request['action']);return $reply;
}
function routeBinding(array $r): array {return array_intersect_key($r,array_flip(array_merge(['id','asset_id','source_id','route_revision'],\Mosa2\MarketIdentity\UNIT_FIELDS)));}
function existing(array $rows): array {
    $out=[];foreach($rows as $r){$version=$r['observation_format_version']===null?1:(int)$r['observation_format_version'];
        $fields=$version===1?\Mosa2\Phase3O\CORE:array_merge(\Mosa2\Phase3O\CORE,\Mosa2\Phase3O\UNITS);
        $out[]=['format_version'=>$version,'payload'=>array_intersect_key($r,array_flip($fields)),'dedupe_key'=>['$bytes'=>base64_encode(hex2bin($r['dedupe_key']))]];
    }return $out;
}
function compareDelta(array $before,array $after,array $plan,array $inserted): void {
    foreach($plan['deltas'] as $t=>$n){same(count($after[$t]),count($before[$t])+$n,'delta_'.$t);
        $old=[];foreach($before[$t] as $r)$old[$r[$t==='m2_assets'?'entity_id':'id']]=$r;
        $new=[];foreach($after[$t] as $r){$key=$r[$t==='m2_assets'?'entity_id':'id'];if(isset($old[$key]))same($r,$old[$key],'old_fact_changed');else $new[]=$r;}
        same($new,$inserted[$t]??[],'exact_new_rows');$after[$t]=$before[$t];
    }same($after,$before,'unplanned_delta');
}
/** One read-only plan, one provider acquisition, one atomic business transaction, one independent readback. */
function proofRun(string $privateRoot,string $password,array $config,array $manifest): array {
    $capture=static fn(PDO $db)=>snapshot($db,$config['state_contract']??[]);
    $r=['ok'=>false,'stage'=>'preflight','database_connections'=>0,'provider_requests'=>0,'committed'=>false,'rollback'=>null];
    $p=null;$locked=false;$baseline=null;$plan=null;$inserted=[];$lockKey=null;
    try {
        $r['database_connections']++;$p=connection($password);
        $lockKey='m2-live:'.substr(hash('sha256',\Mosa2\Phase3D\json(\Mosa2\MarketIdentity\identifierKey($manifest['identity']))),0,48);
        $q=$p->prepare('SELECT GET_LOCK(?,0)');$q->execute([$lockKey]);$locked=(int)$q->fetchColumn()===1;check($locked,'identifier_lock_busy');
        $p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
        try{$baseline=$capture($p);$plan=completePlan($baseline,$manifest);
            $indexes=[];foreach($p->query('SHOW INDEX FROM m2_asset_source_routes')->fetchAll() as $index)if((int)$index['Non_unique']===0)$indexes[$index['Key_name']][]=$index['Column_name'];
            check(in_array(['source_id','route_type','external_key','route_revision'],$indexes,true)&&in_array(['asset_id','source_id','route_type','route_revision'],$indexes,true),'route_unique_contracts');
        }finally{if($p->inTransaction())$p->rollBack();}
        $r['stage']='provider';$acquired=bridge($config,['action'=>'fetch','private_root'=>$privateRoot,'php_cli'=>$config['php']]);$r['provider_requests']=1;
        $r['stage']='transaction';$p->beginTransaction();
        try {
            same($capture($p),$baseline,'preflight_drift');same(completePlan($baseline,$manifest),$plan,'plan_drift');
            $now=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');$store=new \Mosa2\MarketIdentity\PdoStore($p);
            $asset=applyAssetIdentityPlan($store,$plan['asset'],$now);$route=strings(applyMarketRoutePlan($store,$plan['route'],$asset['asset_id'],$now));$binding=routeBinding($route);
            $writer=bridge($config,['action'=>'plan','acquired'=>$acquired,'route'=>$binding,'created_at'=>$now,'existing'=>existing($baseline['m2_market_observations']),'allow_duplicate'=>($config['allow_duplicate']??false)===true])['plan'];
            $r['writer']=$writer['decision'];
            if($writer['decision']==='INSERT'){
                \Mosa2\Phase3O\executePlan($p,$writer,$binding,$now);$observationId=$p->lastInsertId();
            }else{
                same($config['allow_duplicate']??false,true,'duplicate_not_approved');same($writer['decision'],'DUPLICATE_UNCHANGED','writer_decision');
                $key=strtoupper(bin2hex(base64_decode($writer['dedupe_key']['$bytes'],true)));
                $old=array_values(array_filter($baseline['m2_market_observations'],static fn($row)=>$row['dedupe_key']===$key));same(count($old),1,'duplicate_origin');
                $observationId=$old[0]['id'];$plan['deltas']['m2_market_observations']=0;
            }
            $r['observation_id']=$observationId;
            $state=$capture($p);$rows=array_values(array_filter($state['m2_market_observations'],static fn($row)=>$row['id']===$observationId));same(count($rows),1,'observation_readback');$observation=$rows[0];
            if($writer['decision']==='INSERT'){$expected=\Mosa2\Phase3O\insertValues($writer,$binding,$now);$expected['dedupe_key']=strtoupper(bin2hex($expected['dedupe_key']));same($observation,['id'=>$observationId]+strings($expected),'observation_exact');}
            else same(array_intersect_key($observation,$writer['normalized']),strings($writer['normalized']),'duplicate_payload');
            $stored=array_intersect_key($observation,array_flip(array_merge(\Mosa2\Phase3O\CORE,\Mosa2\Phase3O\UNITS)));
            $replay=bridge($config,['action'=>'replay','route'=>$binding,'stored'=>$stored,'created_at'=>$now,'existing'=>existing($state['m2_market_observations'])])['plan'];
            same($replay['decision'],'DUPLICATE_UNCHANGED','replay');same($replay['canonical_bytes'],$writer['canonical_bytes'],'replay_canonical');same($replay['dedupe_key'],$writer['dedupe_key'],'replay_key');
            foreach($plan['deltas'] as $t=>$delta){$pk=$t==='m2_assets'?'entity_id':'id';$oldIds=array_column($baseline[$t],$pk);$inserted[$t]=array_values(array_filter($state[$t],static fn($row)=>!in_array($row[$pk],$oldIds,true)));}
            compareDelta($baseline,$capture($p),$plan,$inserted);same($p->commit(),true,'commit');$r['committed']=true;
            $r+=['observation_id'=>$observationId,'policy'=>$plan['policy'],'asset_plan'=>$plan['asset']['decision'],'route_plan'=>$plan['route']['decision'],'route_revision'=>$plan['route']['row']['route_revision'],'writer'=>$writer['decision'],'replay'=>'DUPLICATE_UNCHANGED','deltas'=>$plan['deltas']];
        }catch(Throwable $e){if($p->inTransaction())$r['rollback']=$p->rollBack();throw $e;}
    }catch(Throwable $e){$r['failure']=$e->getMessage();}
    finally {
        $r['provider_requests']=is_file($privateRoot.'/provider-consumed.lock')?1:0;
        if($locked&&$p!==null){try{$q=$p->prepare('SELECT RELEASE_LOCK(?)');$q->execute([$lockKey]);same((int)$q->fetchColumn(),1,'lock_release');}catch(Throwable $e){$r['cleanup_failure']=$e->getMessage();}}
        $p=null;
        if($baseline!==null&&($r['committed']||$r['rollback']===true)){
            if($r['committed'])$r['stage']='readback';
            try{$r['database_connections']++;$read=connection($password);$read->exec('SET TRANSACTION READ ONLY');$read->beginTransaction();
                try{$after=$capture($read);if($r['committed'])compareDelta($baseline,$after,$plan,$inserted);else same($after,$baseline,'rollback_delta');}
                finally{if($read->inTransaction())$read->rollBack();$read=null;}
                $r['readback']='PASS';$r['private_evidence']=['plan'=>$plan,'baseline'=>$baseline,'after'=>$after,'inserted'=>$inserted,'writer'=>$writer??null];
            }catch(Throwable $e){$r['readback_failure']=$e->getMessage();}
        }
        unset($password);$r['ok']=$r['committed']&&($r['readback']??null)==='PASS'&&!isset($r['failure'])&&!isset($r['cleanup_failure'])&&!isset($r['readback_failure']);
    }return $r;
}
require_once __DIR__.'/runtime_persistence.php';
/** Exhaustive evidence is an explicit test/proof operation, never the runtime default. */
function run(string $privateRoot,string $password,array $config,array $manifest): array {
    $mode=$config['verification_mode']??'runtime';check(in_array($mode,['runtime','proof'],true),'verification_mode');
    if($mode==='proof')return proofRun($privateRoot,$password,$config,$manifest);
    $consumed=is_file($privateRoot.'/provider-consumed.lock');
    try{$result=runtimeRun($privateRoot,$config,$manifest,static fn()=>connection($password),__NAMESPACE__.'\\bridge');
        $result['provider_requests']=!$consumed&&is_file($privateRoot.'/provider-consumed.lock')?1:0;return $result;}
    finally{unset($password);}
}
