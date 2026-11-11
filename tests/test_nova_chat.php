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
$workerServer = ['REMOTE_USER' => WORKER_USER] + $server;
check(trustedChatRoute($workerServer, true), 'Dedicated worker on worker route');
check(!trustedChatRoute($workerServer, false), 'Dedicated worker denied on browser route');
check(!trustedChatRoute($server, true), 'Browser credentials denied on worker route');
check(acceptsText('Hi Nova, wieviele seiten hat M2 ?'), 'Screenshot question with greeting');
check(acceptsText('Hallo NOVA, wie viele Seiten hat M2?'), 'Greeting and standard spelling');
check(acceptsText("Hey Nova!\nWie funktioniert der Chat?"), 'Greeting on its own line');
foreach ([
    'Hi NOVA, wie geht es dir heute?',
    'Kannst du mir erklären, wie M2 aufgebaut ist',
    'Erzähl mir etwas über deine Aufgaben.',
    'Ich habe eine neue Idee für unser Projekt.',
    "Erstelle einen Entwurf.\r\n\tBitte mit <Beispiel> und einem Abschnitt zur Abnahme.",
    'Mach den zweiten Punkt aus deiner Antwort konkreter',
    str_repeat('Ä', intdiv(MAX_TEXT_BYTES, 2)),
] as $message) check(acceptsText($message), 'Free text accepted');
check(!acceptsText(str_repeat('Ä', intdiv(MAX_TEXT_BYTES, 2) + 1)), 'UTF-8 byte limit');
check(!acceptsText(" \t\r\n\u{00a0}"), 'Whitespace only rejected');
check(!acceptsText("Text\x00"), 'Invalid control character rejected');
check(!acceptsText("\xff"), 'Invalid UTF-8 rejected');
check(navigationLabels(file_get_contents(__DIR__.'/../index.html')) ===
    ['Projektüberblick', 'Marktdaten & Messungen', 'Fundamentaldaten'], 'Use the generated M2 navigation');
$now = 1000;
$data = ['seen' => 0, 'chats' => []];
$request = ['id' => str_repeat('a', 32), 'text' => 'Wie funktioniert ein Test?'];
check(submit($data, 'a', $request, $now) === 503, 'Absent worker');
worker($data, ['action' => 'claim'], $now);
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
$olderTurn = ['question' => 'Früherer Text', 'answer' => 'Frühere Antwort'];
$oldMessages = array_fill(0, 12, ['id' => str_repeat('c', 32), 'text' => $olderTurn['question'],
    'reply' => $olderTurn['answer'], 'state' => 'done', 'at' => $now]);
$longChat = ['seen' => $now, 'chats' => ['a' => ['updated' => $now, 'messages' => $oldMessages]]];
check(submit($longChat, 'a', $request, $now) === 202, 'Conversation can continue after twelve messages');
[, $claim] = worker($longChat, ['action' => 'claim'], $now);
check($claim['job']['history'] === array_fill(0, 12, $olderTurn), 'Earlier turns remain available as context');
check(count(browserView($longChat, 'a', $now, 'csrf')['messages']) === 13, 'Existing messages are preserved');
$largeTurn = ['question' => str_repeat('a', MAX_TEXT_BYTES), 'answer' => str_repeat('b', MAX_REPLY_BYTES)];
check(recentHistory([$largeTurn, $largeTurn, $olderTurn]) === [$largeTurn, $olderTurn], 'Recent context stays within byte budget');
$fullChat = ['seen' => $now, 'chats' => ['a' => ['updated' => $now,
    'messages' => array_fill(0, 83, ['id' => str_repeat('c', 32), 'text' => str_repeat('a', MAX_TEXT_BYTES),
        'reply' => '', 'state' => 'done', 'at' => $now])]]];
$before = $fullChat;
check(submit($fullChat, 'a', $request, $now) === 507 && $fullChat === $before,
    'Storage budget protects existing messages and leaves room for replies');
echo "NOVA chat authentication, isolation, deduplication and timeout tests passed.\n";
