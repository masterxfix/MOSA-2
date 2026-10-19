<?php
declare(strict_types=1);
namespace Mosa2\Phase3D\Import;
require_once dirname(__DIR__).'/phase3c/live_test.php';
require_once __DIR__.'/dry_run.php';
use PDO;
use RuntimeException;
use function Mosa2\Phase2\{check,same,qi,connection,preflight,structure,save};
use function Mosa2\Phase3C\{identity,utcTimestamp,normalizeObservationValues,normalizeObservation,canonicalObservation,dedupeKey,expectedLedger,schemaContractEvidence};
use function Mosa2\Phase3D\{isinValid,json,canonical};

const WRITABLE=['m2_entities','m2_assets','m2_asset_identifiers','m2_sources','m2_asset_source_routes','m2_market_observations','m2_sync_checkpoints'];
const STREAM='phase3d_market_sample_v1';
function normalizedName(string $name): string {
    $name=html_entity_decode(trim($name),ENT_QUOTES|ENT_HTML5,'UTF-8');
    $name=function_exists('mb_strtolower')?mb_strtolower($name,'UTF-8'):strtolower($name);
    return trim(preg_replace('/\s+/u',' ',preg_replace('/[^\p{L}\p{N}]+/u',' ',$name)??'')??'');
}
function objectKey(string $name): string {return 'object_'.substr(hash('sha256',normalizedName($name)),0,24);}
// Evidence is supplied from existing stores, never looked up by this module.
function masterData(string $isin,string $assetKey,array $evidence): array {
    check(isinValid($isin),'isin_invalid');$names=[];$objects=[];$users=[];$types=[];$refs=[];
    $etfProven=false;foreach($evidence as $source)if(($source['source_type']??null)==='mosa_etf_references')foreach($source['records'] as $r)
        if(($r['isin']??null)===$isin&&($r['asset_type']??null)==='etf'&&($r['object_key']??null)===$isin)$etfProven=true;
    foreach($evidence as $source){
        check(isset($source['source_type'],$source['source_sha256'],$source['records'])&&preg_match('/\A[a-f0-9]{64}\z/D',$source['source_sha256'])===1,'evidence_source');
        $type=$source['source_type'];check(in_array($type,['mosa_invested_instruments','mosa_market_identities','mosa_market_sources','mosa_etf_references'],true),'evidence_type');
        $versions=['mosa_invested_instruments'=>'mosa_invested_instrument_store_v1','mosa_market_identities'=>'mosa_market_identity_store_v1','mosa_market_sources'=>'mosa_market_source_registry_v1','mosa_etf_references'=>'mosa_etf_reference_store_v1'];
        same($source['store_contract']??null,$versions[$type],'evidence_contract');
        $refs[$type]=$source['source_sha256'];
        foreach($source['records'] as $r){
            if(($r['isin']??null)!==$isin)continue;
            check(is_int($r['user_id']??null)&&$r['user_id']>0,'evidence_user');
            if($type==='mosa_invested_instruments'){
                check(($r['contract_version']??null)==='mosa_invested_instrument_v1'&&($r['origin']??null)==='explicit_user_input','name_contract');
                $name=$r['object_name']??'';check(is_string($name)&&$name!==''&&($r['object_key']??null)===objectKey($name),'name_object_identity');
                $names[]=$name;$objects[]=$r['object_key'];$users[]=$r['user_id'];
            }elseif($type==='mosa_market_identities'){
                same($r['contract_version']??null,'mosa_market_identity_v1','identity_contract');
                check(($r['asset_key']??null)===$assetKey,'identity_asset_mismatch');
                $name=$r['asset_label']??'';check(is_string($name)&&$name!==''&&($r['object_key']??null)===objectKey($name),'identity_name_object');
                $names[]=$name;$objects[]=$r['object_key'];$users[]=$r['user_id'];
            }elseif($type==='mosa_etf_references'){
                check(($r['contract_version']??null)==='mosa_etf_reference_v1'&&($r['asset_type']??null)==='etf'&&($r['object_key']??null)===$isin,'etf_contract');
                check(is_string($r['object_name']??null)&&trim($r['object_name'])!=='','etf_name');
                $names[]=$r['object_name'];$types[]='etf';$users[]=$r['user_id'];
            }else{
                check(($r['asset_key']??null)===$assetKey,'registry_asset_mismatch');
                if(($r['provider_key']??null)!=='yahoo_finance_chart')continue;
                check(($r['status']??null)==='found'&&is_array($r['technical']??null),'registry_contract');
                $quoteType=$r['technical']['quote_type']??null;
                if($quoteType==='ETF'){check($etfProven,'etf_reference_missing');$users[]=$r['user_id'];continue;}
                check(in_array($quoteType,['EQUITY','STOCK'],true),'explicit_asset_type_missing');
                $types[]='equity';$users[]=$r['user_id'];
            }
        }
    }
    check($names!==[]&&count(array_unique(array_map(__NAMESPACE__.'\\normalizedName',$names)))===1,'name_missing_or_conflict');
    check(count(array_unique($objects))<=1&&count(array_unique($users))===1,'cross_store_identity_conflict');
    check($types!==[]&&count(array_unique($types))===1,'asset_class_missing_or_conflict');
    return ['canonical_name'=>$names[0],'display_name'=>$names[0],'asset_class'=>$types[0],
        'base_currency'=>null,'name_confirmed'=>true,'asset_class_confirmed'=>true,'evidence_fingerprints'=>$refs];
}
function manifest(array $input): array {
    same($input['schema_version']??null,2,'schema_version');
    check(in_array($input['import_contract_version']??null,['phase3d-market-sample-v1','phase3d-market-migration-v1'],true),'import_contract');
    $legacy=$input['import_contract_version']==='phase3d-market-sample-v1';
    if(!$legacy){foreach(['baseline_sha256','package_sha256'] as $k)check(preg_match('/\A[a-f0-9]{64}\z/D',$input[$k]??'')===1,'parent_fingerprint');same($input['stream_key']??null,'phase3d_market_migration_v1','migration_stream');}
    foreach(['snapshot_sha256','mapping_sha256','parent_report_sha256'] as $key)check(is_string($input[$key]??null)&&preg_match('/\A[a-f0-9]{64}\z/D',$input[$key])===1,'manifest_fingerprint');
    $input['import_at']=utcTimestamp($input['import_at']);
    check($legacy?count($input['observations']??[])===3:(count($input['observations']??[])>=1&&count($input['observations'])<=3),'exactly_three');$assets=[];$sources=[];$seen=[];$ccy=[];
    foreach($input['observations'] as &$e){
        check(($legacy?in_array($e['sample_id']??null,['A1','A2','A3'],true):preg_match('/\A[A-Z][A-Z0-9-]{0,15}\z/D',$e['sample_id']??'')===1)&&!isset($seen[$e['sample_id']]),'sample_ids');$seen[$e['sample_id']]=true;
        check(isinValid($e['isin']??null)&&($e['proposed_asset_key']??null)==='isin:'.$e['isin'],'asset_identity');
        check(in_array($e['asset']['asset_class']??null,['equity','etf'],true)&&($e['asset']['name_confirmed']??false)&&($e['asset']['asset_class_confirmed']??false),'asset_evidence');
        check(is_string($e['asset']['canonical_name']??null)&&trim($e['asset']['canonical_name'])!==''&&$e['asset']['canonical_name']===$e['asset']['display_name'],'asset_name');
        same($e['asset']['base_currency'],null,'unproven_base_currency');
        $source=$e['source'];check(($source['source_key']??null)===$e['proposed_source_key']&&strlen($source['source_key'])<=128&&($source['source_type']??null)==='market_data'&&($source['enabled']??null)===1&&($source['base_url']??null)===null,'source_contract');
        check(preg_match('/\Aprovider:[a-z0-9_]+\z/D',$source['source_key'])===1&&is_string($source['display_name'])&&$source['display_name']!=='','source_identity');
        $route=$e['route'];check(($route['route_type']??null)==='quote'&&($route['priority']??null)===0&&($route['enabled']??null)===1,'route_contract');
        same($route['external_key'],'market-v1:'.hash('sha256',$e['proposed_route_key']),'route_external_identity');
        $e['observation']=normalizeObservationValues($e['observation']);
        check($legacy?in_array($e['observation']['currency'],['EUR','NOK'],true):!in_array($e['observation']['currency'],['GBX','XXX'],true),'native_currency_scope');
        check(($e['native_market_quote']??null)===true&&($e['time_semantics_confirmed']??null)===true,'native_time_evidence');
        $assets[$e['isin']]=$e['asset'];$sources[$source['source_key']]=$source;$ccy[]=$e['observation']['currency'];
    }unset($e);
    if($legacy){sort($ccy);same($ccy,['EUR','EUR','NOK'],'one_native_nok');check(count($assets)>=2&&count($sources)>=2,'sample_diversity');}
    usort($input['observations'],static fn($a,$b)=>strcmp($a['sample_id'],$b['sample_id']));
    return $input;
}
interface Store {
    public function find(string $table,array $where): array;
    public function insert(string $table,array $values): string;
}
final class PdoStore implements Store {
    public function __construct(private PDO $p){check($p->inTransaction(),'transaction_required');}
    public function find(string $table,array $where): array {
        check(in_array($table,WRITABLE,true)&&$where!==[],'read_table');
        $sql='SELECT * FROM '.qi($table).' WHERE '.implode(' AND ',array_map(static fn($k)=>qi($k).' <=> ?',array_keys($where)));
        $q=$this->p->prepare($sql);$q->execute(array_values($where));return $q->fetchAll();
    }
    public function insert(string $table,array $values): string {
        check(in_array($table,WRITABLE,true)&&$this->p->inTransaction(),'write_table');
        $sql='INSERT INTO '.qi($table).' ('.implode(',',array_map('Mosa2\\Phase2\\qi',array_keys($values))).') VALUES ('.implode(',',array_fill(0,count($values),'?')).')';
        $q=$this->p->prepare($sql);$q->execute(array_values($values));return $this->p->lastInsertId();
    }
}
function verifyFields(array $actual,array $expected,string $reason): void {
    foreach($expected as $k=>$v){check(array_key_exists($k,$actual),$reason);check($v===null?$actual[$k]===null:($actual[$k]!==null&&(string)$actual[$k]===(string)$v),$reason);}
}
// Preserve timestamps only from the fingerprint-bound baseline, never from an
// unexpected live row. Semantic fields still have to match the manifest.
function catalogExpected(string $table,array $where,array $expected,array $baseline): array {
    foreach($baseline[$table]??[] as $row){$match=true;
        foreach($where as $k=>$v)if(!array_key_exists($k,$row)||($v===null?$row[$k]!==null:(string)$row[$k]!== (string)$v))$match=false;
        if($match){foreach(['created_at','updated_at'] as $k)if(array_key_exists($k,$expected)&&array_key_exists($k,$row))$expected[$k]=$row[$k];return $expected;}
    }return $expected;
}
function resolve(Store $s,string $table,array $where,array $expected,string $id,array &$counts,bool $allowNew,array $baseline=[]): string {
    $expected=catalogExpected($table,$where,$expected,$baseline);
    $rows=$s->find($table,$where);check(count($rows)<=1,'catalog_ambiguous');
    if($rows){verifyFields($rows[0],$expected,'catalog_conflict');return identity($rows[0][$id]);}
    check($allowNew,'replay_missing_catalog');$created=$s->insert($table,$expected);$counts[$table]++;
    return $id==='entity_id'?identity($expected[$id]):identity($created);
}
function apply(Store $s,array $input,bool $allowNew,array $baseline=[]): array {
    $m=manifest($input);$now=$m['import_at'];$counts=array_fill_keys(WRITABLE,0);$bindings=[];$watermarks=[];$sourceIds=[];
    foreach($m['observations'] as $e){
        $expected=$e['source']+['created_at'=>$now,'updated_at'=>$now];
        $sourceIds[$e['proposed_source_key']]=resolve($s,'m2_sources',['source_key'=>$expected['source_key']],$expected,'id',$counts,$allowNew,$baseline);
    }
    foreach($m['observations'] as $e){
        $isin=$e['isin'];$source=$sourceIds[$e['proposed_source_key']];
        $identifier=['identifier_type'=>'isin','normalized_value'=>$isin,'scope_key'=>''];
        $found=$s->find('m2_asset_identifiers',$identifier);check(count($found)<=1,'isin_ambiguous');
        $entity=['entity_type'=>'asset','canonical_name'=>$e['asset']['canonical_name'],'status'=>'active','created_at'=>$now,'updated_at'=>$now];
        if(!$found){
            check($allowNew,'replay_missing_identifier');$asset=identity($s->insert('m2_entities',$entity));$counts['m2_entities']++;
            $s->insert('m2_assets',['entity_id'=>$asset,'asset_class'=>$e['asset']['asset_class'],'display_name'=>$e['asset']['display_name'],'base_currency'=>null,'status'=>'active','created_at'=>$now,'updated_at'=>$now]);$counts['m2_assets']++;
        }else{$asset=identity($found[0]['asset_id']);}
        $entities=$s->find('m2_entities',['id'=>$asset]);same(count($entities),1,'entity_missing');verifyFields($entities[0],catalogExpected('m2_entities',['id'=>$asset],$entity,$baseline),'entity_conflict');
        $assets=$s->find('m2_assets',['entity_id'=>$asset]);same(count($assets),1,'asset_missing');
        verifyFields($assets[0],catalogExpected('m2_assets',['entity_id'=>$asset],['entity_id'=>$asset,'asset_class'=>$e['asset']['asset_class'],'display_name'=>$e['asset']['display_name'],'base_currency'=>null,'status'=>'active','created_at'=>$now,'updated_at'=>$now],$baseline),'asset_conflict');
        resolve($s,'m2_asset_identifiers',$identifier,$identifier+['asset_id'=>$asset,'identifier_value'=>$isin,'is_primary'=>1,'source_id'=>null,'valid_from'=>null,'valid_to'=>null,'created_at'=>$now],'id',$counts,$allowNew,$baseline);
        $route=$e['route']+['asset_id'=>$asset,'source_id'=>$source,'created_at'=>$now,'updated_at'=>$now];
        $external=$s->find('m2_asset_source_routes',array_intersect_key($route,array_flip(['source_id','route_type','external_key'])));
        $scoped=$s->find('m2_asset_source_routes',array_intersect_key($route,array_flip(['asset_id','source_id','route_type'])));
        check(count($external)<=1&&count($scoped)<=1,'route_ambiguous');
        if($external||$scoped){check(count($external)===1&&count($scoped)===1&&(string)$external[0]['id']===(string)$scoped[0]['id'],'route_identity_conflict');}
        $routeId=resolve($s,'m2_asset_source_routes',array_intersect_key($route,array_flip(['source_id','route_type','external_key'])),$route,'id',$counts,$allowNew,$baseline);
        $row=normalizeObservation(['asset_id'=>$asset,'source_id'=>$source,'route_id'=>$routeId]+$e['observation']);$key=dedupeKey($row);
        $existing=$s->find('m2_market_observations',['dedupe_key'=>$key]);check(count($existing)<=1,'dedupe_ambiguous');
        $expected=$row+['dedupe_key'=>$key,'created_at'=>$now];
        if($existing){verifyFields($existing[0],$expected,'dedupe_payload_conflict');$action='duplicate';}
        else{check($allowNew,'replay_missing_observation');$s->insert('m2_market_observations',$expected);$counts['m2_market_observations']++;$action='insert';}
        $bindings[]=['sample_id'=>$e['sample_id'],'source_reference'=>$e['source_reference'],'observation'=>$row,'canonical'=>canonicalObservation($row),'dedupe_hex'=>bin2hex($key),'action'=>$action];
        $watermarks[$source]=max($watermarks[$source]??'',$row['observed_at']);
    }
    $cursor='sha256:'.hash('sha256',json($m));
    foreach($watermarks as $source=>$watermark){$expected=['source_id'=>(string)$source,'stream_key'=>($m['stream_key']??STREAM),'cursor_value'=>$cursor,'watermark_at'=>$watermark,'updated_at'=>$now];
        resolve($s,'m2_sync_checkpoints',['source_id'=>(string)$source,'stream_key'=>($m['stream_key']??STREAM)],$expected,'id',$counts,$allowNew,$baseline);
    }
    return ['new'=>$counts,'bindings'=>$bindings,'checkpoint_cursor'=>$cursor];
}
function state(PDO $p,string $root,bool $mustBeEmpty=false,?array $limits=null): array {
    [$core,$market]=\Mosa2\Phase3B\schemas($root);$r=preflight($p,false);
    $r['structure']=structure($p,$core+$market,null,[16,9,26,23,19]);same($r['structure']['counts']['columns'],140,'columns');
    $r['ledger']=\Mosa2\Phase3B\ledger($p,2);same($r['ledger'],expectedLedger(),'ledger_changed');
    $r['counts']=[];$r['facts']=[];
    foreach(array_keys($core+$market) as $table){$r['counts'][$table]=(int)$p->query('SELECT COUNT(*) FROM '.qi($table))->fetchColumn();
        if($table==='m2_schema_migrations')continue;
        if($mustBeEmpty)same($r['counts'][$table],0,'nonempty:'.$table);
        // Exact counts are bounded before full sample readback, even on replay.
        check($r['counts'][$table]<=($limits[$table]??3),'unexpected_extra_rows');
        $id=$table==='m2_assets'?'entity_id':($table==='m2_market_current'?'asset_id':($table==='m2_module_state'?'module_key':'id'));
        $columns=$table==='m2_market_observations'?'id,asset_id,source_id,route_id,currency,price,bid,ask,volume,market_at,observed_at,HEX(dedupe_key) AS dedupe_hex,created_at':'*';
        $r['facts'][$table]=$p->query('SELECT '.$columns.' FROM '.qi($table).' ORDER BY '.qi($id))->fetchAll();
    }
    same($r['counts']['m2_schema_migrations'],2,'ledger_count');return $r;
}
function expectedCounts(array $m,?array $baseline=null,?array $delta=null): array {
    if($baseline!==null){check($delta!==null,'delta_required');$counts=$baseline['counts'];foreach($delta as $table=>$n){check(in_array($table,WRITABLE,true)&&is_int($n)&&$n>=0,'delta_invalid');$counts[$table]+=$n;}return $counts;}
    $assets=[];$sources=[];$routes=[];foreach($m['observations'] as $e){$assets[$e['isin']]=1;$sources[$e['source']['source_key']]=1;$routes[$e['proposed_route_key']]=1;}
    $counts=array_fill_keys(array_merge(\Mosa2\Phase2\TABLES,\Mosa2\Phase3B\MARKET),0);
    foreach(['m2_entities','m2_assets','m2_asset_identifiers'] as $t)$counts[$t]=count($assets);
    foreach(['m2_sources','m2_sync_checkpoints'] as $t)$counts[$t]=count($sources);
    $counts['m2_asset_source_routes']=count($routes);$counts['m2_market_observations']=3;$counts['m2_schema_migrations']=2;return $counts;
}
// Recursive map canonicalization preserves scalar types and list order.
function sameEvidence(mixed $actual,mixed $expected,string $reason): void {
    check(canonical($actual)===canonical($expected),$reason);
}
function verifyState(array $before,array $after,array $expected): void {
    same($after['counts'],$expected,'exact_counts');sameEvidence($after['ledger'],$before['ledger'],'ledger_changed');same($after['grants'],$before['grants'],'rights_changed');
    sameEvidence(schemaContractEvidence($after['structure']),schemaContractEvidence($before['structure']),'schema_changed');
}
function verifyBaseline(array $baseline,array $actual,bool $exact=true): void {
    verifyState($baseline,$actual,$exact?$baseline['counts']:$actual['counts']);
    if($exact){sameEvidence($actual['facts'],$baseline['facts'],'baseline_values');return;}
    foreach($baseline['facts'] as $table=>$rows){$key=$table==='m2_assets'?'entity_id':($table==='m2_market_current'?'asset_id':($table==='m2_module_state'?'module_key':'id'));
        foreach($rows as $row){$found=array_values(array_filter($actual['facts'][$table],static fn($r)=>(string)$r[$key]===(string)$row[$key]));
            check(count($found)===1,'baseline_missing');sameEvidence($found[0],$row,'baseline_mutated');}
    }
}
function run(string $root): array {
    check(!is_link($root)&&(fileperms($root)&0077)===0,'private_root');
    foreach(['manifest.json','secret.php','0001.sql','0002.sql'] as $f)check(is_file($root.'/'.$f)&&!is_link($root.'/'.$f)&&(fileperms($root.'/'.$f)&0077)===0,'private_file');
    $manifestBytes=file_get_contents($root.'/manifest.json');$m=manifest(json_decode($manifestBytes,true,64,JSON_THROW_ON_ERROR));
    $guard=require $root.'/access.php';same(hash('sha256',$manifestBytes),$guard['manifest_sha256'],'manifest_changed');
    $baseline=null;$limits=null;
    if($m['import_contract_version']==='phase3d-market-migration-v1'){
        check(is_file($root.'/baseline.json')&&!is_link($root.'/baseline.json')&&(fileperms($root.'/baseline.json')&0077)===0,'private_baseline');
        same(hash_file('sha256',$root.'/baseline.json'),$m['baseline_sha256'],'baseline_fingerprint');
        $baseline=json_decode(file_get_contents($root.'/baseline.json'),true,512,JSON_THROW_ON_ERROR);
        $limits=$baseline['counts'];foreach(WRITABLE as $t)$limits[$t]+=3;
    }
    $lock=fopen($root.'/started.lock','x');check($lock!==false&&flock($lock,LOCK_EX|LOCK_NB),'already_started');
    $r=['ok'=>false,'first_committed'=>false,'second_committed'=>false,'manifest_sha256'=>hash('sha256',$manifestBytes)];$p=null;$password=null;$before=null;
    $persist=static function()use(&$r,$root):void{save($root.'/report.json',$r);};
    try{
        $password=require $root.'/secret.php';$p=connection($password);$before=state($p,$root,$baseline===null,$limits);if($baseline!==null)verifyBaseline($baseline,$before);$r['preflight']=$before;$persist();
        $p->beginTransaction();$r['first']=apply(new PdoStore($p),$m,true,$before['facts']);
        same($r['first']['new']['m2_market_observations'],count($m['observations']),'first_exactly_three');
        $expected=$baseline===null?expectedCounts($m):expectedCounts($m,$before,$r['first']['new']);
        $r['before_commit']=state($p,$root,false,$limits);verifyState($before,$r['before_commit'],$expected);verifyBaseline($before,$r['before_commit'],false);$persist();
        // Full resolved manifest and canonical expected keys persisted BEFORE commit.
        save($root.'/resolved-manifest.json',['parent_manifest_sha256'=>$r['manifest_sha256'],'bindings'=>$r['first']['bindings']]);
        $r['commit_attempted']=true;$persist();$p->commit();$r['first_committed']=true;$persist();$p=null;
        $p=connection($password);$r['readback1']=state($p,$root,false,$limits);verifyState($before,$r['readback1'],$expected);verifyBaseline($before,$r['readback1'],false);
        same($r['readback1']['facts'],$r['before_commit']['facts'],'first_readback_values');$persist();$p=null;
        same(hash_file('sha256',$root.'/manifest.json'),$r['manifest_sha256'],'manifest_changed');
        $p=connection($password);$p->beginTransaction();$r['second']=apply(new PdoStore($p),$m,false,$before['facts']);
        same(array_sum($r['second']['new']),0,'replay_new_rows');
        same(array_column($r['second']['bindings'],'action'),array_fill(0,count($m['observations']),'duplicate'),'three_replays');
        $secondState=state($p,$root,false,$limits);verifyState($before,$secondState,$expected);same($secondState['facts'],$r['readback1']['facts'],'replay_mutated');
        $p->commit();$r['second_committed']=true;$persist();$p=null;
        $p=connection($password);$r['readback2']=state($p,$root,false,$limits);verifyState($before,$r['readback2'],$expected);verifyBaseline($before,$r['readback2'],false);
        same($r['readback2']['facts'],$r['readback1']['facts'],'second_readback_values');
        $r['auto_increment_equal']=$r['readback1']['structure']===$r['readback2']['structure'];$r['ok']=true;
    }catch(\Throwable $e){
        if($p!==null&&$p->inTransaction())$p->rollBack();
        $r['failure']=$e instanceof \PDOException?['category'=>'database','errno'=>(int)($e->errorInfo[1]??0)]:['category'=>'guard','reason'=>$e->getMessage()];
        if($password!==null){try{$p=null;$p=connection($password);$r['failure_readback']=state($p,$root,false,$limits);if(!($r['commit_attempted']??false)&&$before!==null)verifyBaseline($before,$r['failure_readback']);}catch(\Throwable){$r['failure_readback_unconfirmed']=true;}}
    }finally{$p=null;unset($password);if(is_file($root.'/secret.php'))check(unlink($root.'/secret.php'),'secret_cleanup');flock($lock,LOCK_UN);fclose($lock);$persist();}
    return $r;
}
