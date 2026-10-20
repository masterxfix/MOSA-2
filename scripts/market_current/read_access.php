<?php
declare(strict_types=1);
namespace Mosa2\MarketReadAccess;
use PDO;
use function Mosa2\Phase2\{check,same};
require_once __DIR__.'/refresh.php';
require_once dirname(__DIR__,2).'/api/read_model.php';

/** Reject every privilege beyond SELECT / SHOW VIEW on the isolated test DB. */
function grants(array $rows,bool $literalDatabaseNames=false): void {
    $select=false;
    foreach($rows as $row){
        $grant=array_values($row)[0];
        check(!str_contains($grant,'WITH GRANT OPTION'),'read_grant_delegation');
        if(preg_match('/^GRANT USAGE ON \*\.\* TO /D',$grant))continue;
        check(preg_match('/^GRANT (SELECT(?:, SHOW VIEW)?) ON `([^`]+)`\.\* TO /D',$grant,$match)===1,'read_grant_scope');
        // With partial_revokes=OFF, bare underscores are wildcard privileges.
        check($match[2]==='h29077\\_mosa2\\_test'||($literalDatabaseNames&&$match[2]==='h29077_mosa2_test'),'read_grant_database_pattern');
        check(!str_contains($grant,'WITH GRANT OPTION'),'read_grant_delegation');$select=true;
    }check($select,'read_select_missing');
}
/** Provision the reader before migration without querying not-yet-existing columns. */
function preflight(PDO $p,array $config,string $now): array {
    $version=(string)$p->query('SELECT MAX(version) FROM m2_schema_migrations')->fetchColumn();
    if($version==='4'){$data=\Mosa2\MarketRead\read($p,$config,$now);return ['stage'=>'SCHEMA4_CURRENT_READ','item_count'=>count($data['items'])];}
    same($version,'3','read_schema_stage');check(count($config['assets'])>0&&count($config['assets'])<=10,'read_asset_scope');
    $p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
    try{
        same((string)$p->query('SELECT COUNT(*) FROM m2_market_current')->fetchColumn(),'0','read_schema3_current_not_empty');
        $q=$p->prepare("SELECT a.entity_id FROM m2_assets a JOIN m2_entities e ON e.id=a.entity_id JOIN m2_asset_source_routes r ON r.asset_id=a.entity_id JOIN m2_sources s ON s.id=r.source_id JOIN m2_units u ON u.unit_key=r.quote_unit_key AND u.unit_version=r.quote_unit_version AND u.unit_contract_version=r.unit_contract_version WHERE a.entity_id=? AND r.id=? AND e.status='active' AND s.enabled=1 AND s.source_type='market_data' AND u.status='frozen' LIMIT 1");
        $seen=[];foreach($config['assets'] as $asset){foreach(['asset_id','route_id'] as $key)check(is_string($asset[$key])&&preg_match('/^[1-9][0-9]*$/D',$asset[$key])===1,'read_asset_identity');check(!isset($seen[$asset['asset_id']]),'read_duplicate_asset');$seen[$asset['asset_id']]=true;$q->execute([$asset['asset_id'],$asset['route_id']]);same((string)$q->fetchColumn(),$asset['asset_id'],'read_asset_reference');}
    }finally{if($p->inTransaction())$p->rollBack();}
    return ['stage'=>'SCHEMA3_EMPTY_CURRENT_PREFLIGHT','item_count'=>count($config['assets'])];
}
/** Password entered by the human only; saved once outside the public webroot. */
function install(string $root,string $webroot,string $password,array $assets): array {
    check(realpath(dirname($root))===realpath(dirname($webroot))&&basename($root)==='mosa2-market-read-private'&&!file_exists($root)&&!is_link($root),'read_private_target');
    $config=['dsn'=>'mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4','user'=>'h29077_mosa2_read','password'=>$password,'assets'=>$assets,'stale_seconds'=>1800];
    $p=new PDO($config['dsn'],$config['user'],$password,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_TIMEOUT=>3]);
    $identity=$p->query('SELECT DATABASE() AS db,CURRENT_USER() AS account')->fetch();same($identity,['db'=>'h29077_mosa2_test','account'=>'h29077_mosa2_read@localhost'],'read_account_identity');
    $literal=(string)$p->query('SELECT @@partial_revokes')->fetchColumn()==='1';
    $grantRows=$p->query('SHOW GRANTS FOR CURRENT_USER')->fetchAll();grants($grantRows,$literal);
    $probe=preflight($p,$config,(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u'));$p=null;
    umask(0077);check(mkdir($root,0700),'read_private_mkdir');$path=$root.'/access.php';$file=fopen($path,'x');check($file!==false,'read_private_create');
    try{$wire="<?php\nreturn ".var_export($config,true).";\n";check(fwrite($file,$wire)===strlen($wire)&&fflush($file)&&chmod($path,0600),'read_private_write');}finally{fclose($file);unset($password,$config,$wire);}
    return ['ok'=>true,'account_verified'=>true,'grants_verified'=>true,'private_file_mode'=>decoct(fileperms($path)&0777),'read_probe'=>$probe];
}
