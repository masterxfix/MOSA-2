<?php
declare(strict_types=1);
namespace Mosa2\MarketBatch;
use Throwable;
use function Mosa2\Phase2\{check,same};
require_once __DIR__.'/live_persistence.php';

const CONTRACT='mosa2-manual-live-batch-v2';
/** Registry qualification belongs to the shared planning library. */
function qualify(array $state,array $selection,callable $manifestFactory): array {
    return \Mosa2\MarketLive\qualifyBatch($state,$selection,$manifestFactory);
}
function path(string $value): string {
    $resolved=realpath($value);check(is_string($resolved)&&is_dir($resolved)&&!is_link($value),'batch_directory');
    $canonical=str_replace('\\','/',$resolved);same(str_replace('\\','/',$value),$canonical,'batch_canonical_path');return $canonical;
}
function inside(string $child,string $parent): bool {return $child===$parent||str_starts_with($child,$parent.'/');}
/** Validate the complete explicit scope before I/O; preserve configured order. */
function prepare(string $privateRoot,string $publicRoot,array $entries): array {
    check(array_is_list($entries)&&count($entries)>=1&&count($entries)<=10,'batch_size');
    $root=path($privateRoot);$web=path($publicRoot);check(!inside($root,$web),'batch_private_root');$prepared=[];$identities=[];$folders=[];
    foreach($entries as $entry){
        check(is_array($entry)&&array_keys($entry)===['private_root']&&is_string($entry['private_root']),'batch_entry');
        $folder=path($entry['private_root']);check($folder!==$root&&inside($folder,$root)&&!inside($folder,$web),'batch_item_root');
        $ancestor=$folder;while($ancestor!==$root){check(!is_link($ancestor),'batch_symlink');$ancestor=str_replace('\\','/',dirname($ancestor));}
        check(!isset($folders[$folder]),'batch_duplicate_folder');$folders[$folder]=true;
        $file=$folder.'/live-manifest.json';check(is_file($file)&&!is_link($file),'batch_manifest');
        $manifest=json_decode(file_get_contents($file),true,64,JSON_THROW_ON_ERROR);
        same($manifest['policy']??null,'USE_EXISTING_ROUTE','batch_policy');
        $identity=\Mosa2\MarketIdentity\qualifiedIdentity($manifest['identity']);
        $key=\Mosa2\MarketIdentity\identifierKey($identity);ksort($key,SORT_STRING);$key=\Mosa2\Phase3D\json($key);
        check(!isset($identities[$key]),'batch_duplicate_identifier');$identities[$key]=true;
        $prepared[]=['key'=>$key,'fingerprint'=>hash('sha256',$key),'private_root'=>$folder,'manifest'=>$manifest];
    }
    return $prepared;
}
function counter(mixed $value): ?int {return is_int($value)&&$value>=0?$value:null;}
function total(?int $sum,?int $value): ?int {return $sum===null||$value===null?null:$sum+$value;}
/** Pure sequential coordination; injected runners are used by offline tests. */
function execute(array $prepared,callable $runner): array {
    check(array_is_list($prepared)&&count($prepared)>=1&&count($prepared)<=10,'batch_size');
    $seen=[];foreach($prepared as $entry){$key=$entry['key'];check(!isset($seen[$key]),'batch_duplicate_identifier');$seen[$key]=true;}
    $report=['contract_version'=>CONTRACT,'started_count'=>0,'completed_count'=>0,'failed_count'=>0,'not_started_count'=>count($prepared),
        'committed_count'=>0,'provider_requests'=>0,'database_connections'=>0,'item_results'=>[],'overall_status'=>'FAILED_BEFORE_FIRST_COMMIT'];$private=[];
    foreach($prepared as $i=>$entry)$report['item_results'][]=['position'=>$i+1,'asset_identity'=>$entry['manifest']['identity']['normalized_value'],
        'status'=>'NOT_STARTED','provider_request_performed'=>false,'committed'=>false,'writer'=>null,'observation_id'=>null,'replay'=>null,'failure_stage'=>null];
    foreach($prepared as $i=>$entry){
        $report['started_count']++;$report['not_started_count']--;
        try{$result=$runner($entry);check(is_array($result),'batch_runner_result');}
        catch(Throwable){$result=['ok'=>false,'committed'=>null,'provider_requests'=>null,'database_connections'=>null,'failure'=>'runner_exception'];}
        $success=($result['ok']??false)===true&&($result['committed']??false)===true;
        $item=['position'=>$i+1,'status'=>$success?'COMPLETE':'FAILED','committed'=>$result['committed']??null,
            'provider_requests'=>counter($result['provider_requests']??null),'database_connections'=>counter($result['database_connections']??null)];
        $item+=['asset_identity'=>$entry['manifest']['identity']['normalized_value'],'provider_request_performed'=>$item['provider_requests']===null?null:$item['provider_requests']>0,
            'writer'=>null,'observation_id'=>$result['observation_id']??null,'replay'=>null,'failure_stage'=>$success?null:($result['stage']??'runner')];
        foreach(['policy','asset_plan','route_plan','writer','replay','readback','deltas','metrics','provider_duration_ms'] as $field)if(array_key_exists($field,$result))$item[$field]=$result[$field];
        $item['source']=$result['private_evidence']['plan']['source']['decision']??null;
        $report['item_results'][$i]=$item;$private[]=['position'=>$i+1,'fingerprint'=>$entry['fingerprint'],'result'=>$result];
        foreach(['provider_requests','database_connections'] as $field)$report[$field]=total($report[$field],$item[$field]);
        if($item['committed']===true)$report['committed_count']++;
        if(!$success){$report['failed_count']++;break;}$report['completed_count']++;
    }
    $report['overall_status']=$report['completed_count']===count($prepared)?'COMPLETE':($report['committed_count']>0?'PARTIAL_FAILED':'FAILED_BEFORE_FIRST_COMMIT');
    $report['private_evidence']=['items'=>$private];return $report;
}
function run(string $privateRoot,string $password,array $config,array $entries): array {
    try {
        try{$prepared=prepare($privateRoot,$config['public_root'],$entries);}
        catch(Throwable){return ['contract_version'=>CONTRACT,'started_count'=>0,'completed_count'=>0,'failed_count'=>0,'not_started_count'=>count($entries),
            'provider_requests'=>0,'database_connections'=>0,'item_results'=>array_map(static fn($i)=>['position'=>$i+1,'status'=>'NOT_STARTED','asset_identity'=>null,
                'provider_request_performed'=>false,'committed'=>false,'writer'=>null,'observation_id'=>null,'replay'=>null,'failure_stage'=>'batch_validation'],array_keys(array_values($entries))),
            'committed_count'=>0,'overall_status'=>'FAILED_BEFORE_FIRST_COMMIT','failure'=>'batch_validation'];}
        return execute($prepared,static fn($entry)=>\Mosa2\MarketLive\run($entry['private_root'],$password,$config,$entry['manifest']));
    }finally{unset($password);}
}
