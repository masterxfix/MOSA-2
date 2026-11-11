<?php
declare(strict_types=1);

require_once __DIR__.'/nova_status_model.php';
require_once __DIR__.'/nova_chat_store.php';

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
    if (\Mosa2\NovaChat\trustedSite($_SERVER)) {
        try {
            $chat = \Mosa2\NovaChat\snapshot(\Mosa2\NovaChat\privateDirectory());
            if (\Mosa2\NovaChat\running($chat, time())) $state = 'running';
        } catch (\Throwable) {
            // The existing NOVA status remains authoritative if chat storage fails.
        }
    }
    if ($state === null) {
        http_response_code(503);
    }
}

echo json_encode([
    'contract_version' => \Mosa2\NovaStatus\VERSION,
    'state' => $state ?? 'unavailable',
], JSON_THROW_ON_ERROR);
