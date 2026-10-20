<?php
declare(strict_types=1);
namespace Mosa2\Phase3O;
use function Mosa2\Phase2\{check,same,save};
require_once __DIR__.'/live_writer.php';

function verifySources(string $root,array $config): void {
    check(realpath($root)===$root&&!is_link($root)&&(fileperms($root)&0077)===0,'gateway_private');
    $project=dirname($root,2);
    foreach($config['hashes'] as $name=>$hash){
        check(preg_match('~\A(?:scripts|docs|tests)/[a-zA-Z0-9_./-]+\z~D',$name)===1&&!str_contains($name,'..'),'source_path');
        $file=$project.'/'.$name;
        check(is_file($file)&&!is_link($file)&&(fileperms($file)&0077)===0&&hash_file('sha256',$file)===$hash,'source_hash');
    }
    historicalState($root);
    same(\Mosa2\Phase3K\totals(\Mosa2\Phase3K\schemas($root)),
        ['tables'=>17,'columns'=>186,'primary'=>17,'unique'=>10,'secondary'=>39,'foreign_keys'=>36,'checks'=>37],'offline_schema');
}
function capabilityFingerprint(array $config): string {
    check(is_string($config['runtime_path']??null)&&$config['runtime_path']!=='','runtime_path');
    return hash('sha256',json_encode(['hashes'=>$config['hashes'],'runtime_path'=>$config['runtime_path']],JSON_THROW_ON_ERROR));
}
function requireCapability(string $root,array $config): void {
    verifySources($root,$config);
    $proof=json_decode(file_get_contents($root.'/capability.json'),true,512,JSON_THROW_ON_ERROR);
    validateCapability($proof,$config);
}
function validateCapability(array $proof,array $config): void {
    same($proof['status']??null,'RUNTIME_READY','runtime_gate');
    same($proof['context']??null,'gateway','runtime_context');
    same($proof['fingerprint']??null,capabilityFingerprint($config),'runtime_source_binding');
    same($proof['database_connections']??null,0,'capability_no_database');
    same($proof['database_writes']??null,0,'capability_no_writes');
    foreach(['four_full_golden_plans','canonical_bytes_exact','raw_dedupe_keys_exact',
        'writer_exit_zero_stderr_empty','existing_value_adapter_reached'] as $key)same($proof[$key]??null,true,'capability_evidence');
}
function gatewayCapability(string $root,array $config): array {
    verifySources($root,$config);
    check(!file_exists($root.'/capability.json')&&!file_exists($root.'/capability.started'),'probe_already_attempted');
    $lock=fopen($root.'/capability.started','x');check($lock!==false,'probe_one_shot');fclose($lock);chmod($root.'/capability.started',0600);
    $report=['status'=>'RUNTIME_GAP','context'=>'gateway','fingerprint'=>capabilityFingerprint($config),
        'database_connections'=>0,'database_writes'=>0];
    try{
        $project=dirname($root,2);
        $request=json_decode(file_get_contents($project.'/tests/fixtures/phase3o_runtime_request.json'),true,512,JSON_THROW_ON_ERROR);
        $expected=json_decode(file_get_contents($project.'/tests/fixtures/phase3o_runtime_expected.json'),true,512,JSON_THROW_ON_ERROR);
        // This is the identical executor transport used later with DB-generated routes.
        $plans=writerPlans($root,$request,$config['runtime_path']);
        same($plans,$expected,'runtime_golden');
        $report+=['four_full_golden_plans'=>true,'canonical_bytes_exact'=>true,'raw_dedupe_keys_exact'=>true,
            'writer_exit_zero_stderr_empty'=>true,'existing_value_adapter_reached'=>true];
        $report['status']='RUNTIME_READY';
    }catch(\Throwable $e){$report['failure']=\Mosa2\Phase3K\safeError($e);}
    save($root.'/capability.json',$report);return $report;
}
