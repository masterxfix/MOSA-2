<?php
declare(strict_types=1);
namespace Mosa2\DogadoPne;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,qi,connection};
use function Mosa2\MarketLive\{runtimeContract,runtimeState,snapshot,completePlan,compareDelta};
const RELEASE='@RELEASE@';
const RUN='@RUN@';
const ISIN='DE000A0JBPG2';
const PHP='/opt/plesk/php/8.4/bin/php';
const PYTHON='/opt/alt/python311/bin/python3.11';
require_once RELEASE.'/scripts/market_collector/live_batch.php';
require_once RELEASE.'/scripts/collector_release/runtime.php';


/** Public errors are an explicit closed vocabulary, never arbitrary exception text. */
function safeFailureCode(string $code): string {
    $allowed=['one_isin_scope','php_pin','php_binary','release_path','run_path','run_owner_mode',
        'db_secret_required','database_operation_failed','existing_route_only','existing_asset_only',
        'bounded_test_state','manifest_exists','manifest_create','manifest_write','manifest_mode',
        'one_observation_budget','observation_scope','schema_drift','full_preflight_drift',
        'rollback_full_delta','independent_full_delta','checkpoint_budget','bridge_action',
        'one_provider_budget','provider_private_root','bridge_process','bridge_input_limit',
        'bridge_input','bridge_output_limit','bridge_deadline','bridge_exit','bridge_stderr',
        'bridge_fetch','bridge_plan','bridge_replay','connection_budget','four_checkpoints',
        'independent_readback','exact_observation_delta','identifier_lock_busy','acquisition_binding',
        'acquisition_source','one_provider_request','preflight_drift','runtime_route','candidate_plan',
        'candidate_drift','candidate_key_drift','writer_decision','duplicate_origin','duplicate_payload',
        'observation_readback','observation_exact','replay','replay_canonical','replay_key',
        'transaction_binding_drift','commit','independent_binding_drift'];
    return in_array($code,$allowed,true)?$code:'collector_check_failed';
}

function outcome(array $r,int $checkpoint): string {
    if(($r['ok']??false)===true)return 'COMPLETE';
    if(($r['committed']??false)===true||($checkpoint>=3&&($r['rollback']??null)!==true))return 'OUTCOME_UNKNOWN';
    return 'FAILED';
}
function delta(array $before,array $after,array $scope): array {
    $old=array_column($before['m2_market_observations'],'id');$new=[];
    foreach($after['m2_market_observations'] as $row)if(!in_array($row['id'],$old,true))$new[]=$row;
    check(count($new)<=1,'one_observation_budget');
    foreach($new as $row)foreach(['asset_id','source_id','route_id'] as $k)same($row[$k],$scope[$k],'observation_scope');
    compareDelta($before,$after,['deltas'=>['m2_market_observations'=>count($new)]],['m2_market_observations'=>$new]);
    return $new;
}
function schema(PDO $p): string {
    $tables=\Mosa2\Phase2\tables($p);$out=[];
    foreach($tables as $t){
        $sql=$p->query('SHOW CREATE TABLE '.qi($t))->fetch(PDO::FETCH_NUM)[1];
        $out[$t]=preg_replace('/ AUTO_INCREMENT=[0-9]+/','',$sql);
    }
    return hash('sha256',json_encode($out,JSON_THROW_ON_ERROR));
}
class Audit {
    public int $checkpoint=0;
    public float $milliseconds=0;
    public ?array $transactionAfter=null;
    public array $new=[];
    public function __construct(public array $before,public array $scope,public string $schema){}
    public function read(PDO $p,array $m,array $contract): array {
        $start=hrtime(true);
        try{
            $bounded=runtimeState($p,$m,$contract);$state=snapshot($p,$contract);
            same(schema($p),$this->schema,'schema_drift');$this->checkpoint++;
            if($this->checkpoint<=2)same($state,$this->before,'full_preflight_drift');
            elseif($this->checkpoint===3){$this->new=delta($this->before,$state,$this->scope);$this->transactionAfter=$state;}
            elseif($this->checkpoint===4){
                if($this->transactionAfter===null)same($state,$this->before,'rollback_full_delta');
                else same($state,$this->transactionAfter,'independent_full_delta');
            }else throw new \RuntimeException('checkpoint_budget');
            return $bounded;
        }finally{$this->milliseconds+=(hrtime(true)-$start)/1e6;}
    }
}
function boundedBridge(array $config,array $request): array {
    static $fetches=0;
    check(in_array($request['action']??null,['fetch','plan','replay'],true),'bridge_action');
    if($request['action']==='fetch'){
        same(++$fetches,1,'one_provider_budget');
        same($request['private_root'],RUN,'provider_private_root');
    }
    $request['request_script']=RELEASE.'/scripts/market_collector/frankfurt_request.php';
    $p=proc_open([PYTHON,'-I','-B',RELEASE.'/scripts/market_collector/live_bridge.py'],
        [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes,RELEASE,
        ['PATH'=>'/opt/plesk/php/8.4/bin:/usr/bin:/bin','PYTHONDONTWRITEBYTECODE'=>'1',
         'PHPRC'=>'/dev/null','PHP_INI_SCAN_DIR'=>'']);
    check(is_resource($p),'bridge_process');$out='';$err='';$exit=-1;
    $wire=json_encode($request,JSON_THROW_ON_ERROR);check(strlen($wire)<=32768,'bridge_input_limit');
    try{
        same(fwrite($pipes[0],$wire),strlen($wire),'bridge_input');fclose($pipes[0]);unset($pipes[0]);
        stream_set_blocking($pipes[1],false);stream_set_blocking($pipes[2],false);
        $deadline=microtime(true)+($request['action']==='fetch'?35:15);
        do {
            $out.=stream_get_contents($pipes[1]);$err.=stream_get_contents($pipes[2]);
            check(strlen($out)+strlen($err)<=65536,'bridge_output_limit');
            $status=proc_get_status($p);
            if(!$status['running']){
                $exit=$status['exitcode'];
                $out.=stream_get_contents($pipes[1]);$err.=stream_get_contents($pipes[2]);break;
            }
            check(microtime(true)<$deadline,'bridge_deadline');usleep(10000);
        }while(true);
    }finally{
        if(proc_get_status($p)['running'])proc_terminate($p,9);
        foreach($pipes as $pipe)if(is_resource($pipe))fclose($pipe);
        proc_close($p);
    }
    same($exit,0,'bridge_exit');same($err,'','bridge_stderr');check(strlen($out)<=65536,'bridge_output_limit');
    $reply=json_decode($out,true,64,JSON_THROW_ON_ERROR);same($reply['ok']??false,true,'bridge_'.$request['action']);
    return $reply;
}
function perform(string $password,array $input): array {
    $r=['ok'=>false,'status'=>'FAILED','stage'=>'preflight','isin'=>ISIN,'asset'=>'PNE AG','provider_requests'=>0];
    $audit=null;$prim=null;$connections=0;$connectionMs=0;$bridgeMs=0;$collectStart=null;
    $start=hrtime(true);
    try{
        same($input['isin']??null,ISIN,'one_isin_scope');same(PHP_VERSION,'8.4.12','php_pin');
        same(realpath(PHP_BINARY),realpath(PHP),'php_binary');same(realpath(RELEASE),RELEASE,'release_path');
        same(realpath(RUN),RUN,'run_path');check(!is_link(RUN)&&fileowner(RUN)===10317&&filegroup(RUN)===1003&&(fileperms(RUN)&0777)===0700,'run_owner_mode');
        $r['stage']='runtime_configuration';
        $config=\Mosa2\CollectorRelease\configuration(RELEASE);
        $config+=['state_contract'=>['schema_version'=>4,'allow_current'=>true]];
        $r['stage']='database_preflight';
        $t=hrtime(true);$prim=connection($password);$connectionMs+=(hrtime(true)-$t)/1e6;
        $prim->exec('SET TRANSACTION READ ONLY');$prim->beginTransaction();
        try{
            runtimeContract($prim,$config['state_contract']);$before=snapshot($prim,$config['state_contract']);$schema=schema($prim);
            foreach($before as $rows)check(count($rows)<=10000,'bounded_test_state');
            $m=\Mosa2\MarketAcceptance\manifest($before,['isin'=>ISIN,'name'=>'PNE AG']);
            same($m['policy'],'USE_EXISTING_ROUTE','existing_route_only');
            $plan=completePlan($before,$m);
            same($plan['asset']['decision'],'EXISTING_MATCH','existing_asset_only');
            same($plan['route']['decision'],'EXISTING_MATCH','existing_route_only');
            $scope=['asset_id'=>$plan['asset']['asset_id'],'source_id'=>$plan['source']['source_id'],'route_id'=>$plan['route']['route_id']];
        }finally{if($prim->inTransaction())$prim->rollBack();}
        $r['stage']='manifest';
        $r['preflight']='PASS';$r['scope']=$scope;
        $r['preflight_ms']=(hrtime(true)-$start)/1e6;
        check(!file_exists(RUN.'/live-manifest.json')&&!is_link(RUN.'/live-manifest.json'),'manifest_exists');
        $file=fopen(RUN.'/live-manifest.json','x');check(is_resource($file),'manifest_create');
        try{$wire=json_encode($m,JSON_THROW_ON_ERROR);same(fwrite($file,$wire),strlen($wire),'manifest_write');fflush($file);}
        finally{fclose($file);}
        same(fileperms(RUN.'/live-manifest.json')&0777,0600,'manifest_mode');
        $audit=new Audit($before,$scope,$schema);
        $connect=static function()use(&$connections,&$prim,&$connectionMs,$password): PDO {
            check(++$connections<=2,'connection_budget');
            if($connections===1){$p=$prim;$prim=null;return $p;}
            $t=hrtime(true);try{return connection($password);}finally{$connectionMs+=(hrtime(true)-$t)/1e6;}
        };
        $invoke=static function($config,$request)use(&$bridgeMs){
            $t=hrtime(true);try{return boundedBridge($config,$request);}finally{$bridgeMs+=(hrtime(true)-$t)/1e6;}
        };
        $r['stage']='collector';$collectStart=hrtime(true);
        $result=\Mosa2\MarketLive\runtimeRun(RUN,$config,$m,$connect,$invoke,[$audit,'read']);
        $r['collector_ms']=(hrtime(true)-$collectStart)/1e6;
        unset($connect,$invoke,$password);
        if(isset($result['failure']))$result['failure']=safeFailureCode($result['failure']);
        $r['result']=$result;
        if(isset($result['failure'])){$r['failure_code']=$result['failure'];$r['failure_phase']=in_array($result['stage'],['preflight','provider','transaction','readback'],true)?$result['stage']:'collector';}$r['status']=outcome($result,$audit->checkpoint);$r['ok']=$r['status']==='COMPLETE';
        if($r['ok']){
            same($audit->checkpoint,4,'four_checkpoints');same($result['readback'],'PASS','independent_readback');
            same(count($audit->new),$result['writer']==='INSERT'?1:0,'exact_observation_delta');
            $r+=['observation_delta'=>count($audit->new),'current_unchanged'=>'PASS','bars_unchanged'=>'PASS',
                'catalog_route_unit_unchanged'=>'PASS','old_observations_unchanged'=>'PASS','unexpected_business_writes'=>'NONE'];
        }
    }catch(Throwable $e){
        $r['ok']=false;$r['failure_type']=$e instanceof \PDOException?'PDOException':'CollectorCheck';
        $r['failure_code']=$e instanceof \PDOException?'database_operation_failed':safeFailureCode($e->getMessage());
        $r['failure_phase']=$r['stage'];
        if(isset($result))$r['status']=($result['committed']??false)?'OUTCOME_UNKNOWN':outcome($result,$audit?->checkpoint??0);
    }finally{
        $r['provider_requests']=is_file(RUN.'/provider-consumed.lock')?1:0;
        $r['provider_marker_retained']=$r['provider_requests']===1;
        $r['checkpoint_count']=$audit?->checkpoint??0;
        $r['db_checkpoints_ms']=$audit?->milliseconds??0;
        $r['connection_ms']=$connectionMs;$r['bridge_total_ms']=$bridgeMs;
        $r['total_with_preflight_ms']=(hrtime(true)-$start)/1e6;
        $r['stage']=$r['ok']?'complete':$r['stage'];
        $prim=null;unset($password,$input);
    }
    return $r;
}
function main(): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{
        $input=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
        check(is_string($input['password']??null)&&$input['password']!=='','db_secret_required');
        $r=perform($input['password'],$input);unset($input);
        echo json_encode($r,JSON_THROW_ON_ERROR);
    }catch(Throwable $e){echo json_encode(['ok'=>false,'status'=>'FAILED','stage'=>'initialization','failure_code'=>safeFailureCode($e->getMessage()),'failure_phase'=>'initialization'],JSON_THROW_ON_ERROR);}
}
