<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/api/codex_status_model.php';

use function Mosa2\CodexStatus\initial;
use function Mosa2\CodexStatus\event;
use function Mosa2\CodexStatus\normalizeStore;
use function Mosa2\CodexStatus\state;
use function Mosa2\CodexStatus\appendFile;
use function Mosa2\CodexStatus\sourcePresence;
use function Mosa2\CodexStatus\readFile;

$now=(new DateTimeImmutable('2026-11-08T14:00:00Z'))->getTimestamp();
$count=0;
$check=static function(bool $ok,string $reason)use(&$count):void{
    $count++;
    if (!$ok) throw new RuntimeException($reason);
};
$event=static function(string $type,string $session,string $turn,int $diff,int $serial,string $surface='codex_cli')use($now):array{
    return ['contract_version'=>'mosa_ai_control_telemetry_v1','surface'=>$surface,
        'event_type'=>$type,'session_id_short'=>$session,'turn_id_short'=>$turn,
        'event_id'=>str_pad(dechex($serial),32,'0',STR_PAD_LEFT),
        'recorded_at_utc'=>gmdate('Y-m-d\TH:i:s\Z',$now+$diff)];
};
$check(state(initial(),$now)==='unavailable','empty must be unavailable');
$check(event($event('UserPromptSubmit','abcd1234','turn1234',0,1,'work_desktop'),$now)===null,'WORK must not activate Codex');
$check(event($event('UserPromptSubmit','unknown','turn1234',0,2),$now)===null,'unknown session must not activate Codex');
$check(event($event('SessionStart','abcd1234','turn1234',0,3),$now)===null,'session start is not a task start');
$start=event($event('UserPromptSubmit','abcd1234','turn1234',0,4),$now);
$check($start!==null,'native start accepted');
$sourceEnvelope=static fn(string $state,int $at):array=>[
    'contract_version'=>'mosa2_mosa_presence_v1','state'=>$state,
    'observed_at_utc'=>gmdate('Y-m-d\TH:i:s\Z',$at)
];
$check(sourcePresence($sourceEnvelope('running',$now),$now)===['state'=>'running','at'=>$now],
    'canonical MOSA presence accepted');
$check(sourcePresence($sourceEnvelope('idle',$now-601),$now)===null,
    'expired canonical snapshot rejected');
$check(sourcePresence($sourceEnvelope('idle',$now+121),$now)===null,
    'future snapshot rejected');
$check(sourcePresence($sourceEnvelope('fake',$now),$now)===null,
    'invalid source state rejected');
$legacy=['version'=>\Mosa2\CodexStatus\VERSION,'ever_seen'=>true,'runs'=>[
    'abcd1234:turn1234'=>['state'=>'running','at'=>$start['at'],'event_id'=>$start['id']]
]];
$check(state(normalizeStore($legacy),$now)==='unavailable','legacy runs without a MOSA snapshot are unknown');
$legacy['presence']=sourcePresence($sourceEnvelope('idle',$now),$now);
$check(state(normalizeStore($legacy),$now)==='idle','existing MOSA snapshot takes precedence over legacy runs');
$subsecond=$event('UserPromptSubmit','subsecond','turn9876',0,16);
$subsecond['recorded_at_utc']=gmdate('Y-m-d\TH:i:s',$now).'.800Z';
$parsedSubsecond=event($subsecond,$now);
$check($parsedSubsecond!==null,'native fractional timestamp accepted');

$temp=sys_get_temp_dir().'/mosa2-codex-fixture-'.bin2hex(random_bytes(5));
mkdir($temp,0700);
try {
    $path=$temp.'/status.json';
    $check(readFile($path)===null,'missing store is unavailable');
    file_put_contents($path,json_encode($legacy,JSON_THROW_ON_ERROR));
    chmod($path,0600);
    $check(state(readFile($path),$now)==='idle','existing file is readable');
    appendFile($path,$parsedSubsecond['at'],null);
    $check(state(readFile($path),$now)==='unavailable','newer event in the same second without a snapshot is unknown');
    $running=sourcePresence($sourceEnvelope('running',$now),$now)+['event_at'=>$parsedSubsecond['at']];
    appendFile($path,$parsedSubsecond['at'],$running);
    $check(state(readFile($path),$now)==='running','same-second MOSA source snapshot covers fractional event');
    $check(state(readFile($path),$now+181)==='unavailable','stale MOSA evidence expires');
    $next=($now+1)*1000000;
    $unknown=sourcePresence($sourceEnvelope('unavailable',$now+1),$now)+['event_at'=>$next];
    appendFile($path,$next,$unknown);
    appendFile($path,$parsedSubsecond['at'],$running);
    $check(state(readFile($path),$now+1)==='unavailable','older retry cannot replace current unknown state');
    $idle=sourcePresence($sourceEnvelope('idle',$now+2),$now)+['event_at'=>$next+1000000];
    appendFile($path,$next+1000000,$idle);
    $check(state(readFile($path),$now+2)==='idle','fresh MOSA idle is persisted');
    $check(!array_key_exists('runs',json_decode(file_get_contents($path),true)), 'legacy run identifiers are not retained');
    if (DIRECTORY_SEPARATOR !== '\\') {
        $check((fileperms($path)&0077)===0,'private store permissions');
    }
} finally {
    @unlink($temp.'/status.json');
    @rmdir($temp);
}
echo "Codex status: {$count} checks OK\n";
