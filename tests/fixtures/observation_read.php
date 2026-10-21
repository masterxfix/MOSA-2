<?php
declare(strict_types=1);
require $argv[1].'/api/observations_read.php';
require $argv[1].'/scripts/phase3d/dry_run.php';
use function Mosa2\ObservationRead\externalKey;
use const Mosa2\ObservationRead\SCOPE;
const NOW='2026-01-01 01:00:00.000000';
function routeRow(string $isin): array {
    return ['isin'=>$isin,'asset_id'=>'101','asset_class'=>'equity','asset_status'=>'active',
        'source_enabled'=>'1','source_type'=>'market_data','source_id'=>'201','source_key'=>'provider:boerse_frankfurt_api','source_name'=>'Synthetic source',
        'route_id'=>'301','route_revision'=>'1','route_type'=>'quote','external_key'=>externalKey($isin),'priority'=>'0','enabled'=>'0',
        'unit_contract_version'=>'mosa2-market-unit-v1','quote_unit_key'=>'EUR','quote_unit_version'=>'1',
        'quantity_basis_unit_key'=>null,'quantity_basis_unit_version'=>null,'quantity_basis_amount'=>null,'volume_unit_key'=>null,'volume_unit_version'=>null,
        'unit_status'=>'frozen','unit_currency'=>'EUR','unit_dimension'=>'monetary','unit_base'=>'EUR','unit_base_version'=>'1','unit_scale_numerator'=>'1','unit_scale_denominator'=>'1'];
}
function fact(string $id='9002',string $market='2026-01-01 00:00:00.000000',string $observed='2026-01-01 00:00:03.000000',string $price='2.0000000000'): array {
    $r=['asset_id'=>'101','source_id'=>'201','route_id'=>'301','currency'=>'EUR','market_at'=>$market,'observed_at'=>$observed,'price'=>$price,
        'bid'=>null,'ask'=>null,'volume'=>null,'unit_contract_version'=>'mosa2-market-unit-v1','quote_unit_key'=>'EUR','quote_unit_version'=>'1',
        'quantity_basis_unit_key'=>null,'quantity_basis_unit_version'=>null,'quantity_basis_amount'=>null,'volume_unit_key'=>null,'volume_unit_version'=>null];
    return $r+['id'=>$id,'observation_format_version'=>'2','dedupe_hex'=>strtoupper(hash('sha256',"mosa2-observation-v2\n".json_encode($r,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE)))];
}
class ObservationStatement extends PDOStatement {
    public array $params=[];
    public function __construct(public ObservationConnection $db,public string $sql){}
    public function execute(?array $params=null):bool {$this->params=$params??[];$this->db->parameters[]=$params;
        if($this->db->case==='query'&&str_contains($this->sql,'m2_market_observations'))throw new RuntimeException('PRIVATE_CANARY SQL');
        return true;}
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array {
        $case=$this->db->case;
        if(!str_contains($this->sql,'m2_market_observations')){
            $r=routeRow($this->params[0]);
            if($case==='scope')$r['asset_status']='inactive';
            if($case==='source_disabled')$r['source_enabled']='0';
            if($case==='source_type')$r['source_type']='other';
            if($case==='generic_class')$r['asset_class']='index';
            if($case==='scope_unit')$r['unit_currency']='GBP';
            if($case==='scope_key')$r['external_key']='market-v1:wrong';
            return [$r];
        }
        if($case==='missing')return [];
        $r=fact();
        if($case==='legacy'){$r['observation_format_version']=null;return [$r];}
        if($case==='route')$r['route_id']='999';
        if($case==='source')$r['source_id']='999';
        if($case==='unit')$r['quote_unit_key']='GBP';
        if($case==='format')$r['observation_format_version']='1';
        if($case==='hash')$r['dedupe_hex']=str_repeat('0',64);
        if($case==='future')$r=fact('9002','2026-01-02 00:00:00.000000','2026-01-02 00:00:00.000000');
        $rows=[$r,fact('9001','2026-01-01 00:00:00.000000','2026-01-01 00:00:02.000000','1.0000000000'),
            fact('9003','2025-12-31 23:59:59.000000','2026-01-01 00:59:59.000000','9.0000000000')];
        if($case==='equal_conflict')$rows[1]=fact('9001','2026-01-01 00:00:00.000000','2026-01-01 00:00:03.000000','3.0000000000');
        if(in_array($case,['bounded','boundary'],true)){
            while(count($rows)<101){$old=fact((string)(1000+count($rows)),'2025-12-31 22:00:00.000000','2025-12-31 22:00:01.000000');$old['observation_format_version']=null;$rows[]=$old;}
            if($case==='boundary')$rows[100]['market_at']='2026-01-01 00:00:00.000000';
        }
        return $rows;
    }
}
class ObservationConnection extends PDO {
    public array $events=[],$sql=[],$parameters=[];private bool $active=false;
    public function __construct(public string $case){}
    public function prepare(string $query,array $options=[]):PDOStatement|false{$this->sql[]=$query;return new ObservationStatement($this,$query);}
    public function exec(string $statement):int|false{$this->events[]=$statement;return 0;}
    public function beginTransaction():bool{$this->active=true;$this->events[]='BEGIN';return true;}
    public function inTransaction():bool{return $this->active;}
    public function rollBack():bool{$this->active=false;$this->events[]='ROLLBACK';return true;}
}
$db=new ObservationConnection($argv[2]);
try{$result=\Mosa2\ObservationRead\read($db,['stale_seconds'=>1800],NOW);}catch(Throwable){$result=['status'=>'error'];}
$match=true;foreach(array_keys(SCOPE) as $isin){
    $e=['sample_id'=>'synthetic','source_reference'=>'qualified','family'=>'frankfurt_snapshot','row'=>['isin'=>$isin,'provider_key'=>'boerse_frankfurt_api','venue_key'=>'boerse_frankfurt','currency'=>'EUR','quote_variant'=>null,'series'=>'snapshot','observation_kind'=>'market_quote'],
        'proof'=>['external_identity'=>['isin'=>$isin,'venue'=>'boerse_frankfurt'],'route_reference'=>'synthetic','unit_class'=>'currency_per_instrument']];
    $key=\Mosa2\Phase3D\candidate($e)['proposed_route_key'];$match=$match&&externalKey($isin)==='market-v1:'.hash('sha256',$key);
}
echo json_encode($result+['events'=>$db->events,'parameters'=>$db->parameters,'sql'=>$db->sql,'route_contract_matches'=>$match]);
