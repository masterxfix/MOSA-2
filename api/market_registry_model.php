<?php
declare(strict_types=1);
namespace Mosa2\MarketRegistry;

use PDO;
use RuntimeException;

/** Test-database only. HTTP/session/credentials are owned by the endpoint, not this module. */
function isin(string $input): string {
    $code = strtoupper(trim($input));
    if (!preg_match('/\A[A-Z]{2}[A-Z0-9]{9}[0-9]\z/D', $code)) throw new RuntimeException('INVALID_ISIN');
    return $code;
}

/** Use exactly the scheduler and Phase-3D writer locks, in the same order. */
function lockNames(string $code): array {
    require_once dirname(__DIR__).'/scripts/market_collector/onboarding.php';
    $id = ['identifier_type'=>'isin','normalized_value'=>isin($code),'scope_key'=>''];
    $wire = \Mosa2\Phase3D\json(\Mosa2\MarketIdentity\identifierKey($id));
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
            return ['status'=>'deleted','isin'=>$code,'deleted'=>$deleted];
        }catch(\Throwable $e){
            if($db->inTransaction())$db->rollBack();
            throw $e;
        }
    }finally{
        foreach(array_reverse($held) as $name)release($db,$name);
    }
}
