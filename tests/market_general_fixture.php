<?php
// Reuse the transactional SQL double and real bridge/writer from market_runtime_fixture.
require_once dirname(__DIR__).'/scripts/market_collector/batch_scope.php';
require_once dirname(__DIR__).'/scripts/market_current/refresh.php';
$memory->last=max([1000,...array_map('intval',array_column($memory->rows['m2_market_observations'],'id'))]);
$config=$in['config']+['public_root'=>str_replace('\\','/',dirname(__DIR__)),'state_contract'=>['schema_version'=>4,'allow_current'=>true]];
$connect=static function()use($memory,&$connections){$connections++;return new MemoryConnection($memory);};
$invoke=static function($config,$request)use($in,&$providers){
    if($request['action']==='fetch'){
        $providers++;touch($request['private_root'].'/provider-consumed.lock');
        if(($in['fail_provider']??0)===$providers)throw new RuntimeException('fixture_provider_failure');
        $m=json_decode(file_get_contents($request['private_root'].'/live-manifest.json'),true);
        return $in['acquired_by_isin'][$m['instrument']];
    }
    return \Mosa2\MarketLive\bridge($config,$request);
};
$refresh=static function($approvals)use($config,$connect,$in){
    $capture=static fn($db)=>$db->state->rows;
    $inputs=static function($db,$now)use($approvals){
        $items=[];
        foreach($approvals as $approval){
            $route=array_values(array_filter($db->state->rows['m2_asset_source_routes'],static fn($r)=>$r['id']===$approval['route_id']))[0];
            $facts=array_values(array_filter($db->state->rows['m2_market_observations'],static fn($r)=>$r['route_id']===$route['id']));
            $old=array_values(array_filter($db->state->rows['m2_market_current'],static fn($r)=>$r['asset_id']===$route['asset_id']));
            $origin=$old===[]?null:array_values(array_filter($db->state->rows['m2_market_observations'],static fn($r)=>$r['id']===$old[0]['observation_id']))[0];
            $items[]=['route'=>$route,'approval'=>$approval,'facts'=>$facts,'current'=>$old[0]??null,'current_fact'=>$origin,'now'=>$now];
        }return $items;
    };
    $result=\Mosa2\MarketCurrent\transaction($connect(),$inputs,static fn($items)=>\Mosa2\MarketCurrent\plans($config,$items),$capture);
    $actual=$capture($connect());
    if($in['readback_fault']??false)$actual['m2_market_current'][0]['price']='999';
    return \Mosa2\MarketCurrent\verifyReadback($result,$actual);
};
$scope=['mode'=>$in['mode']??'manual','request_budget'=>5,'source_priority'=>['provider:tradegate_bsx_mid','provider:boerse_frankfurt_api']];
$selection=\Mosa2\MarketBatchScope\selection($memory->rows,gmdate('Y-m-d H:i:s').'.000000');
$plan=\Mosa2\MarketBatchScope\plan($memory->rows,$selection,$scope['source_priority'],\Mosa2\MarketBatch\providers(),'Mosa2\\MarketLive\\completePlan',$scope['mode']==='manual');
$scope['routes']=[];
foreach($plan['prepared'] as $item){$route=array_values(array_filter($memory->rows['m2_asset_source_routes'],static fn($r)=>$r['id']===$item['route_id']))[0];$scope['routes'][$item['route_id']]=hash('sha256',\Mosa2\Phase3D\json($route));}
if($in['bad_scope']??false)$scope['routes']=[];
$reports=[];
for($i=0;$i<($in['runs']??1);$i++){
    $root=$in['private_root'].'/run-'.$i;mkdir($root,0700);
    $reports[]=\Mosa2\MarketBatch\collect($root,'synthetic',$config,$scope,$connect,$invoke,$refresh);
}
