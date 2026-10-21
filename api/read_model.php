<?php
declare(strict_types=1);
namespace Mosa2\MarketRead;
use PDO;
use DateTimeImmutable;
use DateTimeZone;
use RuntimeException;
require_once __DIR__.'/market_core/selection.php';

/** No write capability, provider dependency or caller-controlled SQL. */
function timestamp(string $value): DateTimeImmutable {
    $date=DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u',$value,new DateTimeZone('UTC'));
    if(!$date||$date->format('Y-m-d H:i:s.u')!==$value)throw new RuntimeException('market_timestamp');return $date;
}
function present(array $row,string $now,int $staleSeconds): array {
    $base=['name'=>$row['display_name'],'source'=>$row['source_name'],'venue'=>$row['venue']];
    if($row['price']===null)return $base+['status'=>'missing'];
    if($row['valid_binding']!=='1'||!is_string($row['price'])||!preg_match('/^-?[0-9]+\.[0-9]{10}$/D',$row['price']))throw new RuntimeException('market_binding');
    $age=\Mosa2\QuoteSelection\age($row,$now);
    return $base+['status'=>$age>$staleSeconds?'stale':'stored',
        'price'=>$row['price'],'unit'=>$row['quote_unit_key'],'unit_version'=>$row['quote_unit_version'],
        'currency'=>$row['currency'],'quantity_basis_unit'=>$row['quantity_basis_unit_key'],
        'quantity_basis_amount'=>$row['quantity_basis_amount'],'market_at'=>$row['market_at'].'Z','observed_at'=>$row['observed_at'].'Z'];
}
function read(PDO $p,array $config,string $now): array {
    require_once __DIR__.'/current_read.php';
    return \Mosa2\CurrentRead\read($p,$config,$now);
}
