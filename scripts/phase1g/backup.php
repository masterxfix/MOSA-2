<?php
declare(strict_types=1);

namespace Mosa2\BackupRestore;

require_once __DIR__ . '/../phase1c/profile.php';

use PDO;
use Throwable;
use function Mosa2\Phase1B\ensure;
use function Mosa2\Phase1B\connect;
use function Mosa2\Phase1B\tableIdentifier;
use function Mosa2\History10000\{profileSpec,validateState,tableNames,ownedName,proveOwnership,counts,generatedRows,saveState,checkpoint};
use const Mosa2\Phase1B\{COLLATION,SQL_MODE};

const FORMAT = 'mosa2-synthetic-backup-v1';
const MAX_BYTES = 33554432;
const KINDS = ['entity','identity','history','current','migration'];

function validatePair(array $source, array $restore): void
{
    \Mosa2\Phase1B\validateTarget($source);
    foreach (['database','user'] as $key) {
        ensure(is_string($restore[$key] ?? null), 'restore_target_missing');
        ensure(preg_match('/\A[a-z0-9]+_mosa2_restore_test\z/D', $restore[$key]) === 1, 'restore_target_required');
    }
    ensure($restore['database'] === $restore['user'], 'restore_user_mismatch');
    ensure($restore['database'] === substr($source['database'],0,-5).'_restore_test', 'pair_prefix_mismatch');
}

function restoreConnect(array $source, array $restore, string $password): PDO
{
    validatePair($source,$restore);
    \Mosa2\Phase1B\validateRuntime(PHP_VERSION_ID,PHP_SAPI,in_array('mysql',PDO::getAvailableDrivers(),true));
    ensure($password !== '', 'restore_password_missing');
    $pdo = new PDO('mysql:host=127.0.0.1;port=3307;dbname='.$restore['database'].';charset=utf8mb4',
        $restore['user'],$password,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,
        PDO::ATTR_PERSISTENT=>false,PDO::ATTR_STRINGIFY_FETCHES=>false,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>5]);
    $o=$pdo->query('SELECT DATABASE() AS db,CURRENT_USER() AS account,@@port AS port,VERSION() AS version')->fetch();
    ensure($o['db']===$restore['database'] && explode('@',$o['account'],2)[0]===$restore['user'] && (int)$o['port']===3307 && str_starts_with($o['version'],'8.0.'),'restore_identity_mismatch');
    $pdo->exec('SET NAMES utf8mb4 COLLATE '.COLLATION);
    $pdo->exec("SET SESSION sql_mode = '".SQL_MODE."'");
    $pdo->exec("SET SESSION time_zone = '+00:00'");
    $pdo->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
    $pdo->exec('SET SESSION innodb_lock_wait_timeout=3');
    $pdo->exec('SET SESSION lock_wait_timeout=3');
    \Mosa2\Phase1B\sessionState($pdo);
    ensure(!in_array(false,\Mosa2\Phase1B\rights($pdo),true),'restore_rights_missing');
    return $pdo;
}

function canonical(array $row): string
{
    return json_encode($row,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR)."\n";
}

function batches(PDO $pdo,array $state,string $kind,float $deadline): \Generator
{
    $pk=$kind==='current'?'entity_id':'id';
    $sql='SELECT * FROM '.ownedName($state,$kind).' WHERE '.$pk.' > ? ORDER BY '.$pk.' LIMIT 500';
    $q=$pdo->prepare($sql);$last=0;$seen=0;$expected=profileSpec()['expected'][$kind];
    while(true) {
        checkpoint($deadline);$q->execute([$last]);$rows=$q->fetchAll(PDO::FETCH_NUM);
        if($rows===[])break;
        $seen+=count($rows);ensure($seen<=$expected,'scan_row_budget');
        foreach($rows as $row){ensure(is_int($row[0])&&$row[0]>$last,'primary_key_order');$last=$row[0];}
        yield $rows;
    }
    ensure($seen===$expected,'scan_count_mismatch');
}

function assertTables(PDO $pdo,array $state): void
{
    validateState($state);
    $expected=array_values($state['tables']);sort($expected);
    ensure(tableNames($pdo)===$expected,'unexpected_tables');
    foreach(KINDS as $kind)ensure(proveOwnership($pdo,$state,$kind),'owned_table_missing');
}

function snapshot(PDO $pdo,array $state,float $deadline): array
{
    assertTables($pdo,$state);
    $result=['counts'=>counts($pdo,$state),'tables'=>[]];
    foreach(KINDS as $kind) {
        checkpoint($deadline);$table=ownedName($state,$kind);
        $ddl=$pdo->query('SHOW CREATE TABLE '.$table)->fetch(PDO::FETCH_NUM)[1];
        ensure(str_starts_with($ddl,'CREATE TABLE '.$table.' ('),'unexpected_create');
        $meta=$pdo->prepare('SELECT ENGINE,TABLE_COLLATION FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=?');
        $meta->execute([$state['tables'][$kind]]);$definition=$meta->fetch();
        ensure($definition['ENGINE']==='InnoDB'&&$definition['TABLE_COLLATION']===COLLATION,'table_settings');
        $columns=$pdo->query('SHOW FULL COLUMNS FROM '.$table)->fetchAll();
        $indexes=$pdo->query('SHOW INDEX FROM '.$table)->fetchAll();
        foreach($indexes as &$index)unset($index['Cardinality']);unset($index);
        usort($indexes,static fn($a,$b)=>[$a['Key_name'],(int)$a['Seq_in_index']]<=>[$b['Key_name'],(int)$b['Seq_in_index']]);
        $hash=hash_init('sha256');$expected=generatedRows($kind);$expected->rewind();
        foreach(batches($pdo,$state,$kind,$deadline) as $batch)foreach($batch as $row) {
            ensure($expected->valid()&&$row===$expected->current(),'synthetic_fixture_mismatch');
            $expected->next();hash_update($hash,canonical($row));
        }
        ensure(!$expected->valid(),'fixture_count_mismatch');
        $result['tables'][$kind]=['ddl'=>$ddl,'engine_collation'=>$definition,'columns'=>$columns,'indexes'=>$indexes,'sha256'=>hash_final($hash)];
    }
    $e=ownedName($state,'entity');$i=ownedName($state,'identity');$h=ownedName($state,'history');$c=ownedName($state,'current');
    $orphans=(int)$pdo->query("SELECT COUNT(*) FROM $h h LEFT JOIN $e e ON e.id=h.entity_id WHERE e.id IS NULL")->fetchColumn();
    $orphans+=(int)$pdo->query("SELECT COUNT(*) FROM $i i LEFT JOIN $e e ON e.id=i.entity_id WHERE e.id IS NULL")->fetchColumn();
    $orphans+=(int)$pdo->query("SELECT COUNT(*) FROM $c c LEFT JOIN $h h ON h.id=c.history_id AND h.entity_id=c.entity_id WHERE h.id IS NULL")->fetchColumn();
    ensure($orphans===0,'orphans');
    $pairs=(int)$pdo->query("SELECT COUNT(*) FROM (SELECT entity_id,sequence_no FROM $h GROUP BY entity_id,sequence_no) x")->fetchColumn();
    ensure($pairs===profileSpec()['expected']['history'],'duplicates');
    $latest=(int)$pdo->query("SELECT COUNT(*) FROM $c c JOIN $h h ON h.entity_id=c.entity_id WHERE h.observed_at>c.observed_at OR (h.observed_at=c.observed_at AND h.id>c.history_id)")->fetchColumn();
    ensure($latest===0,'current_not_latest');
    $result['integrity']=['all_rows_match_fixture'=>true,'no_orphans'=>true,'no_duplicates'=>true,'current_latest'=>true];
    return $result;
}

function normalizedDdl(string $ddl): string
{
    // MySQL may render an inherited utf8mb4 charset explicitly after SHOW CREATE replay.
    // Full column collations and table settings are compared independently.
    return str_replace(' CHARACTER SET utf8mb4 COLLATE '.COLLATION,' COLLATE '.COLLATION,$ddl);
}

function comparison(array $before,array $after): array
{
    $checks=['counts'=>$before['counts']===$after['counts'],'structure'=>true,'checksums'=>true,'integrity'=>$before['integrity']===$after['integrity']];
    ensure(array_keys($before['tables'])===KINDS && array_keys($after['tables'])===KINDS,'comparison_tables');
    foreach(KINDS as $kind) {
        $a=$before['tables'][$kind];$b=$after['tables'][$kind];
        $checks['checksums']=$checks['checksums']&&hash_equals($a['sha256'],$b['sha256']);
        unset($a['sha256'],$b['sha256']);$a['ddl']=normalizedDdl($a['ddl']);$b['ddl']=normalizedDdl($b['ddl']);$checks['structure']=$checks['structure']&&$a===$b;
    }
    ensure(!in_array(false,$checks,true),'comparison_failed');
    return $checks;
}

function writeRecord($stream,array $record): void
{
    $line=canonical($record);ensure(strlen($line)<=262144,'record_too_large');
    ensure(fwrite($stream,$line)===strlen($line),'backup_write');
    ensure(ftell($stream)<=MAX_BYTES,'backup_size_limit');
}

function readRecord($stream): ?array
{
    $line=fgets($stream,262146);
    if($line===false){ensure(feof($stream),'backup_read');return null;}
    ensure(strlen($line)<=262144&&str_ends_with($line,"\n"),'invalid_backup_record');
    $row=json_decode($line,true,32,JSON_THROW_ON_ERROR);ensure(is_array($row),'invalid_backup_record');return $row;
}

function exportBackup(PDO $source,array $state,array $before,string $path,float $deadline): array
{
    ensure(!file_exists($path)&&!is_link($path),'backup_exists');
    $f=fopen($path,'x');ensure($f!==false&&chmod($path,0600),'backup_create');
    $start=hrtime(true);
    try {
        writeRecord($f,['format'=>FORMAT,'profile'=>profileSpec()['id'],'tables'=>$state['tables']]);
        foreach(KINDS as $kind) {
            writeRecord($f,['kind'=>$kind,'ddl'=>$before['tables'][$kind]['ddl']]);
            foreach(batches($source,$state,$kind,$deadline) as $rows)writeRecord($f,['kind'=>$kind,'rows'=>$rows]);
            writeRecord($f,['kind'=>$kind,'end'=>true]);
        }
        writeRecord($f,['complete'=>true]);ensure(fflush($f),'backup_flush');
        $size=ftell($f);
    } finally {fclose($f);}
    return ['method'=>'PDO streamed JSONL: exact SHOW CREATE TABLE and typed rows, batches <=500','bytes'=>$size,'duration_ms'=>round((hrtime(true)-$start)/1e6,4),'sha256'=>hash_file('sha256',$path)];
}

function importBackup(PDO $restore,array $state,array $before,string $path,array $backup,float $deadline): array
{
    ensure(tableNames($restore)===[],'restore_not_empty');
    ensure(is_file($path)&&!is_link($path)&&(fileperms($path)&0077)===0,'private_backup_required');
    ensure(filesize($path)===$backup['bytes']&&filesize($path)<=MAX_BYTES&&hash_equals($backup['sha256'],hash_file('sha256',$path)),'backup_hash_mismatch');
    $f=fopen($path,'r');ensure($f!==false,'backup_open');$start=hrtime(true);
    try {
        ensure(readRecord($f)===['format'=>FORMAT,'profile'=>profileSpec()['id'],'tables'=>$state['tables']],'backup_header');
        foreach(KINDS as $kind) {
            checkpoint($deadline);
            $header=readRecord($f);ensure($header===['kind'=>$kind,'ddl'=>$before['tables'][$kind]['ddl']],'backup_ddl_mismatch');
            // Only the exact trusted source DDL is accepted; the file cannot select a database.
            $restore->exec($before['tables'][$kind]['ddl']);
            ensure(proveOwnership($restore,$state,$kind),'restore_ownership');
            $restore->beginTransaction();$seen=0;
            try {
                while(true) {
                    checkpoint($deadline);$record=readRecord($f);
                    if($record===['kind'=>$kind,'end'=>true])break;
                    ensure(is_array($record)&&array_keys($record)===['kind','rows']&&$record['kind']===$kind&&is_array($record['rows']),'backup_rows');
                    $rows=$record['rows'];ensure(count($rows)>0&&count($rows)<=500,'import_batch_limit');
                    $width=count($before['tables'][$kind]['columns']);
                    foreach($rows as $row)ensure(is_array($row)&&array_is_list($row)&&count($row)===$width,'import_row_width');
                    $seen+=count($rows);ensure($seen<=profileSpec()['expected'][$kind],'import_row_budget');
                    $marks='('.implode(',',array_fill(0,$width,'?')).')';
                    $q=$restore->prepare('INSERT INTO '.ownedName($state,$kind).' VALUES '.implode(',',array_fill(0,count($rows),$marks)));
                    $q->execute(array_merge(...$rows));
                }
                ensure($seen===profileSpec()['expected'][$kind],'import_count');
                $restore->commit();
            } catch(Throwable $e) {if($restore->inTransaction())$restore->rollBack();throw $e;}
        }
        ensure(readRecord($f)===['complete'=>true]&&readRecord($f)===null,'backup_trailer');
    } finally {fclose($f);}
    return ['duration_ms'=>round((hrtime(true)-$start)/1e6,4),'target_was_empty'=>true];
}

function functional(PDO $pdo,array $state): array
{
    $set=\Mosa2\History10000\querySet($state);$expected=\Mosa2\History10000\expectedQueries();$r=[];
    foreach(['current_single','history_latest','history_window','history_wide_window','identity_lookup'] as $kind) {
        [$sql,$params]=$set[$kind];$q=$pdo->prepare($sql);$q->execute($params);
        $rows=$q->fetchAll(PDO::FETCH_NUM);ensure($rows===$expected[$kind],'restored_query_mismatch');
        $r[$kind]=['executions'=>1,'rows'=>count($rows),'exact'=>true];
    }
    return $r;
}
