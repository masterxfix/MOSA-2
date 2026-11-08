<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/api/codex_status_model.php';

use function Mosa2\CodexStatus\readPrivateToken;
use function Mosa2\CodexStatus\ingestSecret;

$count=0;
$check=static function(bool $condition,string $message) use (&$count): void {
    $count++;
    if (!$condition) throw new RuntimeException($message);
};

$dir=sys_get_temp_dir().'/mosa2-codex-secret-'.bin2hex(random_bytes(8));
if (!mkdir($dir,0700)) throw new RuntimeException('fixture_directory');
$path=$dir.'/token.txt';
$token=bin2hex(random_bytes(32));
$old=getenv('MOSA2_CODEX_STATUS_TOKEN');
try {
    $check(readPrivateToken($path)===null,'missing secret must fail closed');
    file_put_contents($path,$token);
    chmod($path,0600);
    $check(readPrivateToken($path)===$token,'owner-only secret accepted');
    file_put_contents($path,$token."\n");
    $check(readPrivateToken($path)===$token,'single final newline accepted');
    chmod($path,0644);
    $check(readPrivateToken($path)===null,'world-readable secret rejected');
    chmod($path,0600);
    file_put_contents($path,'not-a-secret');
    $check(readPrivateToken($path)===null,'invalid secret rejected');
    file_put_contents($path,$token);
    if (function_exists('symlink')) {
        $link=$dir.'/linked-token.txt';
        if (@symlink($path,$link)) {
            $check(readPrivateToken($link)===null,'symlink secret rejected');
            unlink($link);
        }
    }
    $check(readPrivateToken($path)===$token,'secret reread after invalid file');
    putenv('MOSA2_CODEX_STATUS_TOKEN='.str_repeat('a',64));
    $check(ingestSecret()===str_repeat('a',64),'existing environment secret preferred');
    putenv('MOSA2_CODEX_STATUS_TOKEN=short');
    $check(ingestSecret()===null,'invalid configured environment fails closed');
} finally {
    if ($old===false) putenv('MOSA2_CODEX_STATUS_TOKEN');
    else putenv('MOSA2_CODEX_STATUS_TOKEN='.$old);
    @unlink($path);
    @rmdir($dir);
}
echo "Codex status private token: {$count} checks OK\n";
