<?php
declare(strict_types=1);
namespace Mosa2\CollectorSchema5;
use function Mosa2\Phase2\{check,same};
const DIGEST='2521552c548370806bc311798f12be39f16b102733aeb74ac9c01337e7e46333';
const TABLES=['m2_collector_state','m2_collector_cycles','m2_collector_days','m2_collector_requests'];
/** Version is explicit; historical callers keep their exact old table/ledger sets. */
function envelope(int $version): array {
    check(in_array($version,[3,4,5],true),'schema_contract');
    $tables=array_merge(\Mosa2\Phase2\TABLES,\Mosa2\Phase3B\MARKET,['m2_units'],$version===5?TABLES:[]);sort($tables);
    $digests=[\Mosa2\Phase2\DIGEST,\Mosa2\Phase3B\DIGEST,\Mosa2\Phase3K\DIGEST];
    if($version>=4)$digests[]=hash_file('sha256',dirname(__DIR__,2).'/docs/database/migrations/0004_current_observation_provenance.sql');
    if($version===5){same(hash_file('sha256',dirname(__DIR__,2).'/docs/database/migrations/0005_collector_reservations.sql'),DIGEST,'schema5_artifact');$digests[]=DIGEST;}
    return ['tables'=>$tables,'versions'=>array_map('strval',range(1,$version)),'digests'=>$digests];
}
