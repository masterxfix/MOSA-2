<?php
declare(strict_types=1);
namespace Mosa2\Phase3N;
require_once __DIR__.'/../phase3c/market_flow.php';
use function Mosa2\Phase3C\{identity,decimal,utcTimestamp,compareDecimal,requireValue};

// Local stdio adapter only. Reuse v1 primitives without changing v1 or inventing
// a monetary currency for a nonmonetary observation. No persistence capability.
require_once dirname(__DIR__,2).'/api/market_core/values.php';
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    try {
        $request=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
        $result=match($request['operation']) {
            'values'=>values($request['row']),
            'legacy'=>['row'=>\Mosa2\Phase3C\normalizeObservation($request['row']),
                'canonical'=>\Mosa2\Phase3C\canonicalObservation($request['row']),
                'dedupe_hex'=>bin2hex(\Mosa2\Phase3C\dedupeKey($request['row']))],
            'timestamp'=>utcTimestamp($request['value']),
            'identity'=>identity($request['value']),
            default=>throw new \InvalidArgumentException('operation'),
        };
        echo json_encode(['ok'=>true,'result'=>$result],JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);
    }catch(\Throwable $error){echo json_encode(['ok'=>false,'reason'=>$error->getMessage()],JSON_THROW_ON_ERROR);}
}
