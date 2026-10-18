<?php
declare(strict_types=1);
// Temporary HTTPS entry: configuration and captured password stay outside webroot.
ini_set('display_errors', '0');
ini_set('log_errors', '0');
umask(0077);
function deny(): never { http_response_code(403); exit('Zugriff nicht möglich. Keine Tests ausgeführt.'); }
try {
    $config = require __DIR__.'/access.php';
    if (PHP_SAPI !== 'fpm-fcgi' || ($_SERVER['HTTPS'] ?? '') !== 'on'
        || ($_SERVER['HTTP_HOST'] ?? '') !== $config['host']
        || ($_SERVER['REMOTE_ADDR'] ?? '') !== $config['ip']
        || time() > $config['expires'] || is_link(__FILE__)
        || (fileperms(__DIR__) & 0077) !== 0) deny();
    header('Cache-Control: no-store');
    header('Referrer-Policy: same-origin');
    header('X-Content-Type-Options: nosniff');
    header('X-Robots-Tag: noindex, nofollow');
    header("Content-Security-Policy: default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
    header('Content-Type: text/html; charset=utf-8');
    if (is_file(__DIR__.'/secret.php')) exit('<h1>Passwort geschützt übernommen</h1><p>Keine Migration ausgeführt. Die kontrollierte Prüfung kann fortgesetzt werden.</p>');
    $method = $_SERVER['REQUEST_METHOD'] ?? '';
    if ($method === 'POST') {
        if (($_SERVER['HTTP_ORIGIN'] ?? '') !== 'https://'.$config['host']
            || (int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 4096) deny();
        $csrf = $_POST['csrf'] ?? null;
        $cookie = $_COOKIE['M2P2CSRF'] ?? null;
        if (!is_string($csrf) || !is_string($cookie) || !hash_equals($cookie, $csrf)) deny();
        $parts = explode('.', $csrf);
        if (count($parts) !== 3 || !ctype_digit($parts[0])
            || (int)$parts[0] < time()-600 || (int)$parts[0] > time()
            || !preg_match('/\A[a-f0-9]{64}\z/', $parts[1])
            || !hash_equals(hash_hmac('sha256', $parts[0].'.'.$parts[1], $config['key']), $parts[2])) deny();
        // Safe live POST probe exercises exactly the same Origin/cookie/CSRF path,
        // without accepting or requesting a credential, before user handoff.
        if (($_POST['probe'] ?? '') === '1' && !isset($_POST['password'])) {
            $proof = ['origin_csrf_probe'=>true, 'at_utc'=>gmdate('c')];
            file_put_contents(__DIR__.'/form-proof.json', json_encode($proof, JSON_THROW_ON_ERROR), LOCK_EX);
            header('Location: '.$config['path'], true, 303); exit;
        }
        if (!is_file(__DIR__.'/form-proof.json')) deny();
        $password = $_POST['password'] ?? null;
        if (!is_string($password) || strlen($password)<1 || strlen($password)>1024) deny();
        $lock = fopen(__DIR__.'/access.lock', 'c');
        if (!$lock || !flock($lock, LOCK_EX) || is_file(__DIR__.'/secret.php')) deny();
        require_once __DIR__.'/postcheck.php';
        $pdo = \Mosa2\Phase2\connection($password);
        \Mosa2\Phase2\preflight($pdo);
        $pdo = null;
        $content = '<?php return '.var_export($password, true).';';
        $file = fopen(__DIR__.'/secret.php', 'x');
        if (!$file || fwrite($file, $content) !== strlen($content)) deny();
        fclose($file);
        unset($password, $content, $_POST);
        flock($lock, LOCK_UN); fclose($lock);
        setcookie('M2P2CSRF', '', ['expires'=>1,'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
        header('Location: '.$config['path'], true, 303); exit;
    }
    if ($method !== 'GET') deny();
    $nonce = time().'.'.bin2hex(random_bytes(32));
    $token = $nonce.'.'.hash_hmac('sha256', $nonce, $config['key']);
    setcookie('M2P2CSRF', $token, ['expires'=>time()+600,'path'=>$config['path'],'secure'=>true,'httponly'=>true,'samesite'=>'Strict']);
    echo '<h1>MOSA 2 – isolierter Core-Schema-Test</h1>';
    if (!is_file(__DIR__.'/form-proof.json')) {
        echo '<p>Technische Vorprüfung – noch kein Passwort eingeben.</p><form method="post"><input type="hidden" name="csrf" value="'.$token.'"><input type="hidden" name="probe" value="1"><button>Geschützten Formularweg prüfen</button></form>';
    } else {
        echo '<p>Nur das bestehende Passwort der isolierten Testdatenbank. Kein Reset, keine Produktionsdaten.</p><form method="post" autocomplete="off"><input type="hidden" name="csrf" value="'.$token.'"><label>Testdatenbank-Passwort <input type="password" name="password" autocomplete="off" required maxlength="1024"></label><button>Passwort geschützt übergeben</button></form>';
    }
} catch (Throwable $error) { deny(); }
