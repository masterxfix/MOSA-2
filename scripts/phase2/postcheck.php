<?php
declare(strict_types=1);
namespace Mosa2\Phase2;
use PDO;
use PDOException;
use RuntimeException;
use Throwable;

const DIGEST = '9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd';
const MODE = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY';
const TABLES = ['m2_entities','m2_sources','m2_relationships','m2_files','m2_events','m2_jobs','m2_job_runs','m2_assets','m2_asset_identifiers','m2_asset_source_routes','m2_schema_migrations','m2_sync_checkpoints','m2_module_state'];
function check(bool $ok,string $why): void { if(!$ok)throw new RuntimeException($why); }
function same(mixed $actual,mixed $expected,string $why): void {
    if(is_array($actual)&&is_array($expected)){ksort($actual);ksort($expected);}
    check($actual===$expected,$why);
}
function qi(string $name): string {
    check((bool)preg_match('/\A[a-z][a-z0-9_]*\z/D',$name),'identifier');return '`'.$name.'`';
}
function splitSql(string $text,string $delimiter): array {
    $out=[];$start=0;$depth=0;$quoted=false;$n=strlen($text);
    for($i=0;$i<$n;$i++){
        $c=$text[$i];
        if($c==="'"){if($quoted&&$i+1<$n&&$text[$i+1]==="'"){$i++;continue;}$quoted=!$quoted;}
        elseif(!$quoted){if($c==='(')$depth++;elseif($c===')'){check(--$depth>=0,'parenthesis');}
            elseif($c===$delimiter&&$depth===0){$out[]=trim(substr($text,$start,$i-$start));$start=$i+1;}}
    }
    check(!$quoted&&$depth===0,'unterminated_sql');$out[]=trim(substr($text,$start));return $out;
}
require_once __DIR__.'/check_expression.php';
function contract(string $sql,string $digest=DIGEST,array $tableOrder=TABLES): array {
    check(hash('sha256',$sql)===$digest,'migration_digest');
    $clean=preg_replace('/^\s*--[^\n]*$/m','',$sql);$statements=splitSql($clean,';');
    same(array_pop($statements),'','semicolon');$all=[];
    foreach($statements as $statement){
        check((bool)preg_match('/\ACREATE TABLE (m2_[a-z_]+)\s*\((.*)\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci\z/s',$statement,$m),'create_grammar');
        $name=$m[1];check(!isset($all[$name]),'duplicate_table');
        $t=['columns'=>[],'indexes'=>[],'fks'=>[],'checks'=>[],'ddl'=>$statement];
        foreach(splitSql($m[2],',') as $line){
            if(preg_match('/\A([a-z_0-9]+) (BIGINT UNSIGNED|INT UNSIGNED|SMALLINT UNSIGNED|TINYINT\(1\)|VARCHAR\(\d+\)|CHAR\(\d+\)|BINARY\(32\)|DATETIME\(6\)|DECIMAL\(\d+,\d+\)|JSON)(?: COLLATE ([a-z0-9_]+))? (NOT NULL|NULL)( AUTO_INCREMENT)?( DEFAULT \'\')?\z/',$line,$c)){
                $text=str_starts_with($c[2],'VARCHAR')||str_starts_with($c[2],'CHAR(');
                $t['columns'][$c[1]]=['type'=>strtolower($c[2]),'nullable'=>$c[4]==='NULL'?'YES':'NO','extra'=>empty($c[5])?'':'auto_increment','collation'=>$text?($c[3]?:'utf8mb4_0900_ai_ci'):null,'charset'=>$text?'utf8mb4':null,'default'=>empty($c[6])?null:''];
            }elseif(preg_match('/\A(PRIMARY KEY|(?:UNIQUE )?KEY ([a-z_0-9]+)) \(([^()]+)\)\z/',$line,$k)){
                $t['indexes'][$k[1]==='PRIMARY KEY'?'PRIMARY':$k[2]]=['unique'=>$k[1]==='PRIMARY KEY'||str_starts_with($k[1],'UNIQUE'),'columns'=>array_map('trim',explode(',',$k[3]))];
            }elseif(preg_match('/\ACONSTRAINT ([a-z_0-9]+) FOREIGN KEY \(([a-z_0-9]+)\) REFERENCES (m2_[a-z_]+) \(([a-z_0-9]+)\) ON DELETE RESTRICT\z/',$line,$f)){
                $t['fks'][$f[1]]=['column'=>$f[2],'table'=>$f[3],'target'=>$f[4],'delete'=>'RESTRICT'];
            }elseif(preg_match('/\ACONSTRAINT ([a-z_0-9]+) CHECK \((.*)\)\z/s',$line,$c)){$t['checks'][$c[1]]=$c[2];}
            else throw new RuntimeException('unknown_definition');
        }$all[$name]=$t;
    }
    same(array_keys($all),$tableOrder,'thirteen_table_order');return $all;
}
function tables(PDO $p): array {return $p->query('SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')->fetchAll(PDO::FETCH_COLUMN);}
function connection(string $password): PDO {
    check($password!==''&&PHP_VERSION_ID>=80400&&PHP_VERSION_ID<80500,'runtime_or_secret');
    $p=new PDO('mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4','h29077_mosa2_test',$password,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>5,PDO::ATTR_STRINGIFY_FETCHES=>false]);
    $r=$p->query('SELECT DATABASE() AS db,CURRENT_USER() AS account,VERSION() AS version,@@port AS port')->fetch();
    same($r,['db'=>'h29077_mosa2_test','account'=>'h29077_mosa2_test@localhost','version'=>'8.0.26-16','port'=>3307],'target_identity');
    $p->exec("SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci");$p->exec("SET SESSION time_zone='+00:00'");$p->exec("SET SESSION sql_mode='".MODE."'");
    $p->exec('SET SESSION lock_wait_timeout=3');$p->exec('SET SESSION innodb_lock_wait_timeout=3');return $p;
}
function preflight(PDO $p,bool $empty=true): array {
    if($empty)same(tables($p),[],'target_not_empty');
    foreach(['routines'=>'ROUTINE_SCHEMA','triggers'=>'TRIGGER_SCHEMA','events'=>'EVENT_SCHEMA'] as $kind=>$column){
        same((int)$p->query('SELECT COUNT(*) FROM information_schema.'.$kind.' WHERE '.$column.'=DATABASE()')->fetchColumn(),0,'foreign_objects:'.$kind);
    }
    $grants=$p->query('SHOW GRANTS')->fetchAll(PDO::FETCH_COLUMN);sort($grants);
    $expected=['GRANT USAGE ON *.* TO `h29077_mosa2_test`@`localhost`','GRANT ALL PRIVILEGES ON `h29077\\_mosa2\\_test`.* TO `h29077_mosa2_test`@`localhost`'];sort($expected);same($grants,$expected,'rights_changed');
    $r=$p->query('SELECT @@session.time_zone AS time_zone,@@character_set_connection AS charset,@@collation_connection AS collation,@@session.sql_mode AS sql_mode,@@foreign_key_checks AS fk_checks')->fetch();
    same($r['time_zone'],'+00:00','utc');same($r['charset'],'utf8mb4','charset');same($r['collation'],'utf8mb4_0900_ai_ci','collation');same((int)$r['fk_checks'],1,'fk_enabled');
    $a=explode(',',$r['sql_mode']);$b=explode(',',MODE);sort($a);sort($b);same($a,$b,'strict_mode');
    return ['database'=>'h29077_mosa2_test','account'=>'h29077_mosa2_test@localhost','host'=>'127.0.0.1','port'=>3307,'version'=>'8.0.26-16','tables'=>0,'grants'=>$grants,'session'=>$r];
}
function rows(PDO $p,string $sql,string $table): array {$q=$p->prepare($sql);$q->execute([$table]);return $q->fetchAll();}
function structure(PDO $p,array $schema,?string $diagnosticsPath=null,array $totals=[13,7,16,14,9]): array {
    $expected=array_keys($schema);sort($expected);same(tables($p),$expected,'table_set');$evidence=[];$counts=['tables'=>count($schema),'columns'=>0,'primary'=>0,'unique'=>0,'secondary'=>0,'foreign_keys'=>0,'checks'=>0];
    foreach($schema as $name=>$t){
        $show=$p->query('SHOW CREATE TABLE '.qi($name))->fetch(PDO::FETCH_NUM)[1];
        $meta=rows($p,'SELECT ENGINE,TABLE_COLLATION,TABLE_TYPE FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=?',$name);
        same($meta,[['ENGINE'=>'InnoDB','TABLE_COLLATION'=>'utf8mb4_0900_ai_ci','TABLE_TYPE'=>'BASE TABLE']],'table_options:'.$name);
        $columns=rows($p,'SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,EXTRA,COLLATION_NAME,CHARACTER_SET_NAME,COLUMN_DEFAULT,GENERATION_EXPRESSION FROM information_schema.columns WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? ORDER BY ORDINAL_POSITION',$name);
        $actual=[];foreach($columns as $c){same($c['GENERATION_EXPRESSION'],'','generated_column');$actual[$c['COLUMN_NAME']]=['type'=>$c['COLUMN_TYPE'],'nullable'=>$c['IS_NULLABLE'],'extra'=>$c['EXTRA'],'collation'=>$c['COLLATION_NAME'],'charset'=>$c['CHARACTER_SET_NAME'],'default'=>$c['COLUMN_DEFAULT']];}
        same(array_keys($actual),array_keys($t['columns']),'column_order:'.$name);same($actual,$t['columns'],'columns:'.$name);$counts['columns']+=count($actual);
        $indexes=rows($p,'SELECT INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SEQ_IN_INDEX,SUB_PART,INDEX_TYPE,IS_VISIBLE,COLLATION,EXPRESSION FROM information_schema.statistics WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? ORDER BY INDEX_NAME,SEQ_IN_INDEX',$name);
        $actual=[];foreach($indexes as $i){same($i['SUB_PART'],null,'prefix_index');same($i['INDEX_TYPE'],'BTREE','index_type');same($i['IS_VISIBLE'],'YES','invisible_index');same($i['EXPRESSION'],null,'expression_index');same($i['COLLATION'],'A','index_direction');$key=$i['INDEX_NAME'];$actual[$key]['unique']=(int)$i['NON_UNIQUE']===0;$actual[$key]['columns'][]=$i['COLUMN_NAME'];}
        same($actual,$t['indexes'],'indexes:'.$name);
        $constraints=rows($p,'SELECT CONSTRAINT_NAME,CONSTRAINT_TYPE,ENFORCED FROM information_schema.table_constraints WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=?',$name);$actual=[];$wanted=[];
        foreach($constraints as $c){same($c['ENFORCED'],'YES','constraint_not_enforced');$actual[$c['CONSTRAINT_NAME']]=$c['CONSTRAINT_TYPE'];}
        foreach($t['indexes'] as $key=>$v){if($key==='PRIMARY'){$wanted[$key]='PRIMARY KEY';$counts['primary']++;}elseif($v['unique']){$wanted[$key]='UNIQUE';$counts['unique']++;}else $counts['secondary']++;}
        foreach($t['fks'] as $key=>$v)$wanted[$key]='FOREIGN KEY';foreach($t['checks'] as $key=>$v)$wanted[$key]='CHECK';same($actual,$wanted,'constraints:'.$name);
        $fk=rows($p,'SELECT k.CONSTRAINT_NAME,k.COLUMN_NAME,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,k.REFERENCED_TABLE_SCHEMA,r.DELETE_RULE,r.UPDATE_RULE,r.UNIQUE_CONSTRAINT_NAME FROM information_schema.key_column_usage k JOIN information_schema.referential_constraints r ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME AND r.TABLE_NAME=k.TABLE_NAME WHERE k.TABLE_SCHEMA=DATABASE() AND k.TABLE_NAME=? AND k.REFERENCED_TABLE_NAME IS NOT NULL',$name);
        $actual=[];foreach($fk as $f){same($f['REFERENCED_TABLE_SCHEMA'],'h29077_mosa2_test','foreign_schema');check(in_array($f['UPDATE_RULE'],['NO ACTION','RESTRICT'],true),'update_rule');same($f['UNIQUE_CONSTRAINT_NAME'],'PRIMARY','fk_parent_key');$actual[$f['CONSTRAINT_NAME']]=['column'=>$f['COLUMN_NAME'],'table'=>$f['REFERENCED_TABLE_NAME'],'target'=>$f['REFERENCED_COLUMN_NAME'],'delete'=>$f['DELETE_RULE']];}same($actual,$t['fks'],'foreign_keys:'.$name);$counts['foreign_keys']+=count($fk);
        $checks=rows($p,'SELECT c.CONSTRAINT_NAME,c.CHECK_CLAUSE FROM information_schema.check_constraints c JOIN information_schema.table_constraints t ON t.CONSTRAINT_SCHEMA=c.CONSTRAINT_SCHEMA AND t.CONSTRAINT_NAME=c.CONSTRAINT_NAME WHERE t.TABLE_SCHEMA=DATABASE() AND t.TABLE_NAME=?',$name);
        $comparisons=[];$mismatch=false;
        foreach($checks as $c){
            $key=$c['CONSTRAINT_NAME'];
            check(isset($t['checks'][$key]),'unexpected_check');
            $comparison=compareCheck($name,$key,$t['checks'][$key],$c['CHECK_CLAUSE'],$show,true);
            $comparisons[]=$comparison;
            if(!$comparison['equal'])$mismatch=true;
        }
        if($diagnosticsPath!==null){
            $prior=is_file($diagnosticsPath)?json_decode(file_get_contents($diagnosticsPath),true,512,JSON_THROW_ON_ERROR):[];
            $prior[$name]=$comparisons;save($diagnosticsPath,$prior);
        }
        check(!$mismatch,'check_expressions:'.$name);
        $counts['checks']+=count($checks);
        $evidence[$name]=['show_create'=>$show,'columns'=>$columns,'indexes'=>$indexes,'constraints'=>$constraints,'foreign_keys'=>$fk,'checks'=>$checks];
    }
    same([$counts['primary'],$counts['unique'],$counts['secondary'],$counts['foreign_keys'],$counts['checks']],$totals,'structural_totals');
    return ['counts'=>$counts,'metadata'=>$evidence];
}
function reject(PDO $p,string $sql,int $errno,string $name,array &$results): void {
    try{$p->exec($sql);}catch(PDOException $e){
        $actual=(int)($e->errorInfo[1]??0);
        $results[$name]=['rejected'=>true,'mysql_errno'=>$actual,'expected_errno'=>$errno];
        same($actual,$errno,'wrong_rejection:'.$name.':expected='.$errno.':actual='.$actual);
        return;
    }
    throw new RuntimeException('not_rejected:'.$name);
}
function practical(PDO $p): array {
    $p->beginTransaction();$results=[];$plans=[];
    try{
        $now="'2026-01-01 00:00:00.000000'";
        for($i=1;$i<=128;$i++){
            $type=$i===1?'asset':'fixture';
            $p->exec("INSERT INTO m2_entities VALUES ($i,'$type','Résumé $i','active',$now,$now)");
            $p->exec("INSERT INTO m2_assets VALUES ($i,'equity','Synthetic $i','EUR','active',$now,$now)");
        }
        for($i=1;$i<=16;$i++){
            $p->exec("INSERT INTO m2_sources VALUES ($i,'source$i','derived','Synthetic $i',NULL,1,$now,$now)");
            $p->exec("INSERT INTO m2_jobs VALUES ($i,'job$i','test','test',1,$now,$now)");
            $p->exec("INSERT INTO m2_sync_checkpoints VALUES ($i,$i,'stream',NULL,NULL,$now)");
        }
        for($i=1;$i<=128;$i++){
            $src=($i%16)+1;$other=($i%128)+1;$type=$i===1?'owns':'fixture';
            $p->exec("INSERT INTO m2_relationships VALUES ($i,$i,'$type',$other,$src,NULL,NULL,$now)");
            $p->exec("INSERT INTO m2_asset_identifiers (asset_id,identifier_type,identifier_value,normalized_value,scope_key,is_primary,source_id,created_at) VALUES ($i,'isin','SYN$i','SYN$i','',1,$src,$now),($i,'ticker','T$i','T$i','XETR',0,$src,$now)");
            $p->exec("INSERT INTO m2_asset_source_routes (asset_id,source_id,route_type,external_key,priority,enabled,created_at,updated_at) VALUES ($i,$src,'quote','SYN$i',1,1,$now,$now)");
            $p->exec("INSERT INTO m2_job_runs VALUES ($i,$src,'completed',$now,$now,1,NULL,$now)");
        }
        $results['valid_entity']=((int)$p->query('SELECT COUNT(*) FROM m2_entities WHERE id=1')->fetchColumn()===1);
        reject($p,"UPDATE m2_entities SET status='invalid' WHERE id=1",3819,'entity_status',$results);
        reject($p,'UPDATE m2_sources SET enabled=2 WHERE id=1',3819,'source_boolean',$results);
        reject($p,'UPDATE m2_jobs SET enabled=2 WHERE id=1',3819,'job_boolean',$results);
        reject($p,'UPDATE m2_job_runs SET attempt_no=0 WHERE id=1',3819,'attempt_minimum',$results);
        reject($p,"UPDATE m2_job_runs SET status='invalid' WHERE id=1",3819,'run_status',$results);
        reject($p,'UPDATE m2_asset_source_routes SET enabled=2 WHERE id=1',3819,'route_boolean',$results);
        reject($p,'UPDATE m2_asset_identifiers SET is_primary=2 WHERE id=1',3819,'primary_boolean',$results);
        // Insert a new child with a missing parent. Updating an existing asset PK
        // also touches its own children and can hit DELETE/UPDATE RESTRICT first.
        reject($p,"INSERT INTO m2_relationships (from_entity_id,relationship_type,to_entity_id,created_at) VALUES (999999,'fixture',1,$now)",1452,'foreign_key',$results);
        reject($p,'DELETE FROM m2_entities WHERE id=1',1451,'delete_restrict',$results);
        reject($p,"UPDATE m2_asset_identifiers SET scope_key='' WHERE identifier_type='ticker' AND asset_id=1",3819,'ticker_scope',$results);
        reject($p,"UPDATE m2_asset_identifiers SET scope_key=NULL WHERE id=1",1048,'scope_not_null',$results);
        foreach(['isin','wkn','figi'] as $kind)reject($p,"INSERT INTO m2_asset_identifiers (asset_id,identifier_type,identifier_value,normalized_value,scope_key,is_primary,created_at) VALUES (1,'$kind','INVALID','INVALID','XETR',0,$now)",3819,$kind.'_global_scope',$results);
        reject($p,"INSERT INTO m2_asset_identifiers (asset_id,identifier_type,identifier_value,normalized_value,scope_key,is_primary,created_at) VALUES (1,'isin','SYN1','SYN1','',0,$now)",1062,'identifier_unique',$results);
        $p->exec("INSERT INTO m2_asset_identifiers (asset_id,identifier_type,identifier_value,normalized_value,scope_key,is_primary,created_at) VALUES (1,'isin','syn1','syn1','',0,$now),(1,'ticker','T1','T1','XNYS',0,$now)");
        same((int)$p->query("SELECT COUNT(*) FROM m2_asset_identifiers WHERE normalized_value='SYN1'")->fetchColumn(),1,'binary_identifier_case');$results['binary_identifier_case']=true;
        same((int)$p->query("SELECT COUNT(*) FROM m2_entities WHERE canonical_name='resume 1'")->fetchColumn(),1,'human_ai_ci');$results['human_ai_ci']=true;
        same((int)$p->query("SELECT COUNT(*) FROM m2_sources WHERE source_key='SOURCE1'")->fetchColumn(),0,'binary_source_case');$results['binary_source_case']=true;
        $queries=[
            'entity_id'=>['SELECT * FROM m2_entities WHERE id=1','PRIMARY'],
            'active_type'=>["SELECT id FROM m2_entities WHERE entity_type='asset' AND status='active' ORDER BY id LIMIT 10",'ix_entities_type_status'],
            'relationship_from'=>["SELECT to_entity_id FROM m2_relationships WHERE from_entity_id=1 AND relationship_type='owns' AND valid_to IS NULL",'ix_relationships_from'],
            'relationship_to'=>["SELECT from_entity_id FROM m2_relationships WHERE to_entity_id=2 AND relationship_type='owns' AND valid_to IS NULL",'ix_relationships_to'],
            'source_key'=>["SELECT id FROM m2_sources WHERE source_key='source1'",'uq_sources_key'],
            'global_identifier'=>["SELECT asset_id FROM m2_asset_identifiers WHERE identifier_type='isin' AND normalized_value='SYN1' AND scope_key=''",'uq_identifiers_identity'],
            'ticker_scope'=>["SELECT asset_id FROM m2_asset_identifiers WHERE identifier_type='ticker' AND normalized_value='T1' AND scope_key='XETR'",'uq_identifiers_identity'],
            'asset_identifiers'=>['SELECT id,identifier_type FROM m2_asset_identifiers WHERE asset_id=1 AND valid_to IS NULL','ix_identifiers_asset'],
            'preferred_route'=>['SELECT id,priority FROM m2_asset_source_routes WHERE asset_id=1 AND enabled=1 ORDER BY priority,id LIMIT 1','ix_routes_preferred'],
            'job_runs'=>['SELECT id,started_at FROM m2_job_runs WHERE job_id=1 ORDER BY started_at DESC,id DESC LIMIT 10','ix_job_runs_job'],
            'checkpoint'=>["SELECT id FROM m2_sync_checkpoints WHERE source_id=1 AND stream_key='stream'",'uq_checkpoints_stream']
        ];
        foreach($queries as $name=>[$sql,$key]){
            $explain=$p->query('EXPLAIN '.$sql)->fetchAll();same(count($explain),1,'plan_rows');$r=$explain[0];same($r['key'],$key,'plan_key:'.$name);check(in_array($r['type'],['const','eq_ref','ref','range'],true),'unbounded_plan:'.$name);
            $plans[$name]=['sql'=>$sql,'key'=>$r['key'],'access_type'=>$r['type'],'estimated_rows'=>$r['rows'],'extra'=>$r['Extra'],'expected_path'=>true];
        }
    }finally{if($p->inTransaction())$p->rollBack();}
    foreach(TABLES as $name)same((int)$p->query('SELECT COUNT(*) FROM '.qi($name))->fetchColumn(),0,'fixture_remaining:'.$name);
    return ['constraints'=>$results,'explain'=>$plans,'fixtures_rolled_back'=>true];
}
function save(string $path,array $report): void {
    $json=json_encode($report,JSON_PRETTY_PRINT|JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);
    check(file_put_contents($path,$json,LOCK_EX)===strlen($json)&&chmod($path,0600),'report_write');
}
function reviewablePostcheck(string $stage,array $structureCounts,array $rowCounts): bool {
    $expected=['tables'=>13,'columns'=>96,'primary'=>13,'unique'=>7,'secondary'=>16,'foreign_keys'=>14,'checks'=>9];
    ksort($structureCounts);ksort($expected);
    $names=array_keys($rowCounts);sort($names);$tables=TABLES;sort($tables);
    return $stage==='practical'&&$structureCounts===$expected&&$names===$tables
        &&count(array_filter($rowCounts,static fn($count)=>$count!==0))===0;
}
function run(string $root,bool $resume=false): array {
    check(PHP_SAPI==='cli'&&!is_link($root)&&(fileperms($root)&0077)===0,'private_cli');
    check(is_file($root.'/secret.php')&&!is_link($root.'/secret.php')&&(fileperms($root.'/secret.php')&0077)===0,'private_secret');
    check($resume===file_exists($root.'/started.json'),'start_state');
    $sql=file_get_contents($root.'/migration.sql');$schema=contract($sql);$p=connection(require $root.'/secret.php');
    if($resume){
        $report=json_decode(file_get_contents($root.'/report.json'),true,512,JSON_THROW_ON_ERROR);
        check((($report['awaiting_check_review']??false)===true||($report['awaiting_postcheck_review']??false)===true)&&($report['ok']??true)===false,'not_review_state');
        same($report['migration_sha256'],DIGEST,'resume_digest');same($report['created'],TABLES,'resume_ownership');
        $expected=TABLES;sort($expected);same(tables($p),$expected,'resume_table_set');
        preflight($p,false);
        foreach(TABLES as $name)same((int)$p->query('SELECT COUNT(*) FROM '.qi($name))->fetchColumn(),0,'resume_not_empty');
        $created=TABLES;
        unset($report['awaiting_check_review'],$report['awaiting_postcheck_review'],$report['failure'],$report['structure']);
        $report['postcheck_resumed_at_utc']=gmdate('c');
    }else{
        $report=['ok'=>false,'started_at_utc'=>gmdate('c'),'migration_sha256'=>hash('sha256',$sql),'preflight'=>preflight($p),'created'=>[]];
        $created=[];
    }
    $lock=fopen($root.'/run.lock',$resume?'c':'x');check($lock!==false&&flock($lock,LOCK_EX|LOCK_NB),'run_lock');
    if(!$resume)save($root.'/started.json',$report);
    $stage='ddl';
    try{
        if(!$resume)foreach($schema as $name=>$t){$p->exec($t['ddl']);$created[]=$name;$report['created']=$created;save($root.'/report.json',$report);}
        $stage='structure';$report['structure']=structure($p,$schema,$root.'/check-diagnostics.json');
        $stage='practical';$report['practical']=practical($p);
        $stage='ledger';
        $p->beginTransaction();
        $q=$p->prepare('INSERT INTO m2_schema_migrations (version,migration_key,checksum,applied_at) VALUES (1,?,UNHEX(?),UTC_TIMESTAMP(6))');$q->execute(['0001_core_asset_identity',DIGEST]);
        $ledger=$p->query('SELECT version,migration_key,LOWER(HEX(checksum)) AS checksum,applied_at FROM m2_schema_migrations')->fetchAll();
        same(count($ledger),1,'ledger_count');same((int)$ledger[0]['version'],1,'ledger_version');same($ledger[0]['migration_key'],'0001_core_asset_identity','ledger_key');same($ledger[0]['checksum'],DIGEST,'ledger_digest');$p->commit();
        $report['ledger']=$ledger[0];$report['final_counts']=[];
        foreach(TABLES as $name){$n=(int)$p->query('SELECT COUNT(*) FROM '.qi($name))->fetchColumn();same($n,$name==='m2_schema_migrations'?1:0,'end_count');$report['final_counts'][$name]=$n;}
        $report['ok']=true;$report['finished_at_utc']=gmdate('c');save($root.'/report.json',$report);
    }catch(Throwable $e){
        if($p->inTransaction())$p->rollBack();
        // Never retry DDL. Record exact server error; only owned successful CREATEs
        // from this empty-database run may be dropped, with FK checks left on.
        $report['failure']=['message'=>$e->getMessage(),'mysql_error'=>$e instanceof PDOException?$e->errorInfo:null];
        if(str_starts_with($e->getMessage(),'check_expressions:')){
            $report['awaiting_check_review']=true;
            save($root.'/report.json',$report);
            return $report;
        }
        $present=tables($p);$allowed=$created;sort($allowed);
        if($stage==='practical'&&$present===$allowed&&count($created)===13){
            $rowCounts=[];
            foreach(TABLES as $name)$rowCounts[$name]=(int)$p->query('SELECT COUNT(*) FROM '.qi($name))->fetchColumn();
            if(reviewablePostcheck($stage,$report['structure']['counts']??[],$rowCounts)){
                $report['awaiting_postcheck_review']=true;$report['review_empty_counts']=$rowCounts;
                save($root.'/report.json',$report);return $report;
            }
        }
        if($present===$allowed){foreach(array_reverse($created) as $name)$p->exec('DROP TABLE '.qi($name));$report['cleanup_tables_remaining']=count(tables($p));}
        else $report['cleanup_blocked']='unexpected_tables_ownership_not_proven';
        save($root.'/report.json',$report);
    }finally{flock($lock,LOCK_UN);fclose($lock);}
    return $report;
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{check(in_array($argv[1]??'',['--apply-postcheck','--resume-postcheck'],true),'explicit_action');$r=run(__DIR__,($argv[1]??'')==='--resume-postcheck');$summary=$r;unset($summary['structure']['metadata']);echo json_encode($summary,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE),PHP_EOL;exit($r['ok']?0:1);}
    catch(Throwable $e){echo json_encode(['ok'=>false,'pre_ddl_failure'=>$e instanceof PDOException?'connection_failed':$e->getMessage()]),PHP_EOL;exit(1);}
}
