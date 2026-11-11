<?php
declare(strict_types=1);

require_once __DIR__.'/nova_status_model.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');

$state = null;
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') {
    http_response_code(405);
    header('Allow: GET');
} else {
    // Document root of the existing MOSA installation under the same account.
    $mosaRoot = dirname(__DIR__, 2).'/httpdocs/scharwerk.de/dashboard_neu';
    $state = \Mosa2\NovaStatus\readSource($mosaRoot);
    if ($state === null) {
        http_response_code(503);
    }
}

echo json_encode([
    'contract_version' => \Mosa2\NovaStatus\VERSION,
    'state' => $state ?? 'unavailable',
], JSON_THROW_ON_ERROR);
