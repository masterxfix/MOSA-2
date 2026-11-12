<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/api/market_registry_model.php';
use function Mosa2\MarketRegistry\isin;
assert(isin('no0010081235')==='NO0010081235');
foreach(['abc','NO001008123','NO00100812356','DE000000000-',''] as $invalid){
    try { isin($invalid); throw new Exception('Invalid ISIN accepted'); }
    catch(RuntimeException $e){
        if($e->getMessage()!=='INVALID_ISIN')throw $e;
    }
}
echo "market registry validation: PASS\n";
