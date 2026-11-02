<?php
namespace Mosa2\MarketSelection;

const MAX_ASSETS = 1000;
const SUPPORTED_CURRENCIES = ['EUR', 'GBP', 'GBX'];

function fail(string $reason): void { throw new \InvalidArgumentException($reason); }
function requireValue(bool $ok, string $reason): void { if (!$ok) fail($reason); }
function text(array $row, string $key): ?string {
    if (!array_key_exists($key, $row) || $row[$key] === null) return null;
    return (string)$row[$key];
}
function positiveId(mixed $value): bool { return is_string($value) && preg_match('/^[1-9][0-9]*$/D', $value) === 1; }
function truthy(mixed $value, string $expected = '1'): bool { return (string)$value === $expected; }
function validIsin(?string $value): bool { return $value !== null && preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D', $value) === 1; }
function validUtc(?string $value): bool {
    if ($value === null || preg_match('/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}$/D', $value) !== 1) return false;
    $date = \DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u', $value, new \DateTimeZone('UTC'));
    return $date !== false && $date->format('Y-m-d H:i:s.u') === $value;
}
function dateValue(string $value): \DateTimeImmutable {
    requireValue(validUtc($value), 'selection_timestamp');
    return \DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u', $value, new \DateTimeZone('UTC'));
}
function listInput(mixed $value, string $reason): array {
    requireValue(is_array($value) && array_is_list($value), $reason);
    return $value;
}
function routeKey(array $route): string {
    return implode(':', [(string)($route['asset_id'] ?? ''), (string)($route['source_id'] ?? ''),
        (string)($route['id'] ?? $route['route_id'] ?? '')]);
}
function routeReason(array $route, string $assetId): ?string {
    if ((string)($route['asset_id'] ?? '') !== $assetId) return 'ROUTE_ASSET_MISMATCH';
    if (!positiveId(text($route, 'id') ?? text($route, 'route_id'))) return 'ROUTE_ID_INVALID';
    if (!positiveId(text($route, 'source_id')) || !positiveId(text($route, 'route_revision'))) return 'ROUTE_IDENTITY_INVALID';
    if (text($route, 'route_type') !== 'quote') return 'ROUTE_TYPE_UNSUPPORTED';
    if ((string)($route['priority'] ?? '') !== '0') return 'ROUTE_PRIORITY_UNSUPPORTED';
    if (!truthy($route['enabled'])) return 'ROUTE_DISABLED';
    if (text($route, 'source_key') === null || preg_match('/^provider:[a-z0-9_]+$/D', text($route, 'source_key')) !== 1) return 'SOURCE_IDENTITY_INVALID';
    if (text($route, 'source_type') !== 'market_data' || !truthy($route['source_enabled'])) return 'SOURCE_NOT_ENABLED_MARKET_DATA';
    if (text($route, 'unit_contract_version') !== 'mosa2-market-unit-v1' || text($route, 'unit_status') !== 'frozen') return 'UNIT_NOT_QUALIFIED';
    $currency = text($route, 'unit_currency') ?? text($route, 'monetary_currency_code');
    if (!in_array($currency, SUPPORTED_CURRENCIES, true)) return 'CURRENCY_NOT_QUALIFIED';
    if (!in_array(text($route, 'quote_unit_key'), SUPPORTED_CURRENCIES, true) || text($route, 'quote_unit_version') === null) return 'QUOTE_UNIT_NOT_QUALIFIED';
    if (!preg_match('/^market-v1:[a-f0-9]{64}$/D', text($route, 'external_key') ?? '')) return 'ROUTE_EXTERNAL_ID_INVALID';
    return null;
}
function routeView(array $route, string $assetId): array {
    $reason = routeReason($route, $assetId);
    $currency = text($route, 'unit_currency') ?? text($route, 'monetary_currency_code');
    return [
        'route_id' => text($route, 'id') ?? text($route, 'route_id'),
        'asset_id' => text($route, 'asset_id'),
        'source_id' => text($route, 'source_id'),
        'source_key' => text($route, 'source_key'),
        'source_name' => text($route, 'source_name'),
        'source_type' => text($route, 'source_type'),
        'source_enabled' => text($route, 'source_enabled'),
        'route_revision' => text($route, 'route_revision'),
        'route_type' => text($route, 'route_type'),
        'priority' => text($route, 'priority'),
        'enabled' => text($route, 'enabled'),
        'external_key' => text($route, 'external_key'),
        'quote_unit_key' => text($route, 'quote_unit_key'),
        'quote_unit_version' => text($route, 'quote_unit_version'),
        'currency' => $currency,
        'unit_status' => text($route, 'unit_status'),
        'qualification' => $reason === null ? 'QUALIFIED' : 'NOT_QUALIFIED',
        'reason' => $reason,
    ];
}
function routeDecision(array $rows, string $assetId): array {
    if ($rows === []) return ['status' => 'NO_QUALIFIED_ROUTE', 'reason' => 'NO_ROUTE', 'route' => null, 'routes' => []];
    $views = array_map(static fn(array $row): array => routeView($row, $assetId), $rows);
    $bySource = [];
    foreach ($rows as $row) $bySource[(string)($row['source_id'] ?? '')][] = $row;
    $latest = [];
    foreach ($bySource as $sourceRows) {
        $max = max(array_map(static fn(array $row): int => (int)($row['route_revision'] ?? 0), $sourceRows));
        $top = array_values(array_filter($sourceRows, static fn(array $row): bool => (int)($row['route_revision'] ?? 0) === $max));
        if (count($top) !== 1) return ['status' => 'AMBIGUOUS_ROUTE', 'reason' => 'SAME_REVISION_MULTIPLE_ROUTES', 'route' => null, 'routes' => $views];
        $latest[] = $top[0];
    }
    $qualified = array_values(array_filter($latest, static fn(array $row): bool => routeReason($row, $assetId) === null));
    if (count($qualified) === 1) return ['status' => 'QUALIFIED', 'reason' => null, 'route' => routeView($qualified[0], $assetId), 'routes' => $views];
    if (count($qualified) > 1) return ['status' => 'AMBIGUOUS_ROUTE', 'reason' => 'MULTIPLE_QUALIFIED_SOURCES', 'route' => null, 'routes' => $views];
    $reasons = array_values(array_unique(array_map(static fn(array $row): string => routeReason($row, $assetId) ?? 'ROUTE_NOT_QUALIFIED', $latest)));
    return ['status' => 'NO_QUALIFIED_ROUTE', 'reason' => count($reasons) === 1 ? $reasons[0] : 'ROUTE_NOT_QUALIFIED', 'route' => null, 'routes' => $views];
}
function currentDecision(?array $current, array $observations, array $routeRows, string $assetId, string $now, int $staleSeconds): array {
    if ($current === null) return ['status' => 'NO_CURRENT', 'current' => null];
    $observationId = text($current, 'observation_id');
    $origin = $observationId === null ? null : ($observations[$observationId] ?? null);
    $routeMap = [];
    foreach ($routeRows as $row) $routeMap[routeKey($row)] = $row;
    $route = $routeMap[implode(':', [$assetId, text($current, 'source_id') ?? '', text($current, 'route_id') ?? ''])] ?? null;
    $invalid = $origin === null || text($current, 'asset_id') !== $assetId
        || text($current, 'source_id') !== text($origin, 'source_id') || text($current, 'route_id') !== text($origin, 'route_id')
        || text($origin, 'asset_id') !== $assetId || text($origin, 'observation_format_version') !== '2'
        || text($current, 'observation_format_version') !== '2' || !validUtc(text($origin, 'market_at'))
        || !validUtc(text($origin, 'observed_at')) || !validUtc(text($current, 'market_at'))
        || !validUtc(text($current, 'observed_at')) || text($current, 'market_at') !== text($origin, 'market_at')
        || text($current, 'observed_at') !== text($origin, 'observed_at')
        || (text($current, 'price') !== null && text($origin, 'price') !== null && text($current, 'price') !== text($origin, 'price'))
        || (text($current, 'currency') !== null && text($origin, 'currency') !== null && text($current, 'currency') !== text($origin, 'currency'))
        || (text($current, 'price') !== null && (float)text($current, 'price') <= 0)
        || ($route !== null && text($current, 'route_revision') !== text($route, 'route_revision'));
    if ($invalid) return ['status' => 'CURRENT_INVALID', 'current' => null];
    $nowDate = dateValue($now);$market = dateValue(text($origin, 'market_at'));$observed = dateValue(text($origin, 'observed_at'));
    if ($market > $observed || $observed > $nowDate) return ['status' => 'CURRENT_INVALID', 'current' => null];
    $age = max(0, $nowDate->getTimestamp() - $market->getTimestamp());
    $view = ['observation_id'=>$observationId,'source_id'=>text($current,'source_id'),'route_id'=>text($current,'route_id'),
        'route_revision'=>text($current,'route_revision'),'market_at'=>text($origin,'market_at'),'observed_at'=>text($origin,'observed_at'),
        'price'=>text($origin,'price'),'currency'=>text($origin,'currency'),'age_seconds'=>$age];
    return ['status' => $age > $staleSeconds ? 'CURRENT_STALE' : 'CURRENT_VALID', 'current' => $view];
}
function select(array $assets, array $identifiers, array $routes, array $currents, array $observations, string $now, int $staleSeconds = 1800, int $maxAssets = MAX_ASSETS): array {
    listInput($assets, 'asset_rows');listInput($identifiers, 'identifier_rows');listInput($routes, 'route_rows');listInput($currents, 'current_rows');listInput($observations, 'observation_rows');
    requireValue(validUtc($now) && $staleSeconds >= 60 && $staleSeconds <= 86400 && $maxAssets >= 1, 'selection_parameters');
    $active = [];$seenAssets = [];
    foreach ($assets as $asset) {
        requireValue(is_array($asset), 'asset_row');$id = text($asset, 'asset_id') ?? text($asset, 'entity_id');
        if (!positiveId($id) || !in_array(text($asset, 'asset_class'), ['equity', 'etf'], true) || text($asset, 'status') !== 'active') continue;
        requireValue(!isset($seenAssets[$id]), 'duplicate_asset');$seenAssets[$id] = true;$asset['asset_id'] = $id;$active[] = $asset;
    }
    requireValue(count($active) <= $maxAssets, 'selection_scope_overflow');
    $equities = array_values(array_filter($active, static fn(array $row): bool => text($row, 'asset_class') === 'equity'));
    $etfs = count($active) - count($equities);$idsByAsset = [];$isinOwners = [];
    foreach ($identifiers as $identifier) {
        if (!is_array($identifier) || text($identifier, 'identifier_type') !== 'isin' || text($identifier, 'scope_key') !== '' || text($identifier, 'valid_to') !== null || !truthy($identifier['is_primary'] ?? null)) continue;
        $assetId = text($identifier, 'asset_id');$isin = text($identifier, 'normalized_value');
        if ($assetId === null || !isset($seenAssets[$assetId])) continue;
        $idsByAsset[$assetId][] = $identifier;if (validIsin($isin)) $isinOwners[$isin][] = $assetId;
    }
    $routesByAsset = [];
    foreach ($routes as $route) if (is_array($route) && isset($seenAssets[(string)($route['asset_id'] ?? '')])) $routesByAsset[(string)$route['asset_id']][] = $route;
    $observationsById = [];
    foreach ($observations as $observation) if (is_array($observation) && text($observation, 'id') !== null) $observationsById[text($observation, 'id')] = $observation;
    $currentByAsset = [];
    foreach ($currents as $current) if (is_array($current) && isset($seenAssets[(string)($current['asset_id'] ?? '')])) $currentByAsset[(string)$current['asset_id']][] = $current;
    $items = [];$candidates=[];$sourceMap=[];$counts=['active_equities'=>count($equities),'active_etfs_excluded'=>$etfs,'current_present'=>0,'current_valid'=>0,'current_stale'=>0,'current_missing'=>0,'current_invalid'=>0,'qualified_for_collector'=>0,'without_usable_route'=>0];
    foreach ($equities as $asset) {
        $assetId=$asset['asset_id'];$rows=$idsByAsset[$assetId]??[];$isin=(count($rows)===1)?text($rows[0],'normalized_value'):null;
        $identityStatus=count($rows)!==1||!validIsin($isin)?'INVALID_OR_AMBIGUOUS_ISIN':(count($isinOwners[$isin]??[])!==1?'DUPLICATE_ISIN':'VALID');
        $route=routeDecision($routesByAsset[$assetId]??[],$assetId);$currentRows=$currentByAsset[$assetId]??[];
        $current=count($currentRows)===1?$currentRows[0]:null;$currentResult=count($currentRows)>1?['status'=>'CURRENT_INVALID','current'=>null]:currentDecision($current,$observationsById,$routesByAsset[$assetId]??[],$assetId,$now,$staleSeconds);
        $collectorStatus=$identityStatus!=='VALID'?'INVALID_IDENTITY':($route['status']==='QUALIFIED'?'READY':'ROUTE_UNAVAILABLE');
        if ($current!==null)$counts['current_present']++;$key=$currentResult['status'];if($key==='CURRENT_VALID')$counts['current_valid']++;elseif($key==='CURRENT_STALE')$counts['current_stale']++;elseif($key==='NO_CURRENT')$counts['current_missing']++;else $counts['current_invalid']++;
        if($collectorStatus==='READY'){$counts['qualified_for_collector']++;$candidates[]=['asset_id'=>$assetId,'name'=>text($asset,'display_name'),'isin'=>$isin,'source_id'=>$route['route']['source_id'],'source_key'=>$route['route']['source_key'],'route_id'=>$route['route']['route_id'],'route_revision'=>$route['route']['route_revision'],'quote_unit_key'=>$route['route']['quote_unit_key'],'currency'=>$route['route']['currency']];}
        else $counts['without_usable_route']++;
        foreach($route['routes'] as $routeView){$sourceId=$routeView['source_id'];if($sourceId!==null)$sourceMap[$sourceId]=array_intersect_key($routeView,array_flip(['source_id','source_key','source_name','source_type','source_enabled']));}
        $items[]=['asset_id'=>$assetId,'name'=>text($asset,'display_name'),'isin'=>$isin,'identity_status'=>$identityStatus,'route_status'=>$route['status'],'route_reason'=>$route['reason'],'routes'=>$route['routes'],'collector_status'=>$collectorStatus,'current_status'=>$currentResult['status'],'current'=>$currentResult['current']];
    }
    ksort($sourceMap);usort($items,static fn(array $a,array $b): int => strcmp((string)$a['name'],(string)$b['name']));
    return ['status'=>'ok','as_of'=>$now,'stale_seconds'=>$staleSeconds,'counts'=>$counts,'sources'=>array_values($sourceMap),'assets'=>$items,'collector_candidates'=>$candidates];
}
