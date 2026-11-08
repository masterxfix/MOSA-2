<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/api/codex_status_model.php';

use function Mosa2\CodexStatus\initial;
use function Mosa2\CodexStatus\event;
use function Mosa2\CodexStatus\apply;
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
$s=initial();
$check(state($s,$now)==='unavailable','empty must be unavailable');
$check(event($event('UserPromptSubmit','abcd1234','turn1234',0,1,'work_desktop'),$now)===null,'WORK must not activate Codex');
$check(event($event('UserPromptSubmit','unknown','turn1234',0,2),$now)===null,'unknown session must not activate Codex');
$check(event($event('SessionStart','abcd1234','turn1234',0,3),$now)===null,'session start is not a task start');
$start=event($event('UserPromptSubmit','abcd1234','turn1234',0,4),$now);
$check($start!==null,'native start accepted');
$s=apply($s,[$start]);
$check(state($s,$now)==='running','native prompt is running');
$check(state($s,$now+181)==='unavailable','silent task must not be reported idle');
$heartbeat=event($event('PostToolUse','abcd1234','turn1234',20,5),$now+20);
$s=apply($s,[$heartbeat]);
$check(state($s,$now+190)==='running','fresh tool event keeps task live');
$stop=event($event('Stop','abcd1234','turn1234',21,6),$now+21);
$s=apply($s,[$stop]);
$check(state($s,$now+21)==='idle','native stop ends task');
$s=apply($s,[$start]);
$check(state($s,$now+21)==='idle','replayed earlier start cannot reopen finished task');
$s=apply($s,[event($event('UserPromptSubmit','abcd1234','next1234',22,7),$now+22),
    event($event('UserPromptSubmit','efgh5678','turn5678',23,8),$now+23)]);
$check(state($s,$now+23)==='running','parallel tasks tracked');
$s=apply($s,[event($event('Stop','abcd1234','next1234',24,9),$now+24)]);
$check(state($s,$now+24)==='running','one Stop leaves second task running');
$s=apply($s,[event($event('SessionEnd','efgh5678','unknown',25,10),$now+25)]);
$check(state($s,$now+25)==='idle','session end finishes remaining task');
$s=apply($s,[event($event('UserPromptSubmit','abcd1234','third123',26,11),$now+26)]);
$s=apply($s,[event($event('Stop','abcd1234','unknown',27,12),$now+27)]);
$check(state($s,$now+27)==='idle','unknown turn on native Stop closes session');
$s=apply($s,[event($event('UserPromptSubmit','abcd1234','start567',28,13),$now+28)]);
$s=apply($s,[event($event('Stop','abcd1234','newturn1',29,14),$now+29)]);
$check(state($s,$now+29)==='idle','native Stop with a new processing turn closes session');
// The existing MOSA source may provide its own reduced three-state value.
// It is authoritative when newer than or equal to the last native event.
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
$sourceRun=apply(initial(),[$start]);
$sourceRun['presence']=sourcePresence($sourceEnvelope('idle',$now),$now);
$check(state($sourceRun,$now)==='idle','MOSA source state overrides local active reducer');
$check(state($sourceRun,$now+181)==='unavailable','stale source is not presented as idle');
$eventAfter=event($event('UserPromptSubmit','newabc12','newturn1',35,15),$now+35);
$sourceRun=apply($sourceRun,[$eventAfter]);
$check(state($sourceRun,$now+35)==='running','new native event can recover from stale source snapshot');

$temp=sys_get_temp_dir().'/mosa2-codex-fixture-'.bin2hex(random_bytes(5));
mkdir($temp,0700);
try {
    $path=$temp.'/status.json';
    $check(readFile($path)===null,'missing store is unavailable');
    appendFile($path,[$start]);
    $check(state(readFile($path),$now)==='running','private store roundtrip');
    appendFile($path,[],sourcePresence($sourceEnvelope('idle',$now),$now));
    $check(state(readFile($path),$now)==='idle','MOSA source snapshot persisted in existing private store');
    if (DIRECTORY_SEPARATOR !== '\\') {
        $check((fileperms($path)&0077)===0,'private store permissions');
    }
} finally {
    @unlink($temp.'/status.json');
    @rmdir($temp);
}
echo "Codex status: {$count} checks OK\n";
