<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{transaction,storedFile,validate,executionBinding};
[$a,$b]=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
$n=0;
function ensure(bool $ok):void{global $n;$n++;if(!$ok)throw new RuntimeException('assertion_'.$n);}
function reject(callable $f):bool{try{$f();return false;}catch(Throwable){return true;}}
function rejectCode(callable $f,string $code):bool{try{$f();return false;}catch(Throwable $e){return $e->getMessage()===$code;}}
executionBinding($a,$a['metadata']['execution']);
ensure(rejectCode(fn()=>executionBinding($a,$b['metadata']['execution']),'execution_binding'));
ensure(rejectCode(fn()=>executionBinding($a,'fundamentals-esef-unauthorized'),'execution_binding'));
$p=new MemoryPDO();$first=transaction($p,$a,'41',fn()=>null);$old=$p->data;
$second=transaction($p,$b,'42',fn()=>null);
ensure($first['observations']===10&&$first['current']===5);ensure($second['observations']===10&&$second['current']===5);
ensure($second['metrics']===0&&$second['inserted']['m2_fundamental_units']===1);
foreach(['m2_fundamental_observations','m2_fundamental_current'] as $t)ensure(array_values(array_filter($p->data[$t],fn($r)=>$r['asset_id']==='41'))===$old[$t]);
$repeat=transaction($p,$a,'41',fn()=>null);ensure(array_sum($repeat['inserted'])===0&&$repeat['current_updates']===0);
foreach([1,7,15] as $failure){$q=new MemoryPDO($failure);ensure(reject(fn()=>transaction($q,$a,'41',fn()=>null)));ensure($q->data===[]&&$q->rollbacks===1);}
$q=new MemoryPDO(0,true);ensure(reject(fn()=>transaction($q,$a,'41',fn()=>null)));ensure($q->commits===1&&$q->rollbacks===0);
$bad=$a;$bad['stored_evidence']['sha256']=str_repeat('0',64);ensure(rejectCode(fn()=>storedFile($bad),'evidence_hash'));
$bad=$a;$doc=json_decode($bad['evidence_json'],true,64,JSON_THROW_ON_ERROR);
$doc['identity_mapping']['isin']='DK0060252690';
$raw=json_encode($doc,JSON_THROW_ON_ERROR);$bad['evidence_json']=$raw;
$bad['stored_evidence']['sha256']=$bad['archive']['sha256']=hash('sha256',$raw);$bad['stored_evidence']['bytes']=$bad['archive']['bytes']=strlen($raw);
ensure(rejectCode(fn()=>storedFile($bad),'esef_reviewed_profile'));
foreach(['tag','value','currency','entity','dimensions','source','scope'] as $key){
    $bad=$a;$doc=json_decode($bad['evidence_json'],true,64,JSON_THROW_ON_ERROR);
    if($key==='source')$doc['source_response']['sha256']=str_repeat('0',64);
    elseif($key==='scope')$doc['consolidation_evidence'][0]['value']='Separate financial statements';
    else $doc['facts'][0]['selected'][$key]=$key==='dimensions'?['{bad}SegmentAxis'=>'{bad}SegmentMember']:'wrong';
    $raw=json_encode($doc,JSON_THROW_ON_ERROR);$bad['evidence_json']=$raw;
    $bad['stored_evidence']['sha256']=$bad['archive']['sha256']=hash('sha256',$raw);$bad['stored_evidence']['bytes']=$bad['archive']['bytes']=strlen($raw);
    $expected=['tag'=>'esef_tag','value'=>'esef_selected','currency'=>'esef_selected','entity'=>'esef_lei',
        'dimensions'=>'esef_axis','source'=>'esef_response','scope'=>'esef_consolidated'][$key];
    ensure(rejectCode(fn()=>storedFile($bad),$expected));
}
$bad=$a;$bad['observations'][0]['period_type']='fq';$bad['observations'][0]['fiscal_quarter']='1';ensure(rejectCode(fn()=>validate($bad),'reported_fy_only'));
echo json_encode(['ok'=>true,'assertions'=>$n]);
