<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{transaction,validate};
[$pne,$zeiss]=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
$checks=0;
function verify(bool $condition):void {global $checks;$checks++;if(!$condition)throw new RuntimeException('assertion_'.$checks);}
function rejected(callable $fn):bool {try{$fn();return false;}catch(Throwable){return true;}}
$p=new MemoryPDO();$first=transaction($p,$pne,'42',fn()=>null);$original=$p->data;
$second=transaction($p,$zeiss,'99',fn()=>null);
verify($second['observations']===22);verify($second['current']===11);verify($second['metrics']===9);
verify($second['inserted']['m2_fundamental_units']===2);
foreach(['m2_fundamental_observations','m2_fundamental_current'] as $table)
    verify(array_values(array_filter($p->data[$table],fn($r)=>$r['asset_id']==='42'))===$original[$table]);
$repeat=$zeiss;$repeat['metadata']['observed_at']='2026-11-01 00:00:01.000000';
foreach($repeat['observations'] as &$r)$r['observed_at']=$repeat['metadata']['observed_at'];unset($r);
$again=transaction($p,$repeat,'99',fn()=>null);
verify($again['observations']===0);verify($again['facts_reused']===22);verify($again['current']===0&&$again['current_updates']===0);
verify($again['metrics']===0&&$again['inserted']['m2_sources']===0&&$again['inserted']['m2_fundamental_units']===0);
$exact=transaction($p,$repeat,'99',fn()=>null);
verify(array_sum($exact['inserted'])===0);verify($exact['current_updates']===0);
$saved=$p->data;
foreach([0,1] as $i){$bad=$repeat;$bad['observations'][$i]['value_decimal']='9999';
    verify(rejected(fn()=>transaction($p,$bad,'99',fn()=>null)));verify($p->data===$saved);}
$bad=$repeat;$bad['metrics'][0]['value_semantics']='changed definition';
verify(rejected(fn()=>transaction($p,$bad,'99',fn()=>null)));verify($p->data===$saved);
// FY and FQ use separate Current slots. Fiscal year is named by its ending year.
$quarter=$zeiss;$quarter['observations']=array_slice($zeiss['observations'],0,1);
$quarter['observations'][0]=array_replace($quarter['observations'][0],['period_type'=>'fq','fiscal_quarter'=>'1','period_end'=>'2024-12-31']);
$q1=transaction($p,$quarter,'99',fn()=>null);verify($q1['observations']===1&&$q1['current']===1);
$q2=$quarter;$q2['observations'][0]=array_replace($q2['observations'][0],['fiscal_quarter'=>'2','period_start'=>'2025-01-01','period_end'=>'2025-03-31']);
$r2=transaction($p,$q2,'99',fn()=>null);verify($r2['current_updates']===1&&$r2['current']===0);
$older=transaction($p,$quarter,'99',fn()=>null);verify($older['current_updates']===0&&$older['observations']===0);
$invalid=$quarter;$invalid['observations'][0]['period_start']='2025-01-01';verify(rejected(fn()=>validate($invalid)));
$invalid=$quarter;$invalid['observations'][0]['fiscal_quarter']='5';verify(rejected(fn()=>validate($invalid)));
$invalid=$zeiss;$invalid['fiscal_year_start_month']=1;verify(rejected(fn()=>validate($invalid)));
// A newer FY advances only after validation; late prior years cannot displace it.
$new=$zeiss;$new['observations']=array_slice($new['observations'],0,1);
$new['observations'][0]=array_replace($new['observations'][0],['fiscal_year'=>'2026','period_start'=>'2025-10-01','period_end'=>'2026-09-30']);
$newResult=transaction($p,$new,'99',fn()=>null);verify($newResult['current_updates']===1);
$oldResult=transaction($p,$zeiss,'99',fn()=>null);verify($oldResult['current_updates']===0);
echo json_encode(['ok'=>true,'assertions'=>$checks],JSON_THROW_ON_ERROR);
