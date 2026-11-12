<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/api/market_core/twelve_data.php';
use function Mosa2\MarketInternational\TwelveData\reserve;

$dsn=getenv('M2_LOCAL_MYSQL_DSN');
if(!is_string($dsn)||!str_starts_with($dsn,'mysql:host=127.0.0.1;'))
    throw new RuntimeException('test_only_isolated_mysql_required');
$db=new PDO($dsn,'root',(string)getenv('M2_LOCAL_MYSQL_PASSWORD'),
    [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
     PDO::ATTR_EMULATE_PREPARES=>false]);
$db->exec("CREATE TABLE m2_sync_checkpoints (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  source_id BIGINT UNSIGNED NOT NULL,
  stream_key VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
  cursor_value VARCHAR(512) NULL,
  watermark_at DATETIME(6) NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_checkpoints_stream (source_id,stream_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
$assert=static function(bool $truth,string $label):void {
    if(!$truth)throw new RuntimeException('international budget test: '.$label);
};
$cfg=['max_daily_requests'=>3,'max_minute_requests'=>2];
$t1=new DateTimeImmutable('2026-11-12T12:04:00+00:00');
$t2=new DateTimeImmutable('2026-11-12T12:05:00+00:00');
$t3=new DateTimeImmutable('2026-11-13T00:00:00+00:00');
$assert(reserve($db,'91',$cfg,$t1),'first credit reserved');
$assert(reserve($db,'91',$cfg,$t1),'second credit reserved');
$read=static function(PDO $db,string $stream):string {
    $q=$db->prepare('SELECT cursor_value FROM m2_sync_checkpoints WHERE source_id=? AND stream_key=?');
    $q->execute(['91',$stream]);
    return (string)$q->fetchColumn();
};
$assert($read($db,'twelvedata_day_budget')==='2026-11-12|2','day reservation 2');
$assert($read($db,'twelvedata_minute_budget')==='2026-11-12 12:04|2','minute reservation 2');
$assert(!reserve($db,'91',$cfg,$t1),'minute cap prevents third GET');
$assert($read($db,'twelvedata_day_budget')==='2026-11-12|2','rejected credit does not burn day allowance');
$assert(reserve($db,'91',$cfg,$t2),'next minute accepts third daily GET');
$assert($read($db,'twelvedata_day_budget')==='2026-11-12|3','daily cap exactly 3');
$assert(!reserve($db,'91',$cfg,$t2),'day cap rejects further GET');
$assert($read($db,'twelvedata_minute_budget')==='2026-11-12 12:05|1',
    'day limit does not create phony request budget');
$assert(reserve($db,'91',$cfg,$t3),'new UTC day resets quotas');
$assert($read($db,'twelvedata_day_budget')==='2026-11-13|1','UTC reset persisted');
$assert(!$db->inTransaction(),'quota reservations close all transactions');
try{reserve($db,'not-a-source-id',$cfg,$t3);throw new RuntimeException('invalid source accepted');}
catch(InvalidArgumentException){$assert(true,'invalid source id rejected');}
$bad=$db->prepare("UPDATE m2_sync_checkpoints SET cursor_value='2026-11-13|NaN'
    WHERE source_id=91 AND stream_key='twelvedata_day_budget'");
$bad->execute();
try{reserve($db,'91',$cfg,$t3);throw new RuntimeException('corrupted budget accepted');}
catch(InvalidArgumentException){$assert(true,'corrupted counter fails closed');}
$assert(!$db->inTransaction(),'corruption rolled back SQL transaction');
echo "PASS 16/16 isolated MySQL daily/minute budget guard checks\n";
