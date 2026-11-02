<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{transaction,readback,storedFile,validate};
[$byd,$ubtech]=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
function hkexExpect(bool $ok):void{if(!$ok)throw new RuntimeException('hkex_assertion');}
$catalog=\Mosa2\Fundamentals\validate($byd);
$p=new MemoryPDO();
foreach(['revenue','profit_before_tax','profit_after_tax','operating_cashflow'] as $key)$p->data['m2_fundamental_metrics'][]=$catalog['metrics'][$key];
$p->data['m2_fundamental_units'][]=$catalog['units']['CNY_THOUSAND'];
$legacy=['id'=>'legacy','asset_id'=>'legacy','metric_key'=>'revenue','period_type'=>'fy','fiscal_year'=>'2025','period_start'=>'2025-01-01','period_end'=>'2025-12-31','unit_key'=>'EUR_MILLION','unit_version'=>'1','value_decimal'=>'7','dedupe_key'=>'legacy-fact'];
$p->data['m2_fundamental_observations'][]=$legacy;$p->data['m2_fundamental_current'][]=$legacy+['observation_id'=>'legacy'];$legacyBefore=$p->data;
foreach([$byd,$ubtech] as $plan){validate($plan);storedFile($plan);}
$r1=transaction($p,$byd,'103',fn()=>null);
$read1=new MemoryPDO();$read1->data=$p->data;readback($read1,$r1);
$r2=transaction($p,$ubtech,'104',fn()=>null);
hkexExpect($r1['observations']===10&&$r1['current']===5&&$r2['observations']===10&&$r2['current']===5);
hkexExpect($r1['metrics']===1&&$r2['metrics']===0&&$r1['inserted']['m2_fundamental_units']===0&&$r2['inserted']['m2_fundamental_units']===0);
$read2=new MemoryPDO();$read2->data=$p->data;readback($read2,$r2);
$repeat1=transaction($p,$byd,'103',fn()=>null);$repeat2=transaction($p,$ubtech,'104',fn()=>null);
hkexExpect($repeat1['observations']===0&&$repeat1['current']===0&&$repeat1['facts_reused']===10);
hkexExpect($repeat2['observations']===0&&$repeat2['current']===0&&$repeat2['facts_reused']===10);
$saved=$p->data;$bad=$byd;$doc=json_decode($bad['evidence_json'],true,64,JSON_THROW_ON_ERROR);$doc['facts'][0]['original_value']='1';
$raw=json_encode($doc,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);$bad['evidence_json']=$raw;$bad['stored_evidence']['sha256']=$bad['archive']['sha256']=hash('sha256',$raw);$bad['stored_evidence']['bytes']=$bad['archive']['bytes']=strlen($raw);
$rejected=false;try{storedFile($bad);}catch(Throwable){$rejected=true;}hkexExpect($rejected&&$p->data===$saved);
$legacyAfter=array_intersect_key($p->data,['m2_fundamental_observations'=>true,'m2_fundamental_current'=>true]);
$legacyExpected=array_intersect_key($legacyBefore,['m2_fundamental_observations'=>true,'m2_fundamental_current'=>true]);
hkexExpect($legacyAfter['m2_fundamental_observations'][0]===$legacyExpected['m2_fundamental_observations'][0]&&$legacyAfter['m2_fundamental_current'][0]===$legacyExpected['m2_fundamental_current'][0]);
echo json_encode(['ok'=>true,'byd_observations'=>$r1['observations'],'ubtech_observations'=>$r2['observations'],'replay'=>'PASS','evidence_tamper'=>'PASS'],JSON_THROW_ON_ERROR);
