<?php
declare(strict_types=1);

namespace Mosa2\Phase1B;

use PDO;
use PDOException;
use RuntimeException;
use Throwable;

const COLLATION = 'utf8mb4_0900_as_cs';
const SQL_MODE = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY';
const REQUIRED_RIGHTS = ['CREATE', 'ALTER', 'INDEX', 'INSERT', 'SELECT', 'UPDATE', 'DELETE', 'DROP'];

final class Failure extends RuntimeException {}

function ensure(bool $condition, string $code): void
{
    if (!$condition) {
        throw new Failure($code);
    }
}

function validateRuntime(int $version, string $sapi, bool $driver): void
{
    ensure($version >= 80400 && $version < 80500, 'php_84_required');
    ensure(in_array($sapi, ['cli', 'fpm-fcgi'], true), 'unsupported_sapi');
    ensure($driver, 'pdo_mysql_required');
}

function validateTarget(array $target): void
{
    foreach (['database', 'user'] as $key) {
        ensure(isset($target[$key]) && is_string($target[$key]), 'target_missing');
        ensure((bool) preg_match('/\A[a-z0-9]+_mosa2_test\z/D', $target[$key]), 'test_target_required');
    }
    ensure($target['database'] === $target['user'], 'unexpected_test_user');
}

function validateObservedTarget(array $observed, array $target): void
{
    ensure(($observed['db'] ?? null) === $target['database'], 'database_mismatch');
    $account = explode('@', (string) ($observed['account'] ?? ''), 2)[0];
    ensure($account === $target['user'], 'authenticated_user_mismatch');
    ensure((int) ($observed['port'] ?? 0) === 3307, 'server_port_mismatch');
    ensure(str_starts_with((string) ($observed['version'] ?? ''), '8.0.'), 'mysql_80_required');
}

function connect(array $target, string $password): PDO
{
    validateRuntime(PHP_VERSION_ID, PHP_SAPI, in_array('mysql', PDO::getAvailableDrivers(), true));
    validateTarget($target);
    ensure($password !== '', 'test_password_missing');
    $pdo = new PDO(
        'mysql:host=127.0.0.1;port=3307;dbname=' . $target['database'] . ';charset=utf8mb4',
        $target['user'],
        $password,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_EMULATE_PREPARES => false,
            PDO::ATTR_PERSISTENT => false,
            PDO::ATTR_STRINGIFY_FETCHES => false,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_TIMEOUT => 5,
        ]
    );
    $observed = $pdo->query('SELECT DATABASE() AS db, CURRENT_USER() AS account, @@port AS port, VERSION() AS version')->fetch();
    validateObservedTarget($observed, $target);
    $pdo->exec("SET NAMES utf8mb4 COLLATE " . COLLATION);
    $pdo->exec("SET SESSION sql_mode = '" . SQL_MODE . "'");
    $pdo->exec("SET SESSION time_zone = '+00:00'");
    $pdo->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
    $pdo->exec('SET SESSION innodb_lock_wait_timeout = 3');
    $pdo->exec('SET SESSION lock_wait_timeout = 3');
    return $pdo;
}

function sessionState(PDO $pdo): array
{
    $state = $pdo->query(
        'SELECT @@character_set_connection AS charset, @@collation_connection AS collation, '
        . '@@session.sql_mode AS sql_mode, @@session.time_zone AS time_zone, '
        . '@@session.transaction_isolation AS isolation'
    )->fetch();
    ensure($state['charset'] === 'utf8mb4', 'connection_charset_mismatch');
    ensure($state['collation'] === COLLATION, 'connection_collation_mismatch');
    $actual = explode(',', $state['sql_mode']);
    $expected = explode(',', SQL_MODE);
    sort($actual);
    sort($expected);
    ensure($actual === $expected, 'strict_session_mode_mismatch');
    ensure($state['time_zone'] === '+00:00', 'utc_session_mismatch');
    ensure($state['isolation'] === 'REPEATABLE-READ', 'isolation_mismatch');
    return $state;
}

function tableIdentifier(string $name): string
{
    ensure((bool) preg_match('/\Amosa2_tmp_[a-f0-9]{16}\z/D', $name), 'unsafe_table_identifier');
    return chr(96) . $name . chr(96);
}

function tableExists(PDO $pdo, string $name): bool
{
    $query = $pdo->prepare(
        'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = ?'
    );
    $query->execute([$name]);
    return (int) $query->fetchColumn() !== 0;
}

function rights(PDO $pdo): array
{
    // MySQL records database grants as patterns, including escaped underscores.
    // Match the actual selected schema using server LIKE semantics before CREATE.
    $grantee = "CONCAT(QUOTE(SUBSTRING_INDEX(CURRENT_USER(), '@', 1)), '@', QUOTE(SUBSTRING_INDEX(CURRENT_USER(), '@', -1)))";
    $query = $pdo->query(
        'SELECT PRIVILEGE_TYPE FROM information_schema.schema_privileges '
        . 'WHERE DATABASE() LIKE TABLE_SCHEMA AND GRANTEE = ' . $grantee
        . ' UNION SELECT PRIVILEGE_TYPE FROM information_schema.user_privileges WHERE GRANTEE = ' . $grantee
    );
    $available = $query->fetchAll(PDO::FETCH_COLUMN);
    $result = [];
    foreach (REQUIRED_RIGHTS as $right) {
        $result[strtolower($right)] = in_array($right, $available, true);
    }
    return $result;
}

final class Budget
{
    public function __construct(private string $path) {}

    public function reserve(): void
    {
        ensure(!is_link($this->path), 'unsafe_budget_file');
        $stream = fopen($this->path, 'c+');
        ensure($stream !== false, 'budget_unavailable');
        try {
            ensure(flock($stream, LOCK_EX), 'budget_lock_failed');
            ensure(chmod($this->path, 0600), 'budget_permissions_failed');
            $raw = stream_get_contents($stream);
            ensure($raw === '' || (bool) preg_match('/\A\d+\z/D', $raw), 'budget_invalid');
            $count = $raw === '' ? 0 : (int) $raw;
            ensure($count < 100, 'total_row_budget_exhausted');
            rewind($stream);
            ensure(ftruncate($stream, 0), 'budget_write_failed');
            ensure(fwrite($stream, (string) ($count + 1)) !== false && fflush($stream), 'budget_write_failed');
        } finally {
            flock($stream, LOCK_UN);
            fclose($stream);
        }
    }
}

function run(array $target, string $password, string $budgetPath): array
{
    $report = [
        'ok' => false,
        'runtime' => ['php' => PHP_VERSION, 'sapi' => PHP_SAPI, 'pdo_mysql' => in_array('mysql', PDO::getAvailableDrivers(), true)],
        'checks' => [],
        'insert_reservations' => 0,
        'cleanup' => ['owned_tables_absent' => false],
    ];
    $writer = null;
    $reader = null;
    $name = 'mosa2_tmp_' . bin2hex(random_bytes(8));
    $table = tableIdentifier($name);
    $owned = false;
    $stage = 'connect';
    try {
        $writer = connect($target, $password);
        $reader = connect($target, $password);
        $report['checks']['target_guard'] = true;
        $writerId = (int) $writer->query('SELECT CONNECTION_ID()')->fetchColumn();
        $readerId = (int) $reader->query('SELECT CONNECTION_ID()')->fetchColumn();
        ensure($writer !== $reader && $writerId !== $readerId, 'independent_connections_required');
        $report['checks']['independent_connections'] = true;
        $report['session'] = sessionState($writer);
        ensure(sessionState($reader) === $report['session'], 'session_state_differs');
        $report['checks']['both_sessions_configured'] = true;
        $report['rights'] = rights($writer);
        // Refuse CREATE unless cleanup permission is visible as well.
        ensure(!in_array(false, $report['rights'], true), 'required_privilege_missing');

        $stage = 'ddl';
        ensure(!$writer->inTransaction() && !$reader->inTransaction(), 'ddl_inside_transaction');
        ensure(!tableExists($writer, $name), 'table_name_collision');
        $writer->exec("CREATE TABLE $table (id INT NOT NULL PRIMARY KEY, marker INT NOT NULL, payload VARCHAR(80) NOT NULL) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=" . COLLATION);
        $owned = true;
        $report['checks']['create'] = true;
        $writer->exec("ALTER TABLE $table ADD COLUMN extra VARCHAR(20) NULL");
        $report['checks']['alter'] = true;
        $writer->exec("CREATE INDEX mosa2_marker_idx ON $table (marker)");
        $index = $writer->query("SHOW INDEX FROM $table WHERE Key_name = 'mosa2_marker_idx'")->fetch();
        ensure($index !== false && $index['Column_name'] === 'marker', 'index_missing');
        $report['checks']['index'] = true;
        $meta = $writer->prepare('SELECT ENGINE, TABLE_COLLATION FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = ?');
        $meta->execute([$name]);
        $definition = $meta->fetch();
        ensure($definition['ENGINE'] === 'InnoDB' && $definition['TABLE_COLLATION'] === COLLATION, 'table_definition_mismatch');
        $report['checks']['utf8mb4_innodb_table'] = true;

        $budget = new Budget($budgetPath);
        $insert = static function (PDO $pdo, int $id, int|string $marker, string $payload) use ($table, $budget, &$report): void {
            $budget->reserve();
            ++$report['insert_reservations'];
            $statement = $pdo->prepare("INSERT INTO $table (id, marker, payload) VALUES (?, ?, ?)");
            $statement->execute([$id, $marker, $payload]);
        };
        $count = static fn(PDO $pdo): int => (int) $pdo->query("SELECT COUNT(*) FROM $table")->fetchColumn();
        $stage = 'crud';
        $insert($writer, 1, 1, 'Grüße 🚀');
        $value = $writer->query("SELECT payload FROM $table WHERE id = 1")->fetchColumn();
        ensure($value === 'Grüße 🚀', 'unicode_roundtrip_failed');
        $report['checks']['insert_select_unicode'] = true;
        $update = $writer->prepare("UPDATE $table SET payload = ? WHERE id = 1");
        $update->execute(['Änderung 🍀']);
        ensure($update->rowCount() === 1 && $writer->query("SELECT payload FROM $table WHERE id = 1")->fetchColumn() === 'Änderung 🍀', 'update_failed');
        $report['checks']['update'] = true;
        ensure($writer->exec("DELETE FROM $table WHERE id = 1") === 1 && $count($writer) === 0, 'delete_failed');
        $report['checks']['delete'] = true;
        try {
            $insert($writer, 4, 'not-an-integer', 'strict rejection');
            throw new Failure('strict_mode_did_not_reject');
        } catch (PDOException $error) {
            ensure(($error->errorInfo[1] ?? null) === 1366, 'unexpected_strict_error');
        }
        ensure($count($writer) === 0, 'strict_rejection_left_row');
        $report['checks']['strict_invalid_integer_rejected'] = true;

        $stage = 'rollback';
        $writer->beginTransaction();
        $insert($writer, 2, 2, 'rollback synthetic');
        ensure($count($writer) === 1 && $count($reader) === 0, 'dirty_read_detected');
        $report['checks']['uncommitted_invisible'] = true;
        $writer->rollBack();
        ensure($count($writer) === 0 && $count($reader) === 0, 'rollback_failed');
        $report['checks']['rollback'] = true;

        $stage = 'commit_visibility';
        $reader->beginTransaction();
        ensure($count($reader) === 0, 'reader_snapshot_not_empty');
        $writer->beginTransaction();
        $insert($writer, 3, 3, 'commit synthetic');
        ensure($count($reader) === 0, 'uncommitted_visible_to_snapshot');
        $writer->commit();
        ensure($count($reader) === 0, 'repeatable_read_snapshot_changed');
        $reader->commit();
        $reader->beginTransaction();
        ensure($count($reader) === 1, 'new_transaction_missing_commit');
        $reader->commit();
        $report['checks']['commit'] = true;
        $report['checks']['repeatable_read_snapshot'] = true;
        $report['checks']['new_reader_transaction_sees_commit'] = true;
        ensure($writer->exec("DELETE FROM $table WHERE id = 3") === 1, 'committed_row_cleanup_failed');
        $report['peak_rows_per_table'] = 1;
        $report['successful_insert_statements'] = 3;
        $report['ok'] = true;
    } catch (Throwable $error) {
        $report['failure'] = [
            'stage' => $stage,
            'code' => $error instanceof Failure ? $error->getMessage() : 'operation_failed',
            'sqlstate' => $error instanceof PDOException && preg_match('/\A[A-Z0-9]{5}\z/D', (string) $error->getCode()) ? $error->getCode() : null,
        ];
    } finally {
        foreach ([$reader, $writer] as $pdo) {
            if ($pdo instanceof PDO && $pdo->inTransaction()) {
                try {
                    $pdo->rollBack();
                } catch (Throwable) {
                    $report['ok'] = false;
                    $report['cleanup']['transaction_rollback_failed'] = true;
                }
            }
        }
        if ($owned && $writer instanceof PDO) {
            try {
                ensure(!$writer->inTransaction() && !($reader instanceof PDO && $reader->inTransaction()), 'cleanup_transaction_active');
                $writer->exec("DROP TABLE $table");
                $report['checks']['drop'] = true;
                $report['cleanup']['owned_tables_absent'] = !tableExists($writer, $name);
                ensure($report['cleanup']['owned_tables_absent'], 'owned_table_still_present');
            } catch (Throwable) {
                $report['ok'] = false;
                $report['cleanup']['owned_tables_absent'] = false;
            }
        } else {
            $report['cleanup']['owned_tables_absent'] = true;
            $report['cleanup']['no_table_created'] = true;
        }
    }
    return $report;
}
