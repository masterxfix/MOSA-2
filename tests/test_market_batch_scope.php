<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/market_collector/batch_scope.php';
use function Mosa2\MarketBatchScope\plan;

function eq(mixed $actual, mixed $expected, string $name): void {
    if ($actual !== $expected) throw new RuntimeException($name . ': ' . json_encode([$actual, $expected]));
}
function fail(callable $work, string $name): void {
    try { $work(); } catch (InvalidArgumentException) { return; }
    throw new RuntimeException('expected rejection: '.$name);
}
function source(string $name): string { return 'provider:'.$name; }
function item(string $id, string $isin, string $status = 'READY', string $manual = 'MANUAL_ROUTE_PREPARABLE'): array {
    return ['asset_id'=>$id,'name'=>'Synthetic '.$id,'isin'=>$isin,'identity_status'=>'VALID',
        'collector_status'=>$status,'manual_status'=>$manual];
}
function candidate(array $asset, string $sourceKey, string $sourceId, string $routeId): array {
    return ['asset_id'=>$asset['asset_id'],'name'=>$asset['name'],'isin'=>$asset['isin'],
        'source_key'=>$sourceKey,'source_id'=>$sourceId,'route_id'=>$routeId];
}
function service(): array {
    $a=item('10','ZZ0000000000');$b=item('20','ZZ0000000010');$c=item('30','ZZ0000000020','ROUTE_UNAVAILABLE');
    $s=['status'=>'ok','assets'=>[$a,$b,$c],
        'collector_candidates'=>[candidate($a,source('one'),'101','501'),candidate($b,source('two'),'102','502'),candidate($b,source('one'),'101','503')],
        'manual_candidates'=>[candidate($a,source('one'),'101','601'),candidate($b,source('two'),'102','602'),candidate($c,source('one'),'101','603')]];
    $factories=[source('one')=>static fn($state,$x)=>['policy'=>'USE_EXISTING_ROUTE','identity'=>['normalized_value'=>$x['isin']]],
        source('two')=>static fn($state,$x)=>['policy'=>'USE_EXISTING_ROUTE','identity'=>['normalized_value'=>$x['isin']]]];
    $planner=static fn($state,$manifest)=>['route'=>['decision'=>'EXISTING_MATCH','route_id'=>match($manifest['identity']['normalized_value']){
        'ZZ0000000000'=>'501','ZZ0000000010'=>'503',default=>'603'}],
        'source'=>['source_id'=>'101'],'asset'=>['asset_id'=>match($manifest['identity']['normalized_value']){'ZZ0000000000'=>'10','ZZ0000000010'=>'20',default=>'30'}]];
    return [$s,$factories,$planner];
}
$n=0;
[$s,$factories,$planner]=service();
$result=plan([],$s,[source('one'),source('two')],$factories,$planner);
eq(count($result['prepared']),2,'two automatic assets');eq(count($result['unavailable']),1,'disabled not automatic');
eq($result['prepared'][1]['route_id'],'503','priority and route binding');$n++;
eq([$result['execution_authorized'],$result['provider_requests'],$result['database_writes']],[false,0,0],'no side effects');$n++;
fail(static fn()=>plan([],$s,[source('two'),source('one')],$factories,$planner),'wrong source physical route');$n++;
fail(static fn()=>plan([],$s,[source('one'),source('one')],$factories,$planner),'duplicate source priority');$n++;
fail(static fn()=>plan([],$s,[source('unknown')],$factories,$planner),'unknown provider');$n++;
fail(static fn()=>plan([],$s,[source('one'),source('two')],$factories,$planner,false,1),'bounded batch');$n++;
$mut=$s;$mut['collector_candidates'][]=$mut['collector_candidates'][0];
fail(static fn()=>plan([],$mut,[source('one')],$factories,$planner),'ambiguous route');$n++;
$mut=$s;$mut['collector_candidates'][0]['isin']='ZZ9999999999';
fail(static fn()=>plan([],$mut,[source('one')],$factories,$planner),'different ISIN binding');$n++;
$mut=$s;$mut['assets'][]=$mut['assets'][0];
fail(static fn()=>plan([],$mut,[source('one')],$factories,$planner),'duplicate asset');$n++;
$mut=$s;$mut['status']='failure';
fail(static fn()=>plan([],$mut,[source('one')],$factories,$planner),'invalid source selection');$n++;
$mut=$s;$mut['collector_candidates']=[];$mut['assets']=[$mut['assets'][2]];
$mut['manual_candidates']=[candidate($mut['assets'][0],source('one'),'101','603')];
$result=plan([],$mut,[source('one')],$factories,$planner,true);
eq(count($result['prepared']),1,'manual does not enable automatic');eq($result['mode'],'manual','explicit mode');$n++;
$mut=$s;$mut['collector_candidates']=[];$mut['assets']=[$mut['assets'][2]];$mut['manual_candidates']=[];
$result=plan([],$mut,[source('one')],$factories,$planner);
eq(count($result['prepared']),0,'zero automatic routes allowed without side effects');$n++;
$mut = $s;
$mut['assets'] = null;
fail(static fn()=>plan([],$mut,[source('one')],$factories,$planner),'missing asset array');$n++;
$mut = $s;
$mut['assets'][1]['isin'] = $mut['assets'][0]['isin'];
fail(static fn()=>plan([],$mut,[source('one')],$factories,$planner),'duplicate qualified ISIN');$n++;
$mut = $s;
$mut['collector_candidates'][1]['route_id'] = '501';
$mut['collector_candidates'][2]['route_id'] = '501';
$sharedPhysicalPlan = static fn($state,$manifest)=>['route'=>['decision'=>'EXISTING_MATCH','route_id'=>'501'],
    'source'=>['source_id'=>'101'], 'asset'=>['asset_id'=>$manifest['identity']['normalized_value']==='ZZ0000000000'?'10':'20']];
fail(static fn()=>plan([],$mut,[source('one')],$factories,$sharedPhysicalPlan),'reused physical route');$n++;
$source=file_get_contents(dirname(__DIR__).'/scripts/market_collector/batch_scope.php');
foreach(['DE000A0JBPG2','tradegate_bsx_mid','MOSA_TEST_DB_PASSWORD','curl_','PDO','file_put_contents'] as $forbidden)
    if (str_contains($source,$forbidden)) throw new RuntimeException('asset or network special case '.$forbidden);
$n++;
echo 'PASS '. $n . '/'.$n." generic routing cases\n";
