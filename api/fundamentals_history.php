<?php
declare(strict_types=1);

ini_set('display_errors', '0');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');

function historyReply(int $code, array $data): never {
    http_response_code($code);
    echo json_encode($data, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
    exit;
}

function historyFile(string $path): ?array {
    clearstatcache(true, $path);
    if (is_link($path)) throw new RuntimeException('link');
    if (!is_file($path)) return null;
    if ((fileperms($path) & 0777) !== 0600 || filesize($path) > 4096)
        throw new RuntimeException('file');
    return json_decode(file_get_contents($path), true, 8, JSON_THROW_ON_ERROR);
}

function historyStatus(string $directory, string $id, string $owner): never {
    $request = historyFile($directory.'/'.$id.'.request');
    if ($request === null || !hash_equals($request['owner'], $owner))
        historyReply(404, ['message' => 'Anfrage nicht gefunden.']);
    $result = historyFile($directory.'/'.$id.'.result');
    $claim = historyFile($directory.'/'.$id.'.claim');
    $status = $result['status'] ?? ($claim === null ? 'queued' : (time() - $claim['at'] > 1200 ? 'unknown' : 'running'));
    $message = match ($status) {
        'queued' => 'Anfrage gespeichert. Der kontrollierte Importjob wartet auf Ausführung.',
        'running' => 'Der Job prüft den Bestand, die Berichtsfundstellen und den Datenbank-Readback.',
        'complete' => 'Der angeforderte Bestand wurde bestätigt.',
        'partial' => 'Neue Werte wurden geprüft und gespeichert. Für weitere Perioden oder Kennzahlen fehlen belastbare Quellen.',
        'unavailable' => 'Für die offenen Perioden oder Kennzahlen liegt keine qualifizierte offizielle Quelle vor.',
        'conflict' => 'Berichtsangaben oder Bestandsdaten sind widersprüchlich. Die betroffenen Werte wurden ausgelassen.',
        'unknown' => 'Der Schreibstatus ist unklar. Der Job bleibt bis zur unabhängigen Prüfung gesperrt.',
        default => 'Der Abruf wurde abgebrochen. Die Jobdetails müssen geprüft werden.',
    };
    $inserted = (int)($result['inserted'] ?? 0);
    historyReply($status === 'queued' ? 202 : 200, [
        'id' => $id, 'status' => $status, 'message' => $message, 'inserted' => $inserted,
        'run' => $result['run'] ?? null,
    ]);
}

if (($_SERVER['HTTP_HOST'] ?? '') !== 'mosa2-test.scharwerk.de' ||
    ($_SERVER['SERVER_NAME'] ?? '') !== 'mosa2-test.scharwerk.de' ||
    ($_SERVER['HTTPS'] ?? '') !== 'on' || ($_SERVER['REMOTE_USER'] ?? '') === '')
    historyReply(403, ['message' => 'Die Anfrage erfordert eine Anmeldung auf der MOSA-2-Testsite.']);

$owner = hash('sha256', $_SERVER['REMOTE_USER']);
$method = $_SERVER['REQUEST_METHOD'] ?? '';
// Issue #61: block new jobs on the testsite; keep existing read/queue logic in source.
if ($method === 'POST')
    historyReply(403, ['message' => 'Historische Importe sind auf der MOSA-2-Testsite gesperrt.']);
if (!in_array($method, ['GET', 'POST'], true)) {
    header('Allow: GET, POST');
    historyReply(405, ['message' => 'Methode nicht unterstützt.']);
}
if ($method === 'POST' &&
    (($_SERVER['HTTP_ORIGIN'] ?? '') !== 'https://mosa2-test.scharwerk.de' ||
     ($_SERVER['CONTENT_TYPE'] ?? '') !== 'application/json'))
    historyReply(403, ['message' => 'Nur Anfragen von der Fundamentaldatenansicht sind zugelassen.']);

try {
    $directory = dirname(__DIR__, 2).'/private/mosa2-collector/history';
    if (realpath($directory) !== $directory || !is_dir($directory) ||
        (fileperms($directory) & 0777) !== 0700)
        historyReply(503, ['message' => 'Der Importjob ist noch nicht eingerichtet. Gespeicherte Werte bleiben verfügbar.']);
    if ($method === 'GET') {
        $id = $_GET['id'] ?? '';
        if (!is_string($id) || preg_match('/\A[0-9a-f]{64}\z/', $id) !== 1)
            historyReply(400, ['message' => 'Ungültige Anfrage-ID.']);
        historyStatus($directory, $id, $owner);
    }
    $raw = file_get_contents('php://input', false, null, 0, 513);
    if ($raw === false || strlen($raw) > 512) historyReply(413, ['message' => 'Anfrage zu groß.']);
    $input = json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
    $isin = $input['isin'] ?? null;
    $start = $input['start'] ?? null;
    $end = $input['end'] ?? null;
    $kind = $input['kind'] ?? null;
    if (!is_string($isin) || preg_match('/\A[A-Z]{2}[A-Z0-9]{9}[0-9]\z/', $isin) !== 1 ||
        !is_int($start) || !is_int($end) || $start < 1900 || $end > (int)gmdate('Y') ||
        $start > $end || $end - $start > 9 || !in_array($kind, ['fy', 'fq', 'both'], true))
        historyReply(422, ['message' => 'Wähle eine Aktie und einen Zeitraum von höchstens zehn Jahren.']);
    $configPath = dirname(__DIR__, 2).'/mosa2-market-read-private/access.php';
    if (!is_file($configPath) || is_link($configPath) || (fileperms($configPath) & 0077) !== 0)
        throw new RuntimeException('config');
    $config = require $configPath;
    $db = new PDO($config['dsn'], $config['user'], $config['password'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_EMULATE_PREPARES => false, PDO::ATTR_TIMEOUT => 3,
    ]);
    $query = $db->prepare("SELECT e.canonical_name FROM m2_assets a JOIN m2_entities e ON e.id=a.entity_id
        JOIN m2_asset_identifiers i ON i.asset_id=a.entity_id WHERE a.asset_class='equity' AND a.status='active'
        AND e.entity_type='asset' AND e.status='active' AND i.identifier_type='isin' AND i.scope_key=''
        AND i.valid_to IS NULL AND i.normalized_value=? LIMIT 2");
    $query->execute([$isin]);
    $names = $query->fetchAll(PDO::FETCH_COLUMN);
    if (count($names) !== 1) historyReply(404, ['message' => 'Aktie nicht gefunden.']);
    $scope = ['isin' => $isin, 'start' => $start, 'end' => $end, 'kind' => $kind, 'owner' => $owner];
    $id = hash('sha256', json_encode($scope, JSON_THROW_ON_ERROR));
    $target = $directory.'/'.$id.'.request';
    if (historyFile($target) === null) {
        $lockPath = $directory.'/.queue-lock';
        if (historyFile($lockPath) === null) throw new RuntimeException('queue lock');
        $lock = fopen($lockPath, 'r+b');
        if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) throw new RuntimeException('queue lock');
        try {
            if (historyFile($target) === null) {
                $requests = glob($directory.'/*.request');
                if ($requests === false || count($requests) >= 512)
                    historyReply(429, ['message' => 'Die Warteschlange ist ausgelastet.']);
                $temporary = tempnam($directory, '.request-');
                if ($temporary === false || dirname($temporary) !== $directory) throw new RuntimeException('temp');
                try {
                    $json = json_encode($scope + ['name' => $names[0], 'at' => time()], JSON_THROW_ON_ERROR);
                    $stream = fopen($temporary, 'wb');
                    if (!$stream) throw new RuntimeException('write');
                    try {
                        if (!chmod($temporary, 0600) || fwrite($stream, $json) !== strlen($json) ||
                            !fflush($stream) || !fsync($stream)) throw new RuntimeException('write');
                    } finally {
                        fclose($stream);
                    }
                    if (!rename($temporary, $target)) throw new RuntimeException('publish');
                } finally {
                    if (is_file($temporary)) unlink($temporary);
                }
            }
        } finally {
            fclose($lock);
        }
    }
    historyStatus($directory, $id, $owner);
} catch (JsonException) {
    historyReply(400, ['message' => 'Ungültige Anfrage.']);
} catch (Throwable) {
    historyReply(503, ['message' => 'Der historische Abruf ist gerade nicht verfügbar.']);
}
