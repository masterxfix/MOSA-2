<?php
declare(strict_types=1);

use function Mosa2\Phase2\connection;

if (PHP_SAPI!=='cli' || realpath($_SERVER['SCRIPT_FILENAME']??'')!==__FILE__) exit(1);
ini_set('display_errors','0');
ini_set('log_errors','0');
umask(0077);

require_once __DIR__.'/../phase2/postcheck.php';

try {
    $project=dirname(__DIR__,2);
    $periodic=dirname($project,2);
    $subscription=dirname($periodic,3);
    if ($periodic!==$subscription.'/private/mosa2-collector/periodic' || realpath($periodic)!==$periodic)
        throw new RuntimeException('periodic_path');
    $config=$subscription.'/mosa2-market-write-private/access.php';
    if (realpath($config)!==$config || (fileperms($config)&0777)!==0600) throw new RuntimeException('private_config');
    $dbConfig=require $config;
    if (($dbConfig['user']??null)!=='h29077_mosa2_test'
        || ($dbConfig['dsn']??null)!=='mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4')
        throw new RuntimeException('test_database_only');
    $db=connection($dbConfig['password']);
    // Keep this lock while the child plans, writes and reads back the batch.
    if ((int)$db->query("SELECT GET_LOCK('m2-collector-scheduler',0)")->fetchColumn()!==1) exit(0);
    try {
        $ids=$db->query("SELECT DISTINCT i.normalized_value FROM m2_asset_identifiers i
            JOIN m2_assets a ON a.entity_id=i.asset_id AND a.status='active'
            JOIN m2_entities e ON e.id=a.entity_id AND e.status='active'
            WHERE i.identifier_type='isin' AND i.scope_key='' AND i.is_primary=1
              AND i.valid_to IS NULL AND (i.valid_from IS NULL OR i.valid_from<=UTC_TIMESTAMP(6))
            ORDER BY i.normalized_value")->fetchAll(PDO::FETCH_COLUMN);
        $python='/opt/alt/python311/bin/python3.11';
        $worker=proc_open([$python,'-I','-B',__DIR__.'/gettex_tick.py'],
            [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes,$project,
            ['PATH'=>'/opt/plesk/php/8.4/bin:/usr/bin:/bin','LANG'=>'C.UTF-8']);
        if (!is_resource($worker)) throw new RuntimeException('worker_start');
        $input=json_encode(['periodic'=>$periodic,'project'=>$project,'web'=>$subscription.'/mosa2-test.scharwerk.de',
            'password'=>$dbConfig['password'],'is_registry'=>$ids,'python'=>$python,'php'=>PHP_BINARY],JSON_THROW_ON_ERROR);
        unset($dbConfig);
        fwrite($pipes[0],$input);
        fclose($pipes[0]);
        unset($input);
        $output=stream_get_contents($pipes[1],32768);
        $errors=stream_get_contents($pipes[2],32768);
        fclose($pipes[1]);fclose($pipes[2]);
        if (proc_close($worker)!==0 || $errors!=='') throw new RuntimeException('worker_failed');
        echo $output;
    } finally {
        $db->query("SELECT RELEASE_LOCK('m2-collector-scheduler')");
    }
} catch (Throwable) {
    fwrite(STDERR,"M2 gettex check failed before a confirmed result\n");
    exit(1);
}
