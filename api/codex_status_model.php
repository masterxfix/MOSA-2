<?php
declare(strict_types=1);

namespace Mosa2\CodexStatus;

const VERSION = 'mosa2_codex_status_v1';
const SOURCE_VERSION = 'mosa_ai_control_telemetry_v1';
const SOURCE_PRESENCE_VERSION = 'mosa2_mosa_order_presence_v1';
const STALE_AFTER_SECONDS = 180;
const MAX_STORE_BYTES = 131072;

function storePath(): string {
    // Same private-directory convention as the MOSA-2 database readers.
    return dirname(__DIR__, 2).'/mosa2-codex-status-private/status.json';
}

/**
 * Plesk-compatible secret source: use the existing environment setting when
 * provided; otherwise read one private, owner-only file outside the webroot.
 * This file is provisioned on the server, NEVER committed or web-deployed.
 */
function privateTokenPath(): string {
    return dirname(storePath()).'/token.txt';
}

function readPrivateToken(string $path): ?string {
    $dir=dirname($path);
    if (is_link($dir) || !is_dir($dir) || is_link($path) || !is_file($path)) return null;
    clearstatcache(true,$path);
    $permissions=@fileperms($path);
    $size=@filesize($path);
    if ($permissions===false || ($permissions & 0077)!==0 ||
        $size===false || $size<64 || $size>66) return null;
    $contents=@file_get_contents($path,false,null,0,67);
    if (!is_string($contents) || strlen($contents)>66) return null;
    $token=rtrim($contents,"\r\n");
    return preg_match('/^[a-f0-9]{64}$/D',$token)===1 ? $token : null;
}

function ingestSecret(): ?string {
    $env=getenv('MOSA2_CODEX_STATUS_TOKEN');
    if (is_string($env) && $env!=='') {
        return strlen($env)>=32 && strlen($env)<=512 ? $env : null;
    }
    return readPrivateToken(privateTokenPath());
}

function initial(): array {
    return ['version'=>VERSION, 'source_presence_version'=>SOURCE_PRESENCE_VERSION,
        'latest_event_at'=>0, 'presence'=>null];
}

function normalizeStore(mixed $data): ?array {
    if (!is_array($data) || ($data['version']??null)!==VERSION) return null;
    // A stored snapshot from before the explicit order filter cannot light the dot.
    if (($data['source_presence_version']??null)!==SOURCE_PRESENCE_VERSION) return initial();
    $latest=$data['latest_event_at']??null;
    if (!is_int($latest) || $latest<0) return null;
    $p=$data['presence']??null;
    if ($p!==null) {
        if (!is_array($p) || !in_array($p['state']??null,['running','idle','unavailable'],true) ||
            !is_int($p['at']??null) || $p['at']<1) return null;
        $eventAt=$p['event_at']??null;
        if (!is_int($eventAt) || $eventAt<0 || $eventAt>$latest ||
            intdiv($eventAt,1000000)>$p['at']) return null;
        $p=['state'=>$p['state'], 'at'=>$p['at'], 'event_at'=>$eventAt];
    }
    return ['version'=>VERSION, 'source_presence_version'=>SOURCE_PRESENCE_VERSION,
        'latest_event_at'=>$latest, 'presence'=>$p];
}

function event(mixed $value, int $now): ?array {
    if (!is_array($value) || ($value['contract_version']??null)!==SOURCE_VERSION ||
        !in_array($value['surface']??null,['codex_cli','codex_vscode'],true) ||
        !in_array($value['event_type']??null,
            ['UserPromptSubmit','Stop','SessionEnd','PreToolUse','PostToolUse','PermissionRequest','WorkStep'],true)) return null;
    $session=$value['session_id_short']??null;
    $turn=$value['turn_id_short']??null;
    $id=$value['event_id']??null;
    $when=$value['recorded_at_utc']??null;
    if (!is_string($session) || $session==='unknown' || !preg_match('/^[A-Za-z0-9_-]{4,16}$/D',$session) ||
        !is_string($turn) || !preg_match('/^(?:unknown|[A-Za-z0-9_-]{4,16})$/D',$turn) ||
        !is_string($id) || !preg_match('/^[a-f0-9]{32}$/D',$id) ||
        !is_string($when) || !preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?Z$/D',$when)) return null;
    try {
        $dt=new \DateTimeImmutable($when);
        if ($dt->getOffset()!==0 || $dt->format('Y-m-d\TH:i:s')!==substr($when,0,19)) return null;
        $at=((int)$dt->format('U'))*1000000+(int)$dt->format('u');
        if ($at>($now+120)*1000000 || $at<($now-86400)*1000000) return null;
    } catch (\Throwable) { return null; }
    return ['type'=>$value['event_type'], 'session'=>$session, 'turn'=>$turn, 'at'=>$at, 'id'=>$id];
}

/**
 * Status evaluated by the original MOSA server, transported only through
 * the already authenticated native mirror. MOSA 2 does not recompute it.
 */
function sourcePresence(mixed $value, int $now): ?array {
    if (!is_array($value) || ($value['contract_version']??null)!==SOURCE_PRESENCE_VERSION ||
        !in_array($value['state']??null,['running','idle','unavailable'],true) ||
        !is_string($value['observed_at_utc']??null) ||
        !preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/D',$value['observed_at_utc'])) return null;
    try {
        $time=new \DateTimeImmutable($value['observed_at_utc']);
        if ($time->getOffset()!==0 ||
            $time->format('Y-m-d\TH:i:s\Z')!==$value['observed_at_utc']) return null;
        $at=$time->getTimestamp();
        return $at>$now+120 || $at<$now-600 ? null : ['state'=>$value['state'],'at'=>$at];
    } catch (\Throwable) { return null; }
}

function state(?array $data, int $now): string {
    $p=$data['presence']??null;
    if ($p===null || $p['at']<$now-STALE_AFTER_SECONDS || $p['at']>$now+120) return 'unavailable';
    // A newer event without a corresponding MOSA snapshot makes the state unknown.
    if ($p['at']<=intdiv($data['latest_event_at'],1000000) && $p['event_at']<$data['latest_event_at'])
        return 'unavailable';
    return $p['state'];
}

function readFile(string $path): ?array {
    if (!is_file($path) || is_link($path) || filesize($path)>MAX_STORE_BYTES) return null;
    $handle=@fopen($path,'rb');
    if (!$handle) return null;
    try {
        if (!flock($handle,LOCK_SH)) return null;
        $raw=stream_get_contents($handle,MAX_STORE_BYTES+1);
        if (!is_string($raw) || strlen($raw)>MAX_STORE_BYTES) return null;
        return normalizeStore(json_decode($raw,true));
    } finally { flock($handle,LOCK_UN); fclose($handle); }
}

function appendFile(string $path, int $latestEvent, ?array $presence): void {
    $dir=dirname($path);
    if (!is_dir($dir) || is_link($dir) || is_link($path)) throw new \RuntimeException('private_store_unavailable');
    $umask=umask(0077);
    try { $handle=@fopen($path,'c+b'); } finally { umask($umask); }
    if (!$handle) throw new \RuntimeException('private_store_unavailable');
    try {
        if (!flock($handle,LOCK_EX) || is_link($path)) throw new \RuntimeException('private_store_unavailable');
        $raw=stream_get_contents($handle,MAX_STORE_BYTES+1);
        if (!is_string($raw) || strlen($raw)>MAX_STORE_BYTES) throw new \RuntimeException('invalid_store');
        $updated=$raw===''?initial():normalizeStore(json_decode($raw,true));
        if ($updated===null) throw new \RuntimeException('invalid_store');
        $updated['latest_event_at']=max($updated['latest_event_at'],$latestEvent);
        if ($presence!==null) {
            $prior=$updated['presence'];
            if ($prior===null || [$presence['at'],$presence['event_at']]>[$prior['at'],$prior['event_at']]) {
                $updated['presence']=$presence;
            }
        }
        $next=json_encode($updated,JSON_THROW_ON_ERROR);
        if (strlen($next)>MAX_STORE_BYTES) throw new \RuntimeException('store_full');
        rewind($handle);
        if (!ftruncate($handle,0) || fwrite($handle,$next)!==strlen($next) || !fflush($handle))
            throw new \RuntimeException('store_write_failed');
    } finally { flock($handle,LOCK_UN); fclose($handle); }
}
