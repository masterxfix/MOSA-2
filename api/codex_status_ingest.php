<?php
declare(strict_types=1);
require_once __DIR__.'/codex_status_model.php';

use function Mosa2\CodexStatus\event;
use function Mosa2\CodexStatus\sourcePresence;
use function Mosa2\CodexStatus\appendFile;
use function Mosa2\CodexStatus\storePath;

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
$reply=static function(int $code,int $accepted=0): never {
    http_response_code($code);
    echo json_encode(['contract_version'=>\Mosa2\CodexStatus\VERSION,'accepted'=>$accepted]);
    exit;
};
if (($_SERVER['REQUEST_METHOD']??'GET')!=='POST') {
    header('Allow: POST');
    $reply(405);
}
// Issue #61: stop background writes to M2 only. The native sender is unchanged.
if (strtolower($_SERVER['SERVER_NAME']??'')==='mosa2-test.scharwerk.de' ||
    strtolower(explode(':',$_SERVER['HTTP_HOST']??'',2)[0])==='mosa2-test.scharwerk.de') $reply(403);
if (strtolower(trim(explode(';',(string)($_SERVER['CONTENT_TYPE']??''),2)[0]))!=='application/json') $reply(415);
$secret=\Mosa2\CodexStatus\ingestSecret();
$given=(string)($_SERVER['HTTP_X_MOSA2_CODEX_TOKEN']??'');
if (!is_string($secret) || strlen($secret)<32 || strlen($secret)>512 ||
    strlen($given)>512 || !hash_equals($secret,$given)) $reply(401);
if ((int)($_SERVER['CONTENT_LENGTH']??0)>65536) $reply(413);
$raw=file_get_contents('php://input',false,null,0,65537);
if (!is_string($raw) || $raw==='' || strlen($raw)>65536) $reply(413);
try {
    $payload=json_decode($raw,true,32,JSON_THROW_ON_ERROR);
    $batch=$payload['events']??null;
    if (!is_array($batch) || !array_is_list($batch) || $batch===[] || count($batch)>50)
        $reply(422);
    $parsed=[]; $now=time(); $presence=null;
    foreach ($batch as $item) {
        if (!is_array($item)) $reply(422);
        // A mirror of the existing MOSA batch may contain WORK or WinSCP events.
        if (!in_array($item['surface']??null,['codex_cli','codex_vscode'],true)) continue;
        if (!in_array($item['event_type']??null,
            ['UserPromptSubmit','Stop','SessionEnd','PreToolUse','PostToolUse','PermissionRequest','WorkStep'],true)) continue;
        $value=event($item,$now);
        if ($value===null) $reply(422);
        $parsed[]=$value;
        if (array_key_exists('mosa_source_presence',$item)) {
            $candidate=sourcePresence($item['mosa_source_presence'],$now);
            if ($candidate!==null && ($presence===null || $candidate['at'] >= $presence['at']))
                $presence=$candidate;
        }
    }
    if ($parsed!==[]) appendFile(storePath(),$parsed,$presence);
    $reply(202,count($parsed));
} catch (Throwable) {
    $reply(503);
}
