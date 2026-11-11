<?php
declare(strict_types=1);

namespace Mosa2\NovaStatus;

const VERSION = 'mosa2_nova_status_v1';

function readSource(string $root, ?\DateTimeImmutable $now = null): ?string
{
    // The two sites share the Dogado subscription. PHP must already allow this
    // fixed, read-only dependency. No user input can select a path or reader.
    $source = @realpath($root);
    if ($source === false || is_link($root)) {
        return null;
    }
    $php = $source.DIRECTORY_SEPARATOR.'php';
    $readers = [];
    foreach (['mosa_nova_read.php', 'mosa_nova_presence.php', 'mosa_nova_activity.php'] as $name) {
        $file = $php.DIRECTORY_SEPARATOR.$name;
        if (@realpath($file) !== $file || !is_file($file) || !is_readable($file)) {
            return null;
        }
        $readers[] = $file;
    }

    try {
        foreach ($readers as $reader) {
            require_once $reader;
        }
        $now ??= new \DateTimeImmutable('now', new \DateTimeZone('UTC'));
        $presence = \fixlabMosaNovaPresenceReadModel($source, $now);
        $activity = \fixlabMosaNovaActivityReadModel($source, $now);
    } catch (\Throwable) {
        return null;
    }

    if (($presence['active'] ?? false) !== true
        || ($activity['fresh'] ?? false) !== true
        || !is_bool($activity['working'] ?? null)) {
        return 'unavailable';
    }
    return $activity['working'] ? 'running' : 'idle';
}
