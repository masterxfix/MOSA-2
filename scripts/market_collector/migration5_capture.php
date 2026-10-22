<?php
declare(strict_types=1);
namespace Mosa2\CollectorMigration5;
use PDO;
use function Mosa2\Phase2\{check,qi};

/** Bounded metadata only; executes inside the existing verified RO transaction. */
function capture(PDO $p): array {
    check($p->inTransaction(),'migration5_transaction');$out=[];
    $record=static function(string $sql,array $args=[],int $limit=128)use($p,&$out):array{
        check(str_starts_with($sql,'SELECT ')||str_starts_with($sql,'SHOW '),'migration5_select_only');
        $bounded=str_starts_with($sql,'SELECT ')&&!str_contains($sql,' LIMIT ')?$sql.' LIMIT '.($limit+1):$sql;
        $q=$p->prepare($bounded);$q->execute($args);$rows=$q->fetchAll(PDO::FETCH_ASSOC);check(count($rows)<=$limit,'migration5_metadata_bound');
        $out[]=['sql'=>$sql,'args'=>$args,'rows'=>$rows];return $rows;
    };
    $tables=$record('SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME',[],23);
    // Query strings are supplied by the unchanged shared metadata checker, not a second checker.
    foreach($tables as $table){$name=$table['TABLE_NAME'];
        $record('SHOW CREATE TABLE '.qi($name),[],1);
        foreach(METADATA_QUERIES as $sql)$record($sql,[$name]);
    }
    $ledger=$record('SELECT version,migration_key,HEX(checksum) AS checksum,applied_at FROM m2_schema_migrations ORDER BY version LIMIT 6',[],6);
    $jobs=$record("SELECT id,job_key,module_key,handler_key,enabled,created_at,updated_at FROM m2_jobs WHERE job_key='collector_reservations_v1' OR module_key='collector_reservations' ORDER BY id LIMIT 3",[],3);
    $modules=$record("SELECT module_key,schema_version,status,updated_at FROM m2_module_state WHERE module_key='collector_reservations' LIMIT 2",[],2);
    $objects=[];foreach(['routines'=>'ROUTINE_SCHEMA','triggers'=>'TRIGGER_SCHEMA','events'=>'EVENT_SCHEMA'] as $kind=>$col)
        $objects[$kind]=$record('SELECT COUNT(*) AS n FROM information_schema.'.$kind.' WHERE '.$col.'=DATABASE()',[],1)[0]['n'];
    $collector=[];foreach(['m2_collector_state','m2_collector_cycles','m2_collector_days','m2_collector_requests'] as $name)
        if(in_array($name,array_column($tables,'TABLE_NAME'),true))$collector[$name]=$record('SELECT * FROM '.qi($name).' LIMIT 2',[],2);
    $properties=$record('SELECT DATABASE() AS db,VERSION() AS version,@@port AS port,@@foreign_key_checks AS fk_checks',[],1)[0];
    return ['inventory'=>$out,'ledger'=>$ledger,'jobs'=>$jobs,'modules'=>$modules,'objects'=>$objects,'collector'=>(object)$collector,'properties'=>$properties];
}
/** Preserve the existing 64 KiB SSH output cap; no global transport-limit change. */
function packed(PDO $p): array {
    $raw=json_encode(capture($p),JSON_THROW_ON_ERROR);check(strlen($raw)<=2000000,'migration5_unpacked_bound');
    return ['encoding'=>'gzip-base64-v1','payload'=>base64_encode(gzencode($raw,9)),'sha256'=>hash('sha256',$raw),'length'=>strlen($raw)];
}
