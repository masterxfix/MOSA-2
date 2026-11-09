<?php
 declare(strict_types=1);
 require __DIR__.'/core.php';
 use function Mosa2\Fundamentals\{query,schema,original,canonical,rowFingerprint};
 use function Mosa2\Phase2\{check,same,connection};
 function validIsin(mixed $value):bool { return is_string($value) && preg_match('/\A[A-Z]{2}[A-Z0-9]{9}[0-9]\z/D',$value)===1; }
 function readOnly(PDO $p):bool { return in_array(strtolower((string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn()),['1','on','true'],true); }
 function fingerprint(PDO $p):string {
 $out=[];foreach(['m2_fundamental_observations','m2_fundamental_current','m2_provider_fetches','m2_fundamental_metrics','m2_fundamental_units'] as $t){
 $rows=query($p,'SELECT * FROM '.$t.' LIMIT 257');check(count($rows)<=256,'bound');$encoded=[];
 foreach($rows as $r){foreach($r as &$v)$v=$v===null?null:bin2hex((string)$v);unset($v);$encoded[]=canonical($r);}sort($encoded);$out[$t]=$encoded;
 }return hash('sha256',canonical($out));}
 function preservationFingerprints(PDO $p,string $asset):array {
     $out=[];
     foreach(['m2_fundamental_observations','m2_fundamental_current','m2_market_observations','m2_market_current'] as $table){
         $fundamental=str_starts_with($table,'m2_fundamental_');
         $rows=query($p,'SELECT * FROM '.$table.($fundamental?' WHERE asset_id<>?':'').' LIMIT 257',$fundamental?[$asset]:[]);
         check(count($rows)<=256,'preservation_bound');$hashes=array_map('Mosa2\Fundamentals\rowFingerprint',$rows);
         sort($hashes,SORT_STRING);$out[$table]=['count'=>count($rows),'sha256'=>hash('sha256',canonical($hashes))];
     }
     return $out;
 }
 /** Wire contract: current is always an object; preserve internal arrays/counts. */
 function analysisWireAssets(array $assets):array {
     foreach($assets as &$asset)$asset['current']=(object)$asset['current'];
     unset($asset);return $assets;
 }
 if(realpath($_SERVER['SCRIPT_FILENAME']??'')!==__FILE__)return;
 $phase='DB_CONNECT';
 try {
 $i=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);$targetIsin=$i['isin']??null;if($targetIsin==='')$targetIsin=null;check($targetIsin===null||validIsin($targetIsin),'isin');$targeted=$targetIsin!==null;$p=connection($i['password'],'127.0.0.1',$i['port']);
 $p->exec('SET SESSION TRANSACTION READ ONLY');$p->beginTransaction();check(readOnly($p),'read_only_transaction');$phase='SCHEMA_CHECK';schema($p,false);$identity=query($p,'SELECT DATABASE() AS database_name,CURRENT_USER() AS db_account');check(count($identity)===1&&$identity[0]['database_name']==='h29077_mosa2_test','target_database');$identity=$identity[0];
 $phase='READBACK_VALIDATION';$before=$targeted?null:original($p);$fp=fingerprint($p);$phase='ASSET_DISCOVERY';
 if($targeted){$assets=query($p,"SELECT a.entity_id AS id,a.asset_class,e.canonical_name AS name FROM m2_asset_identifiers i JOIN m2_assets a ON a.entity_id=i.asset_id JOIN m2_entities e ON e.id=a.entity_id WHERE i.identifier_type='isin' AND i.normalized_value=? AND i.scope_key='' AND i.valid_to IS NULL AND a.asset_class='equity' AND a.status='active' AND e.status='active' LIMIT 2",[$targetIsin]);check(count($assets)===1,'target_asset_unique');}
 else{$assets=query($p,'SELECT a.entity_id AS id,a.asset_class,e.canonical_name AS name FROM m2_assets a JOIN m2_entities e ON e.id=a.entity_id ORDER BY a.entity_id LIMIT 129');check(count($assets)<=128,'assets_bound');}
 $sources=[];$out=[];$performance=[];$sourceIds=[];
 foreach($assets as $a){
 if($a['asset_class']!=='equity')continue;
 $a['identifiers']=query($p,"SELECT normalized_value FROM m2_asset_identifiers WHERE asset_id=? AND identifier_type='isin' AND valid_to IS NULL AND scope_key='' LIMIT 3",[$a['id']]);
 $phase='FUNDAMENTAL_READ';
 $sql='SELECT o.id,o.asset_id,o.source_id,o.metric_key,o.value_decimal,o.unit_key,o.unit_version,o.period_type,o.fiscal_year,o.fiscal_quarter,o.period_start,o.period_end,o.as_of_at,o.fetch_id,o.field_path,u.monetary_currency_code,u.scale_numerator,u.scale_denominator,f.file_id,f.parser_key,f.parser_version,f.parse_status,f.http_status,fi.storage_backend,HEX(fi.sha256) AS evidence_sha256 FROM m2_fundamental_observations o JOIN m2_fundamental_units u ON u.unit_key=o.unit_key AND u.unit_version=o.unit_version JOIN m2_provider_fetches f ON f.id=o.fetch_id AND f.source_id=o.source_id JOIN m2_files fi ON fi.id=f.file_id AND fi.source_id=o.source_id AND fi.entity_id=o.asset_id WHERE o.asset_id=? ORDER BY o.metric_key,o.period_type,o.fiscal_year,o.fiscal_quarter,o.period_end,o.as_of_at,o.id LIMIT 257';
 $start=hrtime(true);$a['facts']=query($p,$sql,[$a['id']]);$ms=(hrtime(true)-$start)/1e6;check(count($a['facts'])<=256,'history_bound');
 if($targeted)same(count($a['facts']),(int)query($p,'SELECT COUNT(*) AS n FROM m2_fundamental_observations WHERE asset_id=?',[$a['id']])[0]['n'],'source_binding_count');
 $phase='CURRENT_READ';$a['current']=[];
 $currentFields=['metric_key','period_type','fiscal_year','fiscal_quarter','period_start','period_end','as_of_at','unit_key','unit_version','value_decimal','source_id'];
 $currents=query($p,'SELECT metric_key,period_type,observation_id,'.implode(',',array_slice($currentFields,2)).' FROM m2_fundamental_current WHERE asset_id=? ORDER BY metric_key,period_type LIMIT 257',[$a['id']]);check(count($currents)<=256,'current_bound');
 $byId=array_column($a['facts'],null,'id');
 foreach($currents as $c){
     $fact=$byId[$c['observation_id']]??null;check($fact!==null,'current_fact_missing');
     foreach($currentFields as $k)same($c[$k],$fact[$k],'current_fact_binding');
     $a['current'][$c['metric_key'].':'.$c['period_type']]=[['observation_id'=>$c['observation_id']]];
 }
 $phase='SOURCE_READ';
 if(!$targeted){$a['market_sources']=query($p,'SELECT DISTINCT source_id FROM m2_market_current WHERE asset_id=? LIMIT 17',[$a['id']]);check(count($a['market_sources'])<=16,'source_bound');}else{$a['market_sources']=[];foreach($a['facts'] as $fact)$sourceIds[(string)$fact['source_id']]=(int)$fact['source_id'];}
 $performance[$a['id']]=['history_client_with_tunnel_ms'=>$ms];
 $phase='PERFORMANCE_CHECK';
 if($a['facts']!==[]){$r=$a['facts'][0];$performance[$a['id']]['indexed_sample']=Mosa2\Fundamentals\timings($p,(string)$a['id'],$r['metric_key'],$r['period_type'],[min(array_column($a['facts'],'fiscal_year')),max(array_column($a['facts'],'fiscal_year'))]);}
 $out[]=$a;
 }
 if($targeted&&$sourceIds!==[]){$marks=implode(',',array_fill(0,count($sourceIds),'?'));$sources=query($p,"SELECT id,source_key,source_type,display_name,base_url,enabled FROM m2_sources WHERE id IN ($marks) ORDER BY id LIMIT 129",array_values($sourceIds));check(count($sources)<=128,'sources_bound');}
 $phase='READBACK_VALIDATION';
 $preserved=($targeted&&($i['preservation_fingerprints']??false)===true)?preservationFingerprints($p,(string)$assets[0]['id']):null;
 if(!$targeted)same(original($p,$before),$before,'original_unchanged');same(fingerprint($p),$fp,'facts_unchanged');$p->commit();
 $p->exec('SET SESSION TRANSACTION READ ONLY');$p->beginTransaction();check(readOnly($p),'fresh_read_only_transaction');
 if(!$targeted)same(original($p,$before),$before,'fresh_original_unchanged');same(fingerprint($p),$fp,'fresh_facts_unchanged');
 if($preserved!==null)same(preservationFingerprints($p,(string)$assets[0]['id']),$preserved,'fresh_preserved_unchanged');
 $totals=[];if(!$targeted){foreach(($i['expected_totals']??['m2_fundamental_observations'=>45,'m2_fundamental_current'=>23,'m2_market_observations'=>28,'m2_market_current'=>5]) as $t=>$n){check(in_array($t,['m2_fundamental_observations','m2_fundamental_current','m2_market_observations','m2_market_current'],true)&&is_int($n)&&$n>=0,'expected_totals');$totals[$t]=(int)$p->query('SELECT COUNT(*) FROM '.$t)->fetchColumn();same($totals[$t],$n,'baseline_count');}foreach(['DE000A0JBPG2'=>[11,6],'DE0005313704'=>[20,10],'AU000000DRO2'=>[14,7]] as $isin=>$counts){$matches=array_values(array_filter($out,fn($a)=>in_array($isin,array_column($a['identifiers'],'normalized_value'),true)));same(count($matches),1,'required_asset');same(count($matches[0]['facts']),$counts[0],'required_observations');same(count($matches[0]['current']),$counts[1],'required_current');}}else{$totals=['target_fundamental_observations'=>count($out[0]['facts']??[]),'target_fundamental_current'=>count($out[0]['current']??[])];}
 $p->commit();$phase='JSON_SERIALIZATION';
 echo json_encode(['ok'=>true,'target_isin'=>$targetIsin,'target_asset_count'=>$targeted?count($out):null,'db_identity'=>$identity,'read_only_confirmed'=>true,'market_data_read'=>!$targeted||$preserved!==null,'preservation_fingerprints'=>$preserved,'validated_totals'=>$totals,'assets'=>analysisWireAssets($out),'sources'=>$sources,'excluded_etfs'=>count(array_filter($assets,fn($a)=>$a['asset_class']==='etf')),'excluded_other'=>count(array_filter($assets,fn($a)=>!in_array($a['asset_class'],['equity','etf'],true))),'db_unchanged'=>true,'performance'=>$performance],JSON_THROW_ON_ERROR);
 }catch(Throwable $e){$code=$e instanceof JsonException?'INVALID_UTF8_OR_JSON':($e instanceof PDOException?'DB_OPERATION_FAILED':'VALIDATION_FAILED');echo json_encode(['ok'=>false,'phase'=>$phase,'error_code'=>$code]);exit(1);}
