<?php
declare(strict_types=1);
namespace Mosa2\MarketIdentity;
use PDO;
use function Mosa2\Phase2\{check,same,qi};
require_once __DIR__.'/../phase2/postcheck.php';
require_once __DIR__.'/../phase3d/dry_run.php';

const UNIT_FIELDS=['unit_contract_version','quote_unit_key','quote_unit_version','quantity_basis_unit_key','quantity_basis_unit_version','quantity_basis_amount','volume_unit_key','volume_unit_version'];
const CATALOG_TABLES=['m2_entities','m2_assets','m2_asset_identifiers','m2_sources','m2_asset_source_routes','m2_market_observations','m2_sync_checkpoints'];
interface Store {
    public function find(string $table,array $where): array;
    public function insert(string $table,array $values): string;
}
class PdoStore implements Store {
    public function __construct(private PDO $p){check($p->inTransaction(),'transaction_required');}
    public function find(string $table,array $where): array {
        check(in_array($table,CATALOG_TABLES,true)&&$where!==[],'read_table');
        $q=$this->p->prepare('SELECT * FROM '.qi($table).' WHERE '.implode(' AND ',array_map(static fn($k)=>qi($k).' <=> ?',array_keys($where))));
        $q->execute(array_values($where));return $q->fetchAll(PDO::FETCH_ASSOC);
    }
    public function insert(string $table,array $values): string {
        check(in_array($table,CATALOG_TABLES,true)&&$this->p->inTransaction(),'write_table');
        $q=$this->p->prepare('INSERT INTO '.qi($table).' ('.implode(',',array_map('Mosa2\\Phase2\\qi',array_keys($values))).') VALUES ('.implode(',',array_fill(0,count($values),'?')).')');
        $q->execute(array_values($values));same($q->rowCount(),1,'one_catalog_insert');return $this->p->lastInsertId();
    }
}
function matchFields(array $row,array $expected): bool {
    foreach($expected as $k=>$v)if(!array_key_exists($k,$row)||($v===null?$row[$k]!==null:($row[$k]===null||(string)$row[$k]!== (string)$v)))return false;
    return true;
}
function qualifiedIdentity(array $q): array {
    $keys=['canonical_name','display_name','asset_class','identifier_type','identifier_value','normalized_value','scope_key','is_primary'];
    same(array_diff(array_keys($q),$keys),[],'identity_fields');same(array_diff($keys,array_keys($q)),[],'identity_fields');
    foreach(['canonical_name','display_name'] as $k)check(is_string($q[$k])&&trim($q[$k])===$q[$k]&&$q[$k]!==''&&strlen($q[$k])<=160,'qualified_name');
    check(in_array($q['asset_class'],['equity','etf'],true),'qualified_class');
    same($q['identifier_type'],'isin','qualified_identifier');same($q['scope_key'],'','global_scope');
    check(\Mosa2\Phase3D\isinValid($q['normalized_value']),'qualified_isin');same($q['identifier_value'],$q['normalized_value'],'canonical_identifier');
    check(in_array($q['is_primary'],[1,'1'],true),'primary_identifier');$q['is_primary']=1;return $q;
}
function identifierKey(array $q): array {return array_intersect_key($q,array_flip(['identifier_type','normalized_value','scope_key']));}
function entityValues(array $q): array {return ['entity_type'=>'asset','canonical_name'=>$q['canonical_name'],'status'=>'active'];}
function assetValues(array $q): array {return ['asset_class'=>$q['asset_class'],'display_name'=>$q['display_name'],'base_currency'=>null,'status'=>'active'];}

/** Pure Phase-3D identity decision; names are qualified exact values, never fuzzy selectors. */
function planAssetIdentity(array $state,array $qualified): array {
    $q=qualifiedIdentity($qualified);$conflict=static fn($why)=>['decision'=>'CONFLICT','reason'=>$why,'identity'=>$q];
    $entities=$state['m2_entities']??[];$assets=$state['m2_assets']??[];$identifiers=$state['m2_asset_identifiers']??[];
    $found=array_values(array_filter($identifiers,static fn($r)=>matchFields($r,identifierKey($q))));
    if(count($found)>1)return $conflict('global_identifier_ambiguous');
    $candidates=[];
    foreach($entities as $e)if(($e['entity_type']??null)==='asset'&&$e['canonical_name']===$q['canonical_name'])$candidates[(string)$e['id']]=true;
    foreach($assets as $a)if($a['display_name']===$q['display_name'])$candidates[(string)$a['entity_id']]=true;
    if($found)$candidates[(string)$found[0]['asset_id']]=true;
    if(count($candidates)>1)return $conflict('asset_candidates_ambiguous');
    $id=$candidates===[]?null:(string)array_key_first($candidates);
    if($id!==null){
        $es=array_values(array_filter($entities,static fn($r)=>(string)$r['id']===$id));
        $as=array_values(array_filter($assets,static fn($r)=>(string)$r['entity_id']===$id));
        if(count($es)!==1||count($as)!==1||!matchFields($es[0],entityValues($q))||!matchFields($as[0],assetValues($q)))return $conflict('asset_semantics_conflict');
        foreach($identifiers as $r)if((string)$r['asset_id']===$id&&$r['identifier_type']===$q['identifier_type']&&$r['scope_key']===$q['scope_key']&&!matchFields($r,identifierKey($q)))return $conflict('competing_global_identifier');
    }
    if($found&&!matchFields($found[0],identifierKey($q)+['asset_id'=>$id,'identifier_value'=>$q['identifier_value'],'is_primary'=>1,'source_id'=>null,'valid_from'=>null,'valid_to'=>null]))return $conflict('identifier_semantics_conflict');
    $decision=$found?'EXISTING_MATCH':($id===null?'CREATE_ASSET_AND_IDENTIFIER':'BIND_IDENTIFIER');
    return ['decision'=>$decision,'identity'=>$q,'asset_id'=>$id,'deltas'=>['m2_entities'=>$id===null?1:0,'m2_assets'=>$id===null?1:0,'m2_asset_identifiers'=>$found?0:1]];
}
/** Extract only identity-related state from either a transaction store or an offline snapshot. */
function identityState(Store $s,array $q): array {
    $q=qualifiedIdentity($q);$state=['m2_entities'=>[],'m2_assets'=>[],'m2_asset_identifiers'=>$s->find('m2_asset_identifiers',identifierKey($q))];
    $ids=[];
    foreach($s->find('m2_entities',['entity_type'=>'asset','canonical_name'=>$q['canonical_name']]) as $r)$ids[(string)$r['id']]=true;
    foreach($s->find('m2_assets',['display_name'=>$q['display_name']]) as $r)$ids[(string)$r['entity_id']]=true;
    foreach($state['m2_asset_identifiers'] as $r)$ids[(string)$r['asset_id']]=true;
    foreach(array_keys($ids) as $id){
        foreach(['m2_entities'=>['id'=>(string)$id],'m2_assets'=>['entity_id'=>(string)$id],'m2_asset_identifiers'=>['asset_id'=>(string)$id]] as $t=>$where){
            foreach($s->find($t,$where) as $row)if(!in_array($row,$state[$t],true))$state[$t][]=$row;
        }
    }return $state;
}
/** Caller owns the transaction. INSERT only, using the same planner again before touching data. */
function applyAssetIdentityPlan(Store $s,array $plan,string $timestamp): array {
    \Mosa2\Phase3C\utcTimestamp($timestamp);
    check(($plan['decision']??'CONFLICT')!=='CONFLICT','identity_plan_conflict');$q=qualifiedIdentity($plan['identity']);
    same(planAssetIdentity(identityState($s,$q),$q),$plan,'identity_plan_drift');
    $id=$plan['asset_id'];
    if($plan['decision']==='CREATE_ASSET_AND_IDENTIFIER'){
        $id=$s->insert('m2_entities',entityValues($q)+['created_at'=>$timestamp,'updated_at'=>$timestamp]);
        $s->insert('m2_assets',['entity_id'=>$id]+assetValues($q)+['created_at'=>$timestamp,'updated_at'=>$timestamp]);
    }
    if($plan['decision']!=='EXISTING_MATCH')$s->insert('m2_asset_identifiers',identifierKey($q)+['asset_id'=>$id,'identifier_value'=>$q['identifier_value'],'is_primary'=>1,'source_id'=>null,'valid_from'=>null,'valid_to'=>null,'created_at'=>$timestamp]);
    $after=planAssetIdentity(identityState($s,$q),$q);same($after['decision'],'EXISTING_MATCH','identity_readback');same($after['asset_id'],$id,'identity_readback_id');
    if($plan['decision']==='CREATE_ASSET_AND_IDENTIFIER')foreach(['m2_entities'=>['id'=>$id],'m2_assets'=>['entity_id'=>$id]] as $t=>$where)check(matchFields($s->find($t,$where)[0],['created_at'=>$timestamp,'updated_at'=>$timestamp]),'asset_timestamp_readback');
    if($plan['decision']!=='EXISTING_MATCH')check(matchFields($s->find('m2_asset_identifiers',identifierKey($q))[0],['created_at'=>$timestamp]),'identifier_timestamp_readback');
    return ['asset_id'=>$id,'deltas'=>$plan['deltas']];
}
function unitBinding(array $u): array {
    same(array_diff(array_keys($u),UNIT_FIELDS),[],'unit_fields');same(array_diff(UNIT_FIELDS,array_keys($u)),[],'unit_fields');
    same($u['unit_contract_version'],'mosa2-market-unit-v1','unit_contract');
    foreach(['quote_unit_key','quote_unit_version'] as $f)check(is_string($u[$f])&&$u[$f]!=='','quote_unit_binding');
    check(preg_match('/\A[1-9][0-9]*\z/D',$u['quote_unit_version'])===1,'unit_version');
    $q=array_map(static fn($f)=>$u[$f]!==null,['quantity_basis_unit_key','quantity_basis_unit_version','quantity_basis_amount']);
    check(count(array_unique($q))===1,'quantity_binding');check(($u['volume_unit_key']===null)===($u['volume_unit_version']===null),'volume_binding');
    return $u;
}
/** Both migration-0003 UNIQUE groups are checked. No DB IDs are invented for new assets. */
function planMarketRoute(array $current,array $qualified,array $units): array {
    $units=unitBinding($units);$q=$qualified;$c=\Mosa2\Phase3D\candidate($q['evidence']);
    check($c['asset_identity']==='unique'&&is_string($c['proposed_route_key'])&&!in_array('identity_conflict',$c['reasons'],true)&&!in_array('route_unresolved',$c['reasons'],true)&&!in_array('route_identity_conflict',$c['reasons'],true),'qualified_route');
    $external='market-v1:'.hash('sha256',$c['proposed_route_key']);
    check(is_string($q['source_id'])&&preg_match('/\A[1-9][0-9]*\z/D',$q['source_id'])===1,'source_id');
    check($q['asset_id']===null||(is_string($q['asset_id'])&&preg_match('/\A[1-9][0-9]*\z/D',$q['asset_id'])),'asset_id');
    check($q['route_type']==='quote'&&$q['priority']===0&&$q['enabled']===0,'inactive_quote_route');
    $base=['asset_id'=>$q['asset_id'],'source_id'=>$q['source_id'],'route_type'=>$q['route_type'],'external_key'=>$external,'priority'=>'0','enabled'=>'0'];
    $seenExternal=[];$seenAsset=[];$group=[];$max=0;
    foreach($current as $r){
        if((string)$r['source_id']!==$q['source_id']||$r['route_type']!==$q['route_type'])continue;
        $ex=$r['external_key']===$external;$as=$q['asset_id']!==null&&(string)$r['asset_id']===$q['asset_id'];
        if(!$ex&&!$as)continue;
        $conflict=static fn($why)=>['decision'=>'CONFLICT','reason'=>$why];
        if(!$ex||!$as)return $conflict('route_group_identity_conflict');
        $rev=(int)$r['route_revision'];
        if($rev<1||isset($seenExternal[$rev])||isset($seenAsset[$rev]))return $conflict('route_unique_conflict');
        $seenExternal[$rev]=true;$seenAsset[$rev]=true;$max=max($max,$rev);$group[]=$r;
    }
    foreach($group as $r)if((int)$r['route_revision']===$max&&matchFields($r,$base+$units))return ['decision'=>'EXISTING_MATCH','route_id'=>(string)$r['id'],'row'=>$base+['route_revision'=>(string)$max]+$units,'proposed_route_key'=>$c['proposed_route_key']];
    if($max>=4294967295)return ['decision'=>'CONFLICT','reason'=>'route_revision_exhausted'];
    return ['decision'=>'CREATE_REVISION','row'=>$base+['route_revision'=>(string)($max+1)]+$units,'proposed_route_key'=>$c['proposed_route_key']];
}
function applyMarketRoutePlan(Store $s,array $plan,string $assetId,string $timestamp): array {
    check(in_array($plan['decision']??null,['CREATE_REVISION','EXISTING_MATCH'],true),'route_plan');\Mosa2\Phase3C\identity($assetId);\Mosa2\Phase3C\utcTimestamp($timestamp);
    $row=$plan['row'];check($row['asset_id']===null||$row['asset_id']===$assetId,'route_asset_binding');$row['asset_id']=$assetId;
    if($plan['decision']==='EXISTING_MATCH'){
        \Mosa2\Phase3C\identity($plan['route_id']);same($plan['row']['asset_id'],$assetId,'existing_route_asset');
        $rows=$s->find('m2_asset_source_routes',['id'=>$plan['route_id']]);same(count($rows),1,'existing_route_count');
        check(matchFields($rows[0],['id'=>$plan['route_id']]+$row),'existing_route_drift');return $rows[0];
    }
    $row+=['created_at'=>$timestamp,'updated_at'=>$timestamp];$id=$s->insert('m2_asset_source_routes',$row);
    $rows=$s->find('m2_asset_source_routes',['id'=>$id]);same(count($rows),1,'route_readback_count');check(matchFields($rows[0],['id'=>$id]+$row),'route_readback');
    return $rows[0];
}
