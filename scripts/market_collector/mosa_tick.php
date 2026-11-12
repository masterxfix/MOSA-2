<?php
declare(strict_types=1);
namespace Mosa2\MosaMarket;

use DateTimeImmutable;
use DateTimeZone;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,connection,same};
use function Mosa2\MarketLive\{proofRun,bridge,completePlan};
use function Mosa2\MarketAcceptance\{capture,quoteManifest};
use function Mosa2\IsinQuote\{asPrice,sourceAllowed};

require_once __DIR__.'/actions_acceptance.php';
require_once __DIR__.'/../market_current/refresh.php';

require_once dirname(__DIR__,2).'/api/market_source_engine.php';
require_once dirname(__DIR__,2).'/api/isin_quote.php';

// Scheduled permissions are independent of the manual preview. The provider
// publishes these quotes for private display and non-display use.
// https://www.ls-tc.de/media/site/service/wissen/Marktdatenstrategie.pdf
const SOURCES=[
    'lang_schwarz'=>[
        'name'=>'Lang & Schwarz','venue'=>'lang_schwarz_tradecenter','url'=>'https://www.ls-tc.de/de/',
        'requests'=>['lang_schwarz_search','lang_schwarz_page'],
    ],
];

function sourceRegistry(PDO $db): array {
    $registry=[];
    $read=$db->prepare('SELECT id,enabled,source_type FROM m2_sources WHERE source_key=?');
    foreach (SOURCES as $provider=>$source) {
        $read->execute(['provider:'.$provider]);
        $row=$read->fetch();
        if ($row===false) {
            $insert=$db->prepare("INSERT INTO m2_sources
                (source_key,source_type,display_name,base_url,enabled,created_at,updated_at)
                VALUES (?,'market_data',?,?,1,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6))");
            $insert->execute(['provider:'.$provider,$source['name'],$source['url']]);
            $row=['id'=>$db->lastInsertId(),'enabled'=>1,'source_type'=>'market_data'];
        }
        if ((int)$row['enabled']===1 && $row['source_type']==='market_data') {
            $registry[$provider]=$source+['id'=>(string)$row['id']];
        }
    }
    return $registry;
}

function deferSource(PDO $db,string $sourceId,int $status,mixed $retryAfter): void {
    $now=time();
    $retry=is_string($retryAfter)&&ctype_digit($retryAfter)?$now+min((float)$retryAfter,31536000):
        (is_string($retryAfter)?strtotime($retryAfter):false);
    $until=max($now+($status===429?60:86400),$retry?:0);
    $query=$db->prepare("INSERT INTO m2_sync_checkpoints (source_id,stream_key,watermark_at,updated_at)
        VALUES (?,'scheduled_market_cooldown',?,UTC_TIMESTAMP(6))
        ON DUPLICATE KEY UPDATE watermark_at=GREATEST(COALESCE(watermark_at,UTC_TIMESTAMP(6)),?),updated_at=UTC_TIMESTAMP(6)");
    $stamp=gmdate('Y-m-d H:i:s',(int)$until);
    $query->execute([$sourceId,$stamp,$stamp]);
}

function fetchSource(array $request,array &$requests): array {
    $request['follow_redirects']=false;
    $response=\fixlabMosaMarketSourceLabLiveTransport($request);
    $key=$request['request_key'];
    $requests[]=['key'=>$key,'status'=>$response['http_status']??null];
    $location=$response['location']??null;
    // L&S redirects its verified numeric instrument URL to its canonical slug.
    // Keep the provider and category fixed and permit only this one redirect.
    if ($key==='lang_schwarz_page' && in_array($response['http_status']??null,[301,302,307,308],true)
        && is_string($location)
        && preg_match('~^https://www\\.ls-tc\\.de/de/(aktie|etf)/[0-9]+$~D',$request['url'],$numeric)
        && preg_match('~^https://www\\.ls-tc\\.de/de/(aktie|etf)/[a-z0-9][a-z0-9-]{0,180}$~D',$location,$canonical)
        && $numeric[1]===$canonical[1]) {
        $request['url']=$location;
        $response=\fixlabMosaMarketSourceLabLiveTransport($request);
        $requests[]=['key'=>$key,'status'=>$response['http_status']??null];
    }
    return $response;
}

function acquire(PDO $db,array $registry,string $isin,array &$requests): ?array {
    $ready=$db->prepare("SELECT COUNT(*) FROM m2_sync_checkpoints WHERE source_id=?
        AND stream_key='scheduled_market_cooldown' AND watermark_at>UTC_TIMESTAMP(6)");
    $allowed=[];
    foreach ($registry as $source) {
        $ready->execute([$source['id']]);
        if ((int)$ready->fetchColumn()!==0) continue;
        foreach ($source['requests'] as $key) $allowed[$key]=$source['id'];
    }
    if ($allowed===[]) return null;

    $captured=[];
    $lab=\fixlabRunMosaMarketSourceLab($isin,\FIXLAB_MOSA_MARKET_SOURCE_LAB_PROVIDER,
        static function(array $request) use($db,$isin,&$allowed,&$requests,&$captured): array {
            $key=$request['request_key'];
            if (!isset($allowed[$key])||!sourceAllowed($request,$isin)) {
                return ['body'=>'','http_status'=>null,'error_code'=>'provider_not_enabled'];
            }
            $response=fetchSource($request,$requests);
            $captured[$key]=(new DateTimeImmutable('now',new DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');
            $status=$response['http_status']??null;
            if (in_array($status,[401,403,429],true)) {
                $id=$allowed[$key];
                deferSource($db,$id,$status,$response['retry_after']??null);
                $allowed=array_filter($allowed,static fn($sourceId)=>$sourceId!==$id);
            }
            return $response;
        },lsQuoteClock:static fn(?string $clock,DateTimeImmutable $now)=>
            \fixlabMosaMarketSourceLabLsDatedQuote($clock,$now)??\fixlabMosaMarketSourceLabLocalClock($clock,$now));
    // Reuse the productive quote router for every ISIN. The lab's optional
    // pilot-only recommendation is deliberately outside this entry point.
    $quote=\fixlabMosaMarketQuoteRouter($lab['sources'])['selected_quote']??null;
    if ($quote===null) return null;
    $provider=$quote['provider_key'];
    $observedAt=null;
    foreach ($registry[$provider]['requests'] as $requestKey) {
        if (isset($captured[$requestKey])) $observedAt=$captured[$requestKey];
    }
    $marketAt=(new DateTimeImmutable($quote['quoted_at']))->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s.u');
    $price=asPrice($quote['mid']);
    if ($observedAt===null||$marketAt>$observedAt||$price===null) return null;
    return ['provider'=>$provider,'market_at'=>$marketAt,'observed_at'=>$observedAt,'currency'=>$quote['currency'],
        'price'=>$price,'bid'=>asPrice($quote['bid']),'ask'=>asPrice($quote['ask']),'volume'=>null];
}

function syncFact(callable $connect,array $config,string $password,string $isin,string $name,array $fact): array {
    $contract=$config['state_contract'];
    $state=capture($connect,$contract);
    $provider=$fact['provider'];
    $manifest=quoteManifest($state,['isin'=>$isin,'name'=>$name],[
        'source_key'=>$provider,'reference_key'=>$provider,'venue_key'=>SOURCES[$provider]['venue'],'family'=>'mosa_live_quote',
        'reference'=>'M2 acquisition using the MOSA source adapter and quote router',
        'provider_key'=>$provider,'adapter_module'=>'m2_market_observation','adapter_class'=>'MarketObservation',
    ]);
    $plan=completePlan($state,$manifest);
    $assetId=$plan['asset']['asset_id'];
    $current=null;
    foreach ($state['m2_market_current'] as $row) if ($row['asset_id']===$assetId) $current=$row;
    if ($current!==null && $current['route_id']===($plan['route']['route_id']??null)
        && $current['market_at']===$fact['market_at']
        && asPrice((float)$current['price'])===$fact['price']
        && asPrice((float)$current['bid'])===$fact['bid'] && asPrice((float)$current['ask'])===$fact['ask']) {
        return ['writer'=>'UNCHANGED'];
    }

    $invoke=static function(array $runtime,array $request) use($fact,$isin): array {
        if ($request['action']==='fetch') return ['m2_market_observation'=>$fact,'instrument'=>$isin];
        return bridge($runtime,$request);
    };
    // The private acquisition above supplies the validated quote to the existing Schema-6 writer.
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
            $registry=$registered===[]?[]:sourceRegistry($db);
            $batches=array_chunk($registered,2,true);
            $due=$batches===[]?[]:$batches[intdiv(time(),60)%count($batches)];
            $config=[
                'project'=>$project,'python'=>'/opt/alt/python311/bin/python3.11','php'=>PHP_BINARY,
                'runtime_path'=>'/opt/plesk/php/8.4/bin:/usr/bin:/bin','private_root'=>$periodic.'/work',
                'db_host'=>'127.0.0.1','db_port'=>3307,'allow_duplicate'=>true,
                'state_contract'=>['schema_version'=>6,'allow_current'=>true],
            ];
            $items=[];$unavailable=[];$requests=[];
            foreach ($due as $isin=>$name) {
                try {
                    $fact=acquire($db,$registry,$isin,$requests);
                    if ($fact===null) {
                        $unavailable[]=$isin;
                        continue;
                    }
                    $items[$isin]=['provider'=>$fact['provider']]+syncFact($connect,$config,$password,$isin,$name,$fact);
                } catch (Throwable $error) {
                    $code=$error->getMessage();
                    $items[$isin]=['failure'=>preg_match('/^[a-z0-9_]{1,80}$/D',$code)?$code:'m2_market_write_failed'];
                }
            }
            echo json_encode(['checked_at'=>gmdate('c'),'registered'=>count($registered),'due'=>count($due),
                'provider_requests'=>$requests,'unavailable'=>$unavailable,'items'=>$items],JSON_THROW_ON_ERROR).PHP_EOL;
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
