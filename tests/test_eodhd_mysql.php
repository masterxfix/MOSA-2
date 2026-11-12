<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/api/market_core/eodhd.php';
use function Mosa2\MarketInternational\Eodhd\{reserve,cachedRoute,saveRoute,saveUnavailable};
$dsn=getenv('M2_LOCAL_MYSQL_DSN');
if(!is_string($dsn)||!str_starts_with($dsn,'mysql:host=127.0.0.1;'))
    throw new RuntimeException('isolated test MySQL required');
$db=new PDO($dsn,'root',(string)getenv('M2_LOCAL_MYSQL_PASSWORD'),
    [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,
     PDO::ATTR_EMULATE_PREPARES=>false]);
$db->exec("CREATE TABLE IF NOT EXISTS m2_sync_checkpoints (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 source_id BIGINT UNSIGNED NOT NULL,
 stream_key VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
 cursor_value VARCHAR(512) NULL,
 watermark_at DATETIME(6) NULL,
 updated_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_checkpoints_stream (source_id,stream_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
$n=0;
$verify=static function(bool $pass,string $test)use(&$n):void {
    if(!$pass)throw new RuntimeException('EODHD isolated MySQL: '.$test);$n++;
};
$cfg=['max_daily_requests'=>3,'max_minute_requests'=>2];
$t1=new DateTimeImmutable('2026-11-12T02:04:00Z');
$t2=new DateTimeImmutable('2026-11-12T02:05:00Z');
$t3=new DateTimeImmutable('2026-11-13T00:00:00Z');
$verify(reserve($db,'319',$cfg,$t1),'first paid HTTP credit');
$verify(reserve($db,'319',$cfg,$t1),'second paid HTTP credit');
$verify(!reserve($db,'319',$cfg,$t1),'exact UTC minute limit');
$verify(reserve($db,'319',$cfg,$t2),'new UTC minute credit');
$verify(!reserve($db,'319',$cfg,$t2),'exact UTC daily limit');
$verify(reserve($db,'319',$cfg,$t3),'new UTC day credit');
$verify(!$db->inTransaction(),'no budget transactions left open');
$isin='AU000000DRO2';$route=['isin'=>$isin,'ticker'=>'DRO.AU','currency'=>'AUD',
    'mic'=>'XASX','venue_label'=>'Australian Securities Exchange'];
$verify(cachedRoute($db,'319',$isin,$t1)===null,'route initially unknown');
saveRoute($db,'319',$isin,$route,$t1);
$read=cachedRoute($db,'319',$isin,$t1);
$verify(($read['ticker']??null)==='DRO.AU','cache verified ISIN-linked ticker');
$verify(($read['mic']??null)==='XASX','cache physically resolved MIC');
$verify(($read['currency']??null)==='AUD','cache original monetary unit');
$verify(cachedRoute($db,'319','NO0010081235',$t1)===null,'cache is not cross-ISIN');
$expired=$t1->modify('+15 days');
$verify(cachedRoute($db,'319',$isin,$expired)===null,'positive cache bounded to 14 days');
saveUnavailable($db,'319',$isin,$t1);
$read=cachedRoute($db,'319',$isin,$t1);
$verify(($read['unavailable']??null)===true,'unavailable ISIN is negatively cached');
$verify(cachedRoute($db,'319',$isin,$t1->modify('+5 hours'))['unavailable']===true,'negative cache within six hours');
$verify(cachedRoute($db,'319',$isin,$t1->modify('+7 hours'))===null,'negative cache expires');
saveRoute($db,'319',$isin,$route,$t1);
$read=cachedRoute($db,'319',$isin,$t1);
$verify(($read['unavailable']??null)!==true,'positive re-evidence replaces negative route');
$q=$db->prepare("SELECT cursor_value FROM m2_sync_checkpoints
 WHERE source_id=319 AND stream_key=?");
$q->execute(['eodhd_route_v1_'.$isin]);
$raw=(string)$q->fetchColumn();
$verify(!str_contains($raw,'api_token')&&!str_contains($raw,'secret'),'no credentials in identity cache');
echo 'PASS '.$n.'/'.$n." isolated MySQL international API budget and exact native route cache checks\n";
