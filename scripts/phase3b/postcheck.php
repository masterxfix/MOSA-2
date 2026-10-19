<?php
declare(strict_types=1);
namespace Mosa2\Phase3B;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,qi,connection,preflight,structure,tables,reject,save,contract};
require_once __DIR__.'/../phase2/postcheck.php';
const DIGEST='205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee';
const MARKET=['m2_market_current','m2_market_observations','m2_market_bars'];
function schemas(string $root): array {
    $core=file_get_contents($root.'/0001.sql');$market=file_get_contents($root.'/0002.sql');
    return [contract($core),contract($market,DIGEST,MARKET)];
}
function ledger(PDO $p,int $versions,?array $original=null): array {
    $rows=$p->query('SELECT version,migration_key,LOWER(HEX(checksum)) AS checksum,applied_at FROM m2_schema_migrations ORDER BY version')->fetchAll();
    same(count($rows),$versions,'ledger_count');
    foreach($rows as $i=>$row){
        same((int)$row['version'],$i+1,'ledger_version');
        same($row['migration_key'],$i===0?'0001_core_asset_identity':'0002_market_current_history','ledger_key');
        same($row['checksum'],$i===0?\Mosa2\Phase2\DIGEST:DIGEST,'ledger_digest');
        check((bool)preg_match('/\A\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}\z/',$row['applied_at']),'ledger_time');
    }
    if($original!==null)same($rows[0],$original,'version_one_changed');
    return $rows;
}
function emptyFacts(PDO $p,array $names): array {
    $counts=[];foreach($names as $name){if($name==='m2_schema_migrations')continue;
        $counts[$name]=(int)$p->query('SELECT COUNT(*) FROM '.qi($name))->fetchColumn();same($counts[$name],0,'nonempty:'.$name);}
    return $counts;
}
function coreState(PDO $p): array {
    $actual=tables($p);$expected=\Mosa2\Phase2\TABLES;sort($expected);
    same($actual,$expected,'table_set');
    return ['tables'=>count($actual),'table_names'=>$actual,'ledger'=>ledger($p,1),'empty'=>emptyFacts($p,$actual)];
}
function before(PDO $p,array $core): array {
    $r=preflight($p,false);unset($r['tables']);
    $r=array_merge($r,coreState($p));$r['structure']=structure($p,$core);return $r;
}
// Capture the failing plan before any guard can throw. Never retain arbitrary
// driver fields, credentials or exception dumps in this diagnostic record.
function rememberPlan(array &$evidence,string $name,array $row,string $expected,int $historyRows,string $sql,?callable $persist=null): void {
    $evidence['history_rows_per_table']=$historyRows;
    $evidence['explain_attempts'][$name][]=[
        'sql'=>$sql,'expected_key'=>$expected,'key'=>$row['key']??null,
        'type'=>$row['type']??null,'rows'=>$row['rows']??null,
        'extra'=>$row['Extra']??null,'history_rows_per_table'=>$historyRows,
        'fixture_rows'=>$evidence['fixture_rows']??[]
    ];
    if($persist!==null)$persist();
}
// Identical interval/time distribution for every asset; no privileged query asset.
function barFixture(int $from,int $to): \Generator {
    foreach(['1m'=>60,'5m'=>300,'1h'=>3600,'1d'=>86400] as $interval=>$seconds){
        $perDay=min(2,intdiv(86400,$seconds));
        for($j=$from;$j<$to;$j++){
            $start=1767225600+(intdiv($j,$perDay)-2)*86400+($j%$perDay)*$seconds;
            yield ['interval_key'=>$interval,'starts_at'=>gmdate('Y-m-d H:i:s',$start).'.000000','ends_at'=>gmdate('Y-m-d H:i:s',$start+$seconds).'.000000'];
        }
    }
}
function checkedExplain(PDO $p,string $name,string $sql,string $key,string $table,array &$evidence,bool &$expanded,callable $expand,?callable $persist=null): array {
    $rows=$p->query('EXPLAIN '.$sql)->fetchAll();same(count($rows),1,'plan_rows');$r=$rows[0];
    rememberPlan($evidence,$name,$r,$key,$evidence['fixture_rows'][$table],$sql,$persist);
    if(!$expanded&&($r['key']!==$key||$r['type']==='ALL')){
        $expanded=true;$expand();
        $rows=$p->query('EXPLAIN '.$sql)->fetchAll();same(count($rows),1,'plan_rows');$r=$rows[0];
        rememberPlan($evidence,$name,$r,$key,$evidence['fixture_rows'][$table],$sql,$persist);
    }
    same($r['key'],$key,'plan_key:'.$name);check(in_array($r['type'],['const','eq_ref','ref','range'],true),'unbounded_plan:'.$name);
    return ['sql'=>$sql,'key'=>$r['key'],'type'=>$r['type'],'rows'=>$r['rows'],'extra'=>$r['Extra']];
}
function practical(PDO $p,array &$evidence=[],?callable $persist=null): array {
    $evidence=['constraints'=>[],'explain'=>[],'explain_attempts'=>[],'history_rows_per_table'=>0];
    $results=[];$plans=[];$p->beginTransaction();
    try {
        $now="'2026-01-01 00:00:00.000000'";
        for($s=1;$s<=32;$s++)$p->exec("INSERT INTO m2_sources VALUES ($s,'synthetic$s','derived','Synthetic $s',NULL,1,$now,$now)");
        for($a=1;$a<=512;$a++){
            $s=($a%32)+1;
            $p->exec("INSERT INTO m2_entities VALUES ($a,'asset','Synthetic $a','active',$now,$now)");
            $p->exec("INSERT INTO m2_assets VALUES ($a,'equity','Synthetic $a','EUR','active',$now,$now)");
            $p->exec("INSERT INTO m2_asset_source_routes VALUES ($a,$a,$s,'quote','SYN$a',1,1,$now,$now)");
            $p->exec("INSERT INTO m2_market_current (asset_id,source_id,route_id,currency,price,bid,ask,day_low,day_high,market_at,observed_at,updated_at) VALUES ($a,$s,$a,'EUR',10,9,11,8,12,$now,$now,$now)");
        }
        $obs=$p->prepare("INSERT INTO m2_market_observations (asset_id,source_id,route_id,currency,price,bid,ask,market_at,observed_at,dedupe_key,created_at) VALUES (?,?,?,'EUR',10,9,11,?,?,UNHEX(?),?)");
        $bars=$p->prepare("INSERT INTO m2_market_bars (asset_id,source_id,route_id,interval_key,currency,starts_at,ends_at,open_price,high_price,low_price,close_price,observed_at,created_at) VALUES (?,?,?,?,'EUR',?,?,10,12,8,11,?,?)");
        $fillObservations=function(int $from,int $to)use($obs):void {
            for($a=1;$a<=512;$a++)for($j=$from;$j<$to;$j++){
                $s=($a%32)+1;$t=gmdate('Y-m-d H:i:s',1767225600+$j*60).'.000000';
                $obs->execute([$a,$s,$a,$t,$t,hash('sha256',"synthetic:$a:$j"),$t]);
            }
        };
        $fillBars=function(int $from,int $to)use($bars):void {
            $rows=iterator_to_array(barFixture($from,$to),false);
            for($a=1;$a<=512;$a++)foreach($rows as $row){
                $t=$row['starts_at'];$bars->execute([$a,($a%32)+1,$a,$row['interval_key'],$t,$row['ends_at'],$t,$t]);
            }
        };
        $fillObservations(0,8);$fillBars(0,8);
        $evidence['fixture_rows']=['m2_market_current'=>512,'m2_market_observations'=>4096,'m2_market_bars'=>16384];
        $evidence['history_rows_per_table']=4096;
        foreach(MARKET as $table){check((int)$p->query('SELECT COUNT(*) FROM '.qi($table))->fetchColumn()>0,'valid_insert');$results[$table.'_valid']=true;}
        foreach(['price=0','price=-1','bid=12,ask=11','day_low=13,day_high=12'] as $i=>$set)reject($p,'UPDATE m2_market_current SET '.$set.' WHERE asset_id=1',3819,'current_check_'.$i,$results);
        foreach(['asset_id','source_id','route_id'] as $col)reject($p,"UPDATE m2_market_current SET $col=999999 WHERE asset_id=1",1452,'current_fk_'.$col,$results);
        reject($p,'INSERT INTO m2_market_current SELECT * FROM m2_market_current WHERE asset_id=1',1062,'current_pk',$results);
        foreach(['price=0','price=-1','bid=12,ask=11'] as $i=>$set)reject($p,'UPDATE m2_market_observations SET '.$set.' WHERE asset_id=1 LIMIT 1',3819,'observation_check_'.$i,$results);
        foreach(['asset_id','source_id','route_id'] as $col)reject($p,"UPDATE m2_market_observations SET $col=999999 WHERE asset_id=1 LIMIT 1",1452,'observation_fk_'.$col,$results);
        reject($p,"INSERT INTO m2_market_observations (asset_id,source_id,route_id,currency,price,market_at,observed_at,dedupe_key,created_at) SELECT asset_id,source_id,route_id,currency,price,market_at,observed_at,dedupe_key,created_at FROM m2_market_observations WHERE asset_id=1 LIMIT 1",1062,'observation_dedupe',$results);
        foreach(["interval_key='1w'",'ends_at=starts_at',"ends_at='2025-01-01 00:00:00'",'open_price=0','open_price=-1','low_price=11','high_price=9'] as $i=>$set)reject($p,'UPDATE m2_market_bars SET '.$set.' WHERE asset_id=1 LIMIT 1',3819,'bar_check_'.$i,$results);
        foreach(['asset_id','source_id','route_id'] as $col)reject($p,"UPDATE m2_market_bars SET $col=999999 WHERE asset_id=1 LIMIT 1",1452,'bar_fk_'.$col,$results);
        reject($p,"INSERT INTO m2_market_bars (asset_id,source_id,route_id,interval_key,currency,starts_at,ends_at,open_price,high_price,low_price,close_price,observed_at,created_at) SELECT asset_id,source_id,route_id,interval_key,currency,starts_at,ends_at,open_price,high_price,low_price,close_price,observed_at,created_at FROM m2_market_bars WHERE asset_id=1 LIMIT 1",1062,'bar_identity',$results);
        reject($p,'DELETE FROM m2_asset_source_routes WHERE id=1',1451,'market_delete_restrict',$results);
        $queries=[
            'current_asset'=>['SELECT * FROM m2_market_current WHERE asset_id=1','PRIMARY'],
            'current_source'=>["SELECT asset_id,observed_at FROM m2_market_current WHERE source_id=2 AND observed_at>='2026-01-01' ORDER BY observed_at,asset_id LIMIT 10",'ix_market_current_source'],
            'observations_asset'=>['SELECT id,market_at FROM m2_market_observations WHERE asset_id=1 ORDER BY market_at DESC,id DESC LIMIT 5','ix_market_observations_asset_time'],
            'observations_asset_source'=>["SELECT id,market_at FROM m2_market_observations WHERE asset_id=1 AND source_id=2 AND market_at>='2026-01-01' AND market_at<'2026-01-02' ORDER BY market_at,id LIMIT 5",'ix_market_observations_asset_source'],
            'observations_source'=>["SELECT id,observed_at FROM m2_market_observations WHERE source_id=2 AND observed_at>='2026-01-01' ORDER BY observed_at,id LIMIT 5",'ix_market_observations_source'],
            'bars_asset'=>["SELECT id,starts_at FROM m2_market_bars WHERE asset_id=1 AND interval_key='1m' AND starts_at>='2026-01-01' AND starts_at<'2026-01-02' ORDER BY starts_at,id LIMIT 5",'ix_market_bars_asset_time'],
            'bars_asset_source'=>["SELECT id,starts_at FROM m2_market_bars WHERE asset_id=1 AND source_id=2 AND interval_key='1m' AND starts_at>='2026-01-01' AND starts_at<'2026-01-02' ORDER BY starts_at,id LIMIT 5",'ix_market_bars_asset_source'],
            'bars_source'=>["SELECT id,observed_at FROM m2_market_bars WHERE source_id=2 AND observed_at>='2026-01-01' ORDER BY observed_at,id LIMIT 5",'ix_market_bars_source']
        ];
        $expanded=false;
        $expand=function()use($fillObservations,$fillBars,&$evidence):void {
            $fillObservations(8,32);$fillBars(8,16);
            $evidence['fixture_rows']=['m2_market_current'=>512,'m2_market_observations'=>16384,'m2_market_bars'=>32768];
        };
        $evidence['constraints']=$results;
        foreach($queries as $name=>[$sql,$key]){
            $table=str_starts_with($name,'current_')?MARKET[0]:(str_starts_with($name,'observations_')?MARKET[1]:MARKET[2]);
            $plans[$name]=checkedExplain($p,$name,$sql,$key,$table,$evidence,$expanded,$expand,$persist);
            $evidence['explain']=$plans;
        }
        return $evidence;
    }finally{if($p->inTransaction())$p->rollBack();}
}
function run(string $root): array {
    check(PHP_SAPI==='cli'&&!is_link($root)&&(fileperms($root)&0077)===0,'private_cli');
    check(!is_link($root.'/secret.php')&&is_file($root.'/secret.php')&&(fileperms($root.'/secret.php')&0077)===0,'private_secret');
    [$core,$market]=schemas($root);$all=$core+$market;
    $password=require $root.'/secret.php';$p=connection($password);
    $before=before($p,$core);$original=$before['ledger'][0];
    // Exclusive durable start marker: no retry/resume after any begun DDL.
    $lock=fopen($root.'/started.lock','x');check($lock!==false&&flock($lock,LOCK_EX|LOCK_NB),'already_started');
    $created=[];$committed=false;$commitAttempted=false;
    $r=['ok'=>false,'started_at_utc'=>gmdate('c'),'migration_sha256'=>DIGEST,'preflight'=>$before];
    try {
        foreach($market as $name=>$table){$p->exec($table['ddl']);$created[]=$name;$r['created']=$created;save($root.'/report.json',$r);}
        $r['structure']=structure($p,$all,null,[16,9,26,23,19]);same($r['structure']['counts']['columns'],140,'column_total');
        $r['practical']=[];
        practical($p,$r['practical'],function()use(&$r,$root):void{save($root.'/report.json',$r);});
        $r['rollback_empty']=emptyFacts($p,array_keys($all));ledger($p,1,$original);
        $p->beginTransaction();$q=$p->prepare('INSERT INTO m2_schema_migrations VALUES (2,?,UNHEX(?),UTC_TIMESTAMP(6))');$q->execute(['0002_market_current_history',DIGEST]);
        $r['ledger']=ledger($p,2,$original);$commitAttempted=true;$p->commit();$committed=true;
        $p=null;$p=connection($password);$r['final_preflight']=preflight($p,false);
        $r['final_preflight']['tables']=count(tables($p));
        $r['final_structure']=structure($p,$all,null,[16,9,26,23,19]);
        same(ledger($p,2,$original),$r['ledger'],'independent_ledger');
        $r['final_empty']=emptyFacts($p,array_keys($all));$r['ok']=true;$r['finished_at_utc']=gmdate('c');
    }catch(Throwable $e){
        if($p!==null&&$p->inTransaction())$p->rollBack();
        $r['failure']=$e instanceof \PDOException?['category'=>'database','errno'=>(int)($e->errorInfo[1]??0)]:['category'=>'guard','message'=>$e->getMessage()];
        if(!$committed&&!$commitAttempted){
            // Prove exact ownership and unchanged empty core before any DROP.
            $present=tables($p);$expected=array_merge(array_keys($core),$created);sort($expected);
            same($present,$expected,'cleanup_unknown_tables');ledger($p,1,$original);emptyFacts($p,$present);
            foreach(array_reverse($created) as $name){check(in_array($name,MARKET,true),'cleanup_scope');$p->exec('DROP TABLE '.qi($name));}
            $r['restored_phase2']=before($p,$core);
        }else $r['cleanup_blocked']='ledger_commit_completed_or_outcome_uncertain_no_automatic_drop';
    }finally{
        unset($password);$p=null;flock($lock,LOCK_UN);fclose($lock);
        if(is_file($root.'/secret.php'))check(unlink($root.'/secret.php'),'secret_cleanup_failed');
        save($root.'/report.json',$r);
    }
    return $r;
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{same($argv[1]??'','--apply-postcheck','explicit_action');$r=run(__DIR__);echo json_encode(['ok'=>$r['ok'],'report'=>'private report.json'],JSON_THROW_ON_ERROR),PHP_EOL;exit($r['ok']?0:1);}
    catch(Throwable $e){
        $removed=!is_file(__DIR__.'/secret.php')||unlink(__DIR__.'/secret.php');
        echo json_encode(['ok'=>false,'secret_removed'=>$removed,'error'=>$e instanceof \PDOException?'database_failure':$e->getMessage()]),PHP_EOL;exit(1);
    }
}
