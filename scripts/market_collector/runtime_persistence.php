<?php
declare(strict_types=1);
namespace Mosa2\MarketLive;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,qi};

/** Bounded catalog lookups; excess/ambiguous scope fails closed, never truncates silently. */
class RuntimeStore extends \Mosa2\MarketIdentity\PdoStore {
    public function __construct(private PDO $db){parent::__construct($db);}
    public function find(string $table,array $where): array {
        check(in_array($table,\Mosa2\MarketIdentity\CATALOG_TABLES,true)&&$where!==[],'runtime_read_scope');
        return boundedRows($this->db,'SELECT * FROM '.qi($table).' WHERE '.implode(' AND ',array_map(static fn($k)=>qi($k).' <=> ?',array_keys($where))).' LIMIT 33',array_values($where),32);
    }
    public function insert(string $table,array $values): string {throw new \RuntimeException('runtime_catalog_write_forbidden');}
}
function boundedRows(PDO $p,string $sql,array $args,int $maximum): array {
    $q=$p->prepare($sql);$q->execute($args);$rows=array_map(__NAMESPACE__.'\\strings',$q->fetchAll(PDO::FETCH_ASSOC));
    check(count($rows)<=$maximum,'runtime_scope_overflow');return $rows;
}
/** Fresh metadata at every checkpoint; no cross-call, transaction or batch cache. */
function runtimeMetadata(PDO $p): array {
    $sql="SELECT 'table' AS runtime_kind,TABLE_NAME AS table_name,NULL AS non_unique,NULL AS key_name,NULL AS seq_in_index,NULL AS column_name"
        ." FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE()"
        ." UNION ALL SELECT 'index',TABLE_NAME,NON_UNIQUE,INDEX_NAME,SEQ_IN_INDEX,COLUMN_NAME"
        ." FROM information_schema.statistics WHERE TABLE_SCHEMA=DATABASE()"
        ." AND TABLE_NAME IN ('m2_asset_source_routes','m2_market_observations','m2_asset_identifiers')";
    $tables=[];$indexes=[];
    foreach($p->query($sql)->fetchAll(PDO::FETCH_ASSOC) as $row){
        if($row['runtime_kind']==='table')$tables[]=$row['table_name'];
        else{
            same($row['runtime_kind'],'index','runtime_metadata_kind');
            $indexes[$row['table_name']][]=['Non_unique'=>$row['non_unique'],'Key_name'=>$row['key_name'],
                'Seq_in_index'=>$row['seq_in_index'],'Column_name'=>$row['column_name']];
        }
    }
    sort($tables,SORT_STRING);
    return ['tables'=>$tables,'indexes'=>$indexes];
}
/** Fixed-size migration/seed contracts, plus the uniqueness relied on by bounded reads. */
function runtimeContract(PDO $p,array $contract,?callable $metadataReader=null): array {
    require_once __DIR__.'/schema_contract.php';
    $version=$contract['schema_version']??4;$envelope=\Mosa2\CollectorSchema5\envelope($version);
    $metadata=($metadataReader??__NAMESPACE__.'\\runtimeMetadata')($p);
    same($metadata['tables'],$envelope['tables'],'table_set');
    $ledger=boundedRows($p,'SELECT *,HEX(checksum) AS checksum FROM m2_schema_migrations ORDER BY version LIMIT '.($version===5?6:5),[],$version===5?5:4);
    same(array_column($ledger,'version'),$envelope['versions'],'ledger_versions');$digests=$envelope['digests'];
    foreach($ledger as $i=>$row)same(strtolower($row['checksum']),$digests[$i],'ledger_checksum');
    $units=boundedRows($p,'SELECT *,HEX(definition_sha256) AS definition_sha256 FROM m2_units ORDER BY unit_key,unit_version LIMIT 5',[],4);
    same(count($units),4,'four_units');
    $seed=json_decode(file_get_contents(dirname(__DIR__,2).'/docs/database/seeds/0001_market_units_v1.json'),true,32,JSON_THROW_ON_ERROR);
    foreach($seed['definitions'] as $d){$rows=array_values(array_filter($units,static fn($r)=>$r['unit_key']===$d['unit_key']&&$r['unit_version']===$d['unit_version']));same(count($rows),1,'seed_binding');
        foreach($d as $k=>$v)if($k!=='definition_reference')check(array_key_exists($k,$rows[0])&&($k==='definition_sha256'?strtolower($rows[0][$k])===$v:$rows[0][$k]===$v),'seed_definition');}
    foreach(['m2_asset_source_routes'=>[['source_id','route_type','external_key','route_revision'],['asset_id','source_id','route_type','route_revision']],
        'm2_market_observations'=>[['id'],['dedupe_key']],'m2_asset_identifiers'=>[['identifier_type','normalized_value','scope_key']]] as $table=>$required){
        $indexes=[];foreach(($metadata['indexes'][$table]??[]) as $index)if((int)$index['Non_unique']===0)$indexes[$index['Key_name']][(int)$index['Seq_in_index']]=$index['Column_name'];
        foreach($indexes as &$columns){ksort($columns);$columns=array_values($columns);}unset($columns);
        foreach($required as $columns)check(in_array($columns,$indexes,true),'runtime_unique_contract');
    }
    return ['m2_units'=>$units,'m2_schema_migrations'=>$ledger];
}
/** Only the explicitly qualified identity, source and both route-unique groups. */
function runtimeState(PDO $p,array $m,array $contract,?callable $metadataReader=null): array {
    same($m['policy']??null,'USE_EXISTING_ROUTE','runtime_existing_route_required');
    $state=runtimeContract($p,$contract,$metadataReader)+\Mosa2\MarketIdentity\identityState(new RuntimeStore($p),$m['identity']);
    $asset=\Mosa2\MarketIdentity\planAssetIdentity($state,$m['identity']);same($asset['decision'],'EXISTING_MATCH','existing_asset_required');
    $c=\Mosa2\Phase3D\candidate($m['route_evidence']);
    $state['m2_sources']=boundedRows($p,'SELECT * FROM m2_sources WHERE source_key=? LIMIT 2',[$c['proposed_source_key']],1);
    same(count($state['m2_sources']),1,'qualified_source');$source=$state['m2_sources'][0]['id'];
    $external='market-v1:'.hash('sha256',$c['proposed_route_key']);$routes=[];
    // Anti-conflict probes preserve the old planner's cross-group identity checks even for old revisions.
    same(boundedRows($p,'SELECT id FROM m2_asset_source_routes WHERE source_id=? AND route_type=? AND external_key=? AND asset_id<>? LIMIT 1',[$source,'quote',$external,$asset['asset_id']],1),[],'route_external_identity_conflict');
    same(boundedRows($p,'SELECT id FROM m2_asset_source_routes WHERE asset_id=? AND source_id=? AND route_type=? AND external_key<>? LIMIT 1',[$asset['asset_id'],$source,'quote',$external],1),[],'route_asset_identity_conflict');
    foreach([['source_id'=>$source,'route_type'=>'quote','external_key'=>$external],['asset_id'=>$asset['asset_id'],'source_id'=>$source,'route_type'=>'quote']] as $where){
        $rows=boundedRows($p,'SELECT * FROM m2_asset_source_routes WHERE '.implode(' AND ',array_map(static fn($k)=>qi($k).'=?',array_keys($where))).' ORDER BY route_revision DESC LIMIT 1',array_values($where),1);
        foreach($rows as $row)$routes[$row['id']]=$row;
    }
    $state['m2_asset_source_routes']=array_values($routes);return $state;
}
function observationBy(PDO $p,string $field,string $value): array {
    check(in_array($field,['id','dedupe_key'],true),'observation_lookup');
    return boundedRows($p,'SELECT *,HEX(dedupe_key) AS dedupe_key FROM m2_market_observations WHERE '.qi($field).'=? LIMIT 2',[$value],1);
}
/** Exact dedupe plus semantic identity (including other physical routes/domains). No history enumeration. */
function relevantFacts(PDO $p,array $writer): array {
    $key=\Mosa2\Phase3O\byteValue($writer['dedupe_key']);$raw=$writer['normalized'];
    $rows=observationBy($p,'dedupe_key',$key);$facts=[];foreach($rows as $row)$facts[$row['id']]=$row;
    $sameFact=boundedRows($p,'SELECT *,HEX(dedupe_key) AS dedupe_key FROM m2_market_observations WHERE asset_id=? AND source_id=? AND market_at <=> ? AND observed_at=? LIMIT 2',
        [$raw['asset_id'],$raw['source_id'],$raw['market_at'],$raw['observed_at']],1);
    foreach($sameFact as $row)$facts[$row['id']]=$row;return array_values($facts);
}
function exactObservation(PDO $p,string $id,array $expected): array {
    $rows=observationBy($p,'id',$id);same(count($rows),1,'observation_readback');same($rows[0],$expected,'observation_exact');return $rows[0];
}
/** Callable dependencies are explicit test seams; the public entry point fixes connection and bridge. */
function runtimeRun(string $privateRoot,array $config,array $manifest,callable $connect,callable $invoke,?callable $stateReader=null): array {
    $r=['ok'=>false,'verification_mode'=>'runtime','stage'=>'preflight','provider_requests'=>0,'database_connections'=>0,'committed'=>false,'rollback'=>null];
    $p=null;$locked=false;$baseline=null;$expected=null;$facts=null;$plan=null;$lockKey=null;
    $contract=$config['state_contract']??['schema_version'=>4];
    $stateReader??=__NAMESPACE__.'\\runtimeState';
    try{
        $r['database_connections']++;$p=$connect();
        $lockKey='m2-live:'.substr(hash('sha256',\Mosa2\Phase3D\json(\Mosa2\MarketIdentity\identifierKey($manifest['identity']))),0,48);
        $q=$p->prepare('SELECT GET_LOCK(?,0)');$q->execute([$lockKey]);$locked=(int)$q->fetchColumn()===1;check($locked,'identifier_lock_busy');
        $p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
        try{$baseline=$stateReader($p,$manifest,$contract);$plan=completePlan($baseline,$manifest);}
        finally{if($p->inTransaction())$p->rollBack();}
        $r['stage']='provider';$r['provider_requests']=1;
        $acquired=$invoke($config,['action'=>'fetch','private_root'=>$privateRoot,'php_cli'=>$config['php']]);
        $r['provider_duration_ms']=$acquired['provider_duration_ms']??null;
        foreach(['adapter_module','adapter_class','instrument'] as $field)same($acquired[$field]??null,$manifest[$field],'acquisition_binding');
        // A versioned adapter contract and the existing canonical Source may have
        // different keys. Such a binding must be explicit in the approved manifest.
        same($acquired['provider_key']??null,$manifest['provider_key']??$manifest['route_evidence']['row']['provider_key'],'acquisition_source');
        same($acquired['provider_requests']??null,1,'one_provider_request');
        $r['stage']='transaction';$p->beginTransaction();
        try{
            same($stateReader($p,$manifest,$contract),$baseline,'preflight_drift');
            $now=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');
            $route=$baseline['m2_asset_source_routes'];$route=array_values(array_filter($route,static fn($row)=>$row['id']===$plan['route']['route_id']));same(count($route),1,'runtime_route');$binding=routeBinding($route[0]);
            $request=['action'=>'plan','acquired'=>$acquired,'route'=>$binding,'created_at'=>$now,'existing'=>[],'allow_duplicate'=>true];
            $candidate=$invoke($config,$request)['plan'];same($candidate['decision'],'INSERT','candidate_plan');
            $facts=relevantFacts($p,$candidate);$request['existing']=existing($facts);$writer=$invoke($config,$request)['plan'];
            same($writer['canonical_bytes'],$candidate['canonical_bytes'],'candidate_drift');same($writer['dedupe_key'],$candidate['dedupe_key'],'candidate_key_drift');
            $r['writer']=$writer['decision'];
            if($writer['decision']==='INSERT'){
                \Mosa2\Phase3O\executePlan($p,$writer,$binding,$now);$id=$p->lastInsertId();
                $values=\Mosa2\Phase3O\insertValues($writer,$binding,$now);$values['dedupe_key']=strtoupper(bin2hex($values['dedupe_key']));$expected=['id'=>$id]+strings($values);
            }else{
                same($writer['decision'],'DUPLICATE_UNCHANGED','writer_decision');
                same(count($facts),1,'duplicate_origin');$expected=$facts[0];$id=$expected['id'];
                same(array_intersect_key($expected,$writer['normalized']),strings($writer['normalized']),'duplicate_payload');
            }
            $r['observation_id']=$id;$observation=exactObservation($p,$id,$expected);
            $stored=array_intersect_key($observation,array_flip(array_merge(\Mosa2\Phase3O\CORE,\Mosa2\Phase3O\UNITS)));
            $replay=$invoke($config,['action'=>'replay','route'=>$binding,'stored'=>$stored,'created_at'=>$now,'existing'=>existing([$observation])])['plan'];
            same($replay['decision'],'DUPLICATE_UNCHANGED','replay');same($replay['canonical_bytes'],$writer['canonical_bytes'],'replay_canonical');same($replay['dedupe_key'],$writer['dedupe_key'],'replay_key');
            $r['replay']='DUPLICATE_UNCHANGED';same($stateReader($p,$manifest,$contract),$baseline,'transaction_binding_drift');
            same($p->commit(),true,'commit');$r['committed']=true;
            $r+=['policy'=>$plan['policy'],'asset_plan'=>$plan['asset']['decision'],'route_plan'=>$plan['route']['decision'],
                'deltas'=>$plan['deltas']];$r['deltas']['m2_market_observations']=$writer['decision']==='INSERT'?1:0;
        }catch(Throwable $e){if($p->inTransaction())$r['rollback']=$p->rollBack();throw $e;}
        $r['stage']='readback';$r['database_connections']++;$read=$connect();$read->exec('SET TRANSACTION READ ONLY');$read->beginTransaction();
        try{same($stateReader($read,$manifest,$contract),$baseline,'independent_binding_drift');exactObservation($read,$id,$expected);$r['readback']='PASS';}
        finally{if($read->inTransaction())$read->rollBack();$read=null;}
    }catch(Throwable $e){$r['failure']=$e instanceof \PDOException?'database_operation_failed':$e->getMessage();}
    finally{
        // Keep the identifier lock through the independent readback, including rollback proof.
        if($r['rollback']===true&&$baseline!==null){
            try{$r['database_connections']++;$read=$connect();$read->exec('SET TRANSACTION READ ONLY');$read->beginTransaction();
                try{same($stateReader($read,$manifest,$contract),$baseline,'rollback_binding_drift');if(isset($candidate))same(relevantFacts($read,$candidate),$facts??[],'rollback_observation_delta');$r['readback']='PASS';}
                finally{if($read->inTransaction())$read->rollBack();$read=null;}
            }catch(Throwable){$r['readback_failure']='rollback_readback_failed';}
        }
        if($locked&&$p!==null){try{$q=$p->prepare('SELECT RELEASE_LOCK(?)');$q->execute([$lockKey]);same((int)$q->fetchColumn(),1,'lock_release');}catch(Throwable){$r['cleanup_failure']='lock_release_failed';}}
        $p=null;$r['ok']=$r['committed']&&($r['readback']??null)==='PASS'&&!isset($r['failure'])&&!isset($r['cleanup_failure']);
    }
    return $r;
}
