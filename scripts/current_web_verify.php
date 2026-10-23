<?php
declare(strict_types=1);
require __DIR__.'/../api/current_read.php';
require_once __DIR__.'/market_current/historical_scope.php';
try{
    $snapshot=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);$rows=[];
    foreach($snapshot['items'] as $entry){
        $isin=$entry['isin'];$r=\Mosa2\ObservationRead\binding($entry['scope_rows'][0],$isin);$data=$entry['input'];
        if(!isset(\Mosa2\ObservationRead\SCOPE[$isin])||$entry['name']!==\Mosa2\ObservationRead\SCOPE[$isin])throw new RuntimeException('scope_name');
        $r['display_name']=$entry['name'];
        $i=\Mosa2\CurrentRead\item($data['current'],$data['current_fact'],$r,$isin,$snapshot['as_of'],1800);
        if(!isset($i['price']))throw new RuntimeException('missing');
        $rows[]=[$i['name'],$i['price'],$i['unit'],$i['unit_version'],$i['source'].' · '.$i['venue'],$i['market_at'],$i['observed_at']];
    }
    echo json_encode(['ok'=>true,'expected_web_sha256'=>hash('sha256',json_encode($rows,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR))],JSON_THROW_ON_ERROR);
}catch(Throwable){echo '{"ok":false}';}
