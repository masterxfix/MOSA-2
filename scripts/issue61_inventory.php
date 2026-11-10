<?php
declare(strict_types=1);
require_once __DIR__.'/database_reset_once.php';

use function Mosa2\Phase2\{connection, same, qi};
use function Mosa2\DatabaseReset\{counts, exactTables, grants, ledger, noForeignObjects, readOnlyBegin};

ini_set('display_errors','0');
ini_set('log_errors','0');
$stage='identity';
try {
    $input=json_decode(stream_get_contents(STDIN,8193),true,8,JSON_THROW_ON_ERROR);
    $db=connection($input['password'],'127.0.0.1',$input['port']);
    readOnlyBegin($db);
    $stage='table_inventory';
    $actual=$db->query("SELECT TABLE_NAME,TABLE_TYPE,ENGINE FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME")->fetchAll(PDO::FETCH_ASSOC);
    $tableNames=array_column($actual,'TABLE_NAME');
    exactTables($db);
    $stage='objects';
    noForeignObjects($db);
    $stage='grants';
    grants($db);
    same($db->query('SELECT CURRENT_ROLE()')->fetchColumn(),'NONE','unexpected_role');
    $stage='ledger';
    $ledger=ledger($db);
    $stage='structure';
    $structure=\Mosa2\Phase3K\structure($db,\Mosa2\CollectorSchema6\schemas());
    $hashes=[];
    foreach ($tableNames as $table) {
        $ddl=$db->query('SHOW CREATE TABLE '.qi($table))->fetch(PDO::FETCH_NUM)[1];
        $hashes[$table]=hash('sha256',preg_replace('/ AUTO_INCREMENT=\d+\b/','',$ddl));
    }
    $stage='counts';
    $counts=counts($db);
    $jobs=$db->query("SELECT COUNT(*) AS total,COALESCE(SUM(enabled=1),0) AS enabled FROM m2_jobs")->fetch(PDO::FETCH_ASSOC);
    $running=(int)$db->query("SELECT COUNT(*) FROM m2_job_runs WHERE status='running'")->fetchColumn();
    $stage='writers';
    $other=$db->query("SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE ID<>CONNECTION_ID()")->fetchColumn();
    $visibility=in_array('GRANT PROCESS ON *.* TO `h29077_mosa2_test`@`localhost`',$db->query('SHOW GRANTS')->fetchAll(PDO::FETCH_COLUMN),true)
        ? 'all_mysql_sessions' : 'own_mysql_account_only';
    $db->rollBack();
    echo json_encode(['ok'=>true,'database'=>'h29077_mosa2_test','db_account'=>'h29077_mosa2_test@localhost',
        'mysql'=>'8.0.26-16','db_port'=>3307,'schema'=>6,'structure_counts'=>$structure['counts'],
        'tables'=>$tableNames,'schema_sha256'=>$hashes,'row_counts'=>$counts,
        'ledger_versions'=>array_map('intval',array_column($ledger,'version')),'ledger_sha256'=>hash('sha256',serialize($ledger)),
        'jobs'=>array_map('intval',$jobs),'running_job_rows'=>$running,'visible_other_connections'=>(int)$other,
        'mysql_connection_visibility'=>$visibility,'events'=>0,'triggers'=>0,'routines'=>0,'database_writes'=>0],JSON_THROW_ON_ERROR),PHP_EOL;
} catch (Throwable $error) {
    $detail=$error->getMessage();
    echo json_encode(['ok'=>false,'stage'=>$stage,'actual_tables'=>isset($tableNames)?array_values(array_filter($tableNames,static fn($name)=>preg_match('/^m2_[a-z0-9_]+$/D',$name))):null,
        'reason'=>preg_match('/\A[a-z][a-z0-9_:.-]{0,100}\z/D',$detail)?$detail:'check_failed','database_writes'=>0]),PHP_EOL;
    exit(1);
}
