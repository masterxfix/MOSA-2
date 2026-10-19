<?php
declare(strict_types=1);
namespace Mosa2\Phase3C;
use PDO;
use PDOException;
use Throwable;
use RuntimeException;
use InvalidArgumentException;
use function Mosa2\Phase2\{check,same,connection,preflight,structure,save};
require_once __DIR__.'/market_flow.php';
require_once __DIR__.'/../phase3b/postcheck.php';

function expectedLedger(): array {
    return [
        ['version'=>1,'migration_key'=>'0001_core_asset_identity','checksum'=>\Mosa2\Phase2\DIGEST,'applied_at'=>'2026-10-18 14:10:22.604406'],
        ['version'=>2,'migration_key'=>'0002_market_current_history','checksum'=>\Mosa2\Phase3B\DIGEST,'applied_at'=>'2026-10-19 08:02:39.939576']
    ];
}
function liveState(PDO $p,string $root,?array $original=null): array {
    [$core,$market]=\Mosa2\Phase3B\schemas($root);
    $r=preflight($p,false);
    $r['structure']=structure($p,$core+$market,null,[16,9,26,23,19]);
    same($r['structure']['counts']['columns'],140,'column_total');
    $r['tables']=$r['structure']['counts']['tables'];
    $r['ledger']=\Mosa2\Phase3B\ledger($p,2);
    same($r['ledger'],$original??expectedLedger(),'ledger_changed');
    $r['empty']=\Mosa2\Phase3B\emptyFacts($p,array_keys($core+$market));
    return $r;
}
function selectRows(PDO $p,string $sql,array $values=[]): array {
    $q=$p->prepare($sql);$q->execute($values);return $q->fetchAll();
}
function dataSnapshot(PDO $p): array {
    return [
        'history'=>selectRows($p,'SELECT id,asset_id,source_id,route_id,currency,price,bid,ask,volume,market_at,observed_at,HEX(dedupe_key) AS digest,created_at FROM m2_market_observations ORDER BY id'),
        'current'=>selectRows($p,'SELECT * FROM m2_market_current ORDER BY asset_id')
    ];
}
// Test-only adapter. It never opens a connection or commits a transaction.
final class LiveTestWriter {
    public function __construct(private PDO $p) {
        $r=$p->query('SELECT DATABASE() AS db,CURRENT_USER() AS account,VERSION() AS version,@@port AS port')->fetch();
        same($r,['db'=>'h29077_mosa2_test','account'=>'h29077_mosa2_test@localhost','version'=>'8.0.26-16','port'=>3307],'target_identity');
    }
    public function write(array $input,?callable $afterHistory=null): array {
        check($this->p->inTransaction(),'outer_transaction_required');
        $row=normalizeObservation($input);$p=$this->p;
        $p->exec('SAVEPOINT m2_observation_write');
        try {
            requireValue(count(selectRows($p,'SELECT entity_id FROM m2_assets WHERE entity_id=?',[$row['asset_id']]))===1,'unknown_asset');
            requireValue(count(selectRows($p,'SELECT id FROM m2_sources WHERE id=?',[$row['source_id']]))===1,'unknown_source');
            $routes=selectRows($p,'SELECT asset_id,source_id FROM m2_asset_source_routes WHERE id=?',[$row['route_id']]);
            requireValue(count($routes)===1,'unknown_route');
            requireValue(identity($routes[0]['asset_id'])===$row['asset_id'],'route_asset');
            requireValue(identity($routes[0]['source_id'])===$row['source_id'],'route_source');
            $previous=selectRows($p,'SELECT * FROM m2_market_current WHERE asset_id=? FOR UPDATE',[$row['asset_id']]);
            $previous=$previous[0]??null;
            if($previous!==null){$previous['source_id']=identity($previous['source_id']);$previous['route_id']=identity($previous['route_id']);}
            $replace=shouldUpdateCurrent($previous,$row);$key=dedupeKey($row);
            try {
                $q=$p->prepare('INSERT INTO m2_market_observations (asset_id,source_id,route_id,currency,market_at,observed_at,price,bid,ask,volume,dedupe_key,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(6))');
                $q->execute([...array_values($row),$key]);
            }catch(PDOException $e){
                // Only this exact UNIQUE constraint with an identical stored payload is replay.
                if(!isReplayError($e))throw $e;
                $stored=selectRows($p,'SELECT asset_id,source_id,route_id,currency,market_at,observed_at,price,bid,ask,volume FROM m2_market_observations WHERE dedupe_key=?',[$key]);
                same(count($stored),1,'duplicate_without_matching_key');
                same(normalizeObservation($stored[0]),$row,'dedupe_conflict');
                $p->exec('ROLLBACK TO SAVEPOINT m2_observation_write');$p->exec('RELEASE SAVEPOINT m2_observation_write');
                return ['history'=>'duplicate','current'=>'unchanged','duplicate_errno'=>1062,'dedupe_key'=>bin2hex($key)];
            }
            if($afterHistory!==null)$afterHistory();
            if($replace){
                $values=[$row['source_id'],$row['route_id'],$row['currency'],$row['price'],$row['bid'],$row['ask'],$row['market_at'],$row['observed_at'],$row['asset_id']];
                if($previous===null)$sql='INSERT INTO m2_market_current (source_id,route_id,currency,price,bid,ask,market_at,observed_at,asset_id,updated_at) VALUES (?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(6))';
                else $sql='UPDATE m2_market_current SET source_id=?,route_id=?,currency=?,price=?,bid=?,ask=?,market_at=?,observed_at=?,updated_at=UTC_TIMESTAMP(6) WHERE asset_id=?';
                $q=$p->prepare($sql);$q->execute($values);
            }
            $p->exec('RELEASE SAVEPOINT m2_observation_write');
            return ['history'=>'inserted','current'=>$replace?'updated':'unchanged','duplicate_errno'=>null,'dedupe_key'=>bin2hex($key)];
        }catch(Throwable $error){
            $p->exec('ROLLBACK TO SAVEPOINT m2_observation_write');$p->exec('RELEASE SAVEPOINT m2_observation_write');throw $error;
        }
    }
}
function isReplayError(PDOException $e): bool {
    return ($e->errorInfo[0]??null)==='23000'&&(int)($e->errorInfo[1]??0)===1062
        &&(bool)preg_match('/(?:\A|[.\x27`])uq_market_observations_dedupe(?:\z|[\x27`])/',$e->errorInfo[2]??'');
}
function fixtureObservation(array $changes=[]): array {
    return array_replace(['asset_id'=>101,'source_id'=>201,'route_id'=>301,'currency'=>'EUR',
        'market_at'=>'2026-01-01 12:00:00','observed_at'=>'2026-01-01 12:00:01',
        'price'=>'10','bid'=>'9','ask'=>'11','volume'=>'1'], $changes);
}
function fixtureCore(PDO $p): void {
    $now="'2026-01-01 00:00:00.000000'";
    foreach([201,202] as $s)$p->exec("INSERT INTO m2_sources VALUES ($s,'synthetic_3c_$s','derived','Synthetic 3C $s',NULL,1,$now,$now)");
    foreach([101,102,103] as $a){
        $p->exec("INSERT INTO m2_entities VALUES ($a,'asset','Synthetic 3C $a','active',$now,$now)");
        $p->exec("INSERT INTO m2_assets VALUES ($a,'equity','Synthetic 3C $a','EUR','active',$now,$now)");
    }
    foreach([[301,101,201],[302,102,201],[303,103,202],[304,101,202]] as [$r,$a,$s])
        $p->exec("INSERT INTO m2_asset_source_routes VALUES ($r,$a,$s,'quote','SYN3C$r',1,1,$now,$now)");
}
function latencyStats(array $milliseconds): array {
    check(count($milliseconds)>=10,'measurement_count');sort($milliseconds);$n=count($milliseconds);
    return ['measurements'=>$n,'median_ms'=>($milliseconds[intdiv($n-1,2)]+$milliseconds[intdiv($n,2)])/2,
        'p95_ms'=>$milliseconds[(int)ceil(.95*$n)-1],'max_ms'=>$milliseconds[$n-1]];
}
const HISTORY_SQL='SELECT id,market_at FROM m2_market_observations WHERE asset_id=? AND market_at>=? AND market_at<? ORDER BY market_at,id LIMIT 5';
const PERFORMANCE_ROUTES=[101=>[201=>301,202=>304],102=>[201=>302,202=>305],103=>[201=>306,202=>303]];
// Identical time distribution for every asset/source; disjoint day batches for expansion.
function performanceObservations(int $firstDay,int $days): \Generator {
    check($firstDay>=0&&$days>0&&$firstDay+$days<=32,'performance_days');
    $epoch=new \DateTimeImmutable('2026-01-01 00:00:00',new \DateTimeZone('UTC'));
    foreach(PERFORMANCE_ROUTES as $asset=>$routes)foreach($routes as $source=>$route)
        for($day=$firstDay;$day<$firstDay+$days;$day++)for($slot=0;$slot<16;$slot++){
            $at=$epoch->modify('+'.($day*1440+$slot*90+10).' minutes')->format('Y-m-d H:i:s');
            yield normalizeObservation(['asset_id'=>$asset,'source_id'=>$source,'route_id'=>$route,
                'currency'=>'EUR','market_at'=>$at,'observed_at'=>$at,'price'=>'10','bid'=>'9','ask'=>'11','volume'=>'1']);
        }
}
function appendPerformanceObservations(PDO $p,int $firstDay,int $days): void {
    check($p->inTransaction(),'outer_transaction_required');
    $q=$p->prepare('INSERT INTO m2_market_observations (asset_id,source_id,route_id,currency,market_at,observed_at,price,bid,ask,volume,dedupe_key,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,UTC_TIMESTAMP(6))');
    foreach(performanceObservations($firstDay,$days) as $row)$q->execute([...array_values($row),dedupeKey($row)]);
}
function performanceFixtureEvidence(PDO $p,int $days): array {
    $assets=selectRows($p,"SELECT asset_id,COUNT(*) AS observations,COUNT(DISTINCT source_id) AS sources,COUNT(DISTINCT route_id) AS routes,SUM(market_at>='2026-01-02' AND market_at<'2026-01-03') AS window_rows FROM m2_market_observations GROUP BY asset_id ORDER BY asset_id");
    return ['performance_days'=>$days,'performance_observations'=>count(PERFORMANCE_ROUTES)*2*16*$days,
        'total_observations'=>array_sum(array_column($assets,'observations')),'per_asset'=>$assets];
}
// The budget is global across all read paths, not a loop until a plan happens to pass.
function guardedReadPlan(string $name,string $sql,array $parameters,string $key,bool &$expanded,array &$report,
    callable $explain,callable $expand,callable $fixture,callable $persist): array {
    $capture=function(int $attempt)use($name,$sql,$parameters,$key,&$report,$explain,$fixture,$persist):array{
        $rows=$explain($sql,$parameters);$plan=$rows[0]??[];
        $evidence=['query_id'=>$name,'sql'=>$sql,'parameters'=>$parameters,'expected_key'=>$key,
            'key'=>$plan['key']??null,'type'=>$plan['type']??null,'rows'=>$plan['rows']??null,'extra'=>$plan['Extra']??null,
            'attempt'=>$attempt,'fixture'=>$fixture(),'explain'=>$rows];
        $report['plans'][$name][]=$evidence;$report['reads'][$name]=$evidence;$persist();
        same(count($rows),1,'plan_rows');return $evidence;
    };
    $plan=$capture(1);
    if(($plan['key']!==$key||$plan['type']==='ALL')&&!$expanded){
        $expanded=true;$report['observation_fixture_expansions']=1;$persist();$expand();$plan=$capture(2);
    }
    same($plan['key'],$key,'plan_key:'.$name);
    check(in_array($plan['type'],['const','eq_ref','ref','range'],true),'unbounded_plan:'.$name);
    check(!str_contains(strtolower($plan['extra']??''),'filesort'),'filesort:'.$name);
    return $plan;
}
function schemaContractEvidence(array $structure): array {
    foreach($structure['metadata'] as &$table){
        // Only the table option changes outside transaction rollback; keep all column/constraint evidence.
        $table['show_create']=preg_replace('/(\) ENGINE=[^\r\n]*?) AUTO_INCREMENT=[0-9]+\b/','$1',$table['show_create']);
    }unset($table);return $structure;
}
function confirmFinalState(array $before,array $after): array {
    same($after['ledger'],$before['ledger'],'ledger_changed');
    same($after['grants'],$before['grants'],'grants_changed');
    same(schemaContractEvidence($after['structure']),schemaContractEvidence($before['structure']),'structure_changed');
    same(count($after['empty']),15,'empty_table_count');
    same(array_sum($after['empty']),0,'facts_remaining');
    return ['facts_empty'=>true,'schema_contract_same'=>true,'ledger_same'=>true,'grants_same'=>true,
        'auto_increment_equal'=>$after['structure']===$before['structure'],'auto_increment_reset_required'=>false];
}
function liveChecks(PDO $p,array &$report,callable $persist): void {
    $results=[];$record=function(string $group,string $name)use(&$results,&$report,$persist):void{
        $results[$group][$name]=true;$report['checks']=$results;$persist();
    };
    fixtureCore($p);$writer=new LiveTestWriter($p);$base=fixtureObservation();
    $first=$writer->write($base);$snapshot=dataSnapshot($p);
    same(count($snapshot['history']),1,'first_history');same($snapshot['history'][0]['digest'],strtoupper(bin2hex(dedupeKey($base))),'raw_dedupe_bytes');$record('history_dedupe','insert_and_raw_digest');
    same($first['current'],'updated','first_current');$normalized=normalizeObservation($base);$expected=$normalized;unset($expected['volume']);
    $actual=array_intersect_key($snapshot['current'][0],$expected);foreach(['asset_id','source_id','route_id'] as $k)$actual[$k]=identity($actual[$k]);same($actual,$expected,'first_projection');$record('current_time','first');
    $replay=$writer->write($base);same($replay['duplicate_errno'],1062,'real_duplicate_errno');same($replay['history'],'duplicate','real_replay');same(dataSnapshot($p),$snapshot,'replay_mutated');$report['duplicate_errno']=1062;$record('history_dedupe','unique_replay');
    $newer=fixtureObservation(['market_at'=>'2026-01-02 12:00:00','observed_at'=>'2026-01-02 12:00:01','price'=>'12','ask'=>'13']);
    $older=fixtureObservation(['observed_at'=>'2026-01-03 12:00:00','price'=>'8']);
    $corrected=array_replace($newer,['observed_at'=>'2026-01-03 12:00:00','price'=>'13','ask'=>'14']);
    $tied=array_replace($corrected,['price'=>'14','ask'=>'15']);
    foreach([['newer',$newer,true],['older_market_later_observed',$older,false],['equal_market_newer_observed',$corrected,true],['identical_times_other_payload',$tied,false]] as [$name,$row,$replace]){
        $before=dataSnapshot($p);$out=$writer->write($row);$after=dataSnapshot($p);
        same(count($after['history']),count($before['history'])+1,'history_append:'.$name);
        foreach($before['history'] as $i=>$old)same($after['history'][$i],$old,'history_changed');
        same($out['current'],$replace?'updated':'unchanged','current_status:'.$name);
        if($replace){same($after['current'][0]['price'],decimal($row['price'],28,10),'current_price');same($after['current'][0]['market_at'],utcTimestamp($row['market_at']),'current_market');same($after['current'][0]['observed_at'],utcTimestamp($row['observed_at']),'current_observed');}
        else same($after['current'],$before['current'],'current_regressed:'.$name);
        $record('current_time',$name);
    }
    $writer->write(fixtureObservation(['asset_id'=>102,'route_id'=>302]));$writer->write(fixtureObservation(['asset_id'=>103,'source_id'=>202,'route_id'=>303]));
    $before=dataSnapshot($p);$writer->write(fixtureObservation(['market_at'=>'2026-01-04 12:00:00','price'=>'15','ask'=>'16']));$after=dataSnapshot($p);
    same(array_slice($after['current'],1),array_slice($before['current'],1),'other_assets_changed');same(count($after['current']),3,'asset_count');same(count($after['history']),8,'asset_history');$record('multi_asset','three_independent_assets');
    foreach([
        ['unknown_asset',['asset_id'=>99999]],['unknown_source',['source_id'=>99999]],['unknown_route',['route_id'=>99999]],
        ['route_asset',['asset_id'=>102]],['route_source',['source_id'=>202]],['selected_route_changed',['route_id'=>304,'source_id'=>202]]
    ] as [$reason,$changes]){
        $before=dataSnapshot($p);$rejected=false;
        try{$writer->write(fixtureObservation($changes));}catch(InvalidArgumentException $e){same($e->getMessage(),$reason,'wrong_provenance_error');$rejected=true;}
        check($rejected,'provenance_accepted');same(dataSnapshot($p),$before,'provenance_mutated');$record('provenance',$reason);
    }
    $before=dataSnapshot($p);$injected=false;
    try{$writer->write(fixtureObservation(['market_at'=>'2026-01-05 12:00:00']),function()use($p,$before):void{
        same(count(dataSnapshot($p)['history']),count($before['history'])+1,'fault_not_after_insert');throw new RuntimeException('injected_after_history');
    });}catch(RuntimeException $e){same($e->getMessage(),'injected_after_history','wrong_fault');$injected=true;}
    check($injected,'fault_not_triggered');same(dataSnapshot($p),$before,'savepoint_not_atomic');$record('atomicity','savepoint_rollback');
    $bars=$p->prepare("INSERT INTO m2_market_bars (asset_id,source_id,route_id,interval_key,currency,starts_at,ends_at,open_price,high_price,low_price,close_price,observed_at,created_at) VALUES (?,?,?,?,'EUR',?,?,10,12,8,11,?,?)");
    foreach([[101,201,301],[102,201,302],[103,202,303]] as [$a,$s,$r])foreach(\Mosa2\Phase3B\barFixture(0,8) as $bar){$t=$bar['starts_at'];$bars->execute([$a,$s,$r,$bar['interval_key'],$t,$bar['ends_at'],$t,$t]);}
    $report['fixtures']=['assets'=>3,'sources'=>2,'functional_routes'=>4,'functional_observations'=>8,'current'=>3,'bars'=>96];
    // Performance-only History rows follow all functional assertions; never arbitrate Current across sources.
    $p->exec("INSERT INTO m2_asset_source_routes VALUES (305,102,202,'quote','SYN3C305',1,1,'2026-01-01','2026-01-01'),(306,103,201,'quote','SYN3C306',1,1,'2026-01-01','2026-01-01')");
    appendPerformanceObservations($p,0,8);$days=8;$expanded=false;$report['observation_fixture_expansions']=0;
    $fixture=function()use($p,&$days):array{return performanceFixtureEvidence($p,$days);};
    $expand=function()use($p,&$days):void{appendPerformanceObservations($p,8,24);$days=32;};
    $explain=function(string $sql,array $parameters)use($p):array{return selectRows($p,'EXPLAIN '.$sql,$parameters);};
    $queries=[
        'current'=>['SELECT * FROM m2_market_current WHERE asset_id=101',[],'PRIMARY',20,1],
        'history'=>[HISTORY_SQL,[101,'2026-01-02','2026-01-03'],'ix_market_observations_asset_time',100,5],
        'bars'=>["SELECT id,starts_at FROM m2_market_bars WHERE asset_id=101 AND interval_key='1m' AND starts_at>='2026-01-01' AND starts_at<'2026-01-02' ORDER BY starts_at,id LIMIT 5",[],'ix_market_bars_asset_time',100,2]
    ];
    foreach($queries as $name=>[$sql,$parameters,$key,$budget,$count]){
        guardedReadPlan($name,$sql,$parameters,$key,$expanded,$report,$explain,$expand,$fixture,$persist);
        $q=$p->prepare($sql);$q->execute($parameters);same(count($q->fetchAll()),$count,'warmup_rows');$times=[];
        for($i=0;$i<20;$i++){$start=hrtime(true);$q->execute($parameters);$rows=$q->fetchAll();$times[]=(hrtime(true)-$start)/1e6;same(count($rows),$count,'measurement_rows');}
        $stats=latencyStats($times);$report['reads'][$name]+=$stats+['result_rows'=>$count,'budget_ms'=>$budget];$persist();
        check($stats['max_ms']<$budget,'latency_budget:'.$name);$record('read_paths',$name);
    }
    $report['counts']=array_map('count',$results);$report['functional_total']=array_sum($report['counts']);same($report['functional_total'],18,'functional_total');$persist();
}
function runLiveTest(string $root): array {
    check(PHP_SAPI==='cli'&&!is_link($root)&&(fileperms($root)&0077)===0,'private_cli');
    check(!is_link($root.'/secret.php')&&is_file($root.'/secret.php')&&(fileperms($root.'/secret.php')&0077)===0,'private_secret');
    check(!file_exists($root.'/started.lock')&&!is_link($root.'/started.lock'),'already_started');
    $password=null;$p=null;$lock=null;$before=null;
    $r=['ok'=>false,'started_at_utc'=>gmdate('c'),'preflight_groups'=>5];$persist=function()use(&$r,$root):void{save($root.'/report.json',$r);};
    try {
        $lock=fopen($root.'/started.lock','x');check($lock!==false&&flock($lock,LOCK_EX|LOCK_NB),'already_started');
        $password=require $root.'/secret.php';$p=connection($password);$before=liveState($p,$root);$r['preflight']=$before;
        $r['preflight_checks']=array_fill_keys(['migration_bytes','identity_session_rights_objects','complete_structure','unchanged_ledger','empty_facts'],true);$persist();
        $p->beginTransaction();
        try{liveChecks($p,$r,$persist);}finally{if($p->inTransaction())$p->rollBack();}
        $r['same_connection_final']=liveState($p,$root,$before['ledger']);
        $r['same_connection_checks']=confirmFinalState($before,$r['same_connection_final']);$p=null;
        $p=connection($password);$r['independent_final']=liveState($p,$root,$before['ledger']);
        $r['independent_checks']=confirmFinalState($before,$r['independent_final']);$r['live_total']=count($r['preflight_checks'])+$r['functional_total'];$r['ok']=true;
    }catch(Throwable $e){
        if($p!==null&&$p->inTransaction()){try{$p->rollBack();}catch(Throwable){$r['rollback_unconfirmed']=true;}}
        $r['failure']=$e instanceof PDOException?['category'=>'database','errno'=>(int)($e->errorInfo[1]??0)]:['category'=>'guard','message'=>$e->getMessage()];
        if($password!==null&&$before!==null){try{$p=null;$p=connection($password);$r['failure_readback']=liveState($p,$root,$before['ledger']);}catch(Throwable){$r['failure_readback_unconfirmed']=true;}}
    }finally{
        $p=null;unset($password);if(is_resource($lock)){flock($lock,LOCK_UN);fclose($lock);}
        if(is_file($root.'/secret.php'))check(unlink($root.'/secret.php'),'secret_cleanup_failed');
        $r['finished_at_utc']=gmdate('c');$persist();
    }
    return $r;
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{same($argv[1]??'','--run-live-test','explicit_action');$r=runLiveTest(__DIR__);echo json_encode(['ok'=>$r['ok'],'report'=>'private report.json']),PHP_EOL;exit($r['ok']?0:1);}
    catch(Throwable){if(is_file(__DIR__.'/secret.php'))unlink(__DIR__.'/secret.php');echo '{"ok":false,"error":"guard_failure"}',PHP_EOL;exit(1);}
}
