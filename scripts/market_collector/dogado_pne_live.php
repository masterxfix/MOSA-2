<?php
declare(strict_types=1);
namespace Mosa2\DogadoPne;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,qi,connection};
use function Mosa2\MarketLive\{runtimeContract,runtimeState,snapshot,completePlan,compareDelta};
const RELEASE='@RELEASE@';
const RUN='@RUN@';
const ISIN='DE000A0JBPG2';
const PHP='/opt/plesk/php/8.4/bin/php';
const PYTHON='/opt/alt/python311/bin/python3.11';
require_once RELEASE.'/scripts/market_collector/live_batch.php';
require_once RELEASE.'/scripts/collector_release/runtime.php';

// Preserve the historical PNE interface; all runtime behavior lives in the shared library.
function safeFailureCode(string $code): string {return \Mosa2\DogadoRuntime\safeFailureCode($code);}
function outcome(array $r,int $checkpoint): string {return \Mosa2\DogadoRuntime\outcome($r,$checkpoint);}
function delta(array $before,array $after,array $scope): array {return \Mosa2\DogadoRuntime\delta($before,$after,$scope);}
function perform(string $password,array $input): array {
    $r=\Mosa2\DogadoRuntime\perform($password,$input,['release'=>RELEASE,'run'=>RUN,'isin'=>ISIN,'name'=>'PNE AG']);
    if(isset($r['baseline']['asset_observation_ids']))$r['baseline']['pne_observation_ids']=$r['baseline']['asset_observation_ids'];
    return $r;
}
function main(): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{
        $input=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
        check(is_string($input['password']??null)&&$input['password']!=='','db_secret_required');
        $r=perform($input['password'],$input);unset($input);
        echo json_encode($r,JSON_THROW_ON_ERROR);
    }catch(Throwable $e){echo json_encode(['ok'=>false,'status'=>'FAILED','stage'=>'initialization','failure_code'=>safeFailureCode($e->getMessage()),'failure_phase'=>'initialization'],JSON_THROW_ON_ERROR);}
}
