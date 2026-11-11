<?php
declare(strict_types=1);

namespace Mosa2\NovaChat;

require __DIR__.'/../api/nova_chat_store.php';

function check(bool $value, string $label): void
{
    if (!$value) throw new \RuntimeException($label);
}

$server = ['HTTP_HOST' => HOST, 'SERVER_NAME' => HOST, 'HTTPS' => 'on', 'REMOTE_USER' => 'test-user'];
check(trustedSite($server), 'Authenticated testsite');
check(!trustedSite(array_diff_key($server, ['REMOTE_USER' => true])), 'Missing authenticated user');
check(!trustedSite(['HTTP_HOST' => 'scharwerk.de'] + $server), 'Production host denied');
$now = 1000;
$data = ['seen' => 0, 'chats' => []];
$request = ['id' => str_repeat('a', 32), 'text' => 'Wie funktioniert ein Test?'];
check(submit($data, 'a', $request, $now) === 503, 'Absent worker');
worker($data, ['action' => 'claim'], $now);
check(submit($data, 'a', ['text' => '/exec shutdown'] + $request, $now) === 422, 'Command denied');
check(submit($data, 'a', $request, $now) === 202, 'Informational request accepted');
check(submit($data, 'a', $request, $now) === 200, 'Duplicate submission acknowledged');
check(browserView($data, 'b', $now, 'csrf')['messages'] === [], 'Other session cannot read chat');
[, $claim] = worker($data, ['action' => 'claim'], $now);
check($claim['job']['text'] === $request['text'], 'Worker receives original request');
check(running($data, $now), 'Activity reported for claimed request');
check(worker($data, ['action' => 'claim'], $now)[1]['job'] === null, 'Duplicate claim denied');
$completion = ['action' => 'complete', 'id' => $request['id'], 'lease' => $claim['job']['lease'],
    'ok' => true, 'reply' => 'Testantwort'];
check(worker($data, ['lease' => str_repeat('b', 32)] + $completion, $now)[0] === 404, 'Wrong lease denied');
check(worker($data, $completion, $now)[0] === 200, 'Correct completion accepted');
check(worker($data, $completion, $now)[0] === 200, 'Completion retry does not repeat work');
$view = browserView($data, 'a', $now, 'csrf');
check($view['messages'][0]['reply'] === 'Testantwort' && !isset($view['messages'][0]['lease']), 'Scoped safe result');
check(!running($data, $now), 'No activity after completion');
$request['id'] = str_repeat('b', 32);
check(submit($data, 'a', $request, $now) === 202, 'Next message accepted');
[, $claim] = worker($data, ['action' => 'claim'], $now);
check(count($claim['job']['history']) === 1, 'Worker history is conversation-specific');
expire($data, $now + MAX_RUN);
check(!running($data, $now + MAX_RUN), 'Expired claim is not active');
check(worker($data, ['action' => 'claim'], $now + MAX_RUN)[1]['job'] === null, 'Expired claim is not replayed');
echo "NOVA chat authentication, isolation, deduplication and timeout tests passed.\n";
