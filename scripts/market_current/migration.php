<?php
declare(strict_types=1);
namespace Mosa2\MarketCurrentMigration;
use PDO;
use function Mosa2\Phase2\{check,same,connection};
require_once __DIR__.'/refresh.php';

function artifact(): string {return dirname(__DIR__,2).'/docs/database/migrations/0004_current_observation_provenance.sql';}
/** Extends the existing exact metadata checker; historic schema contracts stay unchanged. */
function schemas(string $root): array {
    $all=\Mosa2\Phase3K\schemas($root);$current=&$all['m2_market_current'];
    foreach(['observation_id'=>'bigint unsigned','observation_format_version'=>'tinyint unsigned','observation_dedupe_key'=>'binary(32)','route_revision'=>'int unsigned'] as $field=>$type)
        $current['columns'][$field]=['type'=>$type,'nullable'=>'YES','extra'=>'','collation'=>null,'charset'=>null,'default'=>null];
    $current['indexes']['ix_market_current_observation']=['unique'=>false,'columns'=>['observation_id']];
    $current['fks']['fk_market_current_observation']=['columns'=>['observation_id'],'table'=>'m2_market_observations','targets'=>['id'],'delete'=>'RESTRICT'];
    $sql=file_get_contents(artifact());check(preg_match('/ADD CONSTRAINT ck_market_current_provenance CHECK \((.*)\);\s*$/s',$sql,$m)===1,'migration_check_artifact');
    $current['checks']['ck_market_current_provenance']=$m[1];return $all;
}
/** Read-only preview: full facts, exact metadata, SQL checksum, no provider calls. */
function preview(PDO $p,string $root): array {
    $p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
    try{$structure=\Mosa2\Phase3K\structure($p,\Mosa2\Phase3K\schemas($root));$state=\Mosa2\MarketLive\snapshot($p);
        return ['migration_sha256'=>hash_file('sha256',artifact()),'structure'=>$structure,'state'=>$state];
    }finally{if($p->inTransaction())$p->rollBack();}
}
function digest(array $preview): string {return hash('sha256',json_encode($preview,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES));}
/** Explicitly approved preview hash. DDL auto-commits: never retry a partial application. */
function apply(string $password,string $root,array $preview,string $approvedPreviewSha256): array {
    same(digest($preview),$approvedPreviewSha256,'migration_preview_approval');$p=connection($password);$locked=false;
    try{
        $locked=(int)$p->query("SELECT GET_LOCK('m2-current-migration-4',0)")->fetchColumn()===1;check($locked,'migration_lock');
        same(preview($p,$root),$preview,'migration_preview_drift');
        $sql=file_get_contents(artifact());same(hash('sha256',$sql),$preview['migration_sha256'],'migration_artifact_drift');
        $parts=\Mosa2\Phase2\splitSql(preg_replace('/^\s*--[^\n]*$/m','',$sql),';');same(array_pop($parts),'','migration_semicolon');same(count($parts),1,'one_atomic_ddl');
        check(str_starts_with($parts[0],'ALTER TABLE m2_market_current'),'migration_scope');$p->exec($parts[0]);
        $metadata=\Mosa2\Phase3K\structure($p,schemas($root),$root.'/current-check-failure.json');
        same(\Mosa2\MarketLive\snapshot($p),$preview['state'],'migration_fact_delta');
        $p->beginTransaction();try{$q=$p->prepare("INSERT INTO m2_schema_migrations (version,migration_key,checksum,applied_at) VALUES (4,'0004_current_observation_provenance',?,UTC_TIMESTAMP(6))");$q->execute([hex2bin($preview['migration_sha256'])]);same($p->commit(),true,'migration_ledger_commit');}finally{if($p->inTransaction())$p->rollBack();}
        $after=\Mosa2\MarketLive\snapshot($p,\Mosa2\MarketCurrent\CONTRACT);$read=connection($password);unset($password);
        $read->exec('SET TRANSACTION READ ONLY');$read->beginTransaction();try{same(\Mosa2\MarketLive\snapshot($read,\Mosa2\MarketCurrent\CONTRACT),$after,'migration_independent_readback');}finally{$read->rollBack();$read=null;}
        return ['ok'=>true,'readback'=>'PASS','schema_version'=>4,'metadata'=>$metadata,'state'=>$after];
    }finally{if($p->inTransaction())$p->rollBack();if($locked)$p->query("SELECT RELEASE_LOCK('m2-current-migration-4')");$p=null;unset($password);}
}
