<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{transaction,readback};
[$fy,$zeiss,$pdf]=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
function pdfExpect(bool $ok):void {if(!$ok)throw new RuntimeException('pdf_assertion');}
function seeded(array $fy,array $zeiss):MemoryPDO {$p=new MemoryPDO();transaction($p,$fy,'42',fn()=>null);transaction($p,$zeiss,'99',fn()=>null);return $p;}
$p=seeded($fy,$zeiss);$before=$p->data;
$r=transaction($p,$pdf,'103',fn()=>null);pdfExpect($r['observations']===14&&$r['current']===7&&$r['metrics']===5);
pdfExpect($r['inserted']['m2_fundamental_units']===1);
$read=new MemoryPDO();$read->data=$p->data;readback($read,$r);
foreach(['m2_fundamental_observations','m2_fundamental_current'] as $t)
    pdfExpect(array_values(array_filter($p->data[$t],fn($row)=>$row['asset_id']!=='103'))===$before[$t]);
$again=transaction($p,$pdf,'103',fn()=>null);pdfExpect($again['observations']===0&&$again['current']===0&&$again['facts_reused']===14);
$saved=$p->data;$bad=$pdf;$bad['observations'][0]['value_decimal']='999';$rejected=false;
try{transaction($p,$bad,'103',fn()=>null);}catch(Throwable){$rejected=true;}pdfExpect($rejected&&$p->data===$saved);
$read->data['m2_fundamental_current'][count($read->data['m2_fundamental_current'])-1]['value_decimal']='999';$rejected=false;
try{readback($read,$r);}catch(Throwable){$rejected=true;}pdfExpect($rejected);
for($i=1;$i<=array_sum($r['inserted']);$i++){$p2=seeded($fy,$zeiss);$p2->failWrite=$p2->writes+$i;$saved2=$p2->data;$rejected=false;
    try{transaction($p2,$pdf,'103',fn()=>null);}catch(Throwable){$rejected=true;}
    pdfExpect($rejected&&$p2->data===$saved2&&$p2->rollbacks===1);
}
echo json_encode(['ok'=>true,'injected_write_failures'=>array_sum($r['inserted'])]);
