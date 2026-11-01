<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{transaction,readback,storedFile};
[$fy,$zeiss,$html]=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
function expectHtml(bool $ok):void {if(!$ok)throw new RuntimeException('html_assertion');}
$p=new MemoryPDO();transaction($p,$fy,'42',fn()=>null);transaction($p,$zeiss,'99',fn()=>null);$before=$p->data;
$receipt=transaction($p,$html,'103',fn()=>null);
expectHtml($receipt['observations']===14&&$receipt['current']===7&&$receipt['metrics']===5);
$file=end($p->data['m2_files']);$fetch=end($p->data['m2_provider_fetches']);
expectHtml($file['storage_backend']==='dogado_private_evidence_json_v1'&&$file['mime_type']==='application/json');
expectHtml(bin2hex($file['sha256'])===$html['stored_evidence']['sha256']&&bin2hex($fetch['payload_sha256'])===$html['metadata']['sha256']&&$file['sha256']!==$fetch['payload_sha256']);
$read=new MemoryPDO();$read->data=$p->data;$facts=readback($read,$receipt);expectHtml(count($facts)===14);
foreach(['m2_fundamental_observations','m2_fundamental_current'] as $table)
    expectHtml(array_values(array_filter($p->data[$table],fn($r)=>$r['asset_id']!=='103'))===$before[$table]);
$again=transaction($p,$html,'103',fn()=>null);expectHtml($again['observations']===0&&$again['current']===0&&$again['facts_reused']===14);
foreach(['hash','body','binding','locator','conflict'] as $case){$bad=$html;$saved=$p->data;$rejected=false;
    if($case==='hash')$bad['stored_evidence']['sha256']=str_repeat('a',64);
    if($case==='body')$bad['evidence_json'].=' ';
    if($case==='binding')$bad['metadata']['url']='https://invalid.example/';
    if($case==='locator')$bad['observations'][0]['field_path']='false';
    if($case==='conflict')$bad['observations'][0]['value_decimal']='999';
    try{transaction($p,$bad,'103',fn()=>null);}catch(Throwable){$rejected=true;}
    expectHtml($rejected&&$p->data===$saved);
}
$read->data['m2_files'][count($read->data['m2_files'])-1]['sha256']=hex2bin(str_repeat('f',64));$rejected=false;
try{readback($read,$receipt);}catch(Throwable){$rejected=true;}expectHtml($rejected);
echo json_encode(['ok'=>true]);
