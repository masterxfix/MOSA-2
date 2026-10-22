<?php
declare(strict_types=1);
require_once $argv[1].'/scripts/market_current/historical_scope.php';
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
        $readSql=str_ends_with($query,' FOR UPDATE')?substr($query,0,-11):$query;
        if(!str_starts_with($readSql,'SELECT ')||preg_match('/\b(?:INTO|OUTFILE|DUMPFILE|UPDATE|DELETE|INSERT)\b/',$readSql))throw new RuntimeException('write attempt');
        return new PreviewStatement($this,$query);
    }
    public function exec(string $sql):int|false {if($sql!=='SET TRANSACTION READ ONLY')throw new RuntimeException('non-readonly control');$this->events[]=$sql;return 0;}
    public function beginTransaction():bool {$this->active=true;$this->events[]='BEGIN';return true;}
    public function inTransaction():bool{return $this->active;}
    public function commit():bool{throw new RuntimeException('commit forbidden');}
    public function rollBack():bool{$this->active=false;$this->events[]='ROLLBACK';return true;}
}
class GuardStatement extends PDOStatement {
    public function __construct(private mixed $value){}
    public function fetch(int $mode=PDO::FETCH_DEFAULT,int $orientation=PDO::FETCH_ORI_NEXT,int $offset=0):mixed{return $this->value;}
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array{return $this->value;}
    public function fetchColumn(int $column=0):mixed{return $this->value;}
}
class GuardConnection extends PreviewConnection {
    public array $queries=[];private string $readOnly='0';
    public function __construct(array $state,private string $fault){parent::__construct($state);}
    public function query(string $query,?int $fetchMode=null,mixed ...$fetchModeArgs):PDOStatement|false {
        $this->queries[]=$query;
        if(str_contains($query,'CURRENT_USER()'))return new GuardStatement(['db'=>'h29077_mosa2_test','account'=>$this->fault==='identity'?'unexpected':'h29077_mosa2_read@localhost']);
        if(str_contains($query,'VERSION()'))return new GuardStatement(['version'=>$this->fault==='engine'?'10.11.8-MariaDB':'8.0.26-16','comment'=>'synthetic']);
        if(str_starts_with($query,'SHOW SESSION VARIABLES'))return new GuardStatement($this->fault==='unsupported'?[]:[
            ['Variable_name'=>'transaction_read_only','Value'=>'OFF'],['Variable_name'=>'transaction_isolation','Value'=>'REPEATABLE-READ']]);
        if($query==='SELECT @@partial_revokes')return new GuardStatement('1');
        if($query==='SHOW GRANTS FOR CURRENT_USER'&&$this->fault==='missing_select')return new GuardStatement([]);
        if($query==='SHOW GRANTS FOR CURRENT_USER')return new GuardStatement([
            ['grant'=>'GRANT '.($this->fault==='privileges'?'SELECT, INSERT':'SELECT').' ON `h29077_mosa2_test`.* TO x']]);
        if(str_starts_with($query,'SELECT @@session.transaction_read_only')){
            $value=$this->readOnly;
            if($this->fault==='session'||($this->fault==='transaction'&&$this->inTransaction()))$value='0';
            return new GuardStatement(['read_only'=>$value,'isolation'=>$this->fault==='isolation'?'READ-COMMITTED':'REPEATABLE-READ']);
        }
        throw new RuntimeException('SQL private detail password secret price 123.45');
    }
    public function exec(string $sql):int|false {
        if($this->fault==='setup')throw new RuntimeException('SQL private detail password secret price 123.45');
        if(!in_array($sql,['SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ','SET SESSION TRANSACTION READ ONLY'],true))throw new RuntimeException('write forbidden');
        if($sql==='SET SESSION TRANSACTION READ ONLY')$this->readOnly='1';
        $this->events[]=$sql;return 0;
    }
    public function beginTransaction():bool {if($this->fault==='begin')return false;return parent::beginTransaction();}
    public function rollBack():bool {parent::rollBack();return $this->fault!=='rollback';}
    public function prepare(string $query,array $options=[]):PDOStatement|false {
        if($this->fault==='snapshot')throw new RuntimeException('private SQL secret');
        return parent::prepare($query,$options);
    }
}
if($request['action']==='guard'){
    $db=new GuardConnection($request['items'],$request['fault']??'');$before=$db->state;
    if(($request['fault']??'')==='active')$db->beginTransaction();
    $reply=\Mosa2\CurrentPreview\readSnapshot($db);
    echo json_encode(['reply'=>$reply,'calls'=>$db->calls,'events'=>$db->events,'queries'=>$db->queries,
        'unchanged'=>$before===$db->state,'active'=>$db->inTransaction()],JSON_THROW_ON_ERROR);exit;
}
$db=new PreviewConnection($request['items']);$before=$db->state;
if($request['action']==='fresh'){
    require_once $argv[1].'/scripts/market_current/takeover.php';$db->beginTransaction();
    try{$items=\Mosa2\CurrentTakeover\fresh($db,$request['now']);}finally{$db->rollBack();}
    echo json_encode(['items'=>$items,'calls'=>$db->calls,'unchanged'=>$before===$db->state],JSON_THROW_ON_ERROR);exit;
}
$db->exec('SET TRANSACTION READ ONLY');$db->beginTransaction();
try{$snapshot=\Mosa2\CurrentPreview\gather($db,$request['now']);}finally{$db->rollBack();}
echo json_encode(['snapshot'=>$snapshot,'calls'=>$db->calls,'events'=>$db->events,'unchanged'=>$before===$db->state],JSON_THROW_ON_ERROR);
