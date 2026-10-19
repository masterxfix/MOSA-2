<?php
declare(strict_types=1);
require_once __DIR__.'/phase3d_import_fixture.php';
use function Mosa2\Phase3D\Import\{apply,manifest,verifyBaseline,expectedCounts};
use function Mosa2\Phase3D\json;
function batchManifest(): array {
    $m=syntheticManifest();$m['import_contract_version']='phase3d-market-migration-v1';
    $m['stream_key']='phase3d_market_migration_v1';$m['baseline_sha256']=str_repeat('d',64);$m['package_sha256']=str_repeat('e',64);$m['import_at']='2026-01-03 12:00:00';
    foreach($m['observations'] as $i=>&$e){$e['sample_id']='B-'.($i+1);$e['source_reference']='synthetic:new:'.$i;
        $e['isin']=['GB0002634946','US02079K3059','US0231351067'][$i];$e['proposed_asset_key']='isin:'.$e['isin'];
        $e['asset']['canonical_name']=$e['asset']['display_name']='Synthetic new '.$i;
        $e['proposed_source_key']=$i===0?'provider:synthetic_two':'provider:synthetic_three';$e['source']['source_key']=$e['proposed_source_key'];
        $e['proposed_route_key']='synthetic:new-route:'.$i;$e['route']['external_key']='market-v1:'.hash('sha256',$e['proposed_route_key']);
        $e['observation']['currency']=$i===0?'DKK':'EUR';
    }unset($e);return $m;
}
function snapshot(SyntheticStore $s): array {
    $facts=[];$counts=expectedCounts(syntheticManifest());foreach($counts as $t=>&$n){$n=count($s->tables[$t]??[]);if($t!=='m2_schema_migrations')$facts[$t]=$s->tables[$t]??[];}unset($n);$counts['m2_schema_migrations']=2;
    foreach($facts['m2_market_observations'] as &$r){$r['dedupe_hex']=strtoupper(bin2hex($r['dedupe_key']));unset($r['dedupe_key']);}unset($r);
    return ['counts'=>$counts,'facts'=>$facts,'structure'=>['metadata'=>[]],'ledger'=>['synthetic'],'grants'=>['synthetic']];
}
$x=json_decode(stream_get_contents(STDIN),true);$case=$x['scenario']??'replay';
try{
    if($case==='comparison'){\Mosa2\Phase3D\Import\sameEvidence($x['actual'],$x['expected'],'evidence_mismatch');echo json(['ok'=>true]);exit;}
    $s=new SyntheticStore();apply($s,syntheticManifest(),true);$baseline=snapshot($s);$m=batchManifest();
    if($case==='baseline_key_order'){$a=$baseline;$a['ledger']=[['version'=>1,'checksum'=>'synthetic','applied_at'=>'synthetic']];$a['structure']['metadata']=['synthetic'=>['show_create'=>'synthetic','columns'=>[['name'=>'id','type'=>'synthetic']]]];$b=json_decode(json($a),true);verifyBaseline($b,$a);echo json(['ok'=>true]);exit;}
    if($case==='extra_baseline'){$a=$baseline;$a['facts']['m2_sources'][]=$a['facts']['m2_sources'][0];$a['counts']['m2_sources']++;verifyBaseline($baseline,$a);}
    if($case==='changed_baseline'){$a=$baseline;$a['facts']['m2_assets'][0]['display_name']='Changed';verifyBaseline($baseline,$a);}
    if($case==='catalog_conflict')$m['observations'][0]['source']['display_name']='Conflict';
    if($case==='stream_conflict')$m['stream_key']='phase3d_market_sample_v1';
    if($case==='too_many')$m['observations'][]=$m['observations'][0];
    if($case==='determinism'){$a=manifest($m);$m['observations']=array_reverse($m['observations']);echo json(['ok'=>true,'same'=>json($a)===json(manifest($m))]);exit;}
    verifyBaseline($baseline,snapshot($s));$first=apply($s,$m,true,$baseline['facts']);$after=snapshot($s);
    verifyBaseline($baseline,$after,false);$expected=expectedCounts($m,$baseline,$first['new']);
    \Mosa2\Phase2\same($after['counts'],$expected,'counts');$second=apply($s,$m,false,$baseline['facts']);$last=snapshot($s);verifyBaseline($baseline,$last,false);
    $legacyChecks=array_values(array_filter($last['facts']['m2_sync_checkpoints'],static fn($r)=>$r['stream_key']==='phase3d_market_sample_v1'));
    $migrationChecks=array_values(array_filter($last['facts']['m2_sync_checkpoints'],static fn($r)=>$r['stream_key']==='phase3d_market_migration_v1'));
    $watermarks=true;foreach($migrationChecks as $cp){$values=array_column(array_filter($first['bindings'],static fn($r)=>$r['observation']['source_id']===$cp['source_id']),'observation');$watermarks=$watermarks&&$cp['watermark_at']===max(array_column($values,'observed_at'));}
    echo json(['ok'=>true,'first'=>$first,'second'=>$second,'counts'=>$last['counts'],'same'=>$after===$last,
        'legacy_checkpoints_same'=>$legacyChecks===$baseline['facts']['m2_sync_checkpoints'],'migration_checkpoints'=>$migrationChecks,
        'watermarks_correct'=>$watermarks,'baseline_preserved'=>true,'tables'=>array_keys($s->tables)]);
}catch(Throwable $e){echo json(['ok'=>false,'reason'=>$e->getMessage()]);}
