<?php
declare(strict_types=1);
namespace Mosa2\Phase3O;

// Private CLI preflight, no HTTP entry, credentials, DB library or SQL executor.
// PATH selects the already running PHP CLI for the unchanged Python adapter.
function runtimeProbe(string $project): array {
    $request=file_get_contents($project.'/tests/fixtures/phase3o_runtime_request.json');
    $process=proc_open(['python3',$project.'/scripts/phase3o/live_plan.py'],
        [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes,$project,
        ['PATH'=>dirname(PHP_BINARY).PATH_SEPARATOR.getenv('PATH'),'PYTHONDONTWRITEBYTECODE'=>'1']);
    if(!is_resource($process))throw new \RuntimeException('python_process');
    if(fwrite($pipes[0],$request)!==strlen($request))throw new \RuntimeException('stdin_transport');
    fclose($pipes[0]);$out=stream_get_contents($pipes[1]);$error=stream_get_contents($pipes[2]);
    fclose($pipes[1]);fclose($pipes[2]);$code=proc_close($process);
    $response=json_decode($out,true);
    $ok=$code===0&&$error===''&&is_array($response)&&($response['ok']??false)===true;
    if($ok){
        $expected=json_decode(file_get_contents($project.'/tests/fixtures/phase3o_runtime_expected.json'),true,512,JSON_THROW_ON_ERROR);
        $ok=($response['plans']??null)===$expected;
    }
    return ['status'=>$ok?'RUNTIME_READY':'RUNTIME_GAP','writer_response'=>$response,
        'process_exit'=>$code,'stderr_empty'=>$error==='','stderr'=>$error,'database_connections'=>0,
        'database_writes'=>0,'public_gateway_created'=>false];
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    umask(0077);$project=dirname(__DIR__,2);
    if(is_link($project)||(fileperms($project)&0077)!==0)throw new \RuntimeException('private_project');
    $file=__DIR__.'/runtime-report.json';
    if(file_exists($file))throw new \RuntimeException('probe_already_attempted');
    $report=runtimeProbe($project);
    if(file_put_contents($file,json_encode($report,JSON_THROW_ON_ERROR))===false||!chmod($file,0600))throw new \RuntimeException('private_report');
    echo json_encode(['phase3o_runtime'=>$report['status'],'database_connections'=>0,'database_writes'=>0,
        'public_gateway_created'=>false,'writer_failure'=>$report['writer_response']['failure']??null,
        'exception'=>$report['writer_response']['exception']??null,
        'reason'=>$report['writer_response']['reason']??null,'stderr_empty'=>$report['stderr_empty']],JSON_THROW_ON_ERROR);
}
