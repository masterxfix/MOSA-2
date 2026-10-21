<?php
declare(strict_types=1);
namespace Mosa2\MarketCore;
use DateTimeImmutable; use DateTimeZone; use InvalidArgumentException;
// Offline reference only: no connection, SQL, clock, provider or collector.
function requireValue(bool $condition,string $reason): void {
    if(!$condition)throw new InvalidArgumentException($reason);
}
function identity(mixed $value): string {
    requireValue(is_int($value)||is_string($value),'identifier');
    $text=(string)$value;
    requireValue((bool)preg_match('/\A[0-9]+\z/D',$text),'identifier');
    $text=ltrim($text,'0');
    requireValue($text!==''&&(strlen($text)<20||(strlen($text)===20&&strcmp($text,'18446744073709551615')<=0)),'identifier');
    return $text;
}
function decimal(mixed $value,int $precision,int $scale,bool $nullable=false): ?string {
    if($value===null){requireValue($nullable,'decimal_null');return null;}
    requireValue(is_int($value)||is_string($value),'decimal_type');
    requireValue((bool)preg_match('/\A([+-]?)([0-9]+)(?:\.([0-9]+))?\z/D',(string)$value,$parts),'decimal_format');
    $whole=ltrim($parts[2],'0');$whole=$whole===''?'0':$whole;
    $fraction=rtrim($parts[3]??'','0');
    requireValue(strlen($whole)<=$precision-$scale&&strlen($fraction)<=$scale,'decimal_precision');
    $fraction=str_pad($fraction,$scale,'0');
    $negative=$parts[1]==='-'&&($whole!=='0'||trim($fraction,'0')!=='');
    return ($negative?'-':'').$whole.'.'.$fraction;
}
function compareDecimal(string $left,string $right): int {
    $negativeLeft=$left[0]==='-';$negativeRight=$right[0]==='-';
    if($negativeLeft!==$negativeRight)return $negativeLeft?-1:1;
    $left=ltrim($left,'-');$right=ltrim($right,'-');
    $comparison=strlen($left)<=>strlen($right);
    if($comparison===0)$comparison=strcmp($left,$right);
    return $negativeLeft?-$comparison:$comparison;
}
function utcTimestamp(mixed $value): string {
    requireValue(is_string($value)&&(bool)preg_match('/\A([1-9][0-9]{3}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]{1,6}))?\z/D',$value,$parts),'utc_timestamp');
    $canonical=$parts[1].'.'.str_pad($parts[2]??'',6,'0');
    $date=DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u',$canonical,new DateTimeZone('UTC'));
    requireValue($date!==false&&$date->format('Y-m-d H:i:s.u')===$canonical,'utc_timestamp');
    return $canonical;
}
