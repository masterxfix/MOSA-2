<?php
declare(strict_types=1);
namespace Mosa2\MarketPerformanceReference;
use PDO;
/** Previous four-statement metadata reader. Comparison only, never a runtime fallback. */
function metadata(PDO $p): array {
    $out=['tables'=>\Mosa2\Phase2\tables($p),'indexes'=>[]];
    foreach(['m2_asset_source_routes','m2_market_observations','m2_asset_identifiers'] as $table)
        $out['indexes'][$table]=$p->query('SHOW INDEX FROM '.\Mosa2\Phase2\qi($table))->fetchAll();
    return $out;
}
function state(PDO $p,array $manifest,array $contract): array {
    return \Mosa2\MarketLive\runtimeState($p,$manifest,$contract,__NAMESPACE__.'\\metadata');
}
