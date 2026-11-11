<?php
declare(strict_types=1);

namespace Mosa2\NovaChat;

const VERSION = 'mosa2_nova_chat_v1';
const ORIGIN = 'https://mosa2-test.scharwerk.de';
const HOST = 'mosa2-test.scharwerk.de';
const WORKER_USER = 'mosa2-nova-worker';
const FRESH = 20;
const MAX_RUN = 100;
const MAX_BYTES = 1048576;
const MAX_TEXT_BYTES = 12000;
const MAX_REPLY_BYTES = 8000;
const MAX_REQUEST_BYTES = 65536;
const MAX_HISTORY_BYTES = 32768;

function privateDirectory(): string
{
    return dirname(__DIR__, 2).'/mosa2-nova-chat-private';
}

function trustedSite(array $server): bool
{
    return in_array($server['HTTP_HOST'] ?? '', [HOST, HOST.':443'], true)
        && ($server['SERVER_NAME'] ?? '') === HOST
        && ($server['HTTPS'] ?? '') === 'on'
        && is_string($server['REMOTE_USER'] ?? null) && $server['REMOTE_USER'] !== '';
}

function trustedChatRoute(array $server, bool $workerRoute): bool
{
    return trustedSite($server) && (($server['REMOTE_USER'] === WORKER_USER) === $workerRoute);
}

function workerDigest(string $directory): ?string
{
    $path = $directory.'/worker.sha256';
    if (is_link($directory) || !is_dir($directory) || (fileperms($directory) & 0777) !== 0700
        || is_link($path) || !is_file($path) || (fileperms($path) & 0777) !== 0600) return null;
    $digest = trim((string)file_get_contents($path, false, null, 0, 68));
    return preg_match('/\A[0-9a-f]{64}\z/', $digest) === 1 ? $digest : null;
}

function snapshot(string $directory): array
{
    $path = $directory.'/chat.json';
    if (is_link($path)) throw new \RuntimeException('Invalid store');
    if (!is_file($path)) return ['seen' => 0, 'chats' => []];
    $bytes = file_get_contents($path, false, null, 0, MAX_BYTES + 1);
    if (!is_string($bytes) || strlen($bytes) > MAX_BYTES) throw new \RuntimeException('Invalid store');
    $data = json_decode($bytes, true, 16, JSON_THROW_ON_ERROR);
    if (!is_int($data['seen'] ?? null) || !is_array($data['chats'] ?? null))
        throw new \RuntimeException('Invalid store');
    return $data;
}

function transaction(string $directory, callable $update): array
{
    $path = $directory.'/chat.lock';
    if (is_link($path)) throw new \RuntimeException('Invalid lock');
    $previous = umask(0077);
    try {
        $handle = fopen($path, 'c');
    } finally {
        umask($previous);
    }
    if (!$handle) throw new \RuntimeException('Lock unavailable');
    try {
        if (!flock($handle, LOCK_EX)) throw new \RuntimeException('Lock unavailable');
        $data = snapshot($directory);
        $now = time();
        expire($data, $now);
        $result = $update($data, $now);
        $encoded = json_encode($data, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
        if (strlen($encoded) > MAX_BYTES) throw new \RuntimeException('Store limit');
        $tmp = tempnam($directory, '.chat-');
        if ($tmp === false) throw new \RuntimeException('Store unavailable');
        try {
            if (!chmod($tmp, 0600) || file_put_contents($tmp, $encoded) !== strlen($encoded)
                || !rename($tmp, $directory.'/chat.json')) throw new \RuntimeException('Store unavailable');
        } finally {
            if (is_file($tmp)) unlink($tmp);
        }
        return $result;
    } finally {
        fclose($handle);
    }
}

function expire(array &$data, int $now): void
{
    foreach ($data['chats'] as $owner => &$chat) {
        if ($chat['updated'] <= $now - 3600) {
            unset($data['chats'][$owner]);
            continue;
        }
        foreach ($chat['messages'] as &$job) {
            if (($job['state'] === 'queued' && $job['at'] <= $now - 30)
                || ($job['state'] === 'running' && $job['started'] <= $now - MAX_RUN)) {
                $job['state'] = 'error';
                $job['reply'] = 'NOVA hat nicht rechtzeitig geantwortet. Die Anfrage wird nicht erneut ausgeführt.';
            }
        }
        unset($job);
    }
}

function running(array $data, int $now): bool
{
    foreach ($data['chats'] as $chat)
        foreach ($chat['messages'] as $job)
            if ($job['state'] === 'running' && $job['started'] > $now - MAX_RUN) return true;
    return false;
}

function acceptsText(mixed $text): bool
{
    return is_string($text) && strlen($text) <= MAX_TEXT_BYTES
        && preg_match('/(*UCP)\S/u', $text) === 1
        && preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/', $text) === 0;
}

function navigationLabels(string $html): array
{
    if (preg_match('/<nav\b[^>]*\bdata-site-nav\b[^>]*>(.*?)<\/nav>/is', $html, $nav) !== 1) return [];
    preg_match_all('/<a\b[^>]*\bdata-page="[^"]+"[^>]*>([^<]+)<\/a>/i', $nav[1], $links);
    return array_map(static fn(string $label): string => html_entity_decode(trim($label), ENT_QUOTES, 'UTF-8'), $links[1]);
}

function browserView(array $data, string $owner, int $now, string $csrf): array
{
    $messages = [];
    foreach ($data['chats'][$owner]['messages'] ?? [] as $job) {
        $messages[] = array_intersect_key($job, array_flip(['id', 'text', 'state', 'reply']));
    }
    return ['csrf' => $csrf, 'connected' => $data['seen'] > $now - FRESH || running($data, $now),
        'messages' => $messages];
}

function submit(array &$data, string $owner, array $request, int $now): int
{
    $id = $request['id'] ?? '';
    $text = $request['text'] ?? null;
    if (!is_string($id) || preg_match('/\A[a-f0-9]{32}\z/', $id) !== 1 || !acceptsText($text)) return 422;
    $chat = $data['chats'][$owner] ?? ['updated' => $now, 'messages' => []];
    foreach ($chat['messages'] as $job) {
        if ($job['id'] === $id) return $job['text'] === $text ? 200 : 409;
        if (in_array($job['state'], ['queued', 'running'], true)) return 409;
    }
    if ($data['seen'] <= $now - FRESH && !running($data, $now)) return 503;
    $chat['updated'] = $now;
    $chat['messages'][] = ['id' => $id, 'text' => $text, 'state' => 'queued', 'at' => $now];
    $next = $data;
    $next['chats'][$owner] = $chat;
    $bytes = strlen(json_encode($next, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));
    foreach ($next['chats'] as $conversation) {
        foreach ($conversation['messages'] as $job) {
            // Reserve room for claim metadata and the largest JSON-escaped reply.
            if (in_array($job['state'], ['queued', 'running'], true)) $bytes += 6 * MAX_REPLY_BYTES + 200;
        }
    }
    if ($bytes > MAX_BYTES) return 507;
    $data = $next;
    return 202;
}

function recentHistory(array $history): array
{
    $recent = [];
    $bytes = 2; // JSON array delimiters.
    for ($i = count($history) - 1; $i >= 0; $i--) {
        $bytes += 1 + strlen(json_encode($history[$i], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));
        if ($bytes > MAX_HISTORY_BYTES) break;
        $recent[] = $history[$i];
    }
    return array_reverse($recent);
}

function worker(array &$data, array $request, int $now): array
{
    if (($request['action'] ?? '') === 'claim') {
        $data['seen'] = $now;
        if (running($data, $now)) return [200, ['job' => null]];
        foreach ($data['chats'] as &$chat) {
            $history = [];
            foreach ($chat['messages'] as &$job) {
                if ($job['state'] === 'done') {
                    $history[] = ['question' => $job['text'], 'answer' => $job['reply']];
                }
                if ($job['state'] !== 'queued') continue;
                $job['state'] = 'running';
                $job['started'] = $now;
                $job['lease'] = bin2hex(random_bytes(16));
                return [200, ['job' => ['id' => $job['id'], 'lease' => $job['lease'],
                    'text' => $job['text'], 'history' => recentHistory($history)]]];
            }
            unset($job);
        }
        return [200, ['job' => null]];
    }
    $lease = $request['lease'] ?? null;
    $reply = $request['reply'] ?? null;
    if (($request['action'] ?? '') !== 'complete' || !is_string($lease)
        || preg_match('/\A[a-f0-9]{32}\z/', $lease) !== 1
        || !is_bool($request['ok'] ?? null) || !is_string($reply) || strlen($reply) > MAX_REPLY_BYTES
        || ($request['ok'] && trim($reply) === '')) return [422, []];
    foreach ($data['chats'] as &$chat) {
        foreach ($chat['messages'] as &$job) {
            if (($job['id'] ?? '') !== ($request['id'] ?? '') || ($job['lease'] ?? '') !== $lease) continue;
            if (in_array($job['state'], ['done', 'error'], true)) return [200, []];
            if ($job['state'] !== 'running') return [409, []];
            $job['state'] = $request['ok'] ? 'done' : 'error';
            $job['reply'] = $request['ok'] ? $reply : 'NOVA konnte diese Anfrage nicht beantworten.';
            $data['seen'] = $chat['updated'] = $now;
            return [200, []];
        }
        unset($job);
    }
    return [404, []];
}
