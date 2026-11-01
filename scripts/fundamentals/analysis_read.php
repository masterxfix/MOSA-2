<?php
 declare(strict_types=1);
 require __DIR__.'/core.php';
 use function Mosa2\Fundamentals\{query,schema,original,canonical};
 use function Mosa2\Phase2\{check,same,connection};
 function fingerprint(PDO $p):string {
 $out=[];foreach(['m2_fundamental_observations','m2_fundamental_current','m2_provider_fetches','m2_fundamental_metrics','m2_fundamental_units'] as $t){
 $rows=query($p,'SELECT * FROM '.$t.' LIMIT 257');check(count($rows)<=256,'bound');$encoded=[];
 foreach($rows as $r){foreach($r as &$v)$v=$v===null?null:bin2hex((string)$v);unset($v);$encoded[]=canonical($r);}sort($encoded);$out[$t]=$encoded;
 }return hash('sha256',canonical($out));}
 try {
 $i=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);$p=connection($i['password'],'127.0.0.1',$i['port']);
 $p->exec('SET SESSION TRANSACTION READ ONLY');$p->beginTransaction();schema($p,false);
 $before=original($p);$fp=fingerprint($p);$assets=query($p,'SELECT a.entity_id AS id,a.asset_class,e.canonical_name AS name FROM m2_assets a JOIN m2_entities e ON e.id=a.entity_id ORDER BY a.entity_id LIMIT 129');check(count($assets)<=128,'assets_bound');
 $sources=query($p,'SELECT id,source_key,source_type,display_name,base_url,enabled FROM m2_sources LIMIT 129');check(count($sources)<=128,'sources_bound');$out=[];$performance=[];
 foreach($assets as $a){
 if($a['asset_class']!=='equity')continue;
 $a['identifiers']=query($p,"SELECT normalized_value FROM m2_asset_identifiers WHERE asset_id=? AND identifier_type='isin' AND valid_to IS NULL AND scope_key='' LIMIT 3",[$a['id']]);
 $sql='SELECT o.*,u.monetary_currency_code,u.scale_numerator,u.scale_denominator,f.parser_key,f.parser_version,f.parse_status,f.http_status,fi.storage_backend,HEX(fi.sha256) AS evidence_sha256 FROM m2_fundamental_observations o JOIN m2_fundamental_units u ON u.unit_key=o.unit_key AND u.unit_version=o.unit_version JOIN m2_provider_fetches f ON f.id=o.fetch_id AND f.source_id=o.source_id JOIN m2_files fi ON fi.id=f.file_id WHERE o.asset_id=? ORDER BY o.metric_key,o.period_type,o.fiscal_year,o.fiscal_quarter,o.period_end,o.id LIMIT 257';
 $start=hrtime(true);$a['facts']=query($p,$sql,[$a['id']]);$ms=(hrtime(true)-$start)/1e6;check(count($a['facts'])<=256,'history_bound');
 $a['current']=[];foreach($a['facts'] as $r){$key=$r['metric_key'].':'.$r['period_type'];if(isset($a['current'][$key]))continue;
 $c=query($p,'SELECT observation_id FROM m2_fundamental_current WHERE asset_id=? AND metric_key=? AND period_type=?',[$a['id'],$r['metric_key'],$r['period_type']]);$a['current'][$key]=$c;}
 $a['market_sources']=query($p,'SELECT DISTINCT source_id FROM m2_market_current WHERE asset_id=? LIMIT 17',[$a['id']]);check(count($a['market_sources'])<=16,'source_bound');
 $performance[$a['id']]=['history_client_with_tunnel_ms'=>$ms];
 if($a['facts']!==[]){$r=$a['facts'][0];$performance[$a['id']]['indexed_sample']=Mosa2\Fundamentals\timings($p,(string)$a['id'],$r['metric_key'],$r['period_type'],[min(array_column($a['facts'],'fiscal_year')),max(array_column($a['facts'],'fiscal_year'))]);}
 $out[]=$a;
 }
 same(original($p,$before),$before,'original_unchanged');same(fingerprint($p),$fp,'facts_unchanged');$p->commit();
 echo json_encode(['ok'=>true,'assets'=>$out,'sources'=>$sources,'excluded_etfs'=>count(array_filter($assets,fn($a)=>$a['asset_class']==='etf')),'excluded_other'=>count(array_filter($assets,fn($a)=>!in_array($a['asset_class'],['equity','etf'],true))),'db_unchanged'=>true,'performance'=>$performance],JSON_THROW_ON_ERROR);
 }catch(Throwable){echo json_encode(['ok'=>false,'error'=>'READ_ONLY_ANALYSIS_STOP']);exit(1);}
