<?php
declare(strict_types=1);
namespace Mosa2\CurrentPreview;
use PDO;
use function Mosa2\Phase2\{check,same};
require_once dirname(__DIR__,2).'/api/observations_read.php';
require_once __DIR__.'/read_access.php';

/** Existing bounded resolver + existing Current inputs, in one caller-owned RO snapshot. */
function gather(PDO $p,string $now): array {
    $q=$p->prepare(\Mosa2\ObservationRead\scopeSql());$items=[];
    foreach(\Mosa2\ObservationRead\SCOPE as $isin=>$name){
        $entry=['isin'=>$isin,'name'=>$name,'input'=>null,'scope_rows'=>[]];
        try{
            $q->execute([$isin]);$rows=array_map('Mosa2\\MarketLive\\strings',$q->fetchAll(PDO::FETCH_ASSOC));
            check(count($rows)>0&&count($rows)<=2,'qualified_route_missing');
            if(count($rows)===2)check((int)$rows[1]['route_revision']<(int)$rows[0]['route_revision'],'qualified_route_ambiguous');
            $entry['scope_rows']=$rows;
            // An ID is query scope, never a newly generated route approval.
            $entry['input']=\Mosa2\MarketCurrent\inputs($p,[['route_id'=>$rows[0]['route_id']]],$now)[0];
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
/** Exactly one existing SELECT-only account; no fallback to a writer credential. */
function liveRead(): array {
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
        unset($c);$stage='READ_PRIVILEGES_REJECTED';
        same($p->query('SELECT DATABASE() AS db,CURRENT_USER() AS account')->fetch(),['db'=>'h29077_mosa2_test','account'=>'h29077_mosa2_read@localhost'],'read_identity');
        $literal=(string)$p->query('SELECT @@partial_revokes')->fetchColumn()==='1';
        \Mosa2\MarketReadAccess\grants($p->query('SHOW GRANTS FOR CURRENT_USER')->fetchAll(),$literal);
        $stage='READ_SNAPSHOT_REJECTED';
        $p->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');
        $p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
        same((int)$p->query('SELECT @@session.transaction_read_only')->fetchColumn(),1,'read_only_transaction');
        $now=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');
        return ['ok'=>true,'database_connections'=>1,'snapshot'=>gather($p,$now)];
    }catch(\Throwable){return ['ok'=>false,'failure'=>$stage,'database_connections'=>$attempts];}
    finally{if($p!==null&&$p->inTransaction())$p->rollBack();$p=null;}
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
