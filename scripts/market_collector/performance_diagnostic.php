<?php
declare(strict_types=1);
namespace Mosa2\MarketPerformance;
use PDO;
use PDOStatement;
use Throwable;
use function Mosa2\Phase2\{check,same,connection};
use function Mosa2\MarketLive\{boundedRows,runtimeContract,runtimeState,completePlan,relevantFacts,exactObservation,bridge,routeBinding,existing};
require_once __DIR__.'/actions_acceptance.php';

/** Diagnostic-only PDO adapter, layered over a server READ ONLY transaction. */
final class Meter {
    public array $calls=[];
    public int $returnedRows=0;
    public function call(string $kind,string $sql,callable $work): mixed {
        $start=hrtime(true);
        try{return $work();}
        finally{$this->calls[]=['operation'=>$kind,'statement'=>$sql,'ms'=>(hrtime(true)-$start)/1e6];}
    }
    public function summary(): array {
        $by=[];$total=0.0;
        foreach($this->calls as $c){$by[$c['operation']]['calls']=($by[$c['operation']]['calls']??0)+1;
            $by[$c['operation']]['ms']=($by[$c['operation']]['ms']??0)+$c['ms'];$total+=$c['ms'];}
        return ['pdo_calls'=>count($this->calls),'pdo_ms'=>$total,'returned_rows'=>$this->returnedRows,'by_operation'=>$by];
    }
}
function readSql(string $sql): void {
    check(preg_match('/\A(?:SELECT|SHOW)\s/i',$sql)===1
        &&!preg_match('/;|\b(?:INTO|OUTFILE|DUMPFILE|FOR\s+UPDATE|GET_LOCK|RELEASE_LOCK|SLEEP|BENCHMARK)\b/i',$sql),'diagnostic_read_only_sql');
}
final class Statement extends PDOStatement {
    public function __construct(private PDOStatement $inner,private Meter $meter,private string $sql){}
    public function execute(?array $params=null): bool {return $this->meter->call('execute',$this->sql,fn()=>$this->inner->execute($params));}
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args): array {
        $rows=$this->meter->call('fetch_all',$this->sql,fn()=>$this->inner->fetchAll($mode,...$args));$this->meter->returnedRows+=count($rows);return $rows;
    }
    public function fetch(int $mode=PDO::FETCH_DEFAULT,int $orientation=PDO::FETCH_ORI_NEXT,int $offset=0): mixed {
        $row=$this->meter->call('fetch',$this->sql,fn()=>$this->inner->fetch($mode,$orientation,$offset));if($row!==false)$this->meter->returnedRows++;return $row;
    }
    public function fetchColumn(int $column=0): mixed {
        $value=$this->meter->call('fetch_column',$this->sql,fn()=>$this->inner->fetchColumn($column));if($value!==false)$this->meter->returnedRows++;return $value;
    }
}
final class ReadOnlyPDO extends PDO {
    public function __construct(private PDO $inner,public Meter $meter){check($inner->inTransaction(),'diagnostic_read_only_transaction');}
    public function prepare(string $query,array $options=[]): PDOStatement|false {
        readSql($query);$q=$this->meter->call('prepare',$query,fn()=>$this->inner->prepare($query,$options));
        check($q instanceof PDOStatement,'diagnostic_prepare');return new Statement($q,$this->meter,$query);
    }
    public function query(string $query,?int $fetchMode=null,mixed ...$args): PDOStatement|false {
        readSql($query);$q=$this->meter->call('query',$query,fn()=>$fetchMode===null?$this->inner->query($query):$this->inner->query($query,$fetchMode,...$args));
        check($q instanceof PDOStatement,'diagnostic_query');return new Statement($q,$this->meter,$query);
    }
    public function exec(string $statement): int|false {throw new \RuntimeException('diagnostic_exec_forbidden');}
    public function beginTransaction(): bool {throw new \RuntimeException('diagnostic_transaction_owned_by_caller');}
    public function commit(): bool {throw new \RuntimeException('diagnostic_commit_forbidden');}
    public function rollBack(): bool {throw new \RuntimeException('diagnostic_transaction_owned_by_caller');}
    public function inTransaction(): bool {return $this->inner->inTransaction();}
}
function measured(callable $work): array {
    $start=hrtime(true);$value=$work();return [$value,(hrtime(true)-$start)/1e6];
}
function configured(string $password,array $config,array &$connections): PDO {
    [$p,$ms]=measured(fn()=>connection($password,$config['db_host'],$config['db_port']));
    $connections[]=$ms;
    // Session/transaction control only; all subsequent business SQL is SELECT/SHOW.
    $p->exec('SET SESSION TRANSACTION READ ONLY');$p->beginTransaction();return $p;
}
function processCpuMs(): ?float {
    if(!function_exists('getrusage'))return null;$r=getrusage();
    return 1000.0*($r['ru_utime.tv_sec']+$r['ru_stime.tv_sec'])+($r['ru_utime.tv_usec']+$r['ru_stime.tv_usec'])/1000;
}
function summarizePhase(string $label,PDO $real,callable $work): array {
    $meter=new Meter();$db=new ReadOnlyPDO($real,$meter);$cpu=processCpuMs();
    [$value,$wall]=measured(fn()=>$work($db));$summary=$meter->summary();
    return [$value,['label'=>$label,'wall_ms'=>$wall]+$summary+
        ['php_process_cpu_ms'=>$cpu===null?null:processCpuMs()-$cpu,'php_wall_residual_ms'=>max(0.0,$wall-$summary['pdo_ms']),
         'residual_definition'=>'wall minus PDO API calls; not a CPU profiler']];
}
function progress(string $phase,?string $isin=null): void {
    echo json_encode(['event'=>'progress','phase'=>$phase,'isin'=>$isin],JSON_THROW_ON_ERROR)."\n";flush();
}
function manifests(PDO $db,array $scope,array $contract): array {
    $base=runtimeContract($db,$contract);$out=[];
    foreach($scope as $s){
        $ids=boundedRows($db,'SELECT * FROM m2_asset_identifiers WHERE identifier_type=? AND normalized_value=? AND scope_key=? LIMIT 2',['isin',$s['isin'],''],1);
        same(count($ids),1,'diagnostic_existing_identifier');$id=$ids[0]['asset_id'];
        $entities=boundedRows($db,'SELECT * FROM m2_entities WHERE id=? LIMIT 2',[$id],1);
        $assets=boundedRows($db,'SELECT * FROM m2_assets WHERE entity_id=? LIMIT 2',[$id],1);
        same(count($entities),1,'diagnostic_existing_entity');same(count($assets),1,'diagnostic_existing_asset');
        $q=['canonical_name'=>$entities[0]['canonical_name'],'display_name'=>$assets[0]['display_name'],'asset_class'=>$assets[0]['asset_class'],
            'identifier_type'=>'isin','identifier_value'=>$s['isin'],'normalized_value'=>$s['isin'],'scope_key'=>'','is_primary'=>1];
        $state=$base+\Mosa2\MarketIdentity\identityState(new \Mosa2\MarketLive\RuntimeStore($db),$q);
        $state['m2_sources']=boundedRows($db,'SELECT * FROM m2_sources WHERE source_key=? LIMIT 2',['provider:boerse_frankfurt_api'],1);
        same(count($state['m2_sources']),1,'diagnostic_existing_source');$source=$state['m2_sources'][0]['id'];
        $state['m2_asset_source_routes']=boundedRows($db,'SELECT * FROM m2_asset_source_routes WHERE asset_id=? AND source_id=? AND route_type=? ORDER BY route_revision LIMIT 33',[$id,$source,'quote'],32);
        $m=\Mosa2\MarketAcceptance\manifest($state,$s);same($m['policy'],'USE_EXISTING_ROUTE','diagnostic_no_onboarding');$out[]=$m;
    }
    return $out;
}
function diagnose(string $password,array $config): array {
    same($config['db_host'],'127.0.0.1','diagnostic_loopback');check(is_int($config['db_port'])&&$config['db_port']>0&&$config['db_port']<=65535,'diagnostic_port');
    $connections=[];$report=['ok'=>false,'provider_requests'=>0,'business_writes'=>0,'simple_select_executions'=>0,'assets'=>[]];
    progress('pdo_constructor');
    // Bare PDO handshake/auth, same fixed DB/options as the original helper.
    [$raw,$bareMs]=measured(fn()=>new PDO('mysql:host=127.0.0.1;port='.$config['db_port'].';dbname=h29077_mosa2_test;charset=utf8mb4',
        'h29077_mosa2_test',$password,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,
            PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>5,PDO::ATTR_STRINGIFY_FETCHES=>false]));
    $raw=null;$report['pdo_constructor_auth_ms']=$bareMs;
    $global=configured($password,$config,$connections);
    try{
        same((int)$global->query('SELECT @@session.transaction_read_only')->fetchColumn(),1,'diagnostic_server_read_only');
        progress('simple_selects');$probes=[];
        // Exactly 10 executions total: 5 direct + 5 fresh native prepare/execute.
        for($i=0;$i<10;$i++){
            $mode=$i<5?'direct_query':'native_prepare_execute';
            [$value,$phase]=summarizePhase($mode,$global,static function($db)use($i){
                if($i<5)$q=$db->query('SELECT 1 AS probe');
                else{$q=$db->prepare('SELECT 1 AS probe');$q->execute();}
                return (int)$q->fetchColumn();
            });same($value,1,'diagnostic_select_result');$probes[]=$phase;$report['simple_select_executions']++;
        }
        $report['simple_selects']=$probes;
        progress('qualified_scope');
        $scope=json_decode(file_get_contents(__DIR__.'/live_test_scope.json'),true,32,JSON_THROW_ON_ERROR);
        [$items,$setup]=summarizePhase('bounded_scope_setup',$global,fn($db)=>manifests($db,$scope,$config['state_contract']));
        $report['scope_setup']=$setup;
    }finally{$global->rollBack();$global=null;}
    foreach($items as $m){
        progress('bounded_preflight',$m['instrument']);$p=configured($password,$config,$connections);
        try{
            $phases=[];$baseline=null;$pure=0.0;
            // Same four runtimeState calls and two connections as the runtime.
            // No runtimeRun, provider fetch, writer apply or batch invocation.
            for($i=0;$i<3;$i++){
                [$state,$phase]=summarizePhase(['preflight','transaction_recheck','before_commit_recheck'][$i],$p,
                    fn($db)=>runtimeState($db,$m,$config['state_contract']));
                if($baseline===null)$baseline=$state;else same($state,$baseline,'diagnostic_state_drift');
                $phases[]=$phase;
                if($i===0){[$plan,$pure]=measured(fn()=>completePlan($state,$m));same($plan['policy'],'USE_EXISTING_ROUTE','diagnostic_existing_policy');}
            }
            [$fact,$factSetup]=summarizePhase('existing_fact_setup',$p,static function($db)use($plan){
                $rows=boundedRows($db,'SELECT *,HEX(dedupe_key) AS dedupe_key FROM m2_market_observations WHERE asset_id=? AND source_id=? AND route_id=? ORDER BY id DESC LIMIT 2',
                    [$plan['asset']['asset_id'],$plan['source']['source_id'],$plan['route']['route_id']],2);
                check($rows!==[],'diagnostic_existing_observation');return $rows[0];
            });
            [$unused,$lookups]=summarizePhase('runtime_fact_lookup_equivalents',$p,static function($db)use($fact){
                $writer=['dedupe_key'=>['$bytes'=>base64_encode(hex2bin($fact['dedupe_key']))],'normalized'=>$fact];
                relevantFacts($db,$writer);exactObservation($db,$fact['id'],$fact);return null;
            });
        }finally{$p->rollBack();$p=null;}
        $read=configured($password,$config,$connections);
        try{
            [$state,$phase]=summarizePhase('independent_readback_state',$read,fn($db)=>runtimeState($db,$m,$config['state_contract']));
            same($state,$baseline,'diagnostic_independent_state');$phases[]=$phase;
            [$unused,$readFact]=summarizePhase('independent_fact_readback',$read,fn($db)=>exactObservation($db,$fact['id'],$fact));
        }finally{$read->rollBack();$read=null;}
        progress('local_processing',$m['instrument']);
        [$startup,$startupMs]=measured(fn()=>bridge($config,['action'=>'runtime']));
        $stored=array_intersect_key($fact,array_flip(array_merge(\Mosa2\Phase3O\CORE,\Mosa2\Phase3O\UNITS)));
        [$replay,$replayMs]=measured(fn()=>bridge($config,['action'=>'replay','route'=>routeBinding($plan['route']['row']+['id'=>$plan['route']['route_id']]),
            'stored'=>$stored,'created_at'=>$fact['created_at'],'existing'=>existing([$fact])]));
        same($replay['plan']['decision'],'DUPLICATE_UNCHANGED','diagnostic_offline_replay');
        $report['assets'][]=['isin'=>$m['instrument'],'preflights'=>$phases,'local_complete_plan_ms'=>$pure,
            'existing_fact_setup'=>$factSetup,'runtime_fact_lookup_equivalents'=>$lookups,'independent_fact_readback'=>$readFact,
            'local_bridge_runtime_ms'=>$startupMs,'local_bridge_offline_replay_ms'=>$replayMs,'offline_replay'=>'DUPLICATE_UNCHANGED'];
        progress('asset_complete',$m['instrument']);
    }
    $report['configured_connection_ms']=$connections;$report['ok']=true;return $report;
}
function main(): void {
    ini_set('display_errors','0');ini_set('log_errors','0');
    try{$in=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);$r=diagnose($in['password'],$in['config']);unset($in);
        echo json_encode(['event'=>'result','report'=>$r],JSON_THROW_ON_ERROR)."\n";}
    catch(Throwable $e){echo json_encode(['event'=>'result','report'=>['ok'=>false,'failure_type'=>$e instanceof \PDOException?'DATABASE_OPERATION_FAILED':get_class($e),
        'provider_requests'=>0,'business_writes'=>0]],JSON_THROW_ON_ERROR)."\n";}
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)main();
