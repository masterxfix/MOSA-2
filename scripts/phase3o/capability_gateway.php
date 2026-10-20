<?php
declare(strict_types=1);
namespace Mosa2\Phase3O;
require_once __DIR__.'/capability.php';
defined('MOSA2_PHASE3M_LIBRARY_ONLY')||define('MOSA2_PHASE3M_LIBRARY_ONLY',true);
require_once __DIR__.'/../phase3m/password_gateway.php';

function capabilityGateway(string $root): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
    header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'");
    header('Content-Type: text/html; charset=utf-8');
    try{
        $config=require $root.'/access.php';
        \Mosa2\Phase2\check($_SERVER['REQUEST_METHOD']==='GET'&&\Mosa2\Phase3M\requestAllowed($_SERVER,$config,time()),'capability_request');
        set_time_limit(120);$report=gatewayCapability($root,$config);
        echo $report['status']==='RUNTIME_READY'?'<h1>Phase 3O: RUNTIME_READY</h1><p>Vier Goldenpläne. Keine DB-Verbindung.</p>':
            '<h1>Phase 3O: RUNTIME_GAP</h1><p>Keine DB-Verbindung. Keine Wiederholung.</p>';
    }catch(\Throwable $e){http_response_code(403);echo '<h1>Phase 3O: Prüfung gestoppt</h1>';}
}
