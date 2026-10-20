<?php
declare(strict_types=1);
namespace Mosa2\Phase3O;
use PDO;
use function Mosa2\Phase2\{check,same,save};
require_once __DIR__.'/../phase3m/live_seed.php';

function stateHash(array $state): string {
    return \Mosa2\Phase3K\dataHash(['state'=>\Mosa2\Phase3M\stableState($state),'units'=>$state['units']]);
}
function compareBusinessState(array $baseline,array $state): array {
    $diagnostics=\Mosa2\Phase3M\compareState($baseline,$state,4);
    same($state['units'],$baseline['units'],'units_changed');
    same(array_map('count',$state['rows']),\Mosa2\Phase3K\COUNTS,'baseline_counts');
    return $diagnostics;
}
function checkedState(PDO $p,string $root,array $baseline): array {
    $p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
    try {
        $state=\Mosa2\Phase3M\captureState($p,$root);
        compareBusinessState($baseline,$state);
        \Mosa2\Phase3K\ledger($p,3);
        foreach(['m2_entities'=>'canonical_name','m2_assets'=>'display_name','m2_sources'=>'source_key','m2_asset_source_routes'=>'external_key'] as $table=>$field){
            $q=$p->prepare('SELECT COUNT(*) FROM '.\Mosa2\Phase2\qi($table).' WHERE '.\Mosa2\Phase2\qi($field).' LIKE ?');
            $q->execute([NS.'%']);same((int)$q->fetchColumn(),0,'synthetic_keys_present');
        }
    }finally{if($p->inTransaction())$p->rollBack();}
    return $state;
}
function historicalState(string $root): array {
    $file=$root.'/baseline.json';
    $config=require $root.'/access.php';
    same(hash_file('sha256',$file),$config['baseline_sha256'],'historical_file');
    return json_decode(file_get_contents($file),true,512,JSON_THROW_ON_ERROR);
}
