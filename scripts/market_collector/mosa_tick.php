<?php
declare(strict_types=1);
namespace Mosa2\MosaMarket;

use DateTimeImmutable;
use DateTimeZone;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,connection,same};
use function Mosa2\MarketLive\{snapshot,proofRun,bridge,completePlan};
use function Mosa2\MarketAcceptance\{capture,manifest,quoteManifest};

require_once __DIR__.'/actions_acceptance.php';
require_once __DIR__.'/../market_current/refresh.php';

/** The deployed MOSA scheduler remains the only process that acquires provider quotes. */
function observations(string $mosa,array $registered): array {
    require_once $mosa.'/php/mosa_market_source_registry.php';
    require_once $mosa.'/php/mosa_market_live_quote_runner.php';
    require_once $mosa.'/php/mosa_market_control_board_read_model.php';
    $registry=\fixlabReadMosaMarketSourceRegistry($mosa);
    check(\fixlabValidateMosaMarketSourceRegistry($registry),'mosa_registry_unavailable');
    $assets=\fixlabMosaMarketLiveQuoteAssets(
        $registry['registrations'],\fixlabMosaEtfReadStore($mosa),\fixlabReadMosaRelationshipStore($mosa));
    $isinByKey=[];
    foreach ($assets as $asset) {
        if (!isset($registered[$asset['isin']])) continue;
        $key=$asset['asset_key'];
        check(!isset($isinByKey[$key])||$isinByKey[$key]===$asset['isin'],'mosa_asset_key_ambiguous');
        $isinByKey[$key]=$asset['isin'];
    }

    $observations=[];
    $now=new DateTimeImmutable('now',new DateTimeZone('UTC'));
    foreach (array_chunk(array_keys($isinByKey),10) as $keys) {
        $data=\fixlabMosaMarketControlBoardDatabaseReader($mosa)($keys);
        foreach ($keys as $key) {
            $selected=\fixlabMosaMarketControlBoardSelectObservation($data['observations'],$key,$now);
            if ($selected===null) continue;
            foreach ($data['observations'] as $row) {
                if ($row['asset_key']!==$key||$row['source_key']!==$selected['source_key']) continue;
                $fact=\fixlabMosaMarketControlBoardObservation($row,$key,$now);
                if ($fact===null) continue;
                $isin=$isinByKey[$key];
                $candidate=[
                    'provider'=>$fact['provider_key'],'market_at'=>$fact['_quoted']->format('Y-m-d H:i:s.u'),
                    'observed_at'=>$fact['_collected']->format('Y-m-d H:i:s.u'),'currency'=>$row['currency'],
                    'price'=>$fact['price_eur'],'bid'=>$fact['bid_eur'],'ask'=>$fact['ask_eur'],'volume'=>null,
                ];
                check(!isset($observations[$isin])||$observations[$isin]===$candidate,'mosa_isin_ambiguous');
                $observations[$isin]=$candidate;
            }
        }
    }
    return $observations;
}

/** Map the existing MOSA provider identity to M2's physical Source and route. */
function sourceManifest(callable $connect,array $contract,string $isin,string $name,array $fact): array {
    $provider=$fact['provider'];
    $venue=match($provider) {
        'lang_schwarz'=>'lang_schwarz_tradecenter',
        'tradegate_bsx'=>'tradegate_bsx',
        'boerse_frankfurt_api'=>'boerse_frankfurt',
    };
    $db=$connect();
    $state=snapshot($db,$contract);
    $source='provider:'.$provider;
    if (!in_array($source,array_column($state['m2_sources'],'source_key'),true)) {
        $db->beginTransaction();
        try {
            $now=(new DateTimeImmutable('now',new DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');
            $store=new \Mosa2\MarketIdentity\PdoStore($db);
            $store->insert('m2_sources',[
                'source_key'=>$source,'source_type'=>'market_data',
                'display_name'=>\fixlabMosaMarketControlBoardProviderName($provider),
                'base_url'=>null,'enabled'=>'1','created_at'=>$now,'updated_at'=>$now,
            ]);
            same($db->commit(),true,'mosa_source_commit');
        } finally {
            if ($db->inTransaction()) $db->rollBack();
        }
        $state=capture($connect,$contract);
    }
    $selection=['isin'=>$isin,'name'=>$name];
    if ($provider==='boerse_frankfurt_api') return manifest($state,$selection);
    return quoteManifest($state,$selection,[
        'source_key'=>$provider,'reference_key'=>$provider,'venue_key'=>$venue,'family'=>'mosa_live_quote',
        'reference'=>'MOSA live quote router selected observation with original market and collection timestamps',
        'provider_key'=>$provider,'adapter_module'=>'mosa_saved_observation','adapter_class'=>'MosaSavedObservation',
    ]);
}

function syncFact(callable $connect,array $config,string $password,string $isin,string $name,array $fact): array {
    $contract=$config['state_contract'];
    $manifest=sourceManifest($connect,$contract,$isin,$name,$fact);
    $state=capture($connect,$contract);
    $plan=completePlan($state,$manifest);
    $assetId=$plan['asset']['asset_id'];
    $current=null;
    foreach ($state['m2_market_current'] as $row) if ($row['asset_id']===$assetId) $current=$row;
    if ($current!==null && $current['route_id']===($plan['route']['route_id']??null)
        && $current['market_at']===$fact['market_at'] && $current['observed_at']===$fact['observed_at']) {
        return ['writer'=>'UNCHANGED'];
    }

    $invoke=static function(array $runtime,array $request) use($fact): array {
        if ($request['action']==='fetch') return ['mosa_observation'=>$fact];
        return bridge($runtime,$request);
    };
    // The input is a stored observation produced by MOSA. There is no provider request here.
    $result=proofRun($config['private_root'],$password,$config,$manifest,static function(array $runtime) {
        same($runtime['state_contract']['schema_version'],6,'mosa_schema_version');
    },$connect,$invoke);
    if (!$result['ok']) return ['failure'=>$result['failure']??$result['readback_failure']??$result['stage']];
    $after=capture($connect,$contract);
    $manifest['policy']='USE_EXISTING_ROUTE';
    $saved=completePlan($after,$manifest);
    $routes=array_column($after['m2_asset_source_routes'],null,'id');
    $id=$saved['route']['route_id'];
    $approved=(new DateTimeImmutable('now',new DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');
    $approval=[
        'route_id'=>$id,'route_sha256'=>hash('sha256',\Mosa2\Phase3D\json($routes[$id])),
        'approved_at'=>$approved,'allow_disabled_projection'=>true,
    ];
    if ($current!==null&&$current['route_id']!==$id) {
        $approval['allow_route_transition']=true;
        $approval['previous_route_sha256']=hash('sha256',\Mosa2\Phase3D\json($routes[$current['route_id']]));
    }
    $readback=\Mosa2\MarketCurrent\refresh($password,$config,[$approval]);
    same($readback['readback']??null,'PASS','mosa_current_readback');
    return ['writer'=>$result['writer'],'observation_id'=>$result['observation_id'],'readback'=>'PASS'];
}

function main(): void {
    if (PHP_SAPI!=='cli'||realpath($_SERVER['SCRIPT_FILENAME']??'')!==__FILE__) exit(1);
    ini_set('display_errors','0');
    ini_set('log_errors','0');
    umask(0077);
    $project=dirname(__DIR__,2);
    $periodic=dirname($project,2);
    $subscription=dirname($periodic,3);
    try {
        same($periodic,$subscription.'/private/mosa2-collector/periodic','mosa_private_path');
        same(realpath($periodic),$periodic,'mosa_private_path');
        $configFile=$subscription.'/mosa2-market-write-private/access.php';
        check(realpath($configFile)===$configFile&&(fileperms($configFile)&0777)===0600,'mosa_private_config');
        $credentials=require $configFile;
        same($credentials['user']??null,'h29077_mosa2_test','mosa_test_database');
        same($credentials['dsn']??null,'mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4','mosa_test_database');
        $password=$credentials['password'];
        unset($credentials);
        $connect=static fn()=>connection($password);
        $db=$connect();
        if ((int)$db->query("SELECT GET_LOCK('m2-collector-scheduler',0)")->fetchColumn()!==1) return;
        try {
            $registered=$db->query("SELECT i.normalized_value AS isin,a.display_name AS name FROM m2_asset_identifiers i
                JOIN m2_assets a ON a.entity_id=i.asset_id AND a.status='active'
                JOIN m2_entities e ON e.id=a.entity_id AND e.status='active'
                WHERE i.identifier_type='isin' AND i.scope_key='' AND i.is_primary=1 AND i.valid_to IS NULL
                  AND (i.valid_from IS NULL OR i.valid_from<=UTC_TIMESTAMP(6))
                ORDER BY i.normalized_value")->fetchAll(PDO::FETCH_KEY_PAIR);
            $facts=$registered===[]?[]:observations($subscription.'/httpdocs/scharwerk.de/dashboard_neu',$registered);
            $config=[
                'project'=>$project,'python'=>'/opt/alt/python311/bin/python3.11','php'=>PHP_BINARY,
                'runtime_path'=>'/opt/plesk/php/8.4/bin:/usr/bin:/bin','private_root'=>$periodic.'/work',
                'db_host'=>'127.0.0.1','db_port'=>3307,'allow_duplicate'=>true,
                'state_contract'=>['schema_version'=>6,'allow_current'=>true],
            ];
            $items=[];
            foreach ($facts as $isin=>$fact) {
                try { $receipt=syncFact($connect,$config,$password,$isin,$registered[$isin],$fact); }
                catch (Throwable $error) {
                    $code=$error->getMessage();
                    $receipt=['failure'=>preg_match('/^[a-z0-9_]{1,80}$/D',$code)?$code:'mosa_sync_failed'];
                }
                $items[$isin]=['provider'=>$fact['provider']]+$receipt;
            }
            echo json_encode(['checked_at'=>gmdate('c'),'registered'=>count($registered),
                'unavailable'=>array_values(array_diff(array_keys($registered),array_keys($facts))),
                'items'=>$items],JSON_THROW_ON_ERROR).PHP_EOL;
        } finally {
            $db->query("SELECT RELEASE_LOCK('m2-collector-scheduler')");
        }
    } catch (Throwable $error) {
        $code=$error->getMessage();
        fwrite(STDERR,(preg_match('/^[a-z0-9_]{1,80}$/D',$code)?$code:'mosa_market_sync_failed').PHP_EOL);
        exit(1);
    }
}
main();
