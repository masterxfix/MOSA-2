<?php
declare(strict_types=1);

namespace Mosa2\DatabaseReset;

use PDO;
use Throwable;
use function Mosa2\Phase2\{check, same, connection, qi};

require_once __DIR__.'/market_collector/schema6.php';

const TARGET_DATABASE = 'h29077_mosa2_test';
const EXPECTED_VERSION = '8.0.26-16';
const LOCK_NAME = 'mosa2_h29077_mosa2_test_full_reset';
function expectedTables(): array {
    // The live Dogado database was upgraded to Schema 6 on 2026-11-01.
    return \Mosa2\CollectorSchema5\envelope(6)['tables'];
}
// Recorded in independent read-only inventory 42778982325. AUTO_INCREMENT is data.
const SCHEMA_SHA256 = '9070f22389cccb33c1fcde65c2105e17da0371e2b28af61534ebc44efaff1edc';
const LEDGER_SHA256 = '8527723c195d78daec825e83397b2b7e5ebe35c4f7294fc42b62882d8597c018';
const LEDGER = 'm2_schema_migrations';
const PURGE_ORDER = [
    'm2_fundamental_current', 'm2_fundamental_observations', 'm2_provider_fetches',
    'm2_market_current', 'm2_market_observations', 'm2_market_bars',
    'm2_collector_requests', 'm2_collector_cycles', 'm2_collector_days', 'm2_collector_state',
    'm2_asset_identifiers', 'm2_asset_source_routes', 'm2_relationships',
    'm2_files', 'm2_events', 'm2_job_runs', 'm2_sync_checkpoints',
    'm2_assets', 'm2_jobs', 'm2_entities', 'm2_sources', 'm2_module_state',
    'm2_fundamental_metrics', 'm2_fundamental_units', 'm2_units',
];
function fail(string $code): never { throw new \RuntimeException($code); }

function exactTables(PDO $db): void {
    $actual = $db->query('SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')->fetchAll(PDO::FETCH_COLUMN);
    same($actual, expectedTables(), 'table_contract');
}

function noForeignObjects(PDO $db): void {
    foreach (['routines' => 'ROUTINE_SCHEMA', 'triggers' => 'TRIGGER_SCHEMA', 'events' => 'EVENT_SCHEMA'] as $object => $column) {
        same((int)$db->query('SELECT COUNT(*) FROM information_schema.'.$object.' WHERE '.$column.'=DATABASE()')->fetchColumn(), 0, 'foreign_object:'.$object);
    }
}

function grants(PDO $db): array {
    $actual = $db->query('SHOW GRANTS')->fetchAll(PDO::FETCH_COLUMN); sort($actual);
    $expected = [
        'GRANT USAGE ON *.* TO `h29077_mosa2_test`@`localhost`',
        'GRANT ALL PRIVILEGES ON `h29077\\_mosa2\\_test`.* TO `h29077_mosa2_test`@`localhost`',
    ];
    sort($expected); same($actual, $expected, 'grants_contract'); return $actual;
}

function readOnlyBegin(PDO $db): void {
    $db->exec('SET SESSION TRANSACTION READ ONLY');
    check($db->beginTransaction(), 'readonly_transaction');
    same((string)$db->query('SELECT @@session.transaction_read_only')->fetchColumn(), '1', 'readonly_guard');
    same((int)$db->query('SELECT @@foreign_key_checks')->fetchColumn(), 1, 'foreign_keys_enabled');
}

function counts(PDO $db): array {
    $result = [];
    foreach (expectedTables() as $table) $result[$table] = (int)$db->query('SELECT COUNT(*) FROM '.qi($table))->fetchColumn();
    return $result;
}

function ledger(PDO $db): array {
    $actual = $db->query('SELECT version,migration_key,LOWER(HEX(checksum)) AS checksum,applied_at FROM m2_schema_migrations ORDER BY version')->fetchAll(PDO::FETCH_ASSOC);
    $contract = \Mosa2\CollectorSchema5\envelope(6);
    $files = glob(dirname(__DIR__).'/docs/database/migrations/000[1-6]_*.sql');
    sort($files);
    same(count($files), 6, 'migration_files');
    same(count($actual), 6, 'ledger_count');
    foreach ($actual as $i => $row) {
        same((int)$row['version'], $i + 1, 'ledger_version');
        same($row['migration_key'], basename($files[$i], '.sql'), 'ledger_key');
        same($row['checksum'], $contract['digests'][$i], 'ledger_checksum');
        check((bool)preg_match('/\\A\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}\\.\\d{6}\\z/D', $row['applied_at']), 'ledger_timestamp');
    }
    return $actual;
}

function schemaSignature(PDO $db): string {
    $hashes = [];
    foreach (expectedTables() as $table) {
        $ddl = $db->query('SHOW CREATE TABLE '.qi($table))->fetch(PDO::FETCH_NUM)[1];
        $hashes[$table] = hash('sha256',preg_replace('/ AUTO_INCREMENT=\d+\b/','',$ddl));
    }
    return hash('sha256',json_encode($hashes,JSON_THROW_ON_ERROR));
}

function activeWriters(PDO $db): array {
    $enabled = (int)$db->query("SELECT COUNT(*) FROM m2_jobs WHERE enabled=1")->fetchColumn();
    $running = (int)$db->query("SELECT COUNT(*) FROM m2_job_runs WHERE status='running'")->fetchColumn();
    $collector = (int)$db->query("SELECT COUNT(*) FROM m2_collector_state
        WHERE status='RUNNING' OR stop_latched<>1 OR unresolved<>0 OR active_cycle IS NOT NULL OR operation_token IS NOT NULL")->fetchColumn();
    $cycles = (int)$db->query("SELECT COUNT(*) FROM m2_collector_cycles WHERE status IN ('RUNNING','OUTCOME_UNKNOWN')")->fetchColumn();
    $connections = (int)$db->query('SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE ID<>CONNECTION_ID()')->fetchColumn();
    foreach (['m2-collector-scheduler','m2-fundamentals-pilot','m2-schema6-apply','m2-current-refresh'] as $lock) {
        same((int)$db->query("SELECT IS_FREE_LOCK('".$lock."')")->fetchColumn(),1,'active_lock:'.$lock);
    }
    same([$enabled,$running,$collector,$cycles,$connections],[0,0,0,0,0],'active_m2_writer');
    return ['enabled_jobs'=>0,'running_job_runs'=>0,'active_collector_rows'=>0,'same_account_connections'=>0];
}

function checkedStructure(PDO $db): array {
    exactTables($db); noForeignObjects($db); grants($db);
    same($db->query('SELECT CURRENT_ROLE()')->fetchColumn(),'NONE','active_role');
    same((int)$db->query('SELECT @@session.foreign_key_checks')->fetchColumn(),1,'foreign_keys_enabled');
    same((int)$db->query("SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
        WHERE REFERENCED_TABLE_SCHEMA=DATABASE() AND TABLE_SCHEMA<>DATABASE()")->fetchColumn(),0,'external_fk');
    $schema = schemaSignature($db);
    same($schema,SCHEMA_SHA256,'schema_signature_drift');
    $ledgerHash = hash('sha256',serialize(ledger($db)));
    same($ledgerHash,LEDGER_SHA256,'ledger_signature_drift');
    return ['schema_sha256'=>$schema,'ledger_sha256'=>$ledgerHash];
}

/** Only the final, isolated NOT NULL self-FK on m2_units needs this one-statement hint. */
function deleteUnits(PDO $db): int {
    foreach (['m2_asset_source_routes','m2_market_current','m2_market_observations','m2_market_bars'] as $child) {
        same((int)$db->query('SELECT COUNT(*) FROM '.qi($child))->fetchColumn(),0,'unit_fk_child:'.$child);
    }
    same((int)$db->query("SELECT @@log_bin=0 OR @@session.binlog_format='ROW'")->fetchColumn(),1,'unit_fk_requires_row_binlog');
    same((int)$db->query('SELECT /*+ SET_VAR(foreign_key_checks=OFF) */ @@session.foreign_key_checks')->fetchColumn(),0,'unit_fk_hint_unsupported');
    same((int)$db->query('SELECT @@session.foreign_key_checks')->fetchColumn(),1,'unit_fk_hint_not_scoped');
    $deleted=$db->exec('DELETE /*+ SET_VAR(foreign_key_checks=OFF) */ FROM m2_units');
    same((int)$db->query('SELECT @@session.foreign_key_checks')->fetchColumn(),1,'unit_fk_hint_not_restored');
    return $deleted;
}

function purge(PDO $db, array $before): array {
    $set=PURGE_ORDER; sort($set);
    same($set,array_values(array_diff(expectedTables(),[LEDGER])),'purge_scope');
    // Break the nullable collector state/cycle edges inside the same transaction.
    $db->exec('UPDATE m2_collector_state SET active_cycle=NULL,last_confirmed_cycle=NULL
        WHERE active_cycle IS NOT NULL OR last_confirmed_cycle IS NOT NULL');
    $deleted = [];
    foreach (PURGE_ORDER as $table) {
        try {
            $count = $table==='m2_units' && $before[$table]>0 ? deleteUnits($db) : $db->exec('DELETE FROM '.qi($table));
            same($count,$before[$table],'delete_count:'.$table);
            $deleted[$table]=$count;
        } catch (Throwable $error) {
            if (!$error instanceof \PDOException) throw $error;
            throw new \RuntimeException('purge_failed:'.$table, 0, $error);
        }
    }
    return $deleted;
}

function emptyCounts(PDO $db): array {
    $result=counts($db);
    foreach ($result as $table=>$n) same($n,$table===LEDGER?6:0,'remaining_rows:'.$table);
    return $result;
}

function orphanChecks(PDO $db): array {
    $checks = [
        'assets_entities' => 'SELECT COUNT(*) FROM m2_assets a LEFT JOIN m2_entities e ON e.id=a.entity_id WHERE e.id IS NULL',
        'identifiers_assets' => 'SELECT COUNT(*) FROM m2_asset_identifiers i LEFT JOIN m2_assets a ON a.entity_id=i.asset_id WHERE a.entity_id IS NULL',
        'routes_assets' => 'SELECT COUNT(*) FROM m2_asset_source_routes r LEFT JOIN m2_assets a ON a.entity_id=r.asset_id WHERE a.entity_id IS NULL',
        'routes_sources' => 'SELECT COUNT(*) FROM m2_asset_source_routes r LEFT JOIN m2_sources s ON s.id=r.source_id WHERE s.id IS NULL',
        'relationships_entities' => 'SELECT COUNT(*) FROM m2_relationships r LEFT JOIN m2_entities f ON f.id=r.from_entity_id LEFT JOIN m2_entities t ON t.id=r.to_entity_id WHERE f.id IS NULL OR t.id IS NULL',
        'observations_assets' => 'SELECT COUNT(*) FROM m2_market_observations o LEFT JOIN m2_assets a ON a.entity_id=o.asset_id WHERE a.entity_id IS NULL',
        'observations_routes' => 'SELECT COUNT(*) FROM m2_market_observations o LEFT JOIN m2_asset_source_routes r ON r.id=o.route_id WHERE r.id IS NULL',
        'current_observations' => 'SELECT COUNT(*) FROM m2_market_current c LEFT JOIN m2_market_observations o ON o.id=c.observation_id WHERE c.observation_id IS NOT NULL AND o.id IS NULL',
        'bars_assets' => 'SELECT COUNT(*) FROM m2_market_bars b LEFT JOIN m2_assets a ON a.entity_id=b.asset_id WHERE a.entity_id IS NULL',
        'job_runs_jobs' => 'SELECT COUNT(*) FROM m2_job_runs r LEFT JOIN m2_jobs j ON j.id=r.job_id WHERE j.id IS NULL',
        'checkpoints_sources' => 'SELECT COUNT(*) FROM m2_sync_checkpoints c LEFT JOIN m2_sources s ON s.id=c.source_id WHERE s.id IS NULL',
    ];
    $result = [];
    foreach ($checks as $name => $sql) { $result[$name] = (int)$db->query($sql)->fetchColumn(); same($result[$name], 0, 'orphan:'.$name); }
    return $result;
}

function postcheck(PDO $db, array $before): array {
    same(checkedStructure($db),$before,'structure_changed');
    $after=emptyCounts($db);
    return ['counts'=>$after,'schema_sha256'=>$before['schema_sha256'],'ledger_sha256'=>$before['ledger_sha256'],
        'orphans'=>orphanChecks($db),'independent_read_only'=>true];
}

function safeFailureCode(Throwable $error): string {
    if ($error instanceof \PDOException) return 'database_operation_failed';
    $message = $error->getMessage();
    return $error instanceof \RuntimeException
        && preg_match('/\A[a-z][a-z0-9_:.-]{0,127}\z/D', $message)
        ? $message : 'contract_or_runtime_failed';
}

function run(array $input): array {
    $phase = 'INPUT'; $commitAttempted = false; $committed = false; $before = null; $deleted = null;
    try {
        same($input['attempt'] ?? null,'1','first_attempt_only');
        $commit=$input['commit']??'';
        check(is_string($commit) && preg_match('/\A[0-9a-f]{40}\z/D',$commit)===1,'commit_binding');
        same($input['authorization']??null,'MOSA2-ISSUE61-CONTENT-RESET:'.$commit,'reset_authorization');
        same($input['mode']??null,'issue61-schema6-content-reset','reset_mode');
        $password=$input['password']??null;
        check(is_string($password) && $password!=='','reset_secret');
        $port=$input['db_port']??null;
        check(is_int($port) && $port >= 1 && $port <= 65535,'invalid_local_tunnel_port');

        $phase='PRECHECK';
        $db=connection($password,'127.0.0.1',$port);
        try {
            same((int)$db->query("SELECT GET_LOCK('".LOCK_NAME."',0)")->fetchColumn(),1,'reset_lock');
            // InnoDB: SET autocommit=0 before LOCK TABLES. START TRANSACTION would release the table locks.
            $db->exec('SET SESSION autocommit=0');
            $db->exec('LOCK TABLES '.implode(',',array_map(static fn($t)=>qi($t).' WRITE',expectedTables())));
            $structure=checkedStructure($db);
            $writers=activeWriters($db);
            $before=counts($db);
            check(array_sum($before)>6,'already_empty_no_repeat');

            $phase='DELETE';
            $deleted=purge($db,$before);
            emptyCounts($db);
            same(hash('sha256',serialize(ledger($db))),$structure['ledger_sha256'],'ledger_changed_in_transaction');
            $phase='COMMIT';
            $commitAttempted=true;
            $db->exec('COMMIT');
            $committed=true;
        } finally {
            // Closing releases all locks; never issue an implicit commit on a failed/unknown path.
            if (!$commitAttempted) { try { $db->exec('ROLLBACK'); } catch (Throwable) {} }
            $db=null;
        }

        $phase='POSTCHECK';
        $db=connection($password,'127.0.0.1',$port);
        readOnlyBegin($db);
        try { $after=postcheck($db,$structure); }
        finally { if ($db->inTransaction()) $db->rollBack(); $db=null; }
        return ['status'=>'RESET_SUCCEEDED','database'=>TARGET_DATABASE,'schema_version'=>6,'tables'=>count(expectedTables()),
            'deleted'=>$deleted,'preflight_counts'=>$before,'preflight_writers'=>$writers,'postcheck'=>$after,
            'commit_attempted'=>true,'committed'=>true];
    } catch (Throwable $error) {
        $status=$committed?'RESET_POSTCHECK_FAILED':($commitAttempted?'RESET_OUTCOME_UNKNOWN':'RESET_NOT_EXECUTED');
        return ['status'=>$status,'phase'=>$phase,'error_code'=>safeFailureCode($error),
            'commit_attempted'=>$commitAttempted,'committed'=>$committed,'preflight_counts'=>$before];
    }
}

if (PHP_SAPI === 'cli' && realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    ini_set('display_errors', '0'); ini_set('log_errors', '0'); umask(0077);
    try {
        $wire = stream_get_contents(STDIN, 8193); check(strlen($wire) <= 8192, 'input_limit');
        $input = json_decode($wire, true, 32, JSON_THROW_ON_ERROR);
        $report = run($input);
        echo json_encode($report, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE), PHP_EOL;
        exit($report['status'] === 'RESET_SUCCEEDED' ? 0 : 1);
    } catch (Throwable $error) {
        echo json_encode(['status' => 'RESET_OUTCOME_UNKNOWN', 'phase' => 'INPUT_OR_OUTPUT', 'error_code' => 'unhandled_runtime_error'], JSON_THROW_ON_ERROR), PHP_EOL; exit(1);
    }
}

