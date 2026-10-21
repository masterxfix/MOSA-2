<?php
declare(strict_types=1);
require $argv[1].'/api/current_read.php';
$source=file_get_contents($argv[1].'/tests/fixtures/observation_read.php');
$source=substr($source,5,strpos($source,'$db=new ObservationConnection')-5);
$source=str_replace('require $argv','require_once $argv',$source);eval($source);
class WebScalar extends PDOStatement {public function fetchColumn(int $column=0):mixed{return '1';}}
class WebCurrentStatement extends PDOStatement {
    private array $params=[];
    public function __construct(private WebCurrentConnection $db,private string $sql){}
    public function execute(?array $params=null):bool{$this->params=$params??[];$this->db->parameters[]=$this->params;return true;}
    private function index():int {
        if(str_contains($this->sql,'normalized_value'))return array_search($this->params[0],array_keys(\Mosa2\ObservationRead\SCOPE),true);
        return (int)$this->params[str_contains($this->sql,'m2_market_observations')?1:0]-1100;
    }
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array {
        $i=$this->index();$isin=array_keys(\Mosa2\ObservationRead\SCOPE)[$i];$r=routeRow($isin);
        $r['asset_id']=(string)(1100+$i);$r['route_id']=(string)(7100+$i);
        if($i===0){
            if($this->db->case==='route')$r['external_key']='wrong';
            if($this->db->case==='unit')$r['unit_currency']='GBP';
            if($this->db->case==='source')$r['source_enabled']='0';
        }return [$r];
    }
    public function fetch(int $mode=PDO::FETCH_DEFAULT,int $orientation=PDO::FETCH_ORI_NEXT,int $offset=0):mixed {
        $i=$this->index();if($this->db->case==='missing'&&$i===0&&str_contains($this->sql,'m2_market_current'))return false;
        $f=fact((string)(9000+$i));$f['asset_id']=(string)(1100+$i);$f['route_id']=(string)(7100+$i);
        if($i===0&&$this->db->case==='decimal')$f['price']='123456789012345678.1234567890';
        if($this->db->case==='fresh'){$f['market_at']='2026-01-01 00:59:00.000000';$f['observed_at']='2026-01-01 00:59:01.000000';}
        $payload=array_intersect_key($f,array_flip(\Mosa2\QuoteSelection\FIELDS));
        $f['dedupe_key']=strtoupper(hash('sha256',"mosa2-observation-v2\n".json_encode($payload,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE)));unset($f['dedupe_hex']);
        if(str_contains($this->sql,'m2_market_observations'))return $f;
        $c=$f;unset($c['id'],$c['dedupe_key'],$c['volume'],$c['volume_unit_key'],$c['volume_unit_version']);
        $c+=['observation_id'=>$f['id'],'observation_dedupe_key'=>$f['dedupe_key'],'route_revision'=>'1','updated_at'=>'2026-01-01 00:59:10.000000'];
        if($i===0&&$this->db->case==='provenance')$c['observation_dedupe_key']=str_repeat('0',64);
        if($i===0&&$this->db->case==='current_price')$c['price']='3.0000000000';
        if($i===0&&$this->db->case==='current_source')$c['source_id']='999';
        return $c;
    }
}
class WebCurrentConnection extends PDO {
    public array $events=[],$sql=[],$parameters=[];private bool $active=false;
    public function __construct(public string $case='valid'){}
    public function prepare(string $sql,array $options=[]):PDOStatement|false {
        if(!str_starts_with($sql,'SELECT ')||preg_match('/\b(?:INSERT|UPDATE|DELETE|OUTFILE|DUMPFILE)\b/',$sql))throw new RuntimeException('mutation');
        $this->sql[]=$sql;return new WebCurrentStatement($this,$sql);
    }
    public function query(string $sql,?int $fetchMode=null,mixed ...$args):PDOStatement|false{$this->sql[]=$sql;return new WebScalar();}
    public function exec(string $sql):int|false {
        if(!in_array($sql,['SET SESSION TRANSACTION READ ONLY','SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'],true))throw new RuntimeException('unsafe control');
        $this->events[]=$sql;return 0;
    }
    public function beginTransaction():bool{$this->active=true;$this->events[]='BEGIN';return true;}
    public function inTransaction():bool{return $this->active;}
    public function rollBack():bool{$this->active=false;$this->events[]='ROLLBACK';return true;}
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    $db=new WebCurrentConnection($argv[2]??'valid');
    try{$reply=\Mosa2\MarketRead\read($db,['assets'=>[['asset_id'=>'old','route_id'=>'old']],'stale_seconds'=>1800],NOW);}
    catch(Throwable){$reply=['status'=>'error'];}
    echo json_encode($reply+['events'=>$db->events,'sql'=>$db->sql,'parameters'=>$db->parameters],JSON_THROW_ON_ERROR);
}
