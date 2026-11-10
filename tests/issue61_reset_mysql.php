<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/database_reset_once.php';
use function Mosa2\DatabaseReset\{counts, emptyCounts, expectedTables, ledger, purge, schemaSignature};
use function Mosa2\Phase2\{qi, same};

if (getenv('GITHUB_ACTIONS')!=='true' || getenv('ISSUE61_ISOLATED_MYSQL')!=='1')
    throw new RuntimeException('isolated CI only');
$connect=static function(): PDO {
    $db=new PDO('mysql:host=127.0.0.1;port=3307;dbname=mosa2_reset_isolated;charset=utf8mb4','root','',
        [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false]);
    $server=$db->query('SELECT DATABASE(),@@port,@@hostname,VERSION()')->fetch(PDO::FETCH_NUM);
    same($server,['mosa2_reset_isolated',3306,getenv('ISSUE61_ISOLATED_HOST'),'8.0.46'],'fixture_identity');
    return $db;
};
$db=$connect();
$files=glob(dirname(__DIR__).'/docs/database/migrations/000[1-6]_*.sql');
sort($files);
$q=null;
foreach($files as $i=>$path) {
    $sql=preg_replace('/^--[^\r\n]*/m','',file_get_contents($path));
    foreach(explode(';',$sql) as $stmt) if(trim($stmt)!=='') $db->exec($stmt);
    $q=$db->prepare('INSERT INTO m2_schema_migrations VALUES (?,?,UNHEX(?),UTC_TIMESTAMP(6))');
    $q->execute([$i+1,basename($path,'.sql'),hash_file('sha256',$path)]);
}
$q=null;
$db->exec("INSERT INTO m2_units VALUES ('EUR',1,'mosa2-market-unit-v1','monetary','EUR',1,'EUR',1,1,
    UNHEX(SHA2('fixture',256)),'frozen',UTC_TIMESTAMP(6))");
$db->exec("INSERT INTO m2_units VALUES ('TEST',1,'mosa2-market-unit-v1','monetary','EUR',1,'EUR',1,2,
    UNHEX(SHA2('fixture-child',256)),'frozen',UTC_TIMESTAMP(6))");
try {
    $db->exec("DELETE FROM m2_units WHERE unit_key='EUR'");
    throw new RuntimeException('fixture_restrict_not_enforced');
} catch (PDOException $error) {
    same((int)$error->errorInfo[1],1451,'fixture_expected_fk_restrict');
}
$before=counts($db); $schema=schemaSignature($db); $migrations=ledger($db);
same($before['m2_jobs'],1,'fixture_bootstrap');
$db=null;
foreach (['ROLLBACK','COMMIT'] as $finish) {
    $db=$connect();
    $db->exec('SET SESSION autocommit=0');
    $db->exec('LOCK TABLES '.implode(',',array_map(static fn($t)=>qi($t).' WRITE',expectedTables())));
    same(schemaSignature($db),$schema,'fixture_structure_locked');
    same((int)$db->query("SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
        WHERE REFERENCED_TABLE_SCHEMA=DATABASE() AND TABLE_SCHEMA<>DATABASE()")->fetchColumn(),0,'fixture_fk_inventory');
    $deleted=purge($db,$before);
    same($deleted['m2_units'],2,'fixture_unit_delete');
    same($deleted['m2_jobs'],1,'fixture_bootstrap_delete');
    emptyCounts($db);
    $db->exec($finish);
    $db=null;
    $read=$connect();
    \Mosa2\DatabaseReset\readOnlyBegin($read);
    same(schemaSignature($read),$schema,'fixture_structure_preserved');
    same(ledger($read),$migrations,'fixture_ledger_preserved');
    if($finish==='ROLLBACK') same(counts($read),$before,'fixture_rollback');
    else emptyCounts($read);
    $read->rollBack(); $read=null;
}
echo "Schema 6 fixture: full purge, FK-scoped units, rollback and independent committed readback PASS\n";
