<?php
declare(strict_types=1);

namespace Mosa2\NovaChat;

const VERSION = 'mosa2_nova_chat_v1';
const ORIGIN = 'https://mosa2-test.scharwerk.de';
const HOST = 'mosa2-test.scharwerk.de';
const WORKER_USER = 'mosa2-nova-worker';
const FRESH = 20;
const MAX_RUN = 100;
const MAX_BYTES = 262144;

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
    if (!is_string($text) || strlen($text) > 1000 || preg_match('/[\x00-\x08\x0b-\x1f\x7f]/', $text)) return false;
    // Test greetings and informational questions only. The worker additionally has no tools.
    return preg_match('/\A(?:hallo(?: nova)?[.!]?|(?:test|ping)(?: [\p{L}\p{N}_ -]{1,60})?[.!]?|'
        .'(?:was|wer|wie|warum|wann|wo|woher|wozu|welch\p{L}*|wieviel|what|who|when|why|where|how|which)\b[^<>]{1,999}\?)\z/iu', $text) === 1;
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
    if (count($chat['messages']) >= 12 || (!isset($data['chats'][$owner]) && count($data['chats']) >= 5)) return 429;
    $chat['updated'] = $now;
    $chat['messages'][] = ['id' => $id, 'text' => $text, 'state' => 'queued', 'at' => $now];
    $data['chats'][$owner] = $chat;
    return 202;
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
                    'text' => $job['text'], 'history' => array_slice($history, -3)]]];
            }
            unset($job);
        }
        return [200, ['job' => null]];
    }
    $lease = $request['lease'] ?? null;
    $reply = $request['reply'] ?? null;
    if (($request['action'] ?? '') !== 'complete' || !is_string($lease)
        || preg_match('/\A[a-f0-9]{32}\z/', $lease) !== 1
        || !is_bool($request['ok'] ?? null) || !is_string($reply) || strlen($reply) > 2400
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
