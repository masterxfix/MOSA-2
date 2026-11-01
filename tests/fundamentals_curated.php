<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{transaction,readback};
[$fy,$zeiss,$curated]=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
function expectCurated(bool $ok):void{if(!$ok)throw new RuntimeException('curated_assertion');}
function seedCurated(array $fy,array $zeiss):MemoryPDO{$p=new MemoryPDO();transaction($p,$fy,'42',fn()=>null);transaction($p,$zeiss,'99',fn()=>null);return $p;}
$p=seedCurated($fy,$zeiss);$before=$p->data;$receipt=transaction($p,$curated,'103',fn()=>null);
expectCurated($receipt['observations']===14&&$receipt['current']===7&&$receipt['metrics']===5);
$file=end($p->data['m2_files']);$fetch=end($p->data['m2_provider_fetches']);
expectCurated($file['storage_backend']==='dogado_private_curated_evidence_v1'&&$file['mime_type']==='application/json');
expectCurated($fetch['http_status']===null&&$fetch['parser_key']==='curated_public_facts_v1'&&$fetch['content_type']==='application/json');
expectCurated(bin2hex($file['sha256'])===$curated['stored_evidence']['sha256']&&bin2hex($fetch['payload_sha256'])===$curated['metadata']['sha256']);
$read=new MemoryPDO();$read->data=$p->data;$facts=readback($read,$receipt);expectCurated(count($facts)===14);
foreach(['m2_fundamental_observations','m2_fundamental_current'] as $table)
    expectCurated(array_values(array_filter($p->data[$table],fn($r)=>$r['asset_id']!=='103'))===$before[$table]);
$again=transaction($p,$curated,'103',fn()=>null);expectCurated($again['observations']===0&&$again['current']===0&&$again['facts_reused']===14);
foreach(['hash','http','body','value','source','unit'] as $case){$bad=$curated;$saved=$p->data;$rejected=false;
    if($case==='hash')$bad['stored_evidence']['sha256']=str_repeat('a',64);
    if($case==='http')$bad['metadata']['http_status']=200;
    if($case==='body')$bad['evidence_json'].=' ';
    if($case==='value')$bad['observations'][0]['value_decimal']='999';
    if($case==='source')$bad['source']['source_type']='issuer_release';
    if($case==='unit')$bad['units'][0]['monetary_currency_code']='USD';
    try{transaction($p,$bad,'103',fn()=>null);}catch(Throwable){$rejected=true;}
    expectCurated($rejected&&$p->data===$saved);
}
for($i=1;$i<=array_sum($receipt['inserted']);$i++){$p2=seedCurated($fy,$zeiss);$p2->failWrite=$p2->writes+$i;$saved=$p2->data;$rejected=false;
    try{transaction($p2,$curated,'103',fn()=>null);}catch(Throwable){$rejected=true;}
    expectCurated($rejected&&$p2->data===$saved&&$p2->rollbacks===1);
}
$p3=new MemoryPDO(0,true);$unknown=false;try{transaction($p3,$curated,'103',fn()=>null);}catch(Throwable){$unknown=true;}
expectCurated($unknown&&$p3->commits===1&&$p3->rollbacks===0&&count($p3->data['m2_fundamental_observations'])===14);
$read->data['m2_provider_fetches'][count($read->data['m2_provider_fetches'])-1]['http_status']='200';$rejected=false;
try{readback($read,$receipt);}catch(Throwable){$rejected=true;}expectCurated($rejected);
echo json_encode(['ok'=>true,'injected_write_failures'=>array_sum($receipt['inserted'])]);
