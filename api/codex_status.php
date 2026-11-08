<?php
declare(strict_types=1);
require_once __DIR__.'/codex_status_model.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private');
header('X-Content-Type-Options: nosniff');
if (($_SERVER['REQUEST_METHOD']??'GET')!=='GET') {
    http_response_code(405);
    header('Allow: GET');
    echo '{"status":"error"}';
    exit;
}
try {
    $data=\Mosa2\CodexStatus\readFile(\Mosa2\CodexStatus\storePath());
    $state=\Mosa2\CodexStatus\state($data,time());
} catch (Throwable) {
    $state='unavailable';
}
echo json_encode(['contract_version'=>\Mosa2\CodexStatus\VERSION,'state'=>$state],
    JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);
