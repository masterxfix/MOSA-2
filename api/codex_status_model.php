<?php
declare(strict_types=1);

namespace Mosa2\CodexStatus;

const VERSION = 'mosa2_codex_status_v1';
const SOURCE_VERSION = 'mosa_ai_control_telemetry_v1';
const STALE_AFTER_SECONDS = 180;
const MAX_STORE_BYTES = 131072;

function storePath(): string {
    // Same private-directory convention as the MOSA-2 database readers.
    return dirname(__DIR__, 2).'/mosa2-codex-status-private/status.json';
}

function initial(): array {
    return ['version'=>VERSION, 'ever_seen'=>false, 'runs'=>[]];
}

function validStore(mixed $data): bool {
    if (!is_array($data) || ($data['version']??null)!==VERSION ||
        !is_bool($data['ever_seen']??null) || !is_array($data['runs']??null) ||
        count($data['runs'])>128) return false;
    foreach ($data['runs'] as $key=>$run) {
        if (!is_string($key) || !preg_match('/^[A-Za-z0-9_-]{4,16}:[A-Za-z0-9_-]{4,16}$/D',$key) ||
            !is_array($run) || !in_array($run['state']??null,['running','finished'],true) ||
            !is_int($run['at']??null) || ($run['at']??0)<1 ||
            !is_string($run['event_id']??null) || !preg_match('/^[a-f0-9]{32}$/D',$run['event_id'])) return false;
    }
    return true;
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

function apply(array $state, array $events): array {
    if (!validStore($state)) throw new \RuntimeException('invalid_store');
    $runs=$state['runs'];
    foreach ($events as $e) {
        $key=$e['session'].':'.$e['turn'];
        $type=$e['type'];
        if ($type==='UserPromptSubmit') {
            if (isset($runs[$key]) && ($e['at']<$runs[$key]['at'] ||
                $e['id']===$runs[$key]['event_id'])) continue;
            $runs[$key]=['state'=>'running','at'=>$e['at'],'event_id'=>$e['id']];
            $state['ever_seen']=true;
            continue;
        }
        $targets=[];
        if ($type==='SessionEnd' || ($type==='Stop' && $e['turn']==='unknown') ||
            ($e['turn']==='unknown' && $type!=='Stop')) {
            foreach ($runs as $candidate=>$run) {
                if (str_starts_with($candidate,$e['session'].':') && $run['state']==='running') $targets[]=$candidate;
            }
        } elseif (isset($runs[$key])) {
            $targets[]=$key;
        }
        foreach ($targets as $target) {
            if ($runs[$target]['state']!=='running' || $e['at']<$runs[$target]['at'] ||
                $e['id']===$runs[$target]['event_id']) continue;
            $runs[$target]=['state'=>in_array($type,['Stop','SessionEnd'],true)?'finished':'running',
                'at'=>$e['at'],'event_id'=>$e['id']];
        }
    }
    uasort($runs,static fn(array $a,array $b):int=>$b['at']<=>$a['at']);
    // Never evict an unfinished task and thereby fabricate an idle state.
    $active=array_filter($runs,static fn(array $run):bool=>$run['state']==='running');
    if (count($active)>128) throw new \RuntimeException('too_many_active_tasks');
    $finished=array_filter($runs,static fn(array $run):bool=>$run['state']==='finished');
    $state['runs']=$active+array_slice($finished,0,128-count($active),true);
    return $state;
}

function state(?array $data, int $now): string {
    if (!validStore($data) || !$data['ever_seen']) return 'unavailable';
    $fresh=false; $stale=false;
    foreach ($data['runs'] as $run) {
        if ($run['state']!=='running') continue;
        if ($run['at']>=($now-STALE_AFTER_SECONDS)*1000000 &&
            $run['at']<=($now+120)*1000000) $fresh=true;
        else $stale=true;
    }
    return $fresh?'running':($stale?'unavailable':'idle');
}

function readFile(string $path): ?array {
    if (!is_file($path) || is_link($path) || filesize($path)>MAX_STORE_BYTES) return null;
    $handle=@fopen($path,'rb');
    if (!$handle) return null;
    try {
        if (!flock($handle,LOCK_SH)) return null;
        $raw=stream_get_contents($handle,MAX_STORE_BYTES+1);
        if (!is_string($raw) || strlen($raw)>MAX_STORE_BYTES) return null;
        $data=json_decode($raw,true);
        return validStore($data)?$data:null;
    } finally { flock($handle,LOCK_UN); fclose($handle); }
}

function appendFile(string $path, array $events): void {
    $dir=dirname($path);
    if (!is_dir($dir) || is_link($dir) || is_link($path)) throw new \RuntimeException('private_store_unavailable');
    $umask=umask(0077);
    try { $handle=@fopen($path,'c+b'); } finally { umask($umask); }
    if (!$handle) throw new \RuntimeException('private_store_unavailable');
    try {
        if (!flock($handle,LOCK_EX) || is_link($path)) throw new \RuntimeException('private_store_unavailable');
        $raw=stream_get_contents($handle,MAX_STORE_BYTES+1);
        if (!is_string($raw) || strlen($raw)>MAX_STORE_BYTES) throw new \RuntimeException('invalid_store');
        $data=$raw===''?initial():json_decode($raw,true);
        if (!validStore($data)) throw new \RuntimeException('invalid_store');
        $next=json_encode(apply($data,$events),JSON_THROW_ON_ERROR);
        if (strlen($next)>MAX_STORE_BYTES) throw new \RuntimeException('store_full');
        rewind($handle);
        if (!ftruncate($handle,0) || fwrite($handle,$next)!==strlen($next) || !fflush($handle))
            throw new \RuntimeException('store_write_failed');
    } finally { flock($handle,LOCK_UN); fclose($handle); }
}
