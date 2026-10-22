<?php
declare(strict_types=1);
namespace Mosa2\CollectorSchema5;
use function Mosa2\Phase2\{check,same};
const DIGEST='2521552c548370806bc311798f12be39f16b102733aeb74ac9c01337e7e46333';
const TABLES=['m2_collector_state','m2_collector_cycles','m2_collector_days','m2_collector_requests'];
/** No schema discovery: configuration is explicit and type-strict. */
function selected(array $config,int $default=4): array {
    $contract=array_key_exists('state_contract',$config)?$config['state_contract']:['schema_version'=>$default];
    if(!is_array($contract)||!is_int($contract['schema_version']??null)
        ||!in_array($contract['schema_version'],[4,5],true))throw new \RuntimeException('schema_contract');
    return $contract;
}
/** Initial migration5 anchors are compatibility evidence, never an operating grant. */
function locked(array $jobs,array $modules,array $state,array $activity): void {
    same(count($jobs),1,'schema5_job');same(count($modules),1,'schema5_module');same(count($state),1,'schema5_state');
    $job=$jobs[0];$module=$modules[0];
    foreach(['job_key'=>'collector_reservations_v1','module_key'=>'collector_reservations','handler_key'=>'UNWIRED','enabled'=>'0'] as $k=>$v)same($job[$k]??null,$v,'schema5_job');
    foreach(['module_key'=>'collector_reservations','schema_version'=>'5','status'=>'LOCKED'] as $k=>$v)same($module[$k]??null,$v,'schema5_module');
    $expected=['provider'=>'boerse_frankfurt_api_v1','job_id'=>$job['id'],'status'=>'IDLE','stop_latched'=>'1','unresolved'=>'0',
        'active_cycle'=>null,'last_confirmed_cycle'=>null,'pending_asset'=>null,'operation_token'=>null,'last_observed_utc'=>null,'error_code'=>'INITIAL_LOCK'];
    $row=$state[0];ksort($row);ksort($expected);same($row,$expected,'schema5_state');
    foreach($activity as $rows)same($rows,[],'schema5_activity');
}
/** Bounded reads only, also used by Current. A locked anchor does not start a collector. */
function lockedDatabase(\PDO $p): void {
    $read=static function(string $sql)use($p):array{return array_map('Mosa2\\MarketLive\\strings',$p->query($sql)->fetchAll(\PDO::FETCH_ASSOC));};
    locked($read("SELECT * FROM m2_jobs WHERE job_key='collector_reservations_v1' OR module_key='collector_reservations' LIMIT 3"),
        $read("SELECT * FROM m2_module_state WHERE module_key='collector_reservations' LIMIT 2"),
        $read('SELECT * FROM m2_collector_state LIMIT 2'),
        array_map(static fn($t)=>$read('SELECT * FROM '.$t.' LIMIT 1'),array_slice(TABLES,1)));
}
function ledger5(array $ledger): void {
    same(array_column($ledger,'migration_key'),['0001_core_asset_identity','0002_market_current_history','0003_market_units',
        '0004_current_observation_provenance','0005_collector_reservations'],'schema5_ledger_keys');
}
function acquisitionAllowed(array $contract): void {
    check(($contract['schema_version']??4)!==5,'schema5_collector_locked');
}
/** Version is explicit; historical callers keep their exact old table/ledger sets. */
function envelope(int $version): array {
    check(in_array($version,[3,4,5],true),'schema_contract');
    $tables=array_merge(\Mosa2\Phase2\TABLES,\Mosa2\Phase3B\MARKET,['m2_units'],$version===5?TABLES:[]);sort($tables);
    $digests=[\Mosa2\Phase2\DIGEST,\Mosa2\Phase3B\DIGEST,\Mosa2\Phase3K\DIGEST];
    if($version>=4)$digests[]=hash_file('sha256',dirname(__DIR__,2).'/docs/database/migrations/0004_current_observation_provenance.sql');
    if($version===5){same(hash_file('sha256',dirname(__DIR__,2).'/docs/database/migrations/0005_collector_reservations.sql'),DIGEST,'schema5_artifact');$digests[]=DIGEST;}
    return ['tables'=>$tables,'versions'=>array_map('strval',range(1,$version)),'digests'=>$digests];
}
