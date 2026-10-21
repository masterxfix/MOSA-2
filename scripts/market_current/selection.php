<?php
declare(strict_types=1);
namespace Mosa2\QuoteSelection;
require_once dirname(__DIR__,2).'/api/market_core/selection.php';
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    try{
        $input=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
        echo json_encode(['ok'=>true,'result'=>select($input['facts'],$input['route'],$input['now'],$input['previous']??null,$input['units']??null)],JSON_THROW_ON_ERROR);
    }catch(\Throwable $e){echo json_encode(['ok'=>false,'failure'=>$e->getMessage()],JSON_THROW_ON_ERROR);}
}
