<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/fundamentals/core.php';
/** In-memory SQL double only: deterministic failures, never a real connection. */
class MemoryStatement extends PDOStatement {
    public array $rows=[];
    public function __construct(private MemoryPDO $p,private string $sql){}
    public function execute(?array $params=null):bool{$this->rows=$this->p->run($this->sql,$params??[]);return true;}
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array{return $this->rows;}
    public function fetchColumn(int $column=0):mixed{return array_values($this->rows[0]??[] )[$column]??false;}
}
class MemoryPDO extends PDO {
    public array $data=[];private array $saved=[];private bool $tx=false;public int $writes=0;public int $commits=0;public int $rollbacks=0;private int $last=0;
    public function __construct(public int $failWrite=0,public bool $uncertainCommit=false){}
    public function prepare(string $query,array $options=[]):PDOStatement|false{return new MemoryStatement($this,$query);}
    public function query(string $query,?int $fetchMode=null,mixed ...$args):PDOStatement|false{$s=$this->prepare($query);$s->execute();return $s;}
    public function lastInsertId(?string $name=null):string|false{return (string)$this->last;}
    public function beginTransaction():bool{$this->saved=$this->data;$this->tx=true;return true;}
    public function inTransaction():bool{return $this->tx;}
    public function rollBack():bool{$this->data=$this->saved;$this->tx=false;$this->rollbacks++;return true;}
    public function commit():bool{$this->commits++;$this->tx=false;if($this->uncertainCommit)throw new RuntimeException('lost_confirmation');return true;}
    public function run(string $sql,array $args):array {
        if(preg_match('/^SELECT \* FROM `([a-z0-9_]+)` LIMIT 257$/',$sql,$m))
            return array_slice($this->data[$m[1]]??[],0,257);
        if(preg_match('/^INSERT INTO `([a-z0-9_]+)` \((.+)\) VALUES/',$sql,$m)){
            $this->writes++;if($this->writes===$this->failWrite)throw new RuntimeException('injected_write');
            $columns=array_map(fn($x)=>trim($x,'`'),explode(',',$m[2]));$r=array_combine($columns,$args);
            if(in_array($m[1],['m2_sources','m2_files','m2_provider_fetches','m2_fundamental_observations']))$r=['id'=>(string)++$this->last]+$r;
            $this->data[$m[1]][]=$r;return [];
        }
        if(preg_match('/^SELECT COUNT\(\*\) FROM `([a-z0-9_]+)`/',$sql,$m))return [['n'=>count($this->data[$m[1]]??[])]];
        if(str_starts_with($sql,'SELECT c.*,o.dedupe_key')){
            foreach($this->data['m2_fundamental_current']??[] as $r)if([$r['asset_id'],$r['metric_key'],$r['period_type']]===$args){
                foreach($this->data['m2_fundamental_observations'] as $o)if($o['id']===$r['observation_id'])return [$r+['dedupe_key'=>$o['dedupe_key']]];
            }return [];
        }
        if(preg_match('/^UPDATE m2_fundamental_current SET (.+) WHERE/',$sql,$m)){
            $this->writes++;if($this->writes===$this->failWrite)throw new RuntimeException('injected_update');
            preg_match_all('/`([a-z_]+)`=\?/',$m[1],$cols);$n=count($cols[1]);$key=array_slice($args,$n);
            foreach($this->data['m2_fundamental_current'] as &$row)if([$row['asset_id'],$row['metric_key'],$row['period_type']]===$key)$row=array_combine($cols[1],array_slice($args,0,$n));
            unset($row);return [];
        }
        if(preg_match('/^SELECT \* FROM `?([a-z0-9_]+)`? WHERE (.+)/',$sql,$m)){
            preg_match_all('/`?([a-z_]+)`?=\?/',$m[2],$keys);$rows=$this->data[$m[1]]??[];
            return array_values(array_filter($rows,function($r)use($keys,$args){foreach($keys[1] as $i=>$k)if($r[$k]!==$args[$i])return false;return true;}));
        }
        throw new RuntimeException('unhandled_sql');
    }
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')!==__FILE__)return;
$plan=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
$out=[];
foreach([0,1,3,7,10,14,18,19] as $fail){$p=new MemoryPDO($fail);$ok=false;
    try{$receipt=\Mosa2\Fundamentals\transaction($p,$plan,'42',fn()=>null);$ok=true;}catch(Throwable $e){$failure=$e->getMessage();}
    $out[]=['ok'=>$ok,'writes'=>$p->writes,'commits'=>$p->commits,'rollbacks'=>$p->rollbacks,'empty'=>$p->data===[],
        'current_years'=>array_column($p->data['m2_fundamental_current']??[],'fiscal_year'),'error'=>$ok?null:$failure];
}
$p=new MemoryPDO(0,true);try{\Mosa2\Fundamentals\transaction($p,$plan,'42',fn()=>null);}catch(Throwable){}
$out[]=['commits'=>$p->commits,'rollbacks'=>$p->rollbacks,'retained'=>!empty($p->data)];
echo json_encode($out,JSON_THROW_ON_ERROR);
