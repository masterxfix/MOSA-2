<?php
declare(strict_types=1);
namespace Mosa2\Phase3O;
require_once __DIR__.'/password_gateway.php';
use PDO;
use PDOStatement;
use RuntimeException;
use function Mosa2\Phase2\{check,same};

class TestStatement extends PDOStatement {
    public function __construct(private TestPDO $db){}
    public function execute(?array $params=null): bool {
        if($this->db->fail)throw new RuntimeException('synthetic_sql_failure');
        $this->db->parameters[]=$params;return true;
    }
    public function rowCount(): int {return 1;}
}
class TestPDO extends PDO {
    public bool $active=false;
    public bool $fail=false;
    public bool $rollbackThrows=false;
    public bool $beginThrows=false;
    public int $begins=0;
    public int $rollbacks=0;
    public int $commits=0;
    public array $sql=[];
    public array $parameters=[];
    public function __construct(){}
    public function inTransaction(): bool {return $this->active;}
    public function beginTransaction(): bool {$this->begins++;if($this->beginThrows)throw new RuntimeException('begin_exception');return $this->active=true;}
    public function rollBack(): bool {$this->rollbacks++;if($this->rollbackThrows)throw new RuntimeException('rollback_exception');$this->active=false;return true;}
    public function commit(): bool {$this->commits++;throw new RuntimeException('commit_forbidden');}
    public function prepare(string $query,array $options=[]): PDOStatement|false {$this->sql[]=$query;return new TestStatement($this);}
    public function lastInsertId(?string $name=null): string {return '9001';}
}
function rejected(callable $body): void {
    $caught=false;try{$body();}catch(\Throwable $e){$caught=true;}
    check($caught,'invalid_plan_accepted');
}
function selfTest(): array {
    $fixture=dirname(__DIR__,2).'/tests/fixtures/phase3o_runtime_expected.json';
    $plans=json_decode(file_get_contents($fixture),true,512,JSON_THROW_ON_ERROR);$result=[];
    foreach($plans as $plan){
        $db=new TestPDO;$route=$plan['route_binding']['matched_fields'];
        same(rollbackTransaction($db,function()use($db,$plan,$route){executePlan($db,$plan,$route);return 'done';}),'done','body_result');
        same([$db->begins,$db->rollbacks,$db->commits,$db->active],[1,1,0,false],'success_rollback');
        same(count($db->sql),1,'one_prepared');check(str_starts_with($db->sql[0],'INSERT INTO m2_market_observations ('),'prepared_sql');
        same(substr_count($db->sql[0],'?'),21,'placeholders');same(count($db->parameters[0]),21,'bound_values');
        $values=insertValues($plan,$route);same($db->parameters[0],array_values($values),'exact_plan_parameters');
        $closed=new TestPDO;rejected(fn()=>executePlan($closed,$plan,$route));same($closed->sql,[],'no_sql_outside_tx');
    }
    $result['four_insert_plans_exact']=true;$result['prepared_only']=true;$result['success_rollback']=true;
    $plan=$plans[0];$route=$plan['route_binding']['matched_fields'];
    $mutations=[
        'decision'=>function(&$p){$p['decision']='DUPLICATE_UNCHANGED';},
        'format'=>function(&$p){$p['observation_format_version']=1;},
        'catalog'=>function(&$p){$p['catalog_fingerprint']=str_repeat('0',64);},
        'missing_column'=>function(&$p){array_pop($p['expected_db_columns']);},
        'extra_column'=>function(&$p){$p['db_values']['id']='1';},
        'value_marker'=>function(&$p){$p['db_values']['observation_format_version']=null;},
        'changed_value'=>function(&$p){$p['db_values']['price']='999';},
        'float'=>function(&$p){$p['db_values']['price']=42.125;},
        'key_length'=>function(&$p){$p['dedupe_key']=wireKey(str_repeat('x',32));$p['dedupe_key']['$bytes']=base64_encode('short');},
        'key_hash'=>function(&$p){$p['dedupe_key']=wireKey(str_repeat('x',32));},
        'value_key'=>function(&$p){$p['db_values']['dedupe_key']=wireKey(str_repeat('x',32));},
        'hex_wire'=>function(&$p){$p['dedupe_key']=str_repeat('0',64);},
        'base64'=>function(&$p){$p['dedupe_key']=['$bytes'=>'!!'];},
        'canonical'=>function(&$p){$p['canonical_bytes']['$bytes']=base64_encode('changed');},
        'normalized'=>function(&$p){$p['normalized']['price']='99';},
        'created'=>function(&$p){$p['db_values']['created_at']='2026-01-01';},
        'route'=>function(&$p){$p['route_binding']['matched_fields']['id']='7';},
        'route_format'=>function(&$p){$p['route_binding']['format_version']=1;},
        'revision'=>function(&$p){$p['route_binding']['route_revision']='2';},
    ];
    foreach($mutations as $name=>$mutate){
        $bad=$plan;$mutate($bad);$db=new TestPDO;$db->active=true;
        rejected(fn()=>executePlan($db,$bad,$route));same($db->sql,[],'mutation_sql:'.$name);
    }
    $result['invalid_plans_rejected']=count($mutations);
    foreach([false,true] as $sqlFailure){
        $db=new TestPDO;$db->fail=$sqlFailure;
        rejected(fn()=>rollbackTransaction($db,function()use($db,$plan,$route,$sqlFailure){
            if($sqlFailure)executePlan($db,$plan,$route);throw new RuntimeException('synthetic_guard_failure');
        }));same([$db->begins,$db->rollbacks,$db->commits,$db->active],[1,1,0,false],'failure_rollback');
    }
    $result['error_and_sql_failure_rollback']=true;
    foreach(['after_begin','after_graph','after_observation','normal'] as $stage){
        $db=new TestPDO;$report=transactionState();$caught=null;
        try{rollbackTransaction($db,function()use($db,$stage,$plan,$route){
            if($stage==='after_begin')throw new RuntimeException($stage);
            // Exercise actual graph-insert primitive without inventing SQL control flow.
            for($i=0;$i<13;$i++)preparedInsert($db,'m2_entities',['canonical_name'=>'synthetic']);
            if($stage==='after_graph')throw new RuntimeException($stage);
            executePlan($db,$plan,$route);
            if($stage==='after_observation')throw new RuntimeException($stage);
        },$report);}catch(RuntimeException $e){$caught=$e->getMessage();}
        same($caught,$stage==='normal'?null:$stage,'failure_stage');
        same(count($db->parameters),['after_begin'=>0,'after_graph'=>13,'after_observation'=>14,'normal'=>14][$stage],'failure_insert_count');
        foreach(['transaction_started','rollback_attempted','rollback_call_succeeded','rollback_transaction_closed'] as $key)same($report[$key],true,'rollback_flag:'.$key);
        same($report['post_rollback_readback_1_confirmed'],false,'no_implicit_readback_1');
        same($report['post_rollback_readback_2_confirmed'],false,'no_implicit_readback_2');
        same([$db->rollbacks,$db->commits,$db->active],[1,0,false],'exactly_one_rollback');
    }
    $db=new TestPDO;$db->beginThrows=true;$report=transactionState();
    try{rollbackTransaction($db,fn()=>null,$report);}catch(RuntimeException $e){same($e->getMessage(),'begin_exception','begin_exception_visible');}
    same($report,transactionState(),'before_begin_flags');same($db->rollbacks,0,'before_begin_no_rollback');
    $db=new TestPDO;$db->rollbackThrows=true;$report=transactionState();$caught=null;
    try{rollbackTransaction($db,fn()=>null,$report);}catch(RuntimeException $e){$caught=$e->getMessage();}
    same($caught,'rollback_exception','rollback_exception_visible');
    same([$report['transaction_started'],$report['rollback_attempted'],$report['rollback_call_succeeded'],$report['rollback_transaction_closed']],[true,true,false,false],'rollback_exception_flags');
    same($db->rollbacks,1,'rollback_exception_no_retry');
    $complete=array_fill_keys(array_keys(transactionState()),true)+['transaction'=>['observation_inserts'=>4],'lock_released'=>true];
    check(completeReport($complete),'complete_confirmed');
    foreach(array_keys(transactionState()) as $key){$bad=$complete;$bad[$key]=false;check(!completeReport($bad),'completion_requires:'.$key);}
    $bad=$complete;$bad['failure']=['reason'=>'synthetic'];check(!completeReport($bad),'failure_not_complete');
    $result['rollback_control_flow_and_post_readback_gates']=true;
    $db=new TestPDO;$db->active=true;rejected(fn()=>rollbackTransaction($db,fn()=>null));same($db->begins,0,'nested_rejected');
    rejected(fn()=>preparedInsert($db,'m2_schema_migrations',[]));same($db->sql,[],'ledger_sql_absent');
    $state=['environment'=>[],'structure'=>['metadata'=>[]],'rows'=>['t'=>[['id'=>'1']]],'row_hash'=>'fixed','ledger'=>[],'units'=>[['unit_key'=>'SYNTH']], 'counter_diagnostics'=>[]];
    $hash=stateHash($state);$state['counter_diagnostics']=['counter'=>'99'];same(stateHash($state),$hash,'counter_diagnostic_only');
    $state['units'][0]['unit_key']='OTHER';check(stateHash($state)!==$hash,'unit_hash_bound');
    $state['units'][0]['unit_key']='SYNTH';$state['rows']['t'][0]['id']='2';check(stateHash($state)!==$hash,'pk_hash_bound');
    $result['state_hash_units_pks_and_counter_diagnostics']=true;
    $config=['host'=>'mosa2-test.scharwerk.de','expires'=>2000];$server=['HTTPS'=>'on','HTTP_HOST'=>$config['host'],'REQUEST_METHOD'=>'POST','HTTP_ORIGIN'=>'https://'.$config['host'],'CONTENT_LENGTH'=>'10','QUERY_STRING'=>''];
    check(\Mosa2\Phase3M\requestAllowed($server,$config,1000),'request_valid');
    foreach(['HTTPS'=>'off','HTTP_ORIGIN'=>'https://invalid.example','QUERY_STRING'=>'secret=bad'] as $k=>$v){$bad=$server;$bad[$k]=$v;check(!\Mosa2\Phase3M\requestAllowed($bad,$config,1000),'request_reject');}
    $token='1000.'.str_repeat('a',64);$token.='.'.hash_hmac('sha256',$token,'synthetic-key');
    check(\Mosa2\Phase3M\tokenValid($token,$token,'synthetic-key',1001),'csrf_valid');
    check(!\Mosa2\Phase3M\tokenValid($token,$token,'wrong-key',1001),'csrf_bad_key');
    check(!\Mosa2\Phase3M\tokenValid($token,$token,'synthetic-key',1700),'csrf_expired');
    $result['origin_https_query_csrf']=true;
    $config=['hashes'=>['scripts/synthetic.php'=>str_repeat('a',64)],'runtime_path'=>'synthetic-path'];
    $proof=['status'=>'RUNTIME_READY','context'=>'gateway','fingerprint'=>capabilityFingerprint($config),'database_connections'=>0,'database_writes'=>0];
    foreach(['four_full_golden_plans','canonical_bytes_exact','raw_dedupe_keys_exact','writer_exit_zero_stderr_empty','existing_value_adapter_reached'] as $key)$proof[$key]=true;
    validateCapability($proof,$config);
    foreach(['status'=>'RUNTIME_GAP','context'=>'cli','fingerprint'=>str_repeat('0',64),'database_connections'=>1,'database_writes'=>1,
        'four_full_golden_plans'=>false,'canonical_bytes_exact'=>false,'raw_dedupe_keys_exact'=>false,'writer_exit_zero_stderr_empty'=>false,'existing_value_adapter_reached'=>false] as $key=>$value){
        $bad=$proof;$bad[$key]=$value;rejected(fn()=>validateCapability($bad,$config));
    }
    $changed=$config;$changed['runtime_path']='other-path';rejected(fn()=>validateCapability($proof,$changed));
    $changed=$config;$changed['hashes']['scripts/synthetic.php']=str_repeat('b',64);rejected(fn()=>validateCapability($proof,$changed));
    $result['capability_fingerprint_and_evidence_fail_closed']=true;return $result;
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)echo json_encode(selfTest(),JSON_THROW_ON_ERROR);
