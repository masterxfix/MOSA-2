<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/market_collector/mosa_tick.php';
require_once dirname(__DIR__).'/scripts/market_collector/schema_contract.php';

use function Mosa2\Phase2\{check,same};
use function Mosa2\CollectorSchema5\{selected,additiveNetworkTables7,ledger7Network};

$tables=additiveNetworkTables7();
same(count($tables),16,'network_table_count');
same(count(array_unique($tables)),16,'network_unique');
foreach($tables as $name)check(str_starts_with($name,'m2_network_'),'network_scope');
same(selected(['state_contract'=>['schema_version'=>6,'additive_schema_7'=>true]]),
    ['schema_version'=>6,'additive_schema_7'=>true],'schema6_additive_optin');
same(selected(['state_contract'=>['schema_version'=>6]])['schema_version'],6,'schema6_legacy_unchanged');
foreach([['schema_version'=>5,'additive_schema_7'=>true],
         ['schema_version'=>6,'additive_schema_7'=>false]] as $invalid){
    try{selected(['state_contract'=>$invalid]);throw new RuntimeException('invalid_extension_accepted');}
    catch(RuntimeException $e){same($e->getMessage(),'schema_extension_contract','invalid_extension_rejected');}
}
$names=['0001_core_asset_identity','0002_market_current_history','0003_market_units',
    '0004_current_observation_provenance','0005_collector_reservations',
    '0006_fundamentals_and_payload_provenance','0007_network_smart_home_core'];
$ledger=[];
foreach($names as $i=>$name){
    $file=dirname(__DIR__).'/docs/database/migrations/'.$name.'.sql';
    $ledger[]=['version'=>(string)($i+1),'migration_key'=>$name,
        'checksum'=>hash_file('sha256',$file)];
}
ledger7Network($ledger);
$altered=$ledger;$altered[6]['checksum']=str_repeat('0',64);
try{ledger7Network($altered);throw new RuntimeException('bad_digest_accepted');}
catch(RuntimeException $e){same($e->getMessage(),'schema7_ledger_digest','bad_digest_rejected');}
$altered=$ledger;$altered[6]['migration_key']='unrelated_migration';
try{ledger7Network($altered);throw new RuntimeException('bad_migration_accepted');}
catch(RuntimeException $e){same($e->getMessage(),'schema7_ledger_key','bad_key_rejected');}
echo "PASS additive network schema 7 compatibility; market schema 6 remains scoped\n";
