<?php
declare(strict_types=1);
namespace Mosa2\MarketRegistry;

use PDO;
use RuntimeException;

require_once __DIR__.'/market_source_engine.php';

/** Test-database only. HTTP/session/credentials are owned by the endpoint, not this module. */
function isin(string $input): string {
    $code = strtoupper(trim($input));
    if (!\fixlabMosaMarketSourceLabIsinValid($code)) throw new RuntimeException('INVALID_ISIN');
    return $code;
}

/** Use exactly the scheduler and Phase-3D writer locks, in the same order. */
function lockNames(string $code): array {
    $id = ['identifier_type'=>'isin','normalized_value'=>isin($code),'scope_key'=>''];
    // This is the same sorted identifier JSON used by Phase3D::json.
    $wire = json_encode($id, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    return ['m2-collector-scheduler','m2-live:'.substr(hash('sha256',$wire),0,48)];
}

function claim(PDO $db, string $name): void {
    $q=$db->prepare('SELECT GET_LOCK(?,0)');
    $q->execute([$name]);
    if ((string)$q->fetchColumn()!=='1') throw new RuntimeException('COLLECTOR_BUSY');
}
function release(PDO $db, string $name): void {
    $q=$db->prepare('SELECT RELEASE_LOCK(?)');
    $q->execute([$name]);
    if ((string)$q->fetchColumn()!=='1') throw new RuntimeException('LOCK_RELEASE_FAILED');
}

/**
 * Remove an entire asset and dependent subject-owned rows.
 * Shared sources, units, metrics, other assets and schema ledger are retained.
 * A failed FK check aborts the whole transaction instead of leaving orphans.
 * The caller must independently verify the post-commit state before reporting success.
 */
function purge(PDO $db,string $raw): array {
    $code=isin($raw);$held=[];
    try {
        foreach(lockNames($code) as $name){ claim($db,$name);$held[]=$name; }
        if($db->inTransaction())throw new RuntimeException('PREEXISTING_TRANSACTION');
        $db->exec('SET SESSION innodb_lock_wait_timeout=3');
        if(!$db->beginTransaction())throw new RuntimeException('TRANSACTION_FAILED');
        try{
            $q=$db->prepare("SELECT a.entity_id FROM m2_asset_identifiers i
                JOIN m2_assets a ON a.entity_id=i.asset_id
                WHERE i.identifier_type='isin' AND i.normalized_value=? AND i.scope_key=''
                  AND i.is_primary=1 AND i.valid_to IS NULL FOR UPDATE");
            $q->execute([$code]);$ids=$q->fetchAll(PDO::FETCH_COLUMN);
            if(count($ids)>1)throw new RuntimeException('AMBIGUOUS_ASSET');
            if(!$ids){
                if(!$db->commit())throw new RuntimeException('COMMIT_FAILED');
                return ['status'=>'absent','isin'=>$code,'deleted'=>[]];
            }
            $id=(string)$ids[0];
            if(!ctype_digit($id)||$id==='0')throw new RuntimeException('INVALID_ASSET');
            // Do not delete work owned by an active or unresolved collector cycle.
            $q=$db->prepare("SELECT COUNT(*) FROM m2_collector_requests WHERE asset_id=? AND status IN ('RESERVED','OUTCOME_UNKNOWN')");
            $q->execute([$id]);if((int)$q->fetchColumn()>0)throw new RuntimeException('ASSET_HAS_PENDING_WORK');
            $q=$db->prepare("SELECT COUNT(*) FROM m2_collector_state WHERE pending_asset=? OR status='RUNNING' OR unresolved=1");
            $q->execute([$id]);if((int)$q->fetchColumn()>0)throw new RuntimeException('COLLECTOR_NOT_IDLE');
            $deleted=[];
            $delete=static function(string $table,string $where,array $args)use($db,&$deleted):void{
                if(!preg_match('/\Am2_[a-z_]+\z/D',$table))throw new RuntimeException('INVALID_TABLE');
                $q=$db->prepare('DELETE FROM '.$table.' WHERE '.$where);
                $q->execute($args);$deleted[$table]=$q->rowCount();
            };
            $delete('m2_fundamental_current','asset_id=?',[$id]);
            $delete('m2_fundamental_observations','asset_id=?',[$id]);
            $delete('m2_market_current','asset_id=?',[$id]);
            $delete('m2_market_bars','asset_id=?',[$id]);
            $delete('m2_market_observations','asset_id=?',[$id]);
            $delete('m2_provider_fetches','asset_id=?',[$id]);
            $delete('m2_collector_requests','asset_id=?',[$id]);
            $delete('m2_events','entity_id=?',[$id]);
            $delete('m2_relationships','from_entity_id=? OR to_entity_id=?',[$id,$id]);
            $delete('m2_files','entity_id=?',[$id]);
            $delete('m2_asset_source_routes','asset_id=?',[$id]);
            $delete('m2_asset_identifiers','asset_id=?',[$id]);
            $delete('m2_assets','entity_id=?',[$id]);
            $delete('m2_entities','id=?',[$id]);
            if($deleted['m2_assets']!==1||$deleted['m2_entities']!==1)throw new RuntimeException('PURGE_INCOMPLETE');
            if(!$db->commit())throw new RuntimeException('COMMIT_FAILED');
            return ['status'=>'deleted','isin'=>$code,'asset_id'=>$id,'deleted'=>$deleted];
        }catch(\Throwable $e){
            if($db->inTransaction())$db->rollBack();
            throw $e;
        }
    }finally{
        foreach(array_reverse($held) as $name)release($db,$name);
    }
}


function connection(string $kind, string $root): PDO {
    $directory = $root.'/mosa2-market-'.$kind.'-private';
    $path = $directory.'/access.php';
    if (realpath($directory)!==$directory || is_link($directory) || !is_file($path)
        || is_link($path) || (fileperms($path)&0077)!==0) throw new RuntimeException('DB_CONFIG');
    $config = require $path;
    $dsn = 'mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4';
    $user = $kind==='write'?'h29077_mosa2_test':'h29077_mosa2_read';
    if (($config['dsn']??null)!==$dsn || ($config['user']??null)!==$user
        || !is_string($config['password']??null)) throw new RuntimeException('DB_CONFIG');
    $db = new PDO($dsn,$user,$config['password'],[
        PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,
        PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>3,
    ]);
    if ($db->query('SELECT DATABASE()')->fetchColumn()!=='h29077_mosa2_test'
        || $db->query('SELECT CURRENT_USER()')->fetchColumn()!==$user.'@localhost'
        || (int)$db->query('SELECT @@foreign_key_checks')->fetchColumn()!==1) throw new RuntimeException('DB_TARGET');
    return $db;
}

function identity(PDO $db, string $code, bool $lock = false): ?array {
    $query=$db->prepare("SELECT a.entity_id,a.display_name,a.status,e.status AS entity_status,i.valid_to,i.is_primary
        FROM m2_asset_identifiers i JOIN m2_assets a ON a.entity_id=i.asset_id
        JOIN m2_entities e ON e.id=a.entity_id
        WHERE i.identifier_type='isin' AND i.normalized_value=? AND i.scope_key=''".($lock?' FOR UPDATE':''));
    $query->execute([$code]);
    return $query->fetch(PDO::FETCH_ASSOC) ?: null;
}

function register(PDO $db, string $code): array {
    $code=isin($code);
    $locks=[];
    try {
        foreach (lockNames($code) as $lock) { claim($db,$lock); $locks[]=$lock; }
        $db->beginTransaction();
        $asset=identity($db,$code,true);
        if ($asset) {
            if ($asset['status']!=='active' || $asset['entity_status']!=='active'
                || $asset['valid_to']!==null || (int)$asset['is_primary']!==1)
                throw new RuntimeException('INACTIVE_IDENTITY');
            $status='existing';
        } else {
            // The ISIN is a valid identity even before a source supplies a display name.
            $q=$db->prepare("INSERT INTO m2_entities (entity_type,canonical_name,status,created_at,updated_at)
                VALUES ('asset',?,'active',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))");
            $q->execute([$code]);
            $id=$db->lastInsertId();
            $q=$db->prepare("INSERT INTO m2_assets (entity_id,asset_class,display_name,status,created_at,updated_at)
                VALUES (?,'unknown',?,'active',UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))");
            $q->execute([$id,$code]);
            $q=$db->prepare("INSERT INTO m2_asset_identifiers
                (asset_id,identifier_type,identifier_value,normalized_value,scope_key,is_primary,created_at)
                VALUES (?,'isin',?,?,'',1,UTC_TIMESTAMP(6))");
            $q->execute([$id,$code,$code]);
            $status='registered';
        }
        $db->commit();
        return ['status'=>$status,'isin'=>$code];
    } finally {
        if ($db->inTransaction()) $db->rollBack();
        foreach (array_reverse($locks) as $lock) release($db,$lock);
    }
}

const MARKET_TABLES = ['m2_market_current','m2_market_bars','m2_market_observations'];

/** The optional scope is for private acceptance against explicitly registered disposable assets. */
function marketDataScope(?array $assetIds): string {
    if ($assetIds===null) return '';
    if ($assetIds===[]) throw new RuntimeException('INVALID_ASSET_SCOPE');
    foreach ($assetIds as $id) {
        if (!is_string($id) || preg_match('/^[1-9][0-9]*$/D',$id)!==1)
            throw new RuntimeException('INVALID_ASSET_SCOPE');
    }
    return ' WHERE asset_id IN ('.implode(',',array_fill(0,count($assetIds),'?')).')';
}

function purgeMarketData(PDO $db, ?array $assetIds=null): array {
    $scope=marketDataScope($assetIds);
    $locks=[];
    try {
        foreach (['m2-collector-scheduler','m2-current-refresh'] as $lock) { claim($db,$lock); $locks[]=$lock; }
        $db->beginTransaction();
        if ((int)$db->query("SELECT COUNT(*) FROM m2_collector_state WHERE status='RUNNING' OR unresolved=1")->fetchColumn()>0)
            throw new RuntimeException('COLLECTOR_NOT_IDLE');
        $deleted=[];
        foreach (MARKET_TABLES as $table) {
            $query=$db->prepare('DELETE FROM '.$table.$scope);
            $query->execute($assetIds??[]);
            $deleted[$table]=$query->rowCount();
        }
        $db->commit();
        return ['status'=>'deleted','deleted'=>$deleted];
    } finally {
        if ($db->inTransaction()) $db->rollBack();
        foreach (array_reverse($locks) as $lock) release($db,$lock);
    }
}

function verify(PDO $db, string $action, string $code, array $result, ?array $assetIds=null): bool {
    $db->exec('SET SESSION TRANSACTION READ ONLY');
    $db->beginTransaction();
    try {
        if ($action==='purge_all') {
            $scope=marketDataScope($assetIds);
            foreach (MARKET_TABLES as $table) {
                $query=$db->prepare('SELECT COUNT(*) FROM '.$table.$scope);
                $query->execute($assetIds??[]);
                if ((int)$query->fetchColumn()!==0) return false;
            }
            return true;
        }
        $asset=identity($db,$code);
        if ($action==='register') return $asset!==null && $asset['status']==='active' && $asset['entity_status']==='active';
        if ($asset!==null) return false;
        if (!isset($result['asset_id'])) return true;
        foreach (['m2_entities'=>'id','m2_assets'=>'entity_id','m2_asset_identifiers'=>'asset_id',
            'm2_asset_source_routes'=>'asset_id','m2_market_current'=>'asset_id','m2_market_bars'=>'asset_id',
            'm2_market_observations'=>'asset_id','m2_collector_requests'=>'asset_id',
            'm2_fundamental_current'=>'asset_id','m2_fundamental_observations'=>'asset_id','m2_provider_fetches'=>'asset_id'] as $table=>$column) {
            $q=$db->prepare('SELECT COUNT(*) FROM '.$table.' WHERE '.$column.'=?');
            $q->execute([$result['asset_id']]);
            if ((int)$q->fetchColumn()!==0) return false;
        }
        return true;
    } finally {
        $db->rollBack();
    }
}
