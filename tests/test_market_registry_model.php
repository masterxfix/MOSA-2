<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/api/market_registry_model.php';
use function Mosa2\MarketRegistry\isin;
assert(isin('no0010081235')==='NO0010081235');
require_once dirname(__DIR__).'/scripts/market_collector/onboarding.php';
$key=\Mosa2\Phase3D\json(\Mosa2\MarketIdentity\identifierKey(['identifier_type'=>'isin','normalized_value'=>'NO0010081235','scope_key'=>'']));
assert(\Mosa2\MarketRegistry\lockNames('NO0010081235')===['m2-collector-scheduler','m2-live:'.substr(hash('sha256',$key),0,48)]);
foreach(['NO0010081234','abc','NO001008123','NO00100812356','DE000000000-',''] as $invalid){
    try { isin($invalid); throw new Exception('Invalid ISIN accepted'); }
    catch(RuntimeException $e){
        if($e->getMessage()!=='INVALID_ISIN')throw $e;
    }
}
echo "market registry validation: PASS\n";
