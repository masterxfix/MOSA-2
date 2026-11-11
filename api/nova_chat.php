<?php
declare(strict_types=1);

namespace Mosa2\NovaChat;

require_once __DIR__.'/nova_chat_store.php';

ini_set('display_errors', '0');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');

function reply(int $status, array $body = []): never
{
    http_response_code($status);
    echo json_encode(['contract_version' => chatName() === 'Codex' ? CODEX_VERSION : VERSION] + $body, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
    exit;
}

$isCodex = chatName() === 'Codex';
$isWorker = $isCodex ? defined('MOSA2_CODEX_WORKER_ROUTE') : defined('MOSA2_NOVA_WORKER_ROUTE');
if (!trustedChatRoute($_SERVER, $isWorker)) reply(403);
$method = $_SERVER['REQUEST_METHOD'] ?? '';
if (!in_array($method, ['GET', 'POST'], true)) {
    header('Allow: GET, POST');
    reply(405);
}

$directory = privateDirectory();
$token = $_SERVER[$isCodex ? 'HTTP_X_M2_CODEX_WORKER' : 'HTTP_X_M2_NOVA_WORKER'] ?? null;
try {
    if ($isWorker && (!is_string($token) || $method !== 'POST' || isset($_SERVER['HTTP_ORIGIN'])
        || preg_match('/\A[0-9a-f]{64}\z/', $token) !== 1)) reply(403);
    if (!$isWorker && $token !== null) reply(403);
    if (!$isWorker && $method === 'POST' && ($_SERVER['HTTP_ORIGIN'] ?? '') !== ORIGIN) reply(403);
    $digest = workerDigest($directory);
    if ($digest === null) reply(503);
    if ($isWorker && !hash_equals($digest, hash('sha256', $token))) reply(403);

    $request = [];
    if ($method === 'POST') {
        if (($_SERVER['CONTENT_TYPE'] ?? '') !== 'application/json') reply(415);
        $body = file_get_contents('php://input', false, null, 0, MAX_REQUEST_BYTES + 1);
        if (!is_string($body) || strlen($body) > MAX_REQUEST_BYTES) reply(413);
        try {
            $request = json_decode($body, true, 8, JSON_THROW_ON_ERROR);
        } catch (\JsonException) {
            reply(400);
        }
        if (!is_array($request)) reply(400);
    }
    if ($isWorker) {
        [$status, $result] = transaction($directory, static function (array &$data, int $now) use ($request): array {
            return worker($data, $request, $now);
        });
        if (isset($result['job'])) {
            $homepage = @file_get_contents(dirname(__DIR__).'/index.html', false, null, 0, 32768);
            $result['job']['navigation'] = is_string($homepage) ? navigationLabels($homepage) : [];
            if ($isCodex && is_string($homepage)) {
                // Supply the published overview as text. The Codex session cannot read repository files.
                $result['job']['overview'] = preg_match('/<main\b[^>]*>(.*?)<\/main>/is', $homepage, $main)
                    ? trim(preg_replace('/\s+/u', ' ', html_entity_decode(strip_tags($main[1]), ENT_QUOTES, 'UTF-8')) ?? '')
                    : '';
            }
        }
        reply($status, $result);
    }

    session_name($isCodex ? 'Mosa2CodexChat' : 'Mosa2NovaChat');
    if (!session_start(['use_strict_mode' => 1, 'use_only_cookies' => 1, 'cookie_secure' => true,
        'cookie_httponly' => true, 'cookie_samesite' => 'Strict', 'cookie_path' => $isCodex ? '/api/codex_chat.php' : '/api/nova_chat.php'])) reply(503);
    $user = hash('sha256', $_SERVER['REMOTE_USER']);
    if (($_SESSION['user'] ?? null) !== $user) {
        if (!session_regenerate_id(true)) reply(503);
        $_SESSION = ['user' => $user, 'nonce' => bin2hex(random_bytes(32)), 'csrf' => bin2hex(random_bytes(32))];
    }
    $owner = hash('sha256', $user.':'.$_SESSION['nonce']);
    $csrf = $_SESSION['csrf'];
    session_write_close();
    if ($method === 'GET') {
        $data = snapshot($directory);
        $now = time();
        expire($data, $now);
        reply(200, browserView($data, $owner, $now, $csrf));
    }
    if (!is_string($request['csrf'] ?? null) || !hash_equals($csrf, $request['csrf'])) reply(403);
    [$status, $result] = transaction($directory, static function (array &$data, int $now) use ($owner, $request, $csrf): array {
        $status = submit($data, $owner, $request, $now);
        return [$status, browserView($data, $owner, $now, $csrf)];
    });
    reply($status, $result);
} catch (\Throwable) {
    reply(503);
}
