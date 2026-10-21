<?php
declare(strict_types=1);
/** Fixed, fileless locality probe. Loaded identically by both PHP interpreters. */
function localityCheck(bool $ok,string $reason): void {if(!$ok)throw new RuntimeException($reason);}
function localityStats(array $values): array {
    return ['mean_ms'=>array_sum($values)/count($values),'min_ms'=>min($values),'max_ms'=>max($values),'samples_ms'=>$values];
}
function localityProbe(array $input,?callable $factory=null): array {
    $all=hrtime(true);$p=null;$stage='configuration';
    $r=['ok'=>false,'provider_requests'=>0,'business_writes'=>0,'select1_executions'=>0,
        'php_version'=>PHP_VERSION,'php_version_id'=>PHP_VERSION_ID,'sapi'=>PHP_SAPI,'pdo_mysql'=>extension_loaded('pdo_mysql')];
    try{
        localityCheck(PHP_VERSION_ID>=80400&&PHP_VERSION_ID<80500&&PHP_SAPI==='cli','php84_cli_required');
        localityCheck($factory!==null||extension_loaded('pdo_mysql'),'pdo_mysql_required');
        localityCheck(is_string($input['password']??null)&&$input['password']!=='','secret_required');
        localityCheck(is_int($input['port']??null)&&$input['port']>=1&&$input['port']<=65535,'endpoint_required');
        $options=[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,
            PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>5,PDO::ATTR_STRINGIFY_FETCHES=>false];
        $stage='pdo_connect';$start=hrtime(true);
        $dsn='mysql:host=127.0.0.1;port='.$input['port'].';dbname=h29077_mosa2_test;charset=utf8mb4';
        $p=$factory!==null?$factory($dsn,'h29077_mosa2_test',$input['password'],$options):new PDO($dsn,'h29077_mosa2_test',$input['password'],$options);
        $r['pdo_connect_ms']=(hrtime(true)-$start)/1e6;
        unset($input['password']);$stage='readonly_setup';$start=hrtime(true);
        $p->exec('SET SESSION TRANSACTION READ ONLY');
        $p->exec("SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci");
        $p->exec("SET SESSION time_zone='+00:00'");
        $p->exec("SET SESSION sql_mode='STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY'");
        $p->exec('SET SESSION lock_wait_timeout=3');$p->exec('SET SESSION innodb_lock_wait_timeout=3');
        localityCheck($p->beginTransaction(),'readonly_begin');
        localityCheck((int)$p->query('SELECT @@session.transaction_read_only')->fetchColumn()===1,'readonly_not_enforced');
        $identity=$p->query('SELECT DATABASE() AS db,CURRENT_USER() AS account,VERSION() AS version,@@port AS port')->fetch(PDO::FETCH_ASSOC);
        localityCheck($identity===['db'=>'h29077_mosa2_test','account'=>'h29077_mosa2_test@localhost','version'=>'8.0.26-16','port'=>3307],'target_identity');
        localityCheck($p->getAttribute(PDO::ATTR_EMULATE_PREPARES)===false,'native_prepares_required');
        localityCheck($p->getAttribute(PDO::ATTR_STRINGIFY_FETCHES)===false,'native_types_required');
        $r['readonly_setup_identity_ms']=(hrtime(true)-$start)/1e6;
        $r['target_identity']='PASS';$r['readonly']='PASS';
        $r['client_version']=$p->getAttribute(PDO::ATTR_CLIENT_VERSION);
        $r['pdo_config']=['emulate_prepares'=>false,'stringify_fetches'=>false,'charset'=>'utf8mb4',
            'collation'=>'utf8mb4_0900_ai_ci','time_zone'=>'+00:00','timeout_s'=>5,'sql_mode'=>'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY'];
        $stage='select1';$samples=[];$sequence=hrtime(true);
        for($i=0;$i<10;$i++){
            $start=hrtime(true);$prepare=0.0;$execute=0.0;$query=0.0;
            if($i<5){$op=hrtime(true);$q=$p->query('SELECT 1 AS probe');$query=(hrtime(true)-$op)/1e6;}
            else{$op=hrtime(true);$q=$p->prepare('SELECT 1 AS probe');$prepare=(hrtime(true)-$op)/1e6;
                $op=hrtime(true);$q->execute();$execute=(hrtime(true)-$op)/1e6;}
            $op=hrtime(true);$value=$q->fetchColumn();$fetch=(hrtime(true)-$op)/1e6;
            $r['select1_executions']++;localityCheck((int)$value===1,'unexpected_probe_value');
            $samples[]=['mode'=>$i<5?'direct':'native','wall_ms'=>(hrtime(true)-$start)/1e6,
                'query_ms'=>$query,'prepare_ms'=>$prepare,'execute_ms'=>$execute,'fetch_ms'=>$fetch];
        }
        $r['select_sequence_ms']=(hrtime(true)-$sequence)/1e6;$r['samples']=$samples;
        $r['direct']=localityStats(array_column(array_slice($samples,0,5),'wall_ms'));
        $r['native']=localityStats(array_column(array_slice($samples,5),'wall_ms'));
        $r['all_selects']=localityStats(array_column($samples,'wall_ms'));
        $stage='rollback';localityCheck($p->rollBack(),'readonly_rollback');$r['rollback']='PASS';$r['ok']=true;
    }catch(Throwable $error){
        $r['failure_stage']=$stage;
        // Neither exception messages nor traces may cross the process boundary.
        $r['failure']=$error instanceof PDOException?'DATABASE_OPERATION_FAILED':'PROBE_VALIDATION_FAILED';
    }finally{
        if($p!==null&&$p->inTransaction()){try{$p->rollBack();}catch(Throwable){$r['ok']=false;$r['cleanup_failure']='ROLLBACK_FAILED';}}
        $p=null;unset($input);$r['total_sequence_ms']=(hrtime(true)-$all)/1e6;
    }
    return $r;
}
if(!defined('MOSA_LOCALITY_LIBRARY_ONLY')){
    ini_set('display_errors','0');ini_set('log_errors','0');
    try{$result=localityProbe($mosa_input);echo json_encode($result,JSON_THROW_ON_ERROR);}
    catch(Throwable){echo '{"ok":false,"failure":"PROBE_PROCESS_FAILED"}';}
}
