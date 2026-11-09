<?php
declare(strict_types=1);
namespace Mosa2\Fundamentals;
use PDO;
use function Mosa2\Phase2\{check,same,qi,connection};
require_once dirname(__DIR__).'/schema6_apply.php';
require_once __DIR__.'/curated.php';
require_once __DIR__.'/xbrl_evidence.php';
require_once __DIR__.'/esef_evidence.php';
require_once __DIR__.'/hkex_evidence.php';
require_once __DIR__.'/nel_q2_evidence.php';

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
        check(in_array($r['period_type'],['fy','fq','snapshot'],true),'period_kind');
        $snapshot=$r['period_type']==='snapshot';
        check($r['period_type']==='fq'?in_array($r['fiscal_quarter'],['1','2','3','4'],true):$r['fiscal_quarter']===null,'quarter');
        same($r['estimate_horizon'],null,'estimate');
        if($snapshot){
            foreach(['fiscal_year','period_start','period_end'] as $k)same($r[$k],null,'snapshot_period');
            check(is_string($r['as_of_at']??null),'snapshot_as_of');
        }else{
        check(preg_match('/\A[1-9][0-9]{3}\z/',$r['fiscal_year'])===1,'fiscal_year');
        foreach(['period_start','period_end'] as $k){$d=\DateTimeImmutable::createFromFormat('!Y-m-d',$r[$k]);check($d!==false&&$d->format('Y-m-d')===$r[$k],'date');}
        check($r['period_start']<$r['period_end'],'period_bounds');
        if(($plan['fiscal_calendar']??null)==='reported_fy'){
            same($r['period_type'],'fy','reported_fy_only');
            $period=$plan['reported_periods'][$r['fiscal_year']]??null;check(is_array($period),'reported_period');
            same($r['period_start'],$period['start'],'reported_start');same($r['period_end'],$period['end'],'reported_end');
            $days=(int)(new \DateTimeImmutable($r['period_start']))->diff(new \DateTimeImmutable($r['period_end']))->days+1;
            check(in_array($days,[364,365,366,371],true),'annual_duration');
            check(abs((int)substr($r['period_end'],0,4)-(int)$r['fiscal_year'])<=1,'reported_year_bound');
            check(in_array($plan['parser_key'],['sec_companyfacts_us_gaap_v1','esef_ifrs_inline_v1'],true),'reported_period_parser');
        }else{
        $month=$plan['fiscal_year_start_month']??null;check(is_int($month)&&$month>=1&&$month<=12,'fiscal_calendar');
        $year=(int)$r['fiscal_year']-($month===1?0:1);
        $start=new \DateTimeImmutable(sprintf('%04d-%02d-01',$year,$month));
        if($r['period_type']==='fq')$start=$start->modify('+'.(3*((int)$r['fiscal_quarter']-1)).' months');
        $end=$start->modify('+'.($r['period_type']==='fy'?12:3).' months')->modify('-1 day');
        same($r['period_start'],$start->format('Y-m-d'),'fiscal_start');same($r['period_end'],$end->format('Y-m-d'),'fiscal_end');
        }
        }
        foreach(['as_of_at','reported_at','observed_at'] as $k)timestamp($r[$k]);
        same($r['observed_at'],$plan['metadata']['observed_at'],'observation_time');
        check($r['reported_at']===null||$r['reported_at']<=$r['observed_at'],'publication_time');
        if($snapshot)check($r['as_of_at']<=($r['reported_at']??$r['observed_at']),'snapshot_as_of_future');
        check(is_string($r['field_path'])&&strlen($r['field_path'])>0&&strlen($r['field_path'])<=512,'field_path');
        $period=array_intersect_key($r,array_flip(['period_type','fiscal_year','fiscal_quarter','period_start','period_end','estimate_horizon']));
        if($snapshot)$period['as_of_at']=$r['as_of_at'];
        $r['period_key']=digest(['fundamental-period-v1',$period]);
        $slot=$r['metric_key'].':'.$r['period_type'].':'.periodPoint($r);check(!isset($slots[$slot]),'ambiguous_duplicate_period');$slots[$slot]=true;
        $records[]=$r;
    }
    return ['metrics'=>$metrics,'units'=>$units,'records'=>$records];
}
function executionBinding(array $plan,mixed $execution): void {
    if(array_key_exists('execution',$plan['metadata']??[]))same($execution,$plan['metadata']['execution'],'execution_binding');
}
function historicalScope(array $scope): void {
    check(is_int($scope['start'])&&is_int($scope['end'])&&$scope['start']>=1900&&
        $scope['end']<=(int)gmdate('Y')&&$scope['end']>=$scope['start']&&$scope['end']-$scope['start']<=9,'history_years');
    check(in_array($scope['kind'],['fy','fq','both'],true),'history_kind');
}
function historicalInventory(PDO $p,string $assetId,array $scope): array {
    historicalScope($scope);
    $rows=query($p,"SELECT o.metric_key,o.period_type,o.fiscal_year,o.fiscal_quarter,o.period_start,o.period_end,
        o.as_of_at,o.value_decimal,o.unit_key,u.monetary_currency_code,u.scale_numerator,u.scale_denominator
        FROM m2_fundamental_observations o JOIN m2_fundamental_units u
          ON u.unit_key=o.unit_key AND u.unit_version=o.unit_version
        WHERE o.asset_id=? AND (o.fiscal_year BETWEEN ? AND ? OR
          (o.period_type='snapshot' AND o.as_of_at>=? AND o.as_of_at<?)) LIMIT 513",
        [$assetId,$scope['start'],$scope['end'],$scope['start'].'-01-01',($scope['end']+1).'-01-01']);
    check(count($rows)<=512,'history_inventory_bound');
    return $rows;
}
function historicalPlan(array $plan): void {
    $scope=$plan['history_scope'];historicalScope($scope);
    same($plan['publish_current'],false,'history_current');
    check(preg_match('/\Afundamentals-history-[a-f0-9]{32}\z/',$plan['metadata']['execution']??'')===1,'history_execution');
    check(in_array($plan['source']['source_type'],['issuer_annual_report','issuer_release','issuer_quarterly_report','exchange_announcement','exchange_annual_report','regulator_xbrl'],true),
        'history_official_source');
    foreach($plan['observations'] as $row){
        $type=$row['period_type'];$year=(int)($row['fiscal_year']??substr($row['as_of_at'],0,4));
        check($year>=$scope['start']&&$year<=$scope['end'],'history_year');
        check($type==='snapshot'||($scope['kind']==='both'&&in_array($type,['fy','fq'],true))||$type===$scope['kind'],'history_period');
    }
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
function original(PDO $p,?array $before=null,int $fileLimit=128): array {
    $out=[];
    foreach(\Mosa2\CollectorSchema5\envelope(5)['tables'] as $t){
        $where='';$max=null;
        if(in_array($t,['m2_sources','m2_files'],true)){
            $max=$before[$t]['max_id']??(string)$p->query('SELECT COALESCE(MAX(id),0) FROM '.qi($t))->fetchColumn();
            check(preg_match('/\A[0-9]+\z/',$max)===1,'max_id');$where=' WHERE id<='.$max;
        }
        $limit=$max===null?128:$fileLimit;
        $rows=query($p,'SELECT * FROM '.qi($t).$where.' LIMIT '.($limit+1));check(count($rows)<=$limit,'baseline_bound');$encoded=[];
        foreach($rows as $row){foreach($row as &$v)$v=$v===null?null:bin2hex((string)$v);unset($v);$encoded[]=canonical($row);}sort($encoded,SORT_STRING);
        $out[$t]=['count'=>count($rows),'sha256'=>hash('sha256',canonical($encoded)),'max_id'=>$max];
    }
    return $out;
}
function asset(PDO $p,array $identity): string {
    check(preg_match('/\A[A-Z]{2}[A-Z0-9]{9}[0-9]\z/',$identity['isin'])===1,'isin');
    $rows=query($p,"SELECT a.entity_id,e.canonical_name FROM m2_asset_identifiers i JOIN m2_assets a ON a.entity_id=i.asset_id JOIN m2_entities e ON e.id=a.entity_id WHERE i.identifier_type='isin' AND i.normalized_value=? AND i.scope_key='' AND i.valid_to IS NULL AND a.asset_class='equity' AND a.status='active' AND e.status='active' LIMIT 2",[$identity['isin']]);
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
/** Explicit bounded preservation scope supplied by the manual pilot, not issuer-specific policy. */
function protectedAssets(PDO $p,array $identities): array {
    $out=[];
    foreach($identities as $identity){$id=asset($p,$identity);
        foreach(['m2_fundamental_observations'=>'observations','m2_fundamental_current'=>'current'] as $t=>$kind){
            $period=$identity['period_type']??null;check($period===null||in_array($period,['fy','fq'],true),'preservation_period');
            $rows=query($p,'SELECT * FROM '.qi($t).' WHERE asset_id=?'.($period===null?'':' AND period_type=?').' LIMIT 257',$period===null?[$id]:[$id,$period]);check(count($rows)<=256,'preservation_bound');
            same(count($rows),$identity[$kind],'preservation_count');$encoded=[];
            foreach($rows as $row){foreach($row as &$v)$v=$v===null?null:bin2hex((string)$v);unset($v);$encoded[]=canonical($row);}sort($encoded,SORT_STRING);
            $out[$id][$kind]=['count'=>count($rows),'sha256'=>hash('sha256',canonical($encoded))];
        }
    }return $out;
}
function counts(PDO $p): array {
    $out=[];foreach(['m2_sources','m2_files',...\Mosa2\CollectorSchema5\FUNDAMENTALS] as $t)
        $out[$t]=(int)$p->query('SELECT COUNT(*) FROM '.qi($t))->fetchColumn();return $out;
}
function receiptKeys(string $table): array {
    return match($table){
        'm2_fundamental_metrics'=>['metric_key'],
        'm2_fundamental_units'=>['unit_key','unit_version'],
        'm2_fundamental_current'=>['asset_id','metric_key','period_type'],
        'm2_sources','m2_files','m2_provider_fetches','m2_fundamental_observations'=>['id'],
    };
}
function rowKey(string $table,array $row): string {
    return canonical(array_map(static fn($k)=>(string)$row[$k],receiptKeys($table)));
}
/** Bounded row fingerprints keyed by primary identity; hashes only cross the runner boundary. */
function fundamentalBaseline(PDO $p,int $limit=256): array {
    $baseline=[];
    foreach(['m2_sources','m2_files',...\Mosa2\CollectorSchema5\FUNDAMENTALS] as $table){
        $rows=query($p,'SELECT * FROM '.qi($table).' LIMIT '.($limit+1));check(count($rows)<=$limit,'fundamental_baseline_bound');
        $map=[];
        foreach($rows as $row){
            $key=rowKey($table,$row);check(!isset($map[$key]),'fundamental_baseline_unique');
            $map[$key]=rowFingerprint($row);
        }
        ksort($map,SORT_STRING);$baseline[$table]=$map;
    }
    return $baseline;
}
function rowFingerprint(array $row): string {
    return hash('sha256',canonical(array_map(static fn($v)=>$v===null?null:bin2hex((string)$v),$row)));
}
/** Verify the exact rows first, then remove only receipt-authorized inserts/replacements. */
function assertFundamentalDelta(PDO $p,array $baseline,array $receipt,int $limit=256): void {
    $after=fundamentalBaseline($p,$limit);
    foreach($receipt['mutations'] as [$table,$row,$previous]){
        $key=rowKey($table,$row);
        check(isset($after[$table][$key]),'delta_missing_row');
        if($previous===null){
            check(!isset($baseline[$table][$key]),'delta_insert_existed');
            unset($after[$table][$key]);
        }else{
            same($table,'m2_fundamental_current','delta_update_table');
            same(rowKey($table,$previous),$key,'delta_update_slot');
            same($baseline[$table][$key]??null,rowFingerprint($previous),'delta_previous_row');
            $after[$table][$key]=$baseline[$table][$key];
        }
    }
    same($after,$baseline,'fundamental_baseline_changed');
}
function currentFields(array $r): array {return array_diff_key($r,array_flip(['id','route_id','fetch_id','field_path','dedupe_key','created_at']));}
function periodPoint(array $r): string {return $r['period_type']==='snapshot'?$r['as_of_at']:$r['period_end'];}
/** Newer period end or snapshot as-of wins, equal-date contradictions stop. */
function choose(array $rows): array {
    $slots=[];
    foreach($rows as $r){$key=$r['asset_id'].':'.$r['metric_key'].':'.$r['period_type'];
        if(!isset($slots[$key])){$slots[$key]=$r;continue;}$old=$slots[$key];
        check($r['unit_key']===$old['unit_key']&&(string)$r['unit_version']===(string)$old['unit_version']&&(string)$r['source_id']===(string)$old['source_id'],'projection_compatibility');
        if(periodPoint($r)===periodPoint($old)){same($r['dedupe_key'],$old['dedupe_key'],'equal_period_conflict');continue;}
        if(periodPoint($r)>periodPoint($old))$slots[$key]=$r;
    }return array_values($slots);
}
/** Generic insert-only catalog/facts path; no issuer-specific SQL. */
function storedFile(array $plan): array {
    $meta=$plan['metadata'];$stored=$meta;$backend='dogado_private_file';
    if(isset($plan['stored_evidence'])){
        $stored=$plan['stored_evidence'];$backend='dogado_private_evidence_json_v1';
        $curated=($stored['kind']??null)==='curated_evidence';
        same($stored['kind'],$curated?'curated_evidence':'derived_evidence','evidence_kind');same($stored['content_type'],'application/json','evidence_mime');
        $raw=$plan['evidence_json'];check(is_string($raw)&&strlen($raw)<=131072,'evidence_bound');
        same(strlen($raw),$stored['bytes'],'evidence_bytes');same(hash('sha256',$raw),$stored['sha256'],'evidence_hash');
        $doc=json_decode($raw,true,64,JSON_THROW_ON_ERROR);
        if($curated){curatedEvidence($plan,$doc);$backend='dogado_private_curated_evidence_v1';}
        elseif(($doc['evidence_type']??null)==='sec_companyfacts'){xbrlEvidence($plan,$doc);}
        elseif(($doc['evidence_type']??null)==='esef_inline'){esefEvidence($plan,$doc);}
        elseif(($doc['evidence_type']??null)==='hkex_pdf'){hkexEvidence($plan,$doc);}
        elseif(($doc['evidence_type']??null)==='nel_q2_pdf'){nelQ2Evidence($plan,$doc);}
        else{
        same($doc['format'],'mosa2-fundamental-evidence-v1','evidence_format');same($doc['kind'],'derived_evidence','evidence_kind');
        same(canonical($doc['source_response']),canonical($meta+['retained'=>false]),'response_binding');
        same($doc['parser'],['key'=>$plan['parser_key'],'version'=>$plan['parser_version']],'parser_binding');
        same(count($doc['facts']),count($plan['observations']),'evidence_count');
        foreach($plan['observations'] as $i=>$row){$fact=$doc['facts'][$i];
            foreach(['metric_key','period_start','period_end'] as $key)same($fact[$key],$row[$key],'evidence_fact');
            same($fact['normalized_value'],$row['value_decimal'],'evidence_value');same($fact['normalized_unit'],$row['unit_key'],'evidence_unit');
            same($fact['validation_status'],'qualified','evidence_validation');
            check(preg_match('/\Ahtml:table=[1-9][0-9]*;row=[1-9][0-9]*;column=[1-9][0-9]*\z/',$fact['position'])===1,'evidence_locator');
            foreach(['original_label','original_value','original_unit'] as $key)check(is_string($fact[$key])&&strlen($fact[$key])>0&&strlen($fact[$key])<=512,'evidence_original');
            same($row['field_path'],'evidence:facts/'.$i.';source='.$fact['position'],'evidence_path');
        }
        }
        same($doc['parser'],['key'=>$plan['parser_key'],'version'=>$plan['parser_version']],'parser_binding');
        check(str_ends_with($plan['archive']['storage_key'],'/evidence.json'),'evidence_storage');
    }
    same($plan['archive']['sha256'],$stored['sha256'],'archive_hash');same($plan['archive']['bytes'],$stored['bytes'],'archive_bytes');same($plan['archive']['durable'],true,'archive_durable');
    return ['storage_backend'=>$backend,'storage_key'=>$plan['archive']['storage_key'],'mime_type'=>$stored['content_type'],
        'byte_size'=>(string)$stored['bytes'],'sha256'=>hex2bin($stored['sha256']),'observed_at'=>$meta['observed_at']];
}
function persist(PDO $p,array $plan,string $assetId): array {
    $stored=storedFile($plan);
    if(isset($plan['history_scope']))historicalPlan($plan);
    elseif(($plan['publish_current']??true)!==true)
        check(($plan['stored_evidence']['kind']??null)==='curated_evidence'&&$plan['parser_version']==='2','projection_contract');
    $v=validate($plan);$now=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');check($now>=$plan['metadata']['observed_at'],'clock');$expected=[];$mutations=[];$beforeCounts=counts($p);$inserted=array_fill_keys(array_keys($beforeCounts),0);$updates=0;
    $record=function(string $table,array $row,string $idColumn='id')use($p,&$expected,&$mutations,&$inserted):array{
        $inserted[$table]++;$id=insert($p,$table,$row);if($idColumn==='id')$row=['id'=>$id]+$row;$expected[]=[$table,$row];$mutations[]=[$table,$row,null];return $row;};
    $catalog=function(string $table,array $definition,array $keys,bool $updated=false)use($p,$record,&$expected,$now):array{
        $rows=query($p,'SELECT * FROM '.qi($table).' WHERE '.implode(' AND ',array_map(fn($k)=>qi($k).'=?',$keys)).' LIMIT 2',array_map(fn($k)=>$definition[$k],$keys));
        check(count($rows)<=1,'catalog_unique');
        if($rows!==[]){equalRow($rows[0],$definition);$expected[]=[$table,$rows[0]];return $rows[0];}
        return $record($table,$definition+['created_at'=>$now]+($updated?['updated_at'=>$now]:[]),$table==='m2_sources'?'id':$keys[0]);
    };
    $source=$catalog('m2_sources',$plan['source'],['source_key'],true);$sourceId=(string)$source['id'];
    $meta=$plan['metadata'];
    $fileDefinition=['entity_id'=>$assetId,'source_id'=>$sourceId]+$stored;
    $curated=($plan['stored_evidence']['kind']??null)==='curated_evidence';
    $fetchDefinition=['fetch_key'=>digest([$curated?'fundamental-curated-import-v1':'fundamental-fetch-v1',$sourceId,$meta['url'],$meta['sha256'],$meta['observed_at']]),
        'source_id'=>$sourceId,'asset_id'=>$assetId,'route_id'=>null,'route_revision'=>null,'route_sha256'=>null,'job_run_id'=>null,
        'payload_sha256'=>hex2bin($meta['sha256']),'payload_bytes'=>(string)$meta['bytes'],
        'content_type'=>$meta['content_type'],'observed_at'=>$meta['observed_at'],'http_status'=>$curated?null:(string)$meta['http_status'],
        'parser_key'=>$plan['parser_key'],'parser_version'=>$plan['parser_version'],'parse_status'=>$plan['parse_status']];
    $known=query($p,'SELECT * FROM m2_provider_fetches WHERE fetch_key=? LIMIT 2',[$fetchDefinition['fetch_key']]);
    check(count($known)<=1,'fetch_unique');
    if($known!==[]){
        $fetch=$known[0];equalRow($fetch,$fetchDefinition);$expected[]=['m2_provider_fetches',$fetch];
        $files=query($p,'SELECT * FROM m2_files WHERE id=? LIMIT 2',[$fetch['file_id']]);same(count($files),1,'fetch_file');
        equalRow($files[0],$fileDefinition);$expected[]=['m2_files',$files[0]];
    }else{
        $file=$record('m2_files',$fileDefinition+['created_at'=>$now]);
        $fetch=$record('m2_provider_fetches',$fetchDefinition+['file_id'=>$file['id'],'created_at'=>$now]);
    }
    foreach($v['metrics'] as $m)$catalog('m2_fundamental_metrics',$m,['metric_key'],true);
    foreach($v['units'] as $u)$catalog('m2_fundamental_units',$u,['unit_key','unit_version']);
    $observations=[];
    foreach($v['records'] as $r){
        $m=$v['metrics'][$r['metric_key']];$u=$v['units'][$r['unit_key']];
        $fact=array_diff_key($r,array_flip(['observed_at','field_path','period_key']));
        $r['dedupe_key']=digest(['fundamental-fact-v1',$assetId,$sourceId,null,bin2hex($m['definition_sha256']),bin2hex($u['definition_sha256']),bin2hex($r['period_key']),$fact]);
        $r=['asset_id'=>$assetId,'source_id'=>$sourceId,'route_id'=>null]+$r+['fetch_id'=>$fetch['id'],'created_at'=>$now];
        $bySnapshot=$r['period_type']==='snapshot';
        $periodRows=query($p,'SELECT * FROM m2_fundamental_observations WHERE asset_id=? AND metric_key=? AND period_type=? AND '.($bySnapshot?'as_of_at=?':'fiscal_year=? AND period_end=?').' LIMIT 2',
            [$assetId,$r['metric_key'],$r['period_type'],...($bySnapshot?[$r['as_of_at']]:[$r['fiscal_year'],$r['period_end']])]);
        check(count($periodRows)<=1,'historical_period_duplicate');
        foreach($periodRows as $oldFact)same($oldFact['dedupe_key'],$r['dedupe_key'],'historical_period_conflict');
        $existing=query($p,'SELECT * FROM m2_fundamental_observations WHERE dedupe_key=? LIMIT 2',[$r['dedupe_key']]);check(count($existing)<=1,'fact_unique');
        if($existing!==[]){equalRow($existing[0],array_diff_key($r,array_flip(['observed_at','field_path','fetch_id','created_at'])));$observations[]=$existing[0];$expected[]=['m2_fundamental_observations',$existing[0]];}
        else $observations[]=$record('m2_fundamental_observations',$r);
    }
    $selected=($plan['publish_current']??true)?choose($observations):[];
    foreach($selected as $r){
        $old=query($p,'SELECT c.*,o.dedupe_key FROM m2_fundamental_current c JOIN m2_fundamental_observations o ON o.id=c.observation_id WHERE c.asset_id=? AND c.metric_key=? AND c.period_type=? FOR UPDATE',[$assetId,$r['metric_key'],$r['period_type']]);
        if($old!==[]){$previous=$old[0];$winner=choose([$previous,$r])[0];
            if($winner===$previous){unset($previous['dedupe_key']);$expected[]=['m2_fundamental_current',$previous];continue;}
        }
        $current=currentFields($r)+['observation_id'=>(string)$r['id'],'updated_at'=>$now];
        if($old===[])$record('m2_fundamental_current',$current,'asset_id');
        else{$updates++;$q=$p->prepare('UPDATE m2_fundamental_current SET '.implode(',',array_map(fn($k)=>qi($k).'=?',array_keys($current))).' WHERE asset_id=? AND metric_key=? AND period_type=?');
            check($q->execute([...array_values($current),$assetId,$r['metric_key'],$r['period_type']]),'current_update');
            unset($previous['dedupe_key']);$expected[]=['m2_fundamental_current',$current];$mutations[]=['m2_fundamental_current',$current,$previous];}
    }
    $afterCounts=[];foreach($beforeCounts as $t=>$n)$afterCounts[$t]=$n+$inserted[$t];
    return ['expected'=>$expected,'mutations'=>$mutations,'counts'=>$afterCounts,'inserted'=>$inserted,'current_updates'=>$updates,
        'metrics'=>$inserted['m2_fundamental_metrics'],'observations'=>$inserted['m2_fundamental_observations'],'current'=>$inserted['m2_fundamental_current'],
        'facts_reused'=>count($observations)-$inserted['m2_fundamental_observations'],
        'source_id'=>$sourceId,'metric_keys'=>array_keys($v['metrics'])];
}
function readback(PDO $p,array $receipt,?array $baseline=null,int $limit=256): array {
    $facts=[];
    foreach($receipt['expected'] as [$table,$row]){
        $keys=receiptKeys($table);
        $rows=query($p,'SELECT * FROM '.qi($table).' WHERE '.implode(' AND ',array_map(fn($k)=>qi($k).'=?',$keys)).' LIMIT 2',array_map(fn($k)=>$row[$k],$keys));
        same(count($rows),1,'readback_unique');equalRow($rows[0],$row);
        if($table==='m2_fundamental_observations')$facts[]=array_intersect_key($rows[0],array_flip(['id','source_id','fetch_id','metric_key','value_decimal','unit_key','period_type','fiscal_year','period_start','period_end','as_of_at','field_path']));
    }
    same(counts($p),$receipt['counts'],'exact_row_deltas');
    if($baseline!==null)assertFundamentalDelta($p,$baseline,$receipt,$limit);
    return $facts;
}
function transaction(PDO $p,array $plan,string $assetId,callable $committing,?array $baseline=null,int $limit=256): array {
    validate($plan);check($p->beginTransaction(),'begin');$commitStarted=false;
    try{if($baseline!==null)same(fundamentalBaseline($p,$limit),$baseline,'transaction_baseline_drift');
        $receipt=persist($p,$plan,$assetId);readback($p,$receipt,$baseline,$limit);$committing();$commitStarted=true;
        check($p->commit(),'commit');return $receipt;
    }catch(\Throwable $e){if(!$commitStarted&&$p->inTransaction())$p->rollBack();throw $e;}
}
function beginIndependentReadback(PDO $writer,PDO $reader): void {
    $writerId=(string)$writer->query('SELECT CONNECTION_ID()')->fetchColumn();
    $readerId=(string)$reader->query('SELECT CONNECTION_ID()')->fetchColumn();
    check(ctype_digit($writerId)&&ctype_digit($readerId)&&$readerId!==$writerId,'independent');
    check($reader->exec('SET SESSION TRANSACTION READ ONLY')!==false,'readonly_mode');
    same((int)$reader->query('SELECT @@session.transaction_read_only')->fetchColumn(),1,'readonly_mode');
    check($reader->beginTransaction(),'readonly');
}
/** A follow-up package is insert-only for its explicitly absent metric/period slots. */
function newSlots(PDO $p,string $assetId,array $scope): void {
    foreach(['observations','current'] as $kind){
        $rows=query($p,'SELECT metric_key,period_type FROM '.qi('m2_fundamental_'.$kind).' WHERE asset_id=? LIMIT 257',[$assetId]);
        same(count($rows),$scope[$kind],'target_baseline_count');
        foreach($rows as $row)check(!in_array($row['metric_key'].':'.$row['period_type'],$scope['slots'],true),'target_slot_exists');
    }
}
function inspectPlanCatalog(PDO $p,array $plan): void {
    $v=validate($plan);
    foreach([
        ['m2_sources',[$plan['source']],['source_key']],
        ['m2_fundamental_metrics',$v['metrics'],['metric_key']],
        ['m2_fundamental_units',$v['units'],['unit_key','unit_version']],
    ] as [$table,$definitions,$keys]){
        foreach($definitions as $definition){
            $rows=query($p,'SELECT * FROM '.qi($table).' WHERE '.implode(' AND ',array_map(fn($k)=>qi($k).'=?',$keys)).' LIMIT 2',array_map(fn($k)=>$definition[$k],$keys));
            check(count($rows)<=1,'catalog_unique');
            if($rows!==[])equalRow($rows[0],$definition);
        }
    }
}
function timings(PDO $p,string $assetId,string $metric,string $period='fy',?array $years=null,bool $roundtripProbe=false,bool $requireCurrent=true): array {
    check(in_array($period,['fy','fq','snapshot'],true),'timing_period');
    $snapshot=$period==='snapshot';$index=$snapshot?'ix_fund_obs_timeline':'ix_fund_obs_period';
    $order=$snapshot?'as_of_at DESC,id DESC':'fiscal_year DESC,fiscal_quarter DESC,period_end DESC,id DESC';
    $queries=['current'=>'SELECT value_decimal,unit_key,unit_version,fiscal_year,period_start,period_end,source_id,observation_id FROM m2_fundamental_current WHERE asset_id=? AND metric_key=? AND period_type=?',
        'history'=>'SELECT id,value_decimal,unit_key,unit_version,fiscal_year,period_start,period_end,as_of_at,source_id FROM m2_fundamental_observations FORCE INDEX ('.$index.') WHERE asset_id=? AND metric_key=? AND period_type=? ORDER BY '.$order.' LIMIT 20'];
    if(!$requireCurrent)unset($queries['current']);
    $out=[];
    if($roundtripProbe){$start=hrtime(true);same((int)query($p,'SELECT 1 AS probe')[0]['probe'],1,'roundtrip_probe');$out['select_one']=['client_with_tunnel_ms'=>(hrtime(true)-$start)/1e6];
        $explain=query($p,'EXPLAIN ANALYZE SELECT 1');$tree=implode(' ',array_map(fn($r)=>implode(' ',array_values($r)),$explain));
        check(preg_match('/actual time=([0-9.eE+-]+)\.\.([0-9.eE+-]+)/',$tree,$m)===1,'probe_server_timing');$out['select_one']['server_explain_actual_end_ms']=(float)$m[2];}
    if($snapshot)$years=null;
    if($years!==null){check(count($years)===2&&$years[0]<=$years[1],'timing_years');$queries['history']=str_replace(' ORDER BY',' AND fiscal_year BETWEEN ? AND ? ORDER BY',$queries['history']);}
    foreach($queries as $key=>$sql){$args=[$assetId,$metric,$period];if($key==='history'&&$years!==null)$args=[...$args,...$years];$start=hrtime(true);$rows=query($p,$sql,$args);$client=(hrtime(true)-$start)/1e6;
        if($key==='current'){
            check($rows!==[],'current_projection_missing');
            same(count($rows),1,'current_projection_duplicate');
        }
        $access=query($p,'EXPLAIN '.$sql,$args);
        check(count($access)===1,'explain_access');check($key==='current'?$access[0]['key']==='PRIMARY':$access[0]['key']===$index,'required_index');
        $explain=query($p,'EXPLAIN ANALYZE '.$sql,$args);$tree=implode("\n",array_map(fn($r)=>implode(' ',array_values($r)),$explain));
        check(preg_match('/actual time=([0-9.eE+-]+)\.\.([0-9.eE+-]+)/',$tree,$m)===1,'server_timing');
        $out[$key]=['rows'=>count($rows),'client_with_tunnel_ms'=>$client,'server_explain_actual_end_ms'=>(float)$m[2],
            'index_access'=>$access[0]['key'],'access_type'=>$access[0]['type'],'server_timing_scope'=>'EXPLAIN iterator only; const lookup may occur before timing','table_scan'=>stripos($tree,'table scan')!==false];
    }return $out;
}
function main(): int {
    ini_set('display_errors','0');ini_set('log_errors','0');$stage='INPUT';$p=null;$read=null;$commitStarted=false;
    try{
        $input=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
        check(in_array($input['action'],['inspect','apply'],true),'action');$stage='IDENTITY';
        $p=connection($input['password'],'127.0.0.1',$input['port']);\Mosa2\Phase2\preflight($p,false);locks($p);
        $stage='SCHEMA6';schema($p,$input['action']==='inspect');
        $history=isset($input['history_scope']);$limit=$history?4096:256;
        $assetId=asset($p,$input['identity']);$before=original($p,null,$history?$limit:128);$fundamentalBefore=fundamentalBaseline($p,$limit);
        $baseline=$before+['fundamentals'=>$history?bin2hex(digest($fundamentalBefore)):$fundamentalBefore];
        $protected=protectedAssets($p,$input['preserve_assets']??[]);
        $newScope=$input['new_scope']??null;if($newScope!==null)newSlots($p,$assetId,$newScope);
        foreach($input['expected_baseline_counts']??[] as $t=>$n)same($before[$t]['count'],$n,'baseline_count');\Mosa2\Schema6Apply\provenance($p);
        if($input['action']==='inspect'){
            if($newScope!==null)inspectPlanCatalog($p,$input['catalog_plan']);
            $result=['ok'=>true,'asset_id'=>$assetId,'baseline'=>$baseline,'protected'=>$protected,'schema'=>6,'tables'=>26];
            if(isset($input['history_scope']))$result['inventory']=historicalInventory($p,$assetId,$input['history_scope']);
        }
        else{
            $stage='PLAN';same($baseline,$input['baseline'],'baseline_drift');same($protected,$input['protected'],'protected_drift');same($assetId,$input['asset_id'],'asset_drift');
            $plan=$input['plan'];executionBinding($plan,$input['execution']??null);validate($plan);storedFile($plan);
            same($plan['history_scope']??null,$input['history_scope']??null,'history_scope_binding');
            if($newScope!==null){
                $slots=array_map(static fn($r)=>$r['metric_key'].':'.$r['period_type'],$plan['observations']);
                sort($slots,SORT_STRING);same($slots,$newScope['slots'],'target_plan_scope');
            }
            if(isset($plan['stored_evidence']))same(canonical(json_decode($plan['evidence_json'],true)['issuer']),canonical($input['identity']),'evidence_issuer');
            $stage='TRANSACTION';$receipt=transaction($p,$plan,$assetId,static function()use(&$stage,&$commitStarted){$stage='COMMIT';$commitStarted=true;},$fundamentalBefore,$limit);
            $stage='INDEPENDENT_READBACK';$read=connection($input['password'],'127.0.0.1',$input['port']);
            beginIndependentReadback($p,$read);
            schema($read,false);same(protectedAssets($read,$input['preserve_assets']??[]),$protected,'protected_unchanged');$verifiedFacts=readback($read,$receipt,$fundamentalBefore,$limit);same(original($read,$before,$history?$limit:128),$before,'original_unchanged');\Mosa2\Schema6Apply\provenance($read);
            $sample=$plan['observations'][0];
            $years=array_column($plan['observations'],'fiscal_year');
            $performance=timings($read,$assetId,$sample['metric_key'],$sample['period_type'],
                [min($years),max($years)],$plan['roundtrip_probe']??false,
                requireCurrent:($plan['publish_current']??true)!==false);
            check($read->commit(),'read_end');
            $result=['ok'=>true,'stage'=>'SUCCESS','metrics'=>$receipt['metrics'],'observations'=>$receipt['observations'],'current'=>$receipt['current'],
                'metric_keys'=>$receipt['metric_keys'],'facts_reused'=>$receipt['facts_reused'],'current_updates'=>$receipt['current_updates'],'protected_assets_unchanged'=>true,'fiscal_periods_validated'=>true,'market_unchanged'=>true,'collector_locked'=>true,'readback'=>'PASS','performance'=>$performance];
            if(isset($plan['stored_evidence']))$result['verified_facts']=$verifiedFacts;
        }
        echo json_encode($result,JSON_THROW_ON_ERROR);return 0;
    }catch(\Throwable){echo json_encode(['ok'=>false,'stage'=>$stage,'outcome'=>$commitStarted?'COMMIT_CONFIRMED_OR_UNKNOWN_NO_RETRY':'NOT_COMMITTED']);return 1;}
    finally{$read=null;$p=null;}
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)exit(main());
