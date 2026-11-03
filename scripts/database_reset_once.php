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
const RETAINED = [
    'm2_sources', 'm2_units', 'm2_module_state', 'm2_schema_migrations',
    'm2_fundamental_metrics', 'm2_fundamental_units', 'm2_collector_state',
];
const PURGE_ORDER = [
    'm2_fundamental_current', 'm2_fundamental_observations', 'm2_provider_fetches',
    'm2_market_current', 'm2_market_observations', 'm2_market_bars',
    'm2_collector_requests', 'm2_collector_cycles', 'm2_collector_days',
    'm2_asset_identifiers', 'm2_asset_source_routes', 'm2_relationships',
    'm2_files', 'm2_events', 'm2_job_runs', 'm2_sync_checkpoints',
    'm2_assets', 'm2_jobs', 'm2_entities',
];
function fail(string $code): never { throw new \RuntimeException($code); }

function migrationSchema(string $root): array {
    return \Mosa2\CollectorSchema6\schemas();
}

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

function rows(PDO $db, string $table): array {
    $order = match ($table) {
        'm2_sources' => 'id',
        'm2_units' => 'unit_key,unit_version',
        'm2_module_state' => 'module_key',
        'm2_schema_migrations' => 'version',
        'm2_fundamental_metrics' => 'metric_key',
        'm2_fundamental_units' => 'unit_key,unit_version',
        'm2_collector_state' => 'provider',
        default => '1',
    };
    return $db->query('SELECT * FROM '.qi($table).' ORDER BY '.$order)->fetchAll(PDO::FETCH_ASSOC);
}

function rowDigest(array $rows): string {
    return hash('sha256', serialize($rows)); // binary SHA-256 columns are not UTF-8
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

function baseline(PDO $db): array {
    $result = [];
    foreach (RETAINED as $table) {
        $data = rows($db, $table);
        $result[$table] = ['count' => count($data), 'sha256' => rowDigest($data)];
    }
    return $result;
}

function activeWriters(PDO $db): array {
    \Mosa2\CollectorSchema5\lockedDatabase($db);
    $enabled = (int)$db->query("SELECT COUNT(*) FROM m2_jobs WHERE enabled=1")->fetchColumn();
    $running = (int)$db->query("SELECT COUNT(*) FROM m2_job_runs WHERE status='running'")->fetchColumn();
    same($enabled, 0, 'enabled_writer_jobs');
    same($running, 0, 'running_job_records');
    return ['enabled_jobs' => $enabled, 'running_job_runs' => $running];
}

function preflight(PDO $db, string $root): array {
    exactTables($db); noForeignObjects($db); $grants = grants($db);
    $schema = migrationSchema($root);
    $structure = \Mosa2\Phase3K\structure($db, $schema);
    $ledger = ledger($db); $counts = counts($db); $baseline = baseline($db); $writers = activeWriters($db);
    return [
        'database' => TARGET_DATABASE, 'account' => 'h29077_mosa2_test@localhost',
        'version' => EXPECTED_VERSION, 'port' => 3307, 'tables' => count(expectedTables()),
        'structure_counts' => $structure['counts'], 'ledger' => $ledger,
        'counts' => $counts, 'baseline' => $baseline, 'grants' => $grants,
        'writers' => $writers, 'foreign_objects' => 0,
    ];
}

function purge(PDO $db): array {
    $deleted = [];
    foreach (PURGE_ORDER as $table) {
        try {
            // Keep the disabled Collector bootstrap job, delete only obsolete jobs.
            $filter = $table === 'm2_jobs' ? " WHERE job_key <> 'collector_reservations_v1'" : '';
            $before = (int)$db->query('SELECT COUNT(*) FROM '.qi($table).$filter)->fetchColumn();
            $db->exec('DELETE FROM '.qi($table).$filter);
            same((int)$db->query('SELECT COUNT(*) FROM '.qi($table).$filter)->fetchColumn(), 0, 'delete_readback:'.$table);
        } catch (Throwable $error) {
            throw new \RuntimeException('purge_failed:'.$table, 0, $error);
        }
        $deleted[$table] = $before;
    }
    return $deleted;
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

function postcheck(PDO $db, string $root, array $before, array $ledgerBefore, array $baselineBefore): array {
    exactTables($db); noForeignObjects($db); grants($db);
    $schema = migrationSchema($root); $structure = \Mosa2\Phase3K\structure($db, $schema);
    same(ledger($db), $ledgerBefore, 'ledger_changed');
    $after = counts($db);
    foreach (PURGE_ORDER as $table) {
        if ($table === 'm2_jobs') same($after[$table], 1, 'bootstrap_job_missing');
        else same($after[$table], 0, 'purge_not_empty:'.$table);
    }
    foreach (RETAINED as $table) {
        $data = rows($db, $table);
        same(count($data), $baselineBefore[$table]['count'], 'baseline_count:'.$table);
        same(rowDigest($data), $baselineBefore[$table]['sha256'], 'baseline_changed:'.$table);
    }
    same((int)$db->query('SELECT @@foreign_key_checks')->fetchColumn(), 1, 'foreign_keys_enabled_after');
    $orphans = orphanChecks($db);
    $simple = $db->query('SELECT id,source_key FROM m2_sources ORDER BY id LIMIT 1')->fetch(PDO::FETCH_ASSOC);
    check(is_array($simple), 'simple_read');
    \Mosa2\CollectorSchema5\lockedDatabase($db);
    same($after['m2_collector_requests'], 0, 'collector_requests_not_empty');
    same($after['m2_collector_cycles'], 0, 'collector_cycles_not_empty');
    same($after['m2_collector_days'], 0, 'collector_days_not_empty');
    return ['counts' => $after, 'structure_counts' => $structure['counts'], 'orphans' => $orphans, 'simple_read' => 'PASS', 'collector_disabled' => true, 'retained_baseline' => $baselineBefore];
}

function safeFailureCode(Throwable $error): string {
    if ($error instanceof \PDOException) return 'database_operation_failed';
    $message = $error->getMessage();
    return $error instanceof \RuntimeException
        && preg_match('/\A[a-z][a-z0-9_:.-]{0,127}\z/D', $message)
        ? $message : 'contract_or_runtime_failed';
}

function run(array $input, string $root): array {
    $phase = 'INPUT'; $commitAttempted = false; $committed = false;
    try {
    check(($input['attempt'] ?? null) === '1', 'first_attempt_only');
    $commit = $input['commit'] ?? '';
    check(is_string($commit) && preg_match('/\\A[0-9a-f]{40}\\z/D', $commit) === 1, 'commit_binding');
    same($input['authorization'] ?? null, 'MOSA2-TEST-DATA-RESET:'.$commit, 'reset_authorization');
    same($input['mode'] ?? null, 'irreversible-full-test-data-reset', 'reset_mode');
    $password = $input['password'] ?? null; check(is_string($password) && $password !== '', 'reset_secret');
    $port = $input['db_port'] ?? null;
    check(is_int($port) && $port >= 1 && $port <= 65535, 'invalid_local_tunnel_port');

    $phase = 'PRECHECK';
    $db = connection($password, '127.0.0.1', $port); readOnlyBegin($db);
    try { $before = preflight($db, $root); $ledgerBefore = $before['ledger']; $baselineBefore = $before['baseline']; }
    finally { if ($db->inTransaction()) $db->rollBack(); $db = null; }

    $phase = 'DELETE';
    $db = connection($password, '127.0.0.1', $port); $lock = null; $deleted = [];
    try {
        $lock = (int)$db->query("SELECT GET_LOCK('".LOCK_NAME."',5)")->fetchColumn();
        same($lock, 1, 'reset_lock');
        check($db->beginTransaction(), 'reset_transaction');
        same((int)$db->query('SELECT @@foreign_key_checks')->fetchColumn(), 1, 'foreign_keys_before_delete');
        $deleted = purge($db);
        $phase = 'COMMIT';
        $commitAttempted = true; $db->commit(); $committed = true;
    } finally {
        if (!$committed && !$commitAttempted && $db->inTransaction()) $db->rollBack();
        if ($lock === 1) { try { $db->query("SELECT RELEASE_LOCK('".LOCK_NAME."')"); } catch (Throwable) {} }
        $db = null;
    }

    $phase = 'POSTCHECK';
    $db = connection($password, '127.0.0.1', $port); readOnlyBegin($db);
    try { $after = postcheck($db, $root, $before['counts'], $ledgerBefore, $baselineBefore); }
    finally { if ($db->inTransaction()) $db->rollBack(); $db = null; }
    unset($password, $input);
    return ['status' => 'RESET_SUCCEEDED', 'database' => TARGET_DATABASE, 'schema_version' => 6, 'tables' => count(expectedTables()), 'deleted' => $deleted, 'preflight_counts' => $before['counts'], 'postcheck' => $after, 'commit_attempted' => $commitAttempted, 'committed' => $committed];
    } catch (Throwable $error) {
        $status = $committed ? 'RESET_POSTCHECK_FAILED' : ($commitAttempted ? 'RESET_OUTCOME_UNKNOWN' : 'RESET_NOT_EXECUTED');
        return ['status' => $status, 'phase' => $phase, 'error_code' => safeFailureCode($error),
            'commit_attempted' => $commitAttempted, 'committed' => $committed];
    }
}

if (PHP_SAPI === 'cli' && realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    ini_set('display_errors', '0'); ini_set('log_errors', '0'); umask(0077);
    try {
        $wire = stream_get_contents(STDIN, 8193); check(strlen($wire) <= 8192, 'input_limit');
        $input = json_decode($wire, true, 32, JSON_THROW_ON_ERROR);
        $report = run($input, dirname(__DIR__).'/docs/database/migrations');
        echo json_encode($report, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE), PHP_EOL;
        exit($report['status'] === 'RESET_SUCCEEDED' ? 0 : 1);
    } catch (Throwable $error) {
        echo json_encode(['status' => 'RESET_OUTCOME_UNKNOWN', 'phase' => 'INPUT_OR_OUTPUT', 'error_code' => 'unhandled_runtime_error'], JSON_THROW_ON_ERROR), PHP_EOL; exit(1);
    }
}

