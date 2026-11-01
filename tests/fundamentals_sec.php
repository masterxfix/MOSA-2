<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{transaction,validate,storedFile};
[$a,$b]=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
$n=0;
function ensure(bool $ok):void{global $n;$n++;if(!$ok)throw new RuntimeException('assertion_'.$n);}
function reject(callable $f):bool{try{$f();return false;}catch(Throwable){return true;}}
$p=new MemoryPDO();$first=transaction($p,$a,'41',fn()=>null);$old=$p->data;
$second=transaction($p,$b,'42',fn()=>null);
ensure($first['observations']===8&&$first['current']===4);ensure($second['observations']===8&&$second['current']===4);
ensure($second['metrics']===0&&$second['inserted']['m2_sources']===0&&$second['inserted']['m2_fundamental_units']===0);
foreach(['m2_fundamental_observations','m2_fundamental_current'] as $t)ensure(array_values(array_filter($p->data[$t],fn($r)=>$r['asset_id']==='41'))===$old[$t]);
$repeat=transaction($p,$a,'41',fn()=>null);ensure(array_sum($repeat['inserted'])===0&&$repeat['current_updates']===0);
foreach([1,4,9,15] as $failure){$q=new MemoryPDO($failure);ensure(reject(fn()=>transaction($q,$a,'41',fn()=>null)));ensure($q->data===[]&&$q->rollbacks===1);}
$q=new MemoryPDO(0,true);ensure(reject(fn()=>transaction($q,$a,'41',fn()=>null)));ensure($q->commits===1&&$q->rollbacks===0);
$bad=$a;$bad['observations'][0]['period_start']='2025-01-01';ensure(reject(fn()=>validate($bad)));
$bad=$a;$bad['observations'][0]['period_type']='fq';$bad['observations'][0]['fiscal_quarter']='1';ensure(reject(fn()=>validate($bad)));
$bad=$a;$bad['stored_evidence']['sha256']=str_repeat('0',64);ensure(reject(fn()=>storedFile($bad)));
// Rehash edited evidence, so rejection proves semantic binding, not just byte hash.
foreach(['tag','original_value','selected','reported_periods','source_response','identity_mapping'] as $key){
    $bad=$a;$doc=json_decode($bad['evidence_json'],true,64,JSON_THROW_ON_ERROR);
    if($key==='tag')$doc['facts'][0]['tag']='GrossProfit';
    elseif($key==='original_value')$doc['facts'][0]['original_value']='999';
    elseif($key==='selected')$doc['facts'][0]['selected']['form']='10-Q';
    elseif($key==='reported_periods')$doc['reported_periods']['2026']['anchor']['filing_fy']='2025';
    elseif($key==='source_response')$doc['source_response']['sha256']=str_repeat('0',64);
    else $doc['identity_mapping']['isin']='US76655K1034';
    $raw=json_encode($doc,JSON_THROW_ON_ERROR);$bad['evidence_json']=$raw;
    $bad['stored_evidence']['sha256']=$bad['archive']['sha256']=hash('sha256',$raw);$bad['stored_evidence']['bytes']=$bad['archive']['bytes']=strlen($raw);
    ensure(reject(fn()=>storedFile($bad)));
}
// Equal-period contradiction rolls back all catalog/fetch/fact changes.
$saved=$p->data;$bad=$a;$bad['observations'][0]['value_decimal']='999';ensure(reject(fn()=>transaction($p,$bad,'41',fn()=>null)));ensure($p->data===$saved);
echo json_encode(['ok'=>true,'assertions'=>$n]);
