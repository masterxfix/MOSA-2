<?php
declare(strict_types=1);

require_once dirname(__DIR__).'/api/nova_status_model.php';

use function Mosa2\NovaStatus\readSource;

$source = $argv[1] ?? '';
$root = sys_get_temp_dir().'/mosa2-nova-fixture-'.bin2hex(random_bytes(12));
$files = ['mosa_nova_read.php', 'mosa_nova_presence.php', 'mosa_nova_activity.php'];
$now = new DateTimeImmutable('2026-11-11T12:00:00Z');
$seen = static fn (int $age): string => gmdate('Y-m-d\TH:i:s\Z', $now->getTimestamp() - $age);
$expect = static function (?string $expected, ?string $actual, string $test): void {
    if ($actual !== $expected) {
        throw new RuntimeException($test.' failed');
    }
};

$expect(null, readSource($root, $now), 'missing source');
mkdir($root, 0700);
mkdir($root.'/php', 0700);
mkdir($root.'/data', 0700);
mkdir($root.'/data/private', 0700);
$private = $root.'/data/private';
try {
    foreach ($files as $file) {
        if ($source === '' || !is_file($source.'/php/'.$file) || !copy($source.'/php/'.$file, $root.'/php/'.$file)) {
            throw new RuntimeException('Pass the fixlab checkout as the first argument');
        }
    }
    file_put_contents($private.'/.htaccess', 'Require all denied');
    $expect('unavailable', readSource($root, $now), 'missing authenticated snapshots');
    $cases = [
        [120, 30, true, 'running'],
        [120, 30, false, 'idle'],
        [121, 0, true, 'unavailable'],
        [0, 31, false, 'unavailable'],
        [0, 31, true, 'unavailable'],
        [-1, 0, true, 'unavailable'],
        [0, -1, false, 'unavailable'],
        [0, '2026-02-31T12:00:00Z', true, 'unavailable'],
        ['2026-02-31T12:00:00Z', 0, false, 'unavailable'],
        [0, 0, 'false', 'unavailable'],
    ];
    foreach ($cases as [$heartbeat, $activity, $working, $expected]) {
        file_put_contents($private.'/mosa_nova_presence.json', json_encode([
            'contract_version' => 'mosa_nova_presence_v1',
            'last_seen_at_utc' => is_int($heartbeat) ? $seen($heartbeat) : $heartbeat,
        ], JSON_THROW_ON_ERROR));
        file_put_contents($private.'/mosa_nova_activity.json', json_encode([
            'contract_version' => 'mosa_nova_activity_v1',
            'working' => $working,
            'output_tokens' => null,
            'received_at_utc' => is_int($activity) ? $seen($activity) : $activity,
        ], JSON_THROW_ON_ERROR));
        $expect($expected, readSource($root, $now), json_encode([$heartbeat, $activity, $working]));
    }
    file_put_contents($private.'/mosa_nova_activity.json', '{invalid');
    $expect('unavailable', readSource($root, $now), 'invalid source JSON');
    echo "PASS MOSA NOVA readers, three states, freshness limits and invalid snapshots\n";
} finally {
    foreach (['.htaccess', 'mosa_nova_presence.json', 'mosa_nova_activity.json'] as $file) {
        if (is_file($private.'/'.$file)) {
            unlink($private.'/'.$file);
        }
    }
    foreach ($files as $file) {
        if (is_file($root.'/php/'.$file)) {
            unlink($root.'/php/'.$file);
        }
    }
    rmdir($private);
    rmdir($root.'/data');
    rmdir($root.'/php');
    rmdir($root);
}
