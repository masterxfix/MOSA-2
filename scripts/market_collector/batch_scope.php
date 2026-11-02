<?php
declare(strict_types=1);
namespace Mosa2\MarketBatchScope;

use InvalidArgumentException;

/**
 * Prepare provider-neutral, already qualified assets for the existing MarketBatch.
 * The caller provides the current read-only MarketSelection result, DB snapshot,
 * registered provider manifest factories and the existing completePlan function.
 * No database, HTTP, filesystem, approval or scheduler capability exists here.
 */
function plan(
    array $state,
    array $selection,
    array $sourcePriority,
    array $providerFactories,
    callable $completePlan,
    bool $manual = false,
    int $maxAssets = 10
): array {
    $ensure = static function (bool $valid, string $why): void {
        if (!$valid) throw new InvalidArgumentException($why);
    };
    $ensure(($selection['status'] ?? null) === 'ok', 'selection_not_qualified');
    $ensure($maxAssets >= 1 && $maxAssets <= 10, 'batch_limit');
    $ensure(is_array($selection['assets'] ?? null) && array_is_list($selection['assets']) &&
        is_array($selection[$manual ? 'manual_candidates' : 'collector_candidates'] ?? null) &&
        array_is_list($selection[$manual ? 'manual_candidates' : 'collector_candidates']),
        'selection_shape');
    $ensure(array_is_list($sourcePriority) && $sourcePriority !== [], 'source_priority');
    $priority = [];
    foreach ($sourcePriority as $index => $key) {
        $ensure(is_string($key) && preg_match('/\Aprovider:[a-z0-9_]+\z/D', $key) === 1 &&
            !isset($priority[$key]) && isset($providerFactories[$key]) && is_callable($providerFactories[$key]),
            'source_priority');
        $priority[$key] = $index;
    }
    $assets = [];
    $isinOwners = [];
    foreach ($selection['assets'] as $asset) {
        $id = $asset['asset_id'] ?? null;
        $ensure(is_string($id) && preg_match('/\A[1-9][0-9]*\z/D', $id) === 1 &&
            !isset($assets[$id]), 'selection_asset');
        $isin = $asset['isin'] ?? null;
        if (($asset['identity_status'] ?? null) === 'VALID') {
            $ensure(is_string($isin) && preg_match('/\A[A-Z]{2}[A-Z0-9]{9}[0-9]\z/D', $isin) === 1 &&
                !isset($isinOwners[$isin]), 'selection_isin');
            $isinOwners[$isin] = true;
        }
        $assets[$id] = $asset;
    }
    $candidates = [];
    $requested = $selection[$manual ? 'manual_candidates' : 'collector_candidates'];
    foreach ($requested as $candidate) {
        $id = $candidate['asset_id'] ?? null;
        $source = $candidate['source_key'] ?? null;
        $route = $candidate['route_id'] ?? null;
        $ensure(is_string($id) && isset($assets[$id]) && is_string($source) &&
            is_string($route) && preg_match('/\A[1-9][0-9]*\z/D', $route) === 1,
            'candidate_identity');
        $asset = $assets[$id];
        $ensure(($asset['identity_status'] ?? null) === 'VALID' &&
            ($candidate['isin'] ?? null) === ($asset['isin'] ?? null) &&
            ($candidate['name'] ?? null) === ($asset['name'] ?? null), 'candidate_binding');
        $ensure(!isset($candidates[$id][$source]), 'candidate_ambiguous');
        $candidates[$id][$source] = $candidate;
    }
    $ready = [];
    $unavailable = [];
    $usedPhysicalRoutes = [];
    foreach ($assets as $asset) {
        $id = $asset['asset_id'];
        $status = $manual ? 'MANUAL_ROUTE_PREPARABLE' : 'READY';
        $actual = $manual ? ($asset['manual_status'] ?? null) : ($asset['collector_status'] ?? null);
        $eligible = $actual === $status && ($asset['identity_status'] ?? null) === 'VALID';
        $ranked = [];
        if ($eligible) foreach ($candidates[$id] ?? [] as $source => $candidate) {
            if (isset($priority[$source])) $ranked[$priority[$source]] = $candidate;
        }
        if ($ranked === []) {
            $unavailable[] = ['asset_id' => $id, 'isin' => $asset['isin'] ?? null,
                'reason' => $eligible ? 'NO_REGISTERED_SOURCE' : 'NOT_QUALIFIED'];
            continue;
        }
        ksort($ranked, SORT_NUMERIC);
        $candidate = reset($ranked);
        $ensure(!isset($usedPhysicalRoutes[$candidate['route_id']]), 'physical_route_ambiguous');
        $usedPhysicalRoutes[$candidate['route_id']] = true;
        $source = $candidate['source_key'];
        $manifest = $providerFactories[$source]($state,
            ['isin' => $candidate['isin'], 'name' => $candidate['name']]);
        $ensure(is_array($manifest) && ($manifest['policy'] ?? null) === 'USE_EXISTING_ROUTE' &&
            ($manifest['identity']['normalized_value'] ?? null) === $candidate['isin'],
            'manifest_binding');
        $decided = $completePlan($state, $manifest);
        $ensure(is_array($decided) && ($decided['route']['decision'] ?? null) === 'EXISTING_MATCH' &&
            ($decided['route']['route_id'] ?? null) === $candidate['route_id'] &&
            ($decided['source']['source_id'] ?? null) === $candidate['source_id'] &&
            ($decided['asset']['asset_id'] ?? null) === $candidate['asset_id'],
            'physical_route_binding');
        $ready[] = ['asset_id' => $id, 'isin' => $candidate['isin'], 'source_key' => $source,
            'route_id' => $candidate['route_id'], 'manifest' => $manifest];
        $ensure(count($ready) <= $maxAssets, 'batch_limit');
    }
    return ['mode' => $manual ? 'manual' : 'automatic', 'prepared' => $ready,
        'unavailable' => $unavailable, 'execution_authorized' => false,
        'provider_requests' => 0, 'database_writes' => 0];
}
