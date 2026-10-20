<?php
declare(strict_types=1);
require dirname(__DIR__).'/scripts/market_collector/onboarding.php';
use function Mosa2\MarketIdentity\{planAssetIdentity,planMarketRoute,applyAssetIdentityPlan,entityValues,assetValues};
final class IdentityMemoryStore implements \Mosa2\MarketIdentity\Store {
    public array $writes=[];
    public function __construct(public array $state){}
    public function find(string $t,array $w): array {return array_values(array_filter($this->state[$t]??[],static fn($r)=>\Mosa2\MarketIdentity\matchFields($r,$w)));}
    public function insert(string $t,array $row): string {$id=(string)(100+count($this->writes));$this->writes[]=['table'=>$t,'row'=>$row];$this->state[$t][]=$t==='m2_assets'?$row:['id'=>$id]+$row;return $id;}
}
$in=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
try{
    if($in['action']==='asset'){
        $plan=planAssetIdentity($in['state'],$in['identity']);$out=['plan'=>$plan];
        if($in['apply']??false){$s=new IdentityMemoryStore($in['state']);$out['applied']=applyAssetIdentityPlan($s,$plan,'2026-01-01 00:00:00.000000');$out['writes']=$s->writes;$out['replay']=planAssetIdentity($s->state,$in['identity']);}
    }else $out=planMarketRoute($in['routes'],$in['qualified'],$in['units']);
    echo json_encode(['ok'=>true,'result'=>$out],JSON_THROW_ON_ERROR);
}catch(Throwable $e){echo json_encode(['ok'=>false,'error'=>$e->getMessage()],JSON_THROW_ON_ERROR);}
