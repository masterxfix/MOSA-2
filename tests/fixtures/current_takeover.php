<?php
declare(strict_types=1);
require $argv[1].'/scripts/market_current/refresh.php';
$in=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
class CurrentScalar extends PDOStatement {
    public function fetchColumn(int $column=0):mixed{return '1';}
}
class CurrentWrite extends PDOStatement {
    public function __construct(private CurrentMemory $db,private string $sql){}
    public function execute(?array $params=null):bool {
        $this->db->writes++;
        if($this->db->fault==='write'&&$this->db->writes===3)throw new RuntimeException('synthetic write failure');
        if(str_starts_with($this->sql,'INSERT INTO m2_market_current ')){
            preg_match('/\(([^)]+)\) VALUES /',$this->sql,$m);$keys=explode(',',str_replace('`','',$m[1]));$row=array_combine($keys,$params);
        }elseif(str_starts_with($this->sql,'UPDATE m2_market_current SET ')){
            $asset=array_pop($params);preg_match('/ SET (.+) WHERE asset_id=\?/',$this->sql,$m);
            $parts=explode(',',$m[1]);$keys=[];foreach($parts as $part){preg_match('/^`([a-z_]+)`=/',$part,$key);$keys[]=$key[1];}
            $row=array_combine($keys,$params);if($asset!==$row['asset_id'])throw new RuntimeException('update scope');
        }else throw new RuntimeException('non-current SQL');
        $rows=&$this->db->state['m2_market_current'];$rows=array_values(array_filter($rows,static fn($r)=>$r['asset_id']!==$row['asset_id']));$rows[]=$row;
        return true;
    }
    public function rowCount():int{return $this->db->fault==='rowcount'?0:1;}
}
class CurrentMemory extends PDO {
    public array $events=[],$state,$baseline;public int $writes=0;private bool $active=false;
    public function __construct(array $state,public string $fault){$this->state=$state;$this->baseline=$state;}
    public function query(string $query,?int $fetchMode=null,mixed ...$args):PDOStatement|false {
        if(!str_contains($query,'GET_LOCK')&&!str_contains($query,'RELEASE_LOCK'))throw new RuntimeException('unknown query');
        $this->events[]=str_contains($query,'GET_LOCK')?'LOCK':'UNLOCK';return new CurrentScalar();
    }
    public function prepare(string $query,array $options=[]):PDOStatement|false{return new CurrentWrite($this,$query);}
    public function exec(string $sql):int|false {$this->events[]=$sql;return 0;}
    public function beginTransaction():bool{$this->events[]='BEGIN';$this->active=$this->fault!=='begin';return $this->active;}
    public function inTransaction():bool{return $this->active;}
    public function rollBack():bool{if($this->fault==='rollback')throw new RuntimeException('private rollback SQL secret');$this->events[]='ROLLBACK';$this->state=$this->baseline;$this->active=false;return true;}
    public function commit():bool{if($this->fault==='commit')return false;$this->events[]='COMMIT';$this->active=false;if($this->fault==='commit_unknown')throw new RuntimeException('private commit secret');return true;}
}
$db=new CurrentMemory($in['before'],$in['fault']??'');$captures=0;$progress=[];
$outcome=new \Mosa2\MarketCurrent\Outcome(static function($event)use(&$progress){$progress[]=$event;});
try{
    $capture=static function($p)use(&$captures,$outcome){$captures++;if($p->fault==='rollback')throw new RuntimeException('private failure');if($p->fault==='timeout_before_commit'){$outcome->cause='PLANNER_TIMEOUT';throw new RuntimeException('current_planner_timeout');}if($captures===2&&$p->fault==='other')$p->state['m2_market_observations'][]=['corruption'=>'synthetic'];return $p->state;};
    $result=\Mosa2\MarketCurrent\transaction($db,static fn($p,$now)=>[],static fn($items)=>$in['plans'],$capture,$outcome);
    if($db->fault==='timeout_after_commit'){$outcome->cause='PHASE_TIMEOUT';throw new RuntimeException('current_phase_timeout');}
    $actual=$db->state;if($db->fault==='readback')$actual['m2_market_current']=[];
    $outcome->step('READBACK');
    $result=\Mosa2\MarketCurrent\verifyReadback($result,$actual,array_fill(0,5,['decision'=>$db->fault==='replay'?'UPDATE':'UNCHANGED']),$outcome);
    $outcome->step('COMPLETE');
    $reply=['ok'=>true,'readback'=>$result['readback']];
}catch(Throwable $error){if($outcome->cause==='NONE')$outcome->cause=$outcome->commit==='CONFIRMED'?'POST_COMMIT_ERROR':'TRANSACTION_ERROR';$reply=['ok'=>false];}
echo json_encode($reply+['outcome'=>$outcome->report($reply['ok']),'progress'=>$progress,'events'=>$db->events,'state'=>$db->state,'writes'=>$db->writes],JSON_THROW_ON_ERROR);
