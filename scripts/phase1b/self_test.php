<?php
declare(strict_types=1);

require __DIR__ . '/probe.php';

use Mosa2\Phase1B\Budget;
use Mosa2\Phase1B\Failure;
use function Mosa2\Phase1B\ensure;
use function Mosa2\Phase1B\tableIdentifier;
use function Mosa2\Phase1B\validateObservedTarget;
use function Mosa2\Phase1B\validateRuntime;
use function Mosa2\Phase1B\validateTarget;

$count = 0;
function rejects(callable $case, string $expected): void
{
    global $count;
    try {
        $case();
    } catch (Failure $error) {
        ensure($error->getMessage() === $expected, 'unexpected_guard_failure');
        ++$count;
        return;
    }
    throw new RuntimeException('guard_did_not_reject');
}
$target = ['database' => 'offline_mosa2_test', 'user' => 'offline_mosa2_test'];
validateTarget($target);
validateRuntime(80400, 'cli', true);
validateRuntime(80499, 'fpm-fcgi', true);
rejects(fn() => validateRuntime(80399, 'cli', true), 'php_84_required');
rejects(fn() => validateRuntime(80500, 'fpm-fcgi', true), 'php_84_required');
rejects(fn() => validateRuntime(80400, 'apache2handler', true), 'unsupported_sapi');
rejects(fn() => validateRuntime(80400, 'cli', false), 'pdo_mysql_required');
rejects(fn() => validateTarget(['database' => 'production', 'user' => 'production']), 'test_target_required');
rejects(fn() => validateTarget(['database' => 'offline_mosa2_test;port=3306', 'user' => 'offline_mosa2_test']), 'test_target_required');
rejects(fn() => validateTarget(['database' => 'offline_mosa2_test', 'user' => 'other_mosa2_test']), 'unexpected_test_user');
$observed = ['db' => 'offline_mosa2_test', 'account' => 'offline_mosa2_test@localhost', 'port' => 3307, 'version' => '8.0.26'];
validateObservedTarget($observed, $target);
foreach ([
    ['db', 'other_mosa2_test', 'database_mismatch'],
    ['account', 'other_mosa2_test@localhost', 'authenticated_user_mismatch'],
    ['port', 3306, 'server_port_mismatch'],
    ['version', '5.7.44', 'mysql_80_required'],
] as [$key, $value, $error]) {
    $wrong = $observed;
    $wrong[$key] = $value;
    rejects(fn() => validateObservedTarget($wrong, $target), $error);
}
ensure(tableIdentifier('mosa2_tmp_0123456789abcdef') === chr(96) . 'mosa2_tmp_0123456789abcdef' . chr(96), 'identifier_failed');
foreach (['existing_table', 'mosa2_tmp_unsafe', 'mosa2_tmp_0123456789abcdef;DROP', 'mosa2_tmp_0123456789abcde' . chr(96)] as $name) {
    rejects(fn() => tableIdentifier($name), 'unsafe_table_identifier');
}
$path = tempnam(sys_get_temp_dir(), 'mosa2-p1b-offline-');
try {
    $budget = new Budget($path);
    for ($i = 0; $i < 100; ++$i) {
        $budget->reserve();
    }
    ensure(file_get_contents($path) === '100', 'budget_count_mismatch');
    rejects(fn() => $budget->reserve(), 'total_row_budget_exhausted');
    ensure(file_get_contents($path) === '100', 'exhausted_budget_changed');
    ensure((fileperms($path) & 0077) === 0, 'budget_not_private');
    file_put_contents($path, 'invalid');
    rejects(fn() => $budget->reserve(), 'budget_invalid');
} finally {
    unlink($path);
}
echo json_encode(['ok' => true, 'offline_guard_rejections' => $count, 'database_connections' => 0], JSON_THROW_ON_ERROR), PHP_EOL;
