<?php
declare(strict_types=1);
namespace Mosa2\Phase3C;

use DateTimeImmutable;
use DateTimeZone;
use InvalidArgumentException;
use RuntimeException;

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
function normalizeObservation(array $input): array {
    $fields=['asset_id','source_id','route_id','currency','market_at','observed_at','price','bid','ask','volume'];
    $keys=array_keys($input);sort($keys);$expected=$fields;sort($expected);
    requireValue($keys===$expected,'observation_fields');
    requireValue(is_string($input['currency'])&&(bool)preg_match('/\A[A-Z]{3}\z/D',$input['currency']),'currency');
    // Build the one canonical field order explicitly, independent of input order.
    $row=['asset_id'=>identity($input['asset_id']),'source_id'=>identity($input['source_id']),
        'route_id'=>identity($input['route_id']),'currency'=>$input['currency'],
        'market_at'=>utcTimestamp($input['market_at']),'observed_at'=>utcTimestamp($input['observed_at']),
        'price'=>decimal($input['price'],28,10),'bid'=>decimal($input['bid'],28,10,true),
        'ask'=>decimal($input['ask'],28,10,true),'volume'=>decimal($input['volume'],32,8,true)];
    requireValue(compareDecimal($row['price'],'0.0000000000')>0,'price');
    requireValue($row['bid']===null||$row['ask']===null||compareDecimal($row['bid'],$row['ask'])<=0,'bid_ask');
    return $row;
}
function canonicalObservation(array $input): string {
    return "mosa2-observation-v1\n".json_encode(normalizeObservation($input),JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);
}
// Raw 32 bytes, matching m2_market_observations.dedupe_key BINARY(32).
function dedupeKey(array $input): string {
    return hash('sha256',canonicalObservation($input),true);
}

final class MarketFlow {
    private array $assets=[];
    private array $sources=[];
    private array $routes=[];
    private array $history=[];
    private array $current=[];

    public function __construct(array $assets,array $sources,array $routes) {
        foreach($assets as $id){$id=identity($id);requireValue(!isset($this->assets[$id]),'duplicate_asset');$this->assets[$id]=true;}
        foreach($sources as $id){$id=identity($id);requireValue(!isset($this->sources[$id]),'duplicate_source');$this->sources[$id]=true;}
        foreach($routes as $route){
            requireValue(is_array($route)&&isset($route['id'],$route['asset_id'],$route['source_id']),'route');
            $id=identity($route['id']);$asset=identity($route['asset_id']);$source=identity($route['source_id']);
            requireValue(isset($this->assets[$asset],$this->sources[$source])&&!isset($this->routes[$id]),'route_catalog');
            $this->routes[$id]=['asset_id'=>$asset,'source_id'=>$source];
        }
    }
    public function history(): array {return $this->history;}
    public function current(): array {return $this->current;}

    public function write(array $input,bool $failAfterHistory=false): array {
        $row=normalizeObservation($input);$asset=$row['asset_id'];
        requireValue(isset($this->assets[$asset]),'unknown_asset');
        requireValue(isset($this->sources[$row['source_id']]),'unknown_source');
        requireValue(isset($this->routes[$row['route_id']]),'unknown_route');
        $route=$this->routes[$row['route_id']];
        requireValue($route['asset_id']===$asset,'route_asset');
        requireValue($route['source_id']===$row['source_id'],'route_source');
        $previous=$this->current[$asset]??null;
        // Arbitration is outside this reference contract: reject a route change.
        requireValue($previous===null||($previous['route_id']===$row['route_id']&&$previous['source_id']===$row['source_id']),'selected_route_changed');
        $key=bin2hex(dedupeKey($row));
        if(isset($this->history[$key])){
            requireValue($this->history[$key]===$row,'dedupe_conflict');
            return ['history'=>'duplicate','current'=>'unchanged','dedupe_key'=>$key];
        }
        // Stage both projections with PHP copy-on-write; publish only on success.
        $history=$this->history;$current=$this->current;$history[$key]=$row;
        if($failAfterHistory)throw new RuntimeException('simulated_after_history');
        $replace=$previous===null||strcmp($row['market_at'],$previous['market_at'])>0
            ||($row['market_at']===$previous['market_at']&&strcmp($row['observed_at'],$previous['observed_at'])>0);
        if($replace){
            // volume belongs to History; Current has no volume column in 0002.
            $projection=$row;unset($projection['volume']);$current[$asset]=$projection;
        }
        $result=['history'=>'inserted','current'=>$replace?'updated':'unchanged','dedupe_key'=>$key];
        $this->history=$history;$this->current=$current;
        return $result;
    }
}
