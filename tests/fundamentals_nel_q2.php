<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{transaction,storedFile,validate};

$plan=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
validate($plan);storedFile($plan);
$p=new MemoryPDO();
$receipt=transaction($p,$plan,'42',fn()=>null);
if($receipt['observations']!==5||$receipt['current']!==5||$receipt['metrics']!==5)throw new RuntimeException('nel_q2_assertion');
echo json_encode(['ok'=>true,'observations'=>$receipt['observations'],'current'=>$receipt['current'],'metrics'=>$receipt['metrics']],JSON_THROW_ON_ERROR);
