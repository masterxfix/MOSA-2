<?php
namespace Mosa2\MarketCoverage;
use PDO;

const READ_CONFIG = '/var/www/vhosts/web213.server10.configcenter.info/mosa2-market-read-private/access.php';
function coverageFail(string $reason): void { throw new \RuntimeException($reason); }
function bounded(PDO $db, string $sql, int $limit): array {
    $rows = $db->query($sql . ' LIMIT ' . ($limit + 1))->fetchAll(PDO::FETCH_ASSOC);
    if (count($rows) > $limit) coverageFail('coverage_scope_overflow');
    return $rows;
}
function coverageRead(): array {
    $config = require READ_CONFIG;
    if (!is_array($config) || ($config['user'] ?? null) !== 'h29077_mosa2_read'
        || ($config['dsn'] ?? null) !== 'mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4') coverageFail('coverage_target_rejected');
    $pdo = new PDO($config['dsn'], $config['user'], $config['password'], [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_EMULATE_PREPARES=>false, PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC, PDO::ATTR_STRINGIFY_FETCHES=>true, PDO::ATTR_TIMEOUT=>5]);
    unset($config);
    $pdo->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');$pdo->exec('SET SESSION TRANSACTION READ ONLY');
    if (!$pdo->beginTransaction() || (string)$pdo->query('SELECT @@session.transaction_read_only')->fetchColumn() !== '1') coverageFail('coverage_read_only_rejected');
    try {
        $assets=bounded($pdo,"SELECT e.id AS asset_id,e.canonical_name,a.display_name,a.asset_class,a.status FROM m2_entities e JOIN m2_assets a ON a.entity_id=e.id WHERE e.entity_type='asset' AND e.status='active' AND a.status='active' AND a.asset_class IN ('equity','etf') ORDER BY a.entity_id",1000);
        $identifiers=bounded($pdo,"SELECT asset_id,identifier_type,identifier_value,normalized_value,scope_key,is_primary,valid_from,valid_to,source_id FROM m2_asset_identifiers WHERE identifier_type='isin' AND scope_key='' AND valid_to IS NULL ORDER BY asset_id,id",5000);
        $routes=bounded($pdo,"SELECT r.id,r.asset_id,r.source_id,r.route_revision,r.route_type,r.external_key,r.priority,r.enabled,r.unit_contract_version,r.quote_unit_key,r.quote_unit_version,r.quantity_basis_unit_key,r.quantity_basis_unit_version,r.quantity_basis_amount,r.volume_unit_key,r.volume_unit_version,s.source_key,s.display_name AS source_name,s.source_type,s.enabled AS source_enabled,u.status AS unit_status,u.monetary_currency_code AS unit_currency FROM m2_asset_source_routes r LEFT JOIN m2_sources s ON s.id=r.source_id LEFT JOIN m2_units u ON u.unit_key=r.quote_unit_key AND u.unit_version=r.quote_unit_version AND u.unit_contract_version=r.unit_contract_version ORDER BY r.asset_id,r.source_id,r.route_revision,r.id",5000);
        $currentRaw=bounded($pdo,"SELECT c.*,o.id AS origin_id,o.asset_id AS origin_asset_id,o.source_id AS origin_source_id,o.route_id AS origin_route_id,o.observation_format_version AS origin_format_version,o.market_at AS origin_market_at,o.observed_at AS origin_observed_at,o.price AS origin_price,o.currency AS origin_currency FROM m2_market_current c LEFT JOIN m2_market_observations o ON o.id=c.observation_id ORDER BY c.asset_id",1000);
        $currents=[];$observations=[];$currentDigest=[];
        foreach($currentRaw as $row){
            $current=array_intersect_key($row,array_flip(['asset_id','source_id','route_id','observation_id','observation_format_version','route_revision','market_at','observed_at','price','currency']));$currents[]=$current;
            if($row['origin_id']!==null)$observations[]=['id'=>(string)$row['origin_id'],'asset_id'=>(string)$row['origin_asset_id'],'source_id'=>(string)$row['origin_source_id'],'route_id'=>(string)$row['origin_route_id'],'observation_format_version'=>(string)$row['origin_format_version'],'market_at'=>(string)$row['origin_market_at'],'observed_at'=>(string)$row['origin_observed_at'],'price'=>$row['origin_price']===null?null:(string)$row['origin_price'],'currency'=>$row['origin_currency']===null?null:(string)$row['origin_currency']];
            $currentDigest[]=$current;
        }
        $now=gmdate('Y-m-d H:i:s.u');$result=\Mosa2\MarketSelection\select($assets,$identifiers,$routes,$currents,$observations,$now,1800);
        $result['database']=['target'=>'h29077_mosa2_test','read_only_confirmed'=>true,'rollback_confirmed'=>false];
        $result['current_digest_sha256']=hash('sha256',json_encode($currentDigest,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
        $result['provider_requests']=0;$result['database_writes']=0;$result['database_connections']=1;
        if (!$pdo->rollBack()) coverageFail('coverage_rollback_rejected');$result['database']['rollback_confirmed']=true;
        return $result;
    } finally { if ($pdo->inTransaction()) $pdo->rollBack();$pdo=null; }
}
/** Scope the audit output to metadata. The public Actions log receives no prices or grants. */
function routeAudit(string $isin,string $password): array {
    if (preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D',$isin)!==1 || $password==='') coverageFail('audit_input');
    $coverage=coverageRead();
    $assets=array_values(array_filter($coverage['assets'],static fn($asset)=>($asset['isin']??null)===$isin));
    $writer=new PDO('mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4',
        'h29077_mosa2_test',$password,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>5]);
    unset($password);
    $writer->exec('SET SESSION TRANSACTION READ ONLY');
    if (!$writer->beginTransaction()) coverageFail('audit_begin');
    try {
        $identity=$writer->query("SELECT DATABASE() AS db,CURRENT_USER() AS account,@@session.transaction_read_only AS read_only")->fetch();
        if ($identity['db']!=='h29077_mosa2_test'||$identity['account']!=='h29077_mosa2_test@localhost'
            ||(string)$identity['read_only']!=='1') coverageFail('audit_target');
        $ledger=bounded($writer,'SELECT migration_key FROM m2_schema_migrations ORDER BY version',20);
        $source=bounded($writer,"SELECT source_key,source_type,enabled FROM m2_sources WHERE source_key='provider:gettex_mund_delayed'",2);
        $unit=bounded($writer,"SELECT unit_key,unit_version,status,monetary_currency_code FROM m2_units WHERE unit_key='EUR' AND unit_version=1",2);
        $jobs=bounded($writer,"SELECT job_key,module_key,handler_key,enabled FROM m2_jobs WHERE job_key IN ('market_collector_scheduler_v1','collector_reservations_v1') ORDER BY job_key",4);
        $gates=[];
        if(in_array('0005_collector_reservations',array_column($ledger,'migration_key'),true)){
            $gates=bounded($writer,"SELECT provider,status,stop_latched,unresolved,error_code FROM m2_collector_state WHERE provider IN ('gettex_mund_delayed_v1','boerse_frankfurt_api_v1')",4);
        }
        if ($writer->query('SELECT CURRENT_ROLE()')->fetchColumn()!=='NONE') coverageFail('audit_unresolved_roles');
        $grants=$writer->query('SHOW GRANTS FOR CURRENT_USER()')->fetchAll(PDO::FETCH_COLUMN);
        $tables=['m2_sources','m2_asset_source_routes','m2_market_observations','m2_market_current'];
        $privileges=[];
        foreach($tables as $table){
            foreach(['INSERT','UPDATE'] as $verb){
                $privileges[$table][$verb]=false;
                foreach($grants as $grant){
                    if(preg_match('/^GRANT (.+) ON (.+) TO /D',$grant,$match)!==1)continue;
                    $object=str_replace(chr(92).'_','_',str_replace(chr(96),'',$match[2]));
                    if(in_array($object,['*.*','h29077_mosa2_test.*','h29077_mosa2_test.'.$table],true)
                        &&(in_array($verb,explode(', ',$match[1]),true)||$match[1]==='ALL PRIVILEGES'))$privileges[$table][$verb]=true;
                }
            }
        }
        $asset=count($assets)===1?$assets[0]:[];
        $routes=array_map(static fn($route)=>array_intersect_key($route,array_flip([
            'source_key','route_revision','route_type','enabled','qualification','manual_qualification','quote_unit_key','currency'
        ])),$asset['routes']??[]);
        $result=['database'=>$coverage['database'],'database_connections'=>2,'provider_requests'=>0,'database_writes'=>0,
            'schema'=>array_column($ledger,'migration_key'),'gettex_source'=>$source,'eur_unit'=>$unit,'jobs'=>$jobs,
            'reservations'=>$gates,'writer_direct_grants'=>$privileges,'matching_assets'=>count($assets),
            'asset_identity'=>$asset['identity_status']??null,'asset_routes'=>$routes,'current_status'=>$asset['current_status']??null];
        if (!$writer->rollBack()) coverageFail('audit_rollback');
        return $result;
    } finally {
        if($writer->inTransaction())$writer->rollBack();
    }
}
ini_set('display_errors','0');ini_set('log_errors','0');
try {
    $result=isset($mosa_input['audit_isin'])
        ?routeAudit($mosa_input['audit_isin'],$mosa_input['writer_password'])
        :coverageRead();
    echo json_encode(['ok'=>true,'coverage'=>$result],JSON_THROW_ON_ERROR);
}
catch (\Throwable) { echo '{"ok":false,"failure":"MARKET_COVERAGE_READ_FAILED","provider_requests":0,"database_writes":0}';exit(1); }
