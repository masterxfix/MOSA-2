<?php
declare(strict_types=1);
require dirname(__DIR__,2).'/api/isin_quote.php';
use function Mosa2\IsinQuote\{isin,decimal,midpoint,tradegate,frankfurt,preview};
function same($a,$b,$name):void{if($a!==$b)throw new RuntimeException($name.' '.var_export([$a,$b],true));}
function reject(callable $fn,string $name):void{try{$fn();}catch(Mosa2\IsinQuote\QuoteFailure){return;}throw new RuntimeException($name);}
$fixture='<!doctype html><html><body><h2>PNE AG</h2><table><tr><th>ISIN</th><th>Handelswährung</th></tr><tr><td>DE000A0JBPG2</td><td>EUR</td></tr><tr><td>Bid</td><td>5,44</td></tr><tr><td>Ask</td><td>5,51</td></tr></table><p>Letzte Aktualisierung: 02.11.2026 @ 11:32:06</p></body></html>';
same(isin(' de000a0jbpg2 '),'DE000A0JBPG2','isin');
reject(fn()=>isin('DE000A0JBPG2&other=1'),'isin injection');
same(decimal('1.234,0000000001'),'1234.0000000001','fraction');
same(decimal('187,00'),'187','zero fraction');
reject(fn()=>decimal('-5,00'),'negative quote');
reject(fn()=>decimal('abc5,00'),'unqualified quote');
same(midpoint('1.234,0000000001','1.234,0000000003'),'1234.0000000002','precise midpoint');
same(midpoint('5,44','5,51'),'5.475','uneven midpoint');
same(midpoint('187,2','187,4'),'187.3','mid');
$r=tradegate($fixture,'DE000A0JBPG2');same($r['name'],'PNE AG','name');same($r['price'],'5.475','price');same($r['quote_type'],'Mid (Geld/Brief)','kind');same($r['market_at'],'2026-11-02T10:32:06Z','timezone');
reject(fn()=>tradegate($fixture,'DE0007030009'),'wrong isin');
reject(fn()=>tradegate(str_replace('EUR','USD',$fixture),'DE000A0JBPG2'),'wrong currency');
reject(fn()=>tradegate(str_replace('5,44','6,00',$fixture),'DE000A0JBPG2'),'crossed');
$json=json_encode(['isin'=>'DE000A0JBPG2','mic'=>'XFRA','currency'=>['originalValue'=>'EUR'],'lastPrice'=>5.52,'timestampLastPrice'=>'2026-11-02T11:30:05+01:00']);
$f=frankfurt($json,'DE000A0JBPG2');same($f['price'],'5.52','frankfurt price');same($f['market_at'],'2026-11-02T10:30:05Z','frankfurt utc');
reject(fn()=>frankfurt(str_replace('XFRA','XGAT',$json),'DE000A0JBPG2'),'frankfurt mic');
$out=preview('DE000A0JBPG2','tradegate',static fn()=> $fixture);same($out['status'],'ok','preview');same($out['provider'],'tradegate','provider');same($out['source'],'Tradegate BSX · Mid','source');same($out['price'],'5.475','price');
echo 'PASS synthetic ISIN quote tests'."\n";
