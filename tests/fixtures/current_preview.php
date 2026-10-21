<?php
declare(strict_types=1);
require $argv[1].'/scripts/market_current/preview_read.php';
// Reuse the existing synthetic qualified-scope builder, without its executable tail.
$source=file_get_contents($argv[1].'/tests/fixtures/observation_read.php');
$source=substr($source,5,strpos($source,'$db=new ObservationConnection')-5);
$source=str_replace('require $argv','require_once $argv',$source);eval($source);
$request=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
if($request['action']==='scope'){
    $rows=[];foreach(\Mosa2\ObservationRead\SCOPE as $isin=>$name)$rows[$isin]=routeRow($isin);
    echo json_encode($rows,JSON_THROW_ON_ERROR);exit;
}
class PreviewStatement extends PDOStatement {
    public array $params=[];
    public function __construct(public PreviewConnection $db,public string $sql){}
    public function execute(?array $params=null):bool{$this->params=$params??[];$this->db->calls[]=['sql'=>$this->sql,'params'=>$this->params];return true;}
    public function entry():array {
        foreach($this->db->state as $entry){
            if(str_contains($this->sql,'i.normalized_value')){if($entry['isin']===$this->params[0])return $entry;}
            elseif(str_contains($this->sql,'FROM m2_asset_source_routes')){if($entry['input']['route']['id']===$this->params[0])return $entry;}
            elseif(str_starts_with($this->sql,'SELECT a.entity_id')){if($entry['input']['route']['asset_id']===$this->params[1])return $entry;}
            elseif(str_contains($this->sql,'WHERE id=? AND asset_id=?')){if($entry['input']['route']['asset_id']===$this->params[1])return $entry;}
            elseif($entry['input']['route']['asset_id']===$this->params[0])return $entry;
        }throw new RuntimeException('unbounded or unknown scope');
    }
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array {
        $e=$this->entry();return str_contains($this->sql,'i.normalized_value')?$e['scope_rows']:$e['input']['facts'];
    }
    public function fetch(int $mode=PDO::FETCH_DEFAULT,int $orientation=PDO::FETCH_ORI_NEXT,int $offset=0):mixed {
        $e=$this->entry();
        if(str_contains($this->sql,'FROM m2_asset_source_routes'))return $e['input']['route'];
        if(str_contains($this->sql,'FROM m2_market_current'))return $e['input']['current']??false;
        if(str_contains($this->sql,'WHERE id=? AND asset_id=?'))return $e['input']['current_fact']??false;
        throw new RuntimeException('unknown fetch');
    }
    public function fetchColumn(int $column=0):mixed{return $this->entry()['input']['route']['asset_id'];}
}
class PreviewConnection extends PDO {
    public array $calls=[],$events=[];private bool $active=false;
    public function __construct(public array $state){}
    public function prepare(string $query,array $options=[]):PDOStatement|false {
        if(!str_starts_with($query,'SELECT ')||preg_match('/\b(?:INTO|OUTFILE|DUMPFILE|UPDATE|DELETE|INSERT)\b/',$query))throw new RuntimeException('write attempt');
        return new PreviewStatement($this,$query);
    }
    public function exec(string $sql):int|false {if($sql!=='SET TRANSACTION READ ONLY')throw new RuntimeException('non-readonly control');$this->events[]=$sql;return 0;}
    public function beginTransaction():bool {$this->active=true;$this->events[]='BEGIN';return true;}
    public function inTransaction():bool{return $this->active;}
    public function commit():bool{throw new RuntimeException('commit forbidden');}
    public function rollBack():bool{$this->active=false;$this->events[]='ROLLBACK';return true;}
}
$db=new PreviewConnection($request['items']);$before=$db->state;
$db->exec('SET TRANSACTION READ ONLY');$db->beginTransaction();
try{$snapshot=\Mosa2\CurrentPreview\gather($db,$request['now']);}finally{$db->rollBack();}
echo json_encode(['snapshot'=>$snapshot,'calls'=>$db->calls,'events'=>$db->events,'unchanged'=>$before===$db->state],JSON_THROW_ON_ERROR);
