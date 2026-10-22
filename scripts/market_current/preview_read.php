<?php
declare(strict_types=1);
namespace Mosa2\CurrentPreview;
use PDO;
use function Mosa2\Phase2\{check,same};
require_once dirname(__DIR__,2).'/api/observations_read.php';
require_once __DIR__.'/read_access.php';
require_once __DIR__.'/historical_scope.php';

/** Existing bounded resolver + existing Current inputs, in one caller-owned RO snapshot. */
function gather(PDO $p,string $now,bool $lock=false): array {
    $q=$p->prepare(\Mosa2\ObservationRead\scopeSql().($lock?' FOR UPDATE':''));$items=[];
    foreach(\Mosa2\ObservationRead\SCOPE as $isin=>$name){
        $entry=['isin'=>$isin,'name'=>$name,'input'=>null,'scope_rows'=>[]];
        try{
            $q->execute([$isin]);$rows=array_map('Mosa2\\MarketLive\\strings',$q->fetchAll(PDO::FETCH_ASSOC));
            check(count($rows)>0&&count($rows)<=2,'qualified_route_missing');
            if(count($rows)===2)check((int)$rows[1]['route_revision']<(int)$rows[0]['route_revision'],'qualified_route_ambiguous');
            $entry['scope_rows']=$rows;
            // An ID is query scope, never a newly generated route approval.
            $entry['input']=\Mosa2\MarketCurrent\inputs($p,[['route_id'=>$rows[0]['route_id']]],$now,$lock)[0];
            $entry['input']['approval']=null;
        }catch(\Throwable){$entry['blocked_reason']='READ_SCOPE_OR_INPUT_REJECTED';}
        $items[]=$entry;
    }
    return ['as_of'=>$now,'items'=>$items];
}
function qualify(array $entry): array {
    check(isset(\Mosa2\ObservationRead\SCOPE[$entry['isin']]),'preview_scope');
    check($entry['name']===\Mosa2\ObservationRead\SCOPE[$entry['isin']],'preview_name');
    $rows=$entry['scope_rows'];check(count($rows)>0&&count($rows)<=2,'preview_routes');
    $r=\Mosa2\ObservationRead\binding($rows[0],$entry['isin']);
    if(count($rows)===2)check((int)$rows[1]['route_revision']<(int)$r['route_revision'],'preview_ambiguous');
    $route=$entry['input']['route'];
    foreach(['asset_id','source_id','route_revision','route_type','priority','enabled','external_key',...\Mosa2\QuoteSelection\UNITS] as $key)
        same($route[$key],$r[$key],'preview_route_drift');
    same($route['id'],$r['route_id'],'preview_route_drift');
    return $entry['input'];
}
/** One fresh connection: session defaults are set BEFORE BEGIN, never during a transaction.
 * SET TRANSACTION alone changes the next transaction, not @@session.transaction_read_only.
 * https://dev.mysql.com/doc/refman/8.0/en/set-transaction.html
 */
function readSnapshot(PDO $p,?callable $extra=null): array {
    $stage='READ_IDENTITY_REJECTED';$diagnostics=[];$result=[];
    try{
        check(!$p->inTransaction(),'read_existing_transaction');
        same($p->query('SELECT DATABASE() AS db,CURRENT_USER() AS account')->fetch(),['db'=>'h29077_mosa2_test','account'=>'h29077_mosa2_read@localhost'],'read_identity');
        $stage='READ_DATABASE_PROPERTIES_REJECTED';
        $properties=$p->query('SELECT VERSION() AS version,@@version_comment AS comment')->fetch();
        // This proof is documented for MySQL 8.0. Other engines fail closed, not guessed.
        check(preg_match('/^8\.0\.[0-9]+(?:[-.][A-Za-z0-9.-]+)?$/D',$properties['version'])===1
            &&stripos($properties['comment'],'MariaDB')===false,'read_database_unsupported');
        $diagnostics[]='MYSQL_80_PROPERTIES_CONFIRMED';
        $stage='READ_TRANSACTION_VARIABLE_UNSUPPORTED';
        $variables=$p->query("SHOW SESSION VARIABLES WHERE Variable_name IN ('transaction_read_only','transaction_isolation')")->fetchAll();
        $values=array_column($variables,'Value','Variable_name');
        check(isset($values['transaction_read_only'],$values['transaction_isolation']),'read_transaction_variables');
        $diagnostics[]='TRANSACTION_READ_ONLY_VARIABLE_SUPPORTED';
        if(in_array($values['transaction_read_only'],['OFF','0'],true))$diagnostics[]='LEGACY_SESSION_DEFAULT_READ_WRITE';
        $stage='READ_PRIVILEGES_REJECTED';
        $literal=(string)$p->query('SELECT @@partial_revokes')->fetchColumn()==='1';
        \Mosa2\MarketReadAccess\grants($p->query('SHOW GRANTS FOR CURRENT_USER')->fetchAll(),$literal);
        $stage='READ_SESSION_SETUP_REJECTED';
        $p->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
        $p->exec('SET SESSION TRANSACTION READ ONLY');
        $stage='READ_SESSION_STATE_REJECTED';
        $expected=['read_only'=>'1','isolation'=>'REPEATABLE-READ'];
        $sql='SELECT @@session.transaction_read_only AS read_only,@@session.transaction_isolation AS isolation';
        same($p->query($sql)->fetch(),$expected,'read_session_defaults');
        $stage='READ_TRANSACTION_START_REJECTED';
        check($p->beginTransaction()&&$p->inTransaction(),'read_transaction_start');
        $stage='READ_TRANSACTION_STATE_REJECTED';
        same($p->query($sql)->fetch(),$expected,'read_transaction_defaults');
        check($p->inTransaction(),'read_transaction_active');
        $stage='READ_SNAPSHOT_DATA_REJECTED';
        $now=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');
        if($extra!==null)$stage='READ_MIGRATION_METADATA_REJECTED';
        $metadata=$extra===null?null:$extra($p);
        $stage='READ_SNAPSHOT_DATA_REJECTED';
        $snapshot=gather($p,$now);
        if($extra!==null)$snapshot['migration5']=$metadata;
        check($p->inTransaction(),'read_snapshot_transaction_lost');
        $result=['ok'=>true,'read_only_confirmed'=>true,'snapshot'=>$snapshot];
    }catch(\Throwable){$result=['ok'=>false,'failure'=>$stage];}
    finally{
        try{if($p->inTransaction())check($p->rollBack(),'read_rollback');}
        catch(\Throwable){$result=['ok'=>false,'failure'=>'READ_ROLLBACK_REJECTED'];}
    }
    return $result+['diagnostics'=>$diagnostics];
}
/** Exactly one existing SELECT-only account; no fallback to a writer credential. */
function liveRead(?callable $extra=null): array {
    $path='/var/www/vhosts/web213.server10.configcenter.info/mosa2-market-read-private/access.php';
    if(!is_file($path))return ['ok'=>false,'failure'=>'READ_CONFIG_UNAVAILABLE','database_connections'=>0];
    if(is_link($path)||is_link(dirname($path))||(fileperms($path)&0077)!==0||(fileperms(dirname($path))&0077)!==0)
        return ['ok'=>false,'failure'=>'READ_CONFIG_UNSAFE','database_connections'=>0];
    $p=null;$attempts=0;$stage='READ_CONFIG_REJECTED';
    try{
        $c=require $path;
        same($c['user'],'h29077_mosa2_read','read_account');
        same($c['dsn'],'mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4','read_target');
        $stage='READ_CONNECTION_UNAVAILABLE';$attempts++;
        $p=new PDO($c['dsn'],$c['user'],$c['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_STRINGIFY_FETCHES=>true,PDO::ATTR_TIMEOUT=>3]);
        unset($c);
        return readSnapshot($p,$extra)+['database_connections'=>1];
    }catch(\Throwable){return ['ok'=>false,'failure'=>$stage,'database_connections'=>$attempts];}
    finally{$p=null;}
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    try{$entry=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
        if(($entry['operation']??null)==='scope')$reply=['scope'=>\Mosa2\ObservationRead\SCOPE];
        elseif(($entry['operation']??null)==='describe'){
            $row=$entry['row']+['display_name'=>'','source_name'=>'','venue'=>'','valid_binding'=>'1'];
            \Mosa2\MarketRead\present($row,$entry['now'],1800);
            $reply=['age_seconds'=>\Mosa2\QuoteSelection\age($row,$entry['now'])];
        }else $reply=['input'=>qualify($entry)];
        echo json_encode(['ok'=>true]+$reply,JSON_THROW_ON_ERROR);}
    catch(\Throwable){echo '{"ok":false,"failure":"QUALIFIED_REFERENCE_REJECTED"}';}
}
