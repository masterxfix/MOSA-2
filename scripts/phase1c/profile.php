<?php
declare(strict_types=1);

namespace Mosa2\History10000;

require_once __DIR__ . '/../phase1b/probe.php';

use PDO;
use Throwable;
use Mosa2\Phase1B\Failure;
use function Mosa2\Phase1B\connect;
use function Mosa2\Phase1B\ensure;
use function Mosa2\Phase1B\rights;
use function Mosa2\Phase1B\sessionState;
use function Mosa2\Phase1B\tableIdentifier;
use const Mosa2\Phase1B\COLLATION;

const LIMITS = ['entity' => 100, 'identity' => 100, 'history' => 10000, 'current' => 100, 'migration' => 10];
const EXPECTED = ['entity' => 100, 'identity' => 100, 'history' => 10000, 'current' => 100, 'migration' => 1];
const SEED = 'mosa2-synthetic-v1';
const BASE_TIME = 1577836800; // 2020-01-01 00:00:00 UTC.
const SAMPLES = 11; // First execution reported separately; ten subsequent samples.
const BATCH = 500;

function profileSpec(?string $id = null): array
{
    if ($id === null) {
        ensure(!(defined('MOSA2_HISTORY_PROFILE') && defined('MOSA2_HISTORY_10000')), 'ambiguous_profile');
        $id = defined('MOSA2_HISTORY_PROFILE') ? MOSA2_HISTORY_PROFILE : 'history10000_v1';
        if (defined('MOSA2_HISTORY_10000')) ensure(MOSA2_HISTORY_10000 === true, 'unknown_profile');
    }
    ensure(is_string($id) && in_array($id, ['history10000_v1','history100000_v1'], true), 'unknown_profile');
    $per = $id === 'history100000_v1' ? 1000 : 100;
    $limits = LIMITS; $limits['history'] = 100 * $per;
    $expected = EXPECTED; $expected['history'] = 100 * $per;
    return ['id'=>$id,'per_entity'=>$per,'limits'=>$limits,'expected'=>$expected];
}

function generatedRows(string $kind, ?string $profile = null): \Generator
{
    $spec=profileSpec($profile);
    ensure(isset($spec['limits'][$kind]), 'unknown_table_kind');
    if ($kind === 'migration') {
        yield [1,'synthetic_schema_v1','2020-01-01 00:00:00.000000'];
        return;
    }
    for ($e=1;$e<=100;++$e) {
        if ($kind==='entity') yield [$e,sprintf('object_%04d',$e)];
        if ($kind==='identity') yield [$e,$e,'synthetic_v1',substr(hash('sha256',SEED.':'.$e),0,24)];
        if ($kind==='current') {
            $h=historyRow($e,$spec['per_entity'],$spec['id']);
            yield [$e,$h[0],$h[3],$h[4]];
        }
        if ($kind==='history') for ($s=1;$s<=$spec['per_entity'];++$s) yield historyRow($e,$s,$spec['id']);
    }
}

function boundedBatches(string $kind, ?string $profile = null): \Generator
{
    $spec=profileSpec($profile); $batch=[]; $seen=0;
    foreach (generatedRows($kind,$spec['id']) as $row) {
        validateCount($kind,++$seen,$spec['id']); $batch[]=$row;
        if (count($batch)===BATCH) { yield $batch; $batch=[]; }
    }
    if ($batch!==[]) yield $batch;
    ensure($seen===$spec['expected'][$kind],'generated_count_mismatch');
}

function stamp(int $sequence, ?string $profile = null): string
{
    ensure($sequence >= 1 && $sequence <= profileSpec($profile)['per_entity'], 'sequence_out_of_profile');
    return gmdate('Y-m-d H:i:s', BASE_TIME + intdiv($sequence - 1, 2) * 60) . '.000000';
}

function historyRow(int $entity, int $sequence, ?string $profile = null): array
{
    ensure($entity >= 1 && $entity <= 100, 'entity_out_of_profile');
    $spec=profileSpec($profile);
    return [($entity - 1) * $spec['per_entity'] + $sequence, $entity, $sequence, stamp($sequence,$spec['id']), $entity * 1000 + $sequence];
}

function rows(string $kind, ?string $profile = null): array
{
    $spec=profileSpec($profile);
    ensure($kind!=='history' || $spec['limits']['history']<=10000, 'large_history_requires_streaming');
    return iterator_to_array(generatedRows($kind,$spec['id']),false);
}

function validateCount(string $kind, int $count, ?string $profile = null): void
{
    $limits=profileSpec($profile)['limits'];
    ensure(isset($limits[$kind]) && $count>=0 && $count<=$limits[$kind], 'row_limit_exceeded');
}

function chunks(array $rows): array
{
    ensure(count($rows) <= profileSpec()['limits']['history'], 'batch_total_exceeded');
    return array_chunk($rows, BATCH);
}

function statistics(array $values): array
{
    ensure(count($values)>=1 && count($values)<=30,'sample_limit_exceeded');
    return distribution($values);
}

function batchStatistics(array $values, ?string $profile = null): array
{
    $maximum=(int)ceil(profileSpec($profile)['limits']['history']/BATCH);
    ensure(count($values)>=1 && count($values)<=$maximum,'batch_sample_limit_exceeded');
    return distribution($values);
}

function distribution(array $values): array
{
    sort($values, SORT_NUMERIC);
    $n = count($values);
    $median = $n % 2 ? $values[intdiv($n, 2)] : ($values[$n / 2 - 1] + $values[$n / 2]) / 2;
    return ['samples' => $n, 'median_ms' => round($median, 4), 'p95_ms' => round($values[(int) ceil($n * 0.95) - 1], 4)];
}

function newer(array $incoming, array $current): bool
{
    return [$incoming[3], $incoming[0]] > [$current[3], $current[0]];
}

function checkpoint(float $deadline): void
{
    ensure(microtime(true) <= $deadline, 'wall_time_limit_exceeded');
}

function saveState(string $path, array $state): void
{
    $tmp = $path . '.next';
    ensure(!is_link($path) && !file_exists($tmp), 'unsafe_manifest');
    $old = umask(0077);
    try {
        $f = fopen($tmp, 'x');
        ensure($f !== false, 'manifest_create_failed');
        try {
            $text = json_encode($state, JSON_THROW_ON_ERROR);
            ensure(chmod($tmp, 0600) && fwrite($f, $text) === strlen($text) && fflush($f), 'manifest_write_failed');
        } finally { fclose($f); }
        ensure(rename($tmp, $path), 'manifest_replace_failed');
    } finally { umask($old); }
}

function tableNames(PDO $pdo): array
{
    $names = $pdo->query('SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() ORDER BY table_name LIMIT 101')->fetchAll(PDO::FETCH_COLUMN);
    ensure(count($names) <= 100, 'unexpected_baseline_size');
    return $names;
}

function ownedName(array $state, string $kind): string
{
    ensure(isset(profileSpec()['limits'][$kind], $state['tables'][$kind]), 'manifest_table_missing');
    return tableIdentifier($state['tables'][$kind]);
}

function proveOwnership(PDO $pdo, array $state, string $kind): bool
{
    $q = $pdo->prepare('SELECT TABLE_COMMENT FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=?');
    $q->execute([$state['tables'][$kind]]);
    $comment = $q->fetchColumn();
    if ($comment === false) return false;
    ensure($comment === 'MOSA2_HISTORY10000:' . $state['owner'], 'table_ownership_mismatch');
    return true;
}

function validateState(array $state, ?string $profile = null): void
{
    $spec=profileSpec($profile);
    ensure(($state['profile'] ?? '') === $spec['id'], 'manifest_profile_mismatch');
    if ($spec['id']==='history100000_v1' || isset($state['per_entity'],$state['limits'],$state['expected'])) {
        ensure(($state['per_entity']??null)===$spec['per_entity'] && ($state['limits']??null)===$spec['limits'] && ($state['expected']??null)===$spec['expected'],'manifest_bounds_mismatch');
    }
    ensure((bool) preg_match('/\A[a-f0-9]{32}\z/D', (string) ($state['owner'] ?? '')), 'manifest_owner_invalid');
    ensure(array_keys($state['tables'] ?? []) === array_keys(LIMITS), 'manifest_tables_invalid');
    foreach ($state['tables'] as $name) tableIdentifier($name);
    ensure(count(array_unique($state['tables'])) === 5, 'manifest_table_collision');
    ensure(is_array($state['baseline'] ?? null), 'manifest_baseline_missing');
    ensure(array_keys($state['used'] ?? []) === ['cli', 'fpm-fcgi'], 'manifest_usage_missing');
    foreach ($state['used'] as $sapi => $used) ensure(in_array($sapi, ['cli', 'fpm-fcgi'], true) && is_bool($used), 'manifest_usage_invalid');
}

function counts(PDO $pdo, array $state): array
{
    $counts = [];
    foreach (profileSpec()['limits'] as $kind => $limit) {
        $counts[$kind] = (int) $pdo->query('SELECT COUNT(*) FROM ' . ownedName($state, $kind))->fetchColumn();
        validateCount($kind, $counts[$kind]);
    }
    ensure($counts === profileSpec()['expected'], 'unexpected_row_counts');
    return $counts;
}

function historyTimeIndex(string $direction = 'ASC'): string
{
    ensure(in_array($direction, ['ASC', 'DESC'], true), 'invalid_index_direction');
    return "KEY history_time(entity_id,observed_at $direction,id $direction)";
}

function build(PDO $pdo, string $path, float $deadline, string $indexDirection = 'ASC'): array
{
    ensure(!file_exists($path), 'build_already_started');
    $available = rights($pdo);
    ensure(!in_array(false, $available, true), 'required_privilege_missing');
    $spec=profileSpec();
    $state = ['profile' => $spec['id'], 'per_entity'=>$spec['per_entity'], 'limits'=>$spec['limits'], 'expected'=>$spec['expected'], 'owner' => bin2hex(random_bytes(16)), 'tables' => [], 'baseline' => tableNames($pdo), 'used' => ['cli' => false, 'fpm-fcgi' => false], 'ready' => false];
    foreach (profileSpec()['limits'] as $kind => $limit) {
        do { $name = 'mosa2_tmp_' . bin2hex(random_bytes(8)); } while (in_array($name, $state['baseline'], true) || in_array($name, $state['tables'], true));
        $state['tables'][$kind] = $name;
    }
    validateState($state);
    saveState($path, $state); // Reserve exact names before DDL; comments prove actual ownership.
    $e = ownedName($state, 'entity'); $i = ownedName($state, 'identity');
    $h = ownedName($state, 'history'); $c = ownedName($state, 'current'); $m = ownedName($state, 'migration');
    $historyMax=$spec['limits']['history']; $perEntity=$spec['per_entity'];
    $timeIndex=historyTimeIndex($indexDirection);
    $definitions = [
        'entity' => "(id SMALLINT UNSIGNED PRIMARY KEY CHECK(id BETWEEN 1 AND 100), code VARCHAR(32) NOT NULL UNIQUE)",
        'identity' => "(id SMALLINT UNSIGNED PRIMARY KEY CHECK(id BETWEEN 1 AND 100), entity_id SMALLINT UNSIGNED NOT NULL UNIQUE, namespace VARCHAR(20) NOT NULL, external_key VARCHAR(24) NOT NULL, UNIQUE KEY identity_lookup(namespace,external_key), FOREIGN KEY(entity_id) REFERENCES $e(id))",
        'history' => "(id INT UNSIGNED PRIMARY KEY CHECK(id BETWEEN 1 AND $historyMax), entity_id SMALLINT UNSIGNED NOT NULL, sequence_no SMALLINT UNSIGNED NOT NULL CHECK(sequence_no BETWEEN 1 AND $perEntity), observed_at DATETIME(6) NOT NULL, synthetic_value INT NOT NULL, UNIQUE KEY history_sequence(entity_id,sequence_no), $timeIndex, FOREIGN KEY(entity_id) REFERENCES $e(id))",
        'current' => "(entity_id SMALLINT UNSIGNED PRIMARY KEY, history_id INT UNSIGNED NOT NULL, observed_at DATETIME(6) NOT NULL, synthetic_value INT NOT NULL, FOREIGN KEY(entity_id) REFERENCES $e(id), FOREIGN KEY(history_id) REFERENCES $h(id))",
        'migration' => "(id SMALLINT UNSIGNED PRIMARY KEY CHECK(id BETWEEN 1 AND 10), version_tag VARCHAR(32) NOT NULL UNIQUE, applied_at DATETIME(6) NOT NULL)",
    ];
    foreach (['entity', 'identity', 'history', 'current', 'migration'] as $kind) {
        checkpoint($deadline);
        $name = $state['tables'][$kind];
        $collision = $pdo->prepare('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=?');
        $collision->execute([$name]); ensure((int) $collision->fetchColumn() === 0, 'table_name_collision');
        $pdo->exec('CREATE TABLE ' . ownedName($state, $kind) . ' ' . $definitions[$kind] . ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=' . COLLATION . ' COMMENT=' . $pdo->quote('MOSA2_HISTORY10000:' . $state['owner']));
        ensure(proveOwnership($pdo, $state, $kind), 'ownership_record_failed');
    }
    $columns = ['entity' => 'id,code', 'identity' => 'id,entity_id,namespace,external_key', 'history' => 'id,entity_id,sequence_no,observed_at,synthetic_value', 'current' => 'entity_id,history_id,observed_at,synthetic_value', 'migration' => 'id,version_tag,applied_at'];
    $timings = [];
    $pdo->beginTransaction();
    try {
        foreach (['entity', 'identity', 'history', 'current', 'migration'] as $kind) {
            $loaded=0; $ms = [];
            foreach (boundedBatches($kind) as $batch) {
                checkpoint($deadline); ensure(count($batch) <= BATCH, 'batch_limit_exceeded');
                $marks = '(' . implode(',', array_fill(0, count($batch[0]), '?')) . ')';
                $query = $pdo->prepare('INSERT INTO ' . ownedName($state, $kind) . '(' . $columns[$kind] . ') VALUES ' . implode(',', array_fill(0, count($batch), $marks)));
                $start = hrtime(true); $query->execute(array_merge(...$batch));
                $ms[] = (hrtime(true) - $start) / 1e6; $loaded+=count($batch);
            }
            ensure($loaded===$spec['expected'][$kind],'loaded_count_mismatch');
            $timings[$kind] = ['rows' => $loaded, 'batches' => count($ms), 'max_batch_rows' => min(BATCH, $loaded), 'total_ms' => round(array_sum($ms), 4)] + batchStatistics($ms);
        }
        counts($pdo, $state);
        $pdo->commit();
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw $error;
    }
    $state['ready'] = true;
    $state['build'] = ['counts' => $spec['expected'], 'seed' => SEED, 'base_utc' => '2020-01-01T00:00:00Z', 'batch_write' => $timings];
    saveState($path, $state);
    return ['ok' => true, 'phase' => 'build', 'counts' => $spec['expected'], 'batches' => (int)ceil($spec['limits']['history']/BATCH)+4, 'maximum_batch_rows' => BATCH];
}

function canonical(array $row): string { return implode('|', $row) . "\n"; }

function expectedDigest(?string $profile = null): string
{
    $hash = hash_init('sha256');
    foreach (generatedRows('history',$profile) as $row) hash_update($hash, canonical($row));
    return hash_final($hash);
}

function actualDigest(PDO $pdo, array $state, float $deadline): string
{
    $hash = hash_init('sha256'); $last = 0; $seen = 0; $maximum=profileSpec()['limits']['history'];
    $q = $pdo->prepare('SELECT id,entity_id,sequence_no,observed_at,synthetic_value FROM ' . ownedName($state, 'history') . ' WHERE id > ? ORDER BY id LIMIT 500');
    while ($seen < $maximum) {
        checkpoint($deadline); $q->execute([$last]); $batch = $q->fetchAll(PDO::FETCH_NUM);
        ensure(count($batch) > 0 && count($batch) <= 500 && $seen + count($batch) <= $maximum, 'history_scan_limit');
        foreach ($batch as $row) { hash_update($hash, canonical($row)); $last = (int) $row[0]; }
        $seen += count($batch);
    }
    return hash_final($hash);
}

function querySet(array $state): array
{
    $c = ownedName($state, 'current'); $h = ownedName($state, 'history'); $i = ownedName($state, 'identity'); $e = ownedName($state, 'entity');
    $set = [
        'current_single' => ["SELECT entity_id,history_id,observed_at,synthetic_value FROM $c WHERE entity_id=? LIMIT 1", [7]],
        'current_batch' => ["SELECT entity_id,history_id,observed_at,synthetic_value FROM $c WHERE entity_id IN (1,2,3,10,50,100) ORDER BY entity_id LIMIT 6", []],
        'history_latest' => ["SELECT id,entity_id,sequence_no,observed_at,synthetic_value FROM $h WHERE entity_id=? ORDER BY observed_at DESC,id DESC LIMIT 1", [7]],
        'history_window' => ["SELECT id,entity_id,sequence_no,observed_at,synthetic_value FROM $h WHERE entity_id=? AND observed_at>=? AND observed_at<? ORDER BY observed_at,id LIMIT 20", [7, stamp(21), stamp(31)]],
        'chart' => ["SELECT id,entity_id,sequence_no,observed_at,synthetic_value FROM $h WHERE entity_id=? AND observed_at>=? AND observed_at<=? ORDER BY observed_at DESC,id DESC LIMIT 25", [7, stamp(1), stamp(profileSpec()['per_entity'])]],
        'identity_lookup' => ["SELECT e.id FROM $i i JOIN $e e ON e.id=i.entity_id WHERE i.namespace=? AND i.external_key=? LIMIT 1", ['synthetic_v1', rows('identity')[6][3]]],
    ];
    if (profileSpec()['id']==='history100000_v1') $set['history_wide_window']=["SELECT id,entity_id,sequence_no,observed_at,synthetic_value FROM $h WHERE entity_id=? AND observed_at>=? AND observed_at<? ORDER BY observed_at,id LIMIT 50",[7,stamp(1),stamp(901)]];
    return $set;
}

function expectedQueries(): array
{
    $current = rows('current'); $per=profileSpec()['per_entity'];
    $set = [
        'current_single' => [$current[6]],
        'current_batch' => array_map(fn(int $e): array => $current[$e - 1], [1,2,3,10,50,100]),
        'history_latest' => [historyRow(7,$per)],
        'history_window' => array_map(fn(int $seq): array => historyRow(7,$seq), range(21,30)),
        'chart' => array_map(fn(int $seq): array => historyRow(7,$seq), range($per,$per-24)),
        'identity_lookup' => [[7]],
    ];
    if (profileSpec()['id']==='history100000_v1') $set['history_wide_window']=array_map(fn(int $seq):array=>historyRow(7,$seq),range(1,50));
    return $set;
}

function upsert(PDO $pdo, array $state, array $row): void
{
    $table = ownedName($state, 'current');
    // Value first, history ID second, timestamp last: tuple comparisons use the old timestamp.
    $newer = '(VALUES(observed_at),VALUES(history_id)) > (observed_at,history_id)';
    $q = $pdo->prepare("INSERT INTO $table(entity_id,history_id,observed_at,synthetic_value) VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE synthetic_value=IF($newer,VALUES(synthetic_value),synthetic_value), history_id=IF($newer,VALUES(history_id),history_id), observed_at=GREATEST(observed_at,VALUES(observed_at))");
    $q->execute([$row[1], $row[0], $row[3], $row[4]]);
}

function correctness(PDO $pdo, array $state, float $deadline): array
{
    $n = counts($pdo, $state); $checks = ['exact_counts' => $n === profileSpec()['expected']];
    $h = ownedName($state, 'history'); $e = ownedName($state, 'entity'); $i = ownedName($state, 'identity'); $c = ownedName($state, 'current');
    $orphans = (int) $pdo->query("SELECT COUNT(*) FROM $h h LEFT JOIN $e e ON e.id=h.entity_id WHERE e.id IS NULL")->fetchColumn();
    $orphans += (int) $pdo->query("SELECT COUNT(*) FROM $i i LEFT JOIN $e e ON e.id=i.entity_id WHERE e.id IS NULL")->fetchColumn();
    $orphans += (int) $pdo->query("SELECT COUNT(*) FROM $c c LEFT JOIN $h h ON h.id=c.history_id AND h.entity_id=c.entity_id WHERE h.id IS NULL")->fetchColumn();
    ensure($orphans === 0, 'orphan_rows'); $checks['no_orphans'] = true;
    $pairs = (int) $pdo->query("SELECT COUNT(*) FROM (SELECT entity_id,sequence_no FROM $h GROUP BY entity_id,sequence_no) pairs")->fetchColumn();
    ensure($pairs === profileSpec()['expected']['history'], 'history_duplicates'); $checks['unique_history_mapping'] = true;
    $all = $pdo->query("SELECT entity_id,history_id,observed_at,synthetic_value FROM $c ORDER BY entity_id LIMIT 100")->fetchAll(PDO::FETCH_NUM);
    ensure($all === rows('current'), 'current_not_latest'); $checks['all_current_latest'] = true;
    ensure(hash_equals(expectedDigest(), actualDigest($pdo, $state, $deadline)), 'history_digest_mismatch'); $checks['history_seed_digest'] = true;
    $expected = expectedQueries();
    foreach (querySet($state) as $kind => [$sql, $params]) {
        checkpoint($deadline); $q = $pdo->prepare($sql); $q->execute($params);
        ensure($q->fetchAll(PDO::FETCH_NUM) === $expected[$kind], 'query_result_' . $kind); $checks[$kind] = true;
    }
    $q = $pdo->prepare("SELECT id FROM $h WHERE entity_id=? AND observed_at>=? AND observed_at<? ORDER BY observed_at,id LIMIT 20");
    foreach ([[101,stamp(1),stamp(profileSpec()['per_entity'])], [7,stamp(21),stamp(21)], [7,'2021-01-01 00:00:00.000000','2021-01-02 00:00:00.000000']] as $params) {
        $q->execute($params); ensure($q->fetchAll() === [], 'empty_boundary_failed');
    }
    $checks['empty_and_time_boundaries'] = true;
    $checks['timestamp_tie_sorted_by_id'] = true;
    $pdo->beginTransaction();
    try {
        $first = historyRow(7,1);
        $q = $pdo->prepare("UPDATE $c SET history_id=?,observed_at=?,synthetic_value=? WHERE entity_id=7");
        $q->execute([$first[0],$first[3],$first[4]]);
        $per=profileSpec()['per_entity'];
        foreach ([2,1,$per,$per-2,$per-1,$per] as $seq) {
            checkpoint($deadline); upsert($pdo, $state, historyRow(7,$seq));
            $expectedSeq = $seq <= 2 ? 2 : $per;
            $row = $pdo->query("SELECT history_id,observed_at,synthetic_value FROM $c WHERE entity_id=7 LIMIT 1")->fetch(PDO::FETCH_NUM);
            $want = historyRow(7,$expectedSeq);
            ensure($row === [$want[0],$want[3],$want[4]], 'upsert_recency_failed');
            ensure((int) $pdo->query("SELECT COUNT(*) FROM $c")->fetchColumn() === 100, 'upsert_duplicate');
        }
    } finally { if ($pdo->inTransaction()) $pdo->rollBack(); }
    ensure($pdo->query("SELECT entity_id,history_id,observed_at,synthetic_value FROM $c ORDER BY entity_id LIMIT 100")->fetchAll(PDO::FETCH_NUM) === rows('current'), 'upsert_rollback_failed');
    ensure(hash_equals(expectedDigest(), actualDigest($pdo, $state, $deadline)), 'history_modified');
    $checks['upsert_no_duplicates_or_regression'] = true; $checks['history_unchanged'] = true;
    return $checks;
}

function measureQueries(PDO $pdo, array $state, float $deadline, ?array $only = null): array
{
    $queries=[];
    $expected = expectedQueries();
    $set=querySet($state);
    ensure($only===null || ($only!==[] && count(array_unique($only))===count($only) && array_diff($only,array_keys($set))===[]), 'invalid_query_selection');
    foreach ($set as $kind => [$sql,$params]) {
        if ($only!==null && !in_array($kind,$only,true)) continue;
        $times = []; $q = $pdo->prepare($sql);
        for ($n=0; $n<SAMPLES; ++$n) {
            checkpoint($deadline); $start=hrtime(true); $q->execute($params); $actual=$q->fetchAll(PDO::FETCH_NUM); $times[]=(hrtime(true)-$start)/1e6;
            ensure($actual === $expected[$kind], 'measured_result_mismatch');
        }
        $explain=$pdo->prepare('EXPLAIN '.$sql); $explain->execute($params); $plan=[];
        foreach ($explain->fetchAll() as $row) {
            $plan[]=['access'=>$row['type'], 'key'=>$row['key'], 'estimated_rows'=>(int)$row['rows'], 'extra'=>$row['Extra'], 'filesort'=>str_contains((string)$row['Extra'],'Using filesort')];
            if (str_starts_with($kind,'history_') || $kind==='chart') ensure($row['type'] !== 'ALL' && $row['key'] !== null, 'history_index_not_used');
        }
        $first=array_shift($times);
        $queries[$kind]=['first_ms'=>round($first,4), 'total_executions'=>SAMPLES, 'subsequent'=>statistics($times), 'explain'=>$plan];
    }
    return $queries;
}

function measure(PDO $pdo, array &$state, string $path, float $deadline): array
{
    ensure(($state['ready'] ?? false) === true && !($state['cleaned'] ?? false), 'dataset_not_ready');
    ensure(isset($state['used'][PHP_SAPI]) && $state['used'][PHP_SAPI] === false, 'runtime_already_measured');
    $state['used'][PHP_SAPI] = true; saveState($path, $state); // Reserve whole bounded run before any samples.
    foreach (profileSpec()['limits'] as $kind => $limit) ensure(proveOwnership($pdo,$state,$kind), 'owned_table_missing');
    $report = ['ok' => true, 'runtime' => ['php' => PHP_VERSION, 'sapi' => PHP_SAPI, 'pdo_mysql' => true], 'session' => sessionState($pdo), 'build' => $state['build'], 'checks' => [], 'queries' => []];
    $report['queries']=measureQueries($pdo,$state,$deadline);
    $report['checks'] = correctness($pdo,$state,$deadline);
    $report['approximate_table_statistics']=tableStatistics($pdo,$state);
    saveState(dirname($path).'/result-'.(PHP_SAPI==='cli'?'cli':'fpm').'.json',$report);
    return $report;
}

function tableStatistics(PDO $pdo, array $state): array
{
    // Bypass only this session's information-schema statistics cache; never flush data caches.
    $pdo->exec('SET SESSION information_schema_stats_expiry=0');
    $sizes=[]; $q=$pdo->prepare('SELECT TABLE_ROWS,DATA_LENGTH,INDEX_LENGTH FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=?');
    foreach (profileSpec()['limits'] as $kind=>$limit) {
        ensure(proveOwnership($pdo,$state,$kind),'owned_table_missing');
        $q->execute([$state['tables'][$kind]]); $r=$q->fetch();
        $sizes[$kind]=['estimated_rows'=>(int)$r['TABLE_ROWS'],'data_bytes'=>(int)$r['DATA_LENGTH'],'index_bytes'=>(int)$r['INDEX_LENGTH']];
    }
    return $sizes;
}

function cleanup(PDO $pdo, array &$state, string $path, float $deadline): array
{
    if ($pdo->inTransaction()) $pdo->rollBack();
    foreach (['migration','current','history','identity','entity'] as $kind) {
        checkpoint($deadline);
        if (proveOwnership($pdo,$state,$kind)) $pdo->exec('DROP TABLE '.ownedName($state,$kind));
    }
    $same=tableNames($pdo)===$state['baseline']; ensure($same,'baseline_not_restored');
    $state['cleaned']=true; saveState($path,$state);
    return ['ok'=>true,'phase'=>'cleanup','baseline_restored'=>true,'baseline_table_count'=>count($state['baseline']),'remaining_table_count'=>count(tableNames($pdo))];
}

function dispatch(array $target, string $password, string $private, string $action): array
{
    ensure(in_array($action,['--build','--measure','--statistics','--cleanup'],true),'explicit_profile_action_required');
    ensure(PHP_SAPI==='cli'||$action==='--measure','fpm_read_profile_only');
    ensure(!is_link($private) && (fileperms($private)&0077)===0,'private_profile_directory_required');
    @set_time_limit(120);
    $deadline=microtime(true)+($action==='--build'?90:30);
    $pdo=connect($target,$password); unset($password);
    $pdo->exec('SET SESSION max_execution_time=3000');
    $spec=profileSpec(); $path=$private.'/'.str_replace('_v1','',$spec['id']).'.json';
    $lock=fopen($private.'/history-profile.lock','c');
    ensure($lock!==false && chmod($private.'/history-profile.lock',0600),'profile_lock_unavailable');
    ensure(flock($lock,LOCK_EX|LOCK_NB),'profile_already_running');
    $state=null;
    try {
        if ($action==='--build') return build($pdo,$path,$deadline);
        ensure(is_file($path)&&!is_link($path)&&(fileperms($path)&0077)===0,'profile_manifest_missing');
        $state=json_decode(file_get_contents($path),true,32,JSON_THROW_ON_ERROR); validateState($state);
        if ($action==='--cleanup') return cleanup($pdo,$state,$path,$deadline);
        if ($action==='--statistics') {
            ensure(($state['ready']??false) && !($state['cleaned']??false), 'dataset_not_ready');
            $counts=counts($pdo,$state);
            ensure(hash_equals(expectedDigest(),actualDigest($pdo,$state,$deadline)), 'history_modified');
            return ['ok'=>true,'phase'=>'statistics','counts'=>$counts,'history_unchanged'=>true,'approximate_table_statistics'=>tableStatistics($pdo,$state)];
        }
        $report=measure($pdo,$state,$path,$deadline);
        if (PHP_SAPI==='fpm-fcgi' && is_file($private.'/result-cli.json')) {
            $report['cli_result']=json_decode(file_get_contents($private.'/result-cli.json'),true,32,JSON_THROW_ON_ERROR);
        }
        return $report;
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        $report=['ok'=>false,'failure'=>['code'=>$error instanceof Failure?$error->getMessage():'profile_operation_failed']];
        // The reserved manifest plus table comments also cover partial DDL failures.
        if (is_file($path)) {
            try {
                $state=json_decode(file_get_contents($path),true,32,JSON_THROW_ON_ERROR); validateState($state);
                $report['cleanup']=cleanup($pdo,$state,$path,microtime(true)+30);
            } catch (Throwable) { $report['cleanup']=['ok'=>false,'manual_owned_cleanup_required'=>true]; }
        }
        return $report;
    } finally { flock($lock,LOCK_UN); fclose($lock); }
}
