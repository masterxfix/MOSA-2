<?php
declare(strict_types=1);
namespace Mosa2\Fundamentals;
use PDO;
use function Mosa2\Phase2\{check,same,qi,connection};
require_once dirname(__DIR__).'/schema6_apply.php';

function canonical(mixed $value): string {
    $sort=function(mixed $v)use(&$sort):mixed{if(is_array($v)){if(!array_is_list($v))ksort($v);foreach($v as &$x)$x=$sort($x);unset($x);}return $v;};
    return json_encode($sort($value),JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
}
function digest(mixed $v): string {return hash('sha256',canonical($v),true);}
function decimal(string $v): string {
    check(preg_match('/\A-?(?:0|[1-9][0-9]{0,25})(?:\.[0-9]{1,12})?\z/',$v)===1,'decimal');
    $v=str_contains($v,'.')?rtrim(rtrim($v,'0'),'.'):$v;return $v==='-0'?'0':$v;
}
function timestamp(?string $v): void {
    if($v===null)return;
    $d=\DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u',$v,new \DateTimeZone('UTC'));
    check($d!==false&&$d->format('Y-m-d H:i:s.u')===$v,'timestamp');
}
function validate(array $plan): array {
    check(count($plan['metrics'])>=1&&count($plan['metrics'])<=64,'metrics_bound');$metrics=[];$units=[];
    foreach($plan['metrics'] as $m){
        check(preg_match('/\A[a-z][a-z0-9_]{0,63}\z/',$m['metric_key'])===1&&!isset($metrics[$m['metric_key']]),'metric_key');
        same($m['value_type'],'decimal','qualified_decimal');same($m['status'],'active','metric_status');
        foreach(['display_name','category','value_semantics','dimension_key'] as $k)check(is_string($m[$k])&&$m[$k]!==''&&strlen($m[$k])<=255,'metric_definition');
        $m['definition_sha256']=digest(['fundamental-metric-v1',$m]);$metrics[$m['metric_key']]=$m;
    }
    foreach($plan['units'] as $u){
        check(preg_match('/\A[A-Z][A-Z0-9_]{0,63}\z/',$u['unit_key'])===1&&!isset($units[$u['unit_key']]),'unit_key');
        check(preg_match('/\A[1-9][0-9]{0,8}\z/',$u['unit_version'])===1,'unit_version');
        foreach(['scale_numerator','scale_denominator'] as $k)check(preg_match('/\A[1-9][0-9]{0,37}\z/',$u[$k])===1,'unit_scale');
        same($u['status'],'frozen','unit_status');
        check(in_array($u['dimension_key'],['monetary','monetary_per_share'],true)?preg_match('/\A[A-Z]{3}\z/',$u['monetary_currency_code']??'')===1:$u['monetary_currency_code']===null,'unit_currency');
        $u['definition_sha256']=digest(['fundamental-unit-v1',$u]);$units[$u['unit_key']]=$u;
    }
    $records=[];$slots=[];
    check(count($plan['observations'])>=1&&count($plan['observations'])<=256,'observation_bound');
    foreach($plan['observations'] as $r){
        $m=$metrics[$r['metric_key']]??null;$u=$units[$r['unit_key']]??null;check($m!==null&&$u!==null,'catalog_binding');
        same($r['value_type'],$m['value_type'],'type');same($r['dimension_key'],$m['dimension_key'],'metric_dimension');same($r['dimension_key'],$u['dimension_key'],'unit_dimension');same($r['unit_version'],$u['unit_version'],'unit_version');
        same($r['value_text'],null,'value_text');same($r['value_date'],null,'value_date');$r['value_decimal']=decimal($r['value_decimal']);
        // Explicitly qualified FY policy. Other period kinds remain raw until qualified.
        same($r['period_type'],'fy','period_kind');same($r['fiscal_quarter'],null,'quarter');same($r['estimate_horizon'],null,'estimate');
        check(preg_match('/\A[1-9][0-9]{3}\z/',$r['fiscal_year'])===1,'fiscal_year');
        foreach(['period_start','period_end'] as $k){$d=\DateTimeImmutable::createFromFormat('!Y-m-d',$r[$k]);check($d!==false&&$d->format('Y-m-d')===$r[$k],'date');}
        check($r['period_start']<$r['period_end'],'period_bounds');
        foreach(['as_of_at','reported_at','observed_at'] as $k)timestamp($r[$k]);
        same($r['observed_at'],$plan['metadata']['observed_at'],'observation_time');
        check($r['reported_at']===null||$r['reported_at']<=$r['observed_at'],'publication_time');
        check(is_string($r['field_path'])&&strlen($r['field_path'])>0&&strlen($r['field_path'])<=512,'field_path');
        $period=array_intersect_key($r,array_flip(['period_type','fiscal_year','fiscal_quarter','period_start','period_end','estimate_horizon']));
        $r['period_key']=digest(['fundamental-period-v1',$period]);
        $slot=$r['metric_key'].':'.$r['period_type'].':'.$r['period_end'];check(!isset($slots[$slot]),'ambiguous_duplicate_period');$slots[$slot]=true;
        $records[]=$r;
    }
    return ['metrics'=>$metrics,'units'=>$units,'records'=>$records];
}
function query(PDO $p,string $sql,array $args=[]): array {$q=$p->prepare($sql);$q->execute($args);return $q->fetchAll(PDO::FETCH_ASSOC);}
function insert(PDO $p,string $table,array $row): string {
    $sql='INSERT INTO '.qi($table).' ('.implode(',',array_map('Mosa2\\Phase2\\qi',array_keys($row))).') VALUES ('.implode(',',array_fill(0,count($row),'?')).')';
    $q=$p->prepare($sql);check($q->execute(array_values($row)),'insert');return $p->lastInsertId();
}
function equalRow(array $actual,array $expected): void {
    foreach($expected as $k=>$v){check(array_key_exists($k,$actual),'readback_column');$a=$actual[$k];
        if($k==='value_decimal'&&$v!==null)same(decimal((string)$a),decimal((string)$v),'readback_decimal');
        else same($a===null?null:(string)$a,$v===null?null:(string)$v,'readback_value');}
}
function original(PDO $p,?array $before=null): array {
    $out=[];
    foreach(\Mosa2\CollectorSchema5\envelope(5)['tables'] as $t){
        $where='';$max=null;
        if(in_array($t,['m2_sources','m2_files'],true)){
            $max=$before[$t]['max_id']??(string)$p->query('SELECT COALESCE(MAX(id),0) FROM '.qi($t))->fetchColumn();
            check(preg_match('/\A[0-9]+\z/',$max)===1,'max_id');$where=' WHERE id<='.$max;
        }
        $rows=query($p,'SELECT * FROM '.qi($t).$where.' LIMIT 129');check(count($rows)<=128,'baseline_bound');$encoded=[];
        foreach($rows as $row){foreach($row as &$v)$v=$v===null?null:bin2hex((string)$v);unset($v);$encoded[]=canonical($row);}sort($encoded,SORT_STRING);
        $out[$t]=['count'=>count($rows),'sha256'=>hash('sha256',canonical($encoded)),'max_id'=>$max];
    }
    same($out['m2_market_current']['count'],5,'five_current');same($out['m2_market_observations']['count'],28,'28_observations');return $out;
}
function asset(PDO $p,array $identity): string {
    check(preg_match('/\A[A-Z]{2}[A-Z0-9]{9}[0-9]\z/',$identity['isin'])===1,'isin');
    $rows=query($p,"SELECT a.entity_id,e.canonical_name FROM m2_asset_identifiers i JOIN m2_assets a ON a.entity_id=i.asset_id JOIN m2_entities e ON e.id=a.entity_id WHERE i.identifier_type='isin' AND i.normalized_value=? AND i.scope_key='' AND i.valid_to IS NULL AND e.status='active' LIMIT 2",[$identity['isin']]);
    same(count($rows),1,'unique_asset');same($rows[0]['canonical_name'],$identity['name'],'asset_name');return (string)$rows[0]['entity_id'];
}
function locks(PDO $p): void {
    foreach(['m2-fundamentals-pilot','m2-schema6-apply','m2-current-refresh','m2-collector-scheduler'] as $name){$r=query($p,'SELECT GET_LOCK(?,0) AS acquired',[$name]);same((int)$r[0]['acquired'],1,'lock_busy');}
    \Mosa2\Schema6Apply\quiet($p);
}
function schema(PDO $p,bool $full): void {
    same(\Mosa2\Phase2\tables($p),\Mosa2\CollectorSchema5\envelope(6)['tables'],'schema6_tables');
    \Mosa2\Schema6Apply\ledger($p,6);\Mosa2\CollectorSchema5\lockedDatabase($p);
    if($full)\Mosa2\CollectorSchema6\database($p);
}
function emptyFundamentals(PDO $p): void {foreach(\Mosa2\CollectorSchema5\FUNDAMENTALS as $t)same((int)$p->query('SELECT COUNT(*) FROM '.qi($t))->fetchColumn(),0,'pilot_initial_fundamentals');}
function currentFields(array $r): array {return array_diff_key($r,array_flip(['id','route_id','fetch_id','field_path','dedupe_key','created_at']));}
/** Exact FY projection: newer period wins, equal-period contradictions stop. */
function choose(array $rows): array {
    $slots=[];
    foreach($rows as $r){$key=$r['asset_id'].':'.$r['metric_key'].':'.$r['period_type'];
        if(!isset($slots[$key])){$slots[$key]=$r;continue;}$old=$slots[$key];
        check($r['unit_key']===$old['unit_key']&&(string)$r['unit_version']===(string)$old['unit_version']&&(string)$r['source_id']===(string)$old['source_id'],'projection_compatibility');
        if($r['period_end']===$old['period_end']){same($r['dedupe_key'],$old['dedupe_key'],'equal_period_conflict');continue;}
        if($r['period_end']>$old['period_end'])$slots[$key]=$r;
    }return array_values($slots);
}
/** Generic insert-only catalog/facts path; no issuer-specific SQL. */
function persist(PDO $p,array $plan,string $assetId): array {
    $v=validate($plan);$now=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');check($now>=$plan['metadata']['observed_at'],'clock');$expected=[];
    $record=function(string $table,array $row,string $idColumn='id')use($p,&$expected):array{
        $id=insert($p,$table,$row);if($idColumn==='id')$row=['id'=>$id]+$row;$expected[]=[$table,$row];return $row;};
    $catalog=function(string $table,array $definition,array $keys,bool $updated=false)use($p,$record,&$expected,$now):array{
        $rows=query($p,'SELECT * FROM '.qi($table).' WHERE '.implode(' AND ',array_map(fn($k)=>qi($k).'=?',$keys)).' LIMIT 2',array_map(fn($k)=>$definition[$k],$keys));
        check(count($rows)<=1,'catalog_unique');
        if($rows!==[]){equalRow($rows[0],$definition);$expected[]=[$table,$rows[0]];return $rows[0];}
        return $record($table,$definition+['created_at'=>$now]+($updated?['updated_at'=>$now]:[]),$table==='m2_sources'?'id':$keys[0]);
    };
    $source=$catalog('m2_sources',$plan['source'],['source_key'],true);$sourceId=(string)$source['id'];
    $meta=$plan['metadata'];
    $file=$record('m2_files',['entity_id'=>$assetId,'source_id'=>$sourceId,'storage_backend'=>'dogado_private_file',
        'storage_key'=>$plan['archive']['storage_key'],'mime_type'=>$meta['content_type'],'byte_size'=>(string)$meta['bytes'],
        'sha256'=>hex2bin($meta['sha256']),'observed_at'=>$meta['observed_at'],'created_at'=>$now]);
    $fetch=$record('m2_provider_fetches',['fetch_key'=>digest(['fundamental-fetch-v1',$sourceId,$meta['url'],$meta['sha256'],$meta['observed_at']]),
        'source_id'=>$sourceId,'asset_id'=>$assetId,'route_id'=>null,'route_revision'=>null,'route_sha256'=>null,'job_run_id'=>null,
        'file_id'=>$file['id'],'payload_sha256'=>hex2bin($meta['sha256']),'payload_bytes'=>(string)$meta['bytes'],
        'content_type'=>$meta['content_type'],'observed_at'=>$meta['observed_at'],'http_status'=>(string)$meta['http_status'],
        'parser_key'=>$plan['parser_key'],'parser_version'=>$plan['parser_version'],'parse_status'=>$plan['parse_status'],'created_at'=>$now]);
    foreach($v['metrics'] as $m)$catalog('m2_fundamental_metrics',$m,['metric_key'],true);
    foreach($v['units'] as $u)$catalog('m2_fundamental_units',$u,['unit_key','unit_version']);
    $observations=[];
    foreach($v['records'] as $r){
        $m=$v['metrics'][$r['metric_key']];$u=$v['units'][$r['unit_key']];
        $fact=array_diff_key($r,array_flip(['observed_at','field_path','period_key']));
        $r['dedupe_key']=digest(['fundamental-fact-v1',$assetId,$sourceId,null,bin2hex($m['definition_sha256']),bin2hex($u['definition_sha256']),bin2hex($r['period_key']),$fact]);
        $r=['asset_id'=>$assetId,'source_id'=>$sourceId,'route_id'=>null]+$r+['fetch_id'=>$fetch['id'],'created_at'=>$now];
        $existing=query($p,'SELECT * FROM m2_fundamental_observations WHERE dedupe_key=? LIMIT 2',[$r['dedupe_key']]);check(count($existing)<=1,'fact_unique');
        if($existing!==[]){equalRow($existing[0],array_diff_key($r,array_flip(['observed_at','field_path','fetch_id','created_at'])));$observations[]=$existing[0];$expected[]=['m2_fundamental_observations',$existing[0]];}
        else $observations[]=$record('m2_fundamental_observations',$r);
    }
    $selected=choose($observations);
    foreach($selected as $r){
        $old=query($p,'SELECT c.*,o.dedupe_key FROM m2_fundamental_current c JOIN m2_fundamental_observations o ON o.id=c.observation_id WHERE c.asset_id=? AND c.metric_key=? AND c.period_type=? FOR UPDATE',[$assetId,$r['metric_key'],$r['period_type']]);
        if($old!==[]){$previous=$old[0];$winner=choose([$previous,$r])[0];
            if($winner===$previous){unset($previous['dedupe_key']);$expected[]=['m2_fundamental_current',$previous];continue;}
        }
        $current=currentFields($r)+['observation_id'=>(string)$r['id'],'updated_at'=>$now];
        if($old===[])$record('m2_fundamental_current',$current,'asset_id');
        else{$q=$p->prepare('UPDATE m2_fundamental_current SET '.implode(',',array_map(fn($k)=>qi($k).'=?',array_keys($current))).' WHERE asset_id=? AND metric_key=? AND period_type=?');
            check($q->execute([...array_values($current),$assetId,$r['metric_key'],$r['period_type']]),'current_update');$expected[]=['m2_fundamental_current',$current];}
    }
    return ['expected'=>$expected,'metrics'=>count($v['metrics']),'observations'=>count($observations),'current'=>count($selected),
        'source_id'=>$sourceId,'metric_keys'=>array_keys($v['metrics'])];
}
function readback(PDO $p,array $receipt): void {
    foreach($receipt['expected'] as [$table,$row]){
        $keys=isset($row['id'])?['id']:match($table){'m2_fundamental_metrics'=>['metric_key'],'m2_fundamental_units'=>['unit_key','unit_version'],default=>['asset_id','metric_key','period_type']};
        $rows=query($p,'SELECT * FROM '.qi($table).' WHERE '.implode(' AND ',array_map(fn($k)=>qi($k).'=?',$keys)).' LIMIT 2',array_map(fn($k)=>$row[$k],$keys));
        same(count($rows),1,'readback_unique');equalRow($rows[0],$row);
    }
    foreach(['m2_provider_fetches'=>1,'m2_fundamental_metrics'=>$receipt['metrics'],'m2_fundamental_units'=>1,
        'm2_fundamental_observations'=>$receipt['observations'],'m2_fundamental_current'=>$receipt['current']] as $t=>$n)
        same((int)$p->query('SELECT COUNT(*) FROM '.qi($t))->fetchColumn(),$n,'no_extra_rows');
}
function transaction(PDO $p,array $plan,string $assetId,callable $committing): array {
    validate($plan);check($p->beginTransaction(),'begin');$commitStarted=false;
    try{$receipt=persist($p,$plan,$assetId);readback($p,$receipt);$committing();$commitStarted=true;
        check($p->commit(),'commit');return $receipt;
    }catch(\Throwable $e){if(!$commitStarted&&$p->inTransaction())$p->rollBack();throw $e;}
}
function timings(PDO $p,string $assetId,string $metric): array {
    $queries=['current'=>'SELECT value_decimal,unit_key,unit_version,fiscal_year,period_start,period_end,source_id,observation_id FROM m2_fundamental_current WHERE asset_id=? AND metric_key=? AND period_type=\'fy\'',
        'history'=>'SELECT id,value_decimal,unit_key,unit_version,fiscal_year,period_start,period_end,source_id FROM m2_fundamental_observations WHERE asset_id=? AND metric_key=? AND period_type=\'fy\' ORDER BY fiscal_year DESC,fiscal_quarter DESC,period_end DESC,id DESC LIMIT 20'];
    $out=[];
    foreach($queries as $key=>$sql){$args=[$assetId,$metric];$start=hrtime(true);$rows=query($p,$sql,$args);$client=(hrtime(true)-$start)/1e6;
        $explain=query($p,'EXPLAIN ANALYZE '.$sql,$args);$tree=implode("\n",array_map(fn($r)=>implode(' ',array_values($r)),$explain));
        check(preg_match('/actual time=([0-9.eE+-]+)\.\.([0-9.eE+-]+)/',$tree,$m)===1,'server_timing');
        $out[$key]=['rows'=>count($rows),'client_with_tunnel_ms'=>$client,'server_explain_actual_end_ms'=>(float)$m[2],
            'index_access'=>stripos($tree,'index')!==false||stripos($tree,'single-row')!==false,'table_scan'=>stripos($tree,'table scan')!==false];
    }return $out;
}
function main(): int {
    ini_set('display_errors','0');ini_set('log_errors','0');$stage='INPUT';$p=null;$read=null;$commitStarted=false;
    try{
        $input=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
        check(in_array($input['action'],['inspect','apply'],true),'action');$stage='IDENTITY';
        $p=connection($input['password'],'127.0.0.1',$input['port']);\Mosa2\Phase2\preflight($p,false);locks($p);
        $stage='SCHEMA6';schema($p,$input['action']==='inspect');emptyFundamentals($p);
        $assetId=asset($p,$input['identity']);$before=original($p);\Mosa2\Schema6Apply\provenance($p);
        if($input['action']==='inspect'){$result=['ok'=>true,'asset_id'=>$assetId,'baseline'=>$before,'schema'=>6,'tables'=>26];}
        else{
            $stage='PLAN';same($before,$input['baseline'],'baseline_drift');same($assetId,$input['asset_id'],'asset_drift');
            $plan=$input['plan'];validate($plan);same($plan['archive']['sha256'],$plan['metadata']['sha256'],'archive_hash');same($plan['archive']['bytes'],$plan['metadata']['bytes'],'archive_bytes');same($plan['archive']['durable'],true,'archive_durable');
            check(query($p,'SELECT id FROM m2_sources WHERE source_key=? LIMIT 1',[$plan['source']['source_key']])===[],'new_source_only');
            $stage='TRANSACTION';$receipt=transaction($p,$plan,$assetId,static function()use(&$stage,&$commitStarted){$stage='COMMIT';$commitStarted=true;});
            $stage='INDEPENDENT_READBACK';$read=connection($input['password'],'127.0.0.1',$input['port']);
            check($read->query('SELECT CONNECTION_ID()')->fetchColumn()!==$p->query('SELECT CONNECTION_ID()')->fetchColumn(),'independent');
            $read->exec('SET TRANSACTION READ ONLY');check($read->beginTransaction(),'readonly');
            schema($read,false);readback($read,$receipt);same(original($read,$before),$before,'original_unchanged');\Mosa2\Schema6Apply\provenance($read);
            foreach(['m2_sources','m2_files'] as $t)same((int)$read->query('SELECT COUNT(*) FROM '.qi($t))->fetchColumn(),$before[$t]['count']+1,'one_new_evidence_row');
            $performance=timings($read,$assetId,$receipt['metric_keys'][0]);check($read->commit(),'read_end');
            $result=['ok'=>true,'stage'=>'SUCCESS','metrics'=>$receipt['metrics'],'observations'=>$receipt['observations'],'current'=>$receipt['current'],
                'metric_keys'=>$receipt['metric_keys'],'market_unchanged'=>true,'collector_locked'=>true,'readback'=>'PASS','performance'=>$performance];
        }
        echo json_encode($result,JSON_THROW_ON_ERROR);return 0;
    }catch(\Throwable){echo json_encode(['ok'=>false,'stage'=>$stage,'outcome'=>$commitStarted?'COMMIT_CONFIRMED_OR_UNKNOWN_NO_RETRY':'NOT_COMMITTED']);return 1;}
    finally{$read=null;$p=null;}
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)exit(main());
