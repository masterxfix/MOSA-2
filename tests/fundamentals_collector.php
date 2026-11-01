<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{transaction,readback,protectedAssets};
[$fy,$zeiss,$fq]=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
function expect(bool $ok):void {if(!$ok)throw new RuntimeException('collector_assertion');}
$p=new MemoryPDO();transaction($p,$fy,'42',fn()=>null);transaction($p,$zeiss,'99',fn()=>null);$before=$p->data;
$r=transaction($p,$fq,'42',fn()=>null);expect($r['observations']===8&&$r['current']===4&&$r['metrics']===0);
// Independent snapshot reader detects tampering; production additionally enforces a new connection.
$read=new MemoryPDO();$read->data=$p->data;readback($read,$r);
foreach(['m2_fundamental_observations','m2_fundamental_current'] as $t)
    expect(array_values(array_filter($p->data[$t],fn($row)=>$row['asset_id']==='99'||$row['period_type']==='fy'))===$before[$t]);
$again=transaction($p,$fq,'42',fn()=>null);expect($again['observations']===0&&$again['current']===0&&$again['facts_reused']===8);
$saved=$p->data;$bad=$fq;$bad['observations'][0]['value_decimal']='999';$rejected=false;
try{transaction($p,$bad,'42',fn()=>null);}catch(Throwable){$rejected=true;}expect($rejected&&$p->data===$saved);
$read->data['m2_fundamental_current'][count($read->data['m2_fundamental_current'])-1]['value_decimal']='999';$rejected=false;
try{readback($read,$r);}catch(Throwable){$rejected=true;}expect($rejected);
// Every write failure rolls back only the new quarter; previous issuers/years survive.
for($i=1;$i<=14;$i++){$p2=new MemoryPDO();transaction($p2,$fy,'42',fn()=>null);transaction($p2,$zeiss,'99',fn()=>null);$p2->failWrite=$p2->writes+$i;$saved2=$p2->data;$rejected=false;
    try{transaction($p2,$fq,'42',fn()=>null);}catch(Throwable){$rejected=true;}
    expect($rejected&&$p2->data===$saved2&&$p2->rollbacks===1);
}
echo json_encode(['ok'=>true]);
