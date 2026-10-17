<?php
declare(strict_types=1);

require_once __DIR__ . '/probe.php';

use Mosa2\Phase1B\Failure;
use function Mosa2\Phase1B\connect;
use function Mosa2\Phase1B\ensure;
use function Mosa2\Phase1B\run;
use function Mosa2\Phase1B\validateTarget;

ini_set('display_errors', '0');
set_error_handler(static function (int $severity): bool {
    if (!(error_reporting() & $severity)) {
        return true;
    }
    throw new Failure('runtime_warning');
});

function settings(): array
{
    ensure(!is_link(__DIR__) && (fileperms(__DIR__) & 0077) === 0, 'private_directory_required');
    $path = __DIR__ . '/target.php';
    ensure(is_file($path) && !is_link($path), 'private_target_missing');
    $target = require $path;
    ensure(is_array($target), 'private_target_invalid');
    validateTarget($target);
    $public = realpath((string) ($target['public_root'] ?? ''));
    $private = realpath(__DIR__);
    ensure(is_string($public) && is_string($private), 'root_check_failed');
    ensure($private !== $public && !str_starts_with($private, $public . DIRECTORY_SEPARATOR), 'configuration_inside_public_root');
    ensure(is_string($target['allowed_ip'] ?? null) && filter_var($target['allowed_ip'], FILTER_VALIDATE_IP) !== false, 'allowed_ip_required');
    $route = defined('MOSA2_HISTORY_PROFILE') ? 'phase1d' : (defined('MOSA2_HISTORY_10000') ? 'phase1c' : 'phase1b');
    ensure((bool) preg_match('~\A/' . $route . '-[a-f0-9]+/\z~D', (string) ($target['entry_path'] ?? '')), 'entry_path_invalid');
    ensure(is_string($target['public_host'] ?? null) && (bool) preg_match('/\A[a-z0-9.-]+\z/D', $target['public_host']), 'public_host_invalid');
    return $target;
}

function storedPassword(): string
{
    $path = __DIR__ . '/secret.php';
    ensure(is_file($path) && !is_link($path) && (fileperms($path) & 0077) === 0, 'private_secret_missing');
    $value = require $path;
    ensure(is_string($value) && $value !== '', 'private_secret_invalid');
    return $value;
}

function rememberPassword(string $password): void
{
    $path = __DIR__ . '/secret.php';
    // Never replace or inspect another application's configuration.
    if (file_exists($path)) {
        ensure(hash_equals(storedPassword(), $password), 'stored_password_differs');
        return;
    }
    $old = umask(0077);
    try {
        $stream = fopen($path, 'x');
        ensure($stream !== false, 'private_secret_create_failed');
        try {
            ensure(chmod($path, 0600), 'private_secret_permissions_failed');
            $code = "<?php\nreturn " . var_export($password, true) . ";\n";
            ensure(fwrite($stream, $code) === strlen($code) && fflush($stream), 'private_secret_write_failed');
        } finally {
            fclose($stream);
        }
    } finally {
        umask($old);
    }
}

function executeProfile(array $target, string $password): array
{
    if (defined('MOSA2_HISTORY_10000') || defined('MOSA2_HISTORY_PROFILE')) {
        \Mosa2\History10000\profileSpec();
        if (defined('MOSA2_HISTORY_CONCURRENCY')) return \Mosa2\HistoryConcurrency\dispatch($target, $password, __DIR__, PHP_SAPI === 'cli' ? (string) ($GLOBALS['argv'][2] ?? '') : '--measure');
        if (defined('MOSA2_HISTORY_OPTIMIZATION')) return \Mosa2\HistoryOptimization\dispatch($target, $password, __DIR__, PHP_SAPI === 'cli' ? (string) ($GLOBALS['argv'][2] ?? '') : '--measure');
        return \Mosa2\History10000\dispatch(
            $target, $password, __DIR__,
            PHP_SAPI === 'cli' ? (string) ($GLOBALS['argv'][2] ?? '') : '--measure'
        );
    }
    return run($target, $password, __DIR__ . '/budget.txt');
}

function reportJson(array $report): string
{
    return json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
}

function page(string $content, int $status = 200): never
{
    http_response_code($status);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Phase 1B Zugang</title><body><main>' . $content . '</main></body></html>';
    exit;
}

try {
    $target = settings();
    if (PHP_SAPI === 'cli') {
        ensure(($argv[1] ?? null) === '--run', 'explicit_run_argument_required');
        $report = executeProfile($target, storedPassword());
        echo reportJson($report), PHP_EOL;
        exit($report['ok'] ? 0 : 1);
    }
    ensure(PHP_SAPI === 'fpm-fcgi', 'fpm_required');
    ensure(($_SERVER['HTTPS'] ?? '') === 'on', 'https_required');
    ensure(($_SERVER['HTTP_HOST'] ?? '') === $target['public_host'], 'public_host_mismatch');
    ensure(($_SERVER['REMOTE_ADDR'] ?? '') === $target['allowed_ip'], 'request_ip_denied');
    header('Cache-Control: no-store, max-age=0');
    header('X-Robots-Tag: noindex, nofollow');
    header('X-Content-Type-Options: nosniff');
    header("Content-Security-Policy: default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
    $method = $_SERVER['REQUEST_METHOD'] ?? '';
    if ($method === 'GET') {
        // No session, secret, database connection or test is created by GET.
        page('<h1>Phase 1B Zugang</h1><p>Bestehendes Testdatenbank-Passwort direkt hier eingeben.</p><form method="post"><input type="hidden" name="action" value="login"><label>Testpasswort <input type="password" name="password" autocomplete="off" required></label><button type="submit">Geschützt anmelden</button></form>');
    }
    ensure($method === 'POST', 'post_required');
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    ensure($origin === 'https://' . $target['public_host'], 'request_origin_denied');
    $sessions = __DIR__ . '/sessions';
    if (!is_dir($sessions)) {
        ensure(mkdir($sessions, 0700), 'session_directory_failed');
    }
    ensure(!is_link($sessions) && (fileperms($sessions) & 0077) === 0, 'private_sessions_required');
    ini_set('session.use_strict_mode', '1');
    session_name('MOSA2PHASE1B');
    session_save_path($sessions);
    session_set_cookie_params([
        'lifetime' => 0,
        'path' => $target['entry_path'],
        'secure' => true,
        'httponly' => true,
        'samesite' => 'Strict',
    ]);
    ensure(session_start(), 'session_start_failed');
    $action = $_POST['action'] ?? '';
    if ($action === 'login') {
        $password = $_POST['password'] ?? null;
        ensure(is_string($password) && $password !== '', 'password_required');
        // Authenticate the existing DB password and verify the target before storing it.
        $connection = connect($target, $password);
        $connection = null;
        rememberPassword($password);
        unset($password, $_POST['password']);
        ensure(session_regenerate_id(true), 'session_regenerate_failed');
        $_SESSION['authenticated_until'] = time() + 600;
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
        $token = htmlspecialchars($_SESSION['csrf'], ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        page('<h1>Phase 1B</h1><p>Geschützt angemeldet. Keine Datenbanktabellen angelegt.</p><form method="post"><input type="hidden" name="action" value="run"><input type="hidden" name="csrf" value="' . $token . '"><button type="submit">Begrenzte Tests einmal ausführen</button></form>');
    }
    ensure($action === 'run', 'unknown_action');
    ensure((int) ($_SESSION['authenticated_until'] ?? 0) >= time(), 'session_authentication_required');
    ensure(is_string($_POST['csrf'] ?? null) && isset($_SESSION['csrf']) && hash_equals($_SESSION['csrf'], $_POST['csrf']), 'csrf_rejected');
    unset($_SESSION['csrf']);
    $report = executeProfile($target, storedPassword());
    if (defined('MOSA2_HISTORY_OPTIMIZATION') && ($report['ok'] ?? false) && ($report['stage'] ?? '') !== 'ascending') {
        // Keep the same bounded authenticated session for the next server-prepared stage.
        // No GET executes a test; a fresh one-use CSRF token is required for every POST.
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
        $token = htmlspecialchars($_SESSION['csrf'], ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        page('<h1>History-Vergleich</h1><pre>' . htmlspecialchars(reportJson($report), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '</pre><form method="post"><input type="hidden" name="action" value="run"><input type="hidden" name="csrf" value="' . $token . '"><button type="submit">Nächste vorbereitete Variante einmal messen</button></form>');
    }
    $_SESSION = [];
    session_destroy();
    setcookie(session_name(), '', ['expires' => time() - 3600, 'path' => $target['entry_path'], 'secure' => true, 'httponly' => true, 'samesite' => 'Strict']);
    page('<h1>Phase 1B Prüfergebnis</h1><pre>' . htmlspecialchars(reportJson($report), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '</pre>', $report['ok'] ? 200 : 500);
} catch (Throwable $error) {
    $failure = ['ok' => false, 'failure' => [
        'code' => $error instanceof Failure ? $error->getMessage() : 'request_failed',
        'sqlstate' => $error instanceof PDOException && preg_match('/\A[A-Z0-9]{5}\z/D', (string) $error->getCode()) ? $error->getCode() : null,
    ]];
    if (PHP_SAPI === 'cli') {
        echo reportJson($failure), PHP_EOL;
        exit(1);
    }
    // Unauthenticated callers receive no runtime, connection or raw exception details.
    page('<h1>Zugriff nicht möglich</h1><p>Keine Tests ausgeführt.</p>', 403);
}
