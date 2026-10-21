<?php
declare(strict_types=1);
require dirname(__DIR__).'/scripts/market_collector/performance_diagnostic.php';
class FakeStatement extends PDOStatement {
    public function execute(?array $params=null): bool {usleep(2000);return true;}
    public function fetchColumn(int $column=0): mixed {return 1;}
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args): array {return [['probe'=>1]];}
    public function fetch(int $mode=PDO::FETCH_DEFAULT,int $orientation=PDO::FETCH_ORI_NEXT,int $offset=0): mixed {return ['probe'=>1];}
}
class FakePDO extends PDO {
    public array $calls=[];public int $writes=0;public bool $transaction=true;
    public function __construct(){}
    public function inTransaction(): bool {return $this->transaction;}
    public function query(string $query,?int $fetchMode=null,mixed ...$args): PDOStatement|false {$this->calls[]=['query',$query];usleep(2000);return new FakeStatement();}
    public function prepare(string $query,array $options=[]): PDOStatement|false {$this->calls[]=['prepare',$query];usleep(2000);return new FakeStatement();}
    public function exec(string $statement): int|false {$this->writes++;return 1;}
    public function commit(): bool {$this->writes++;return true;}
    public function beginTransaction(): bool {$this->writes++;return true;}
    public function rollBack(): bool {$this->writes++;return true;}
}
$in=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);$pdo=new FakePDO();$meter=new \Mosa2\MarketPerformance\Meter();
if(($in['action']??'')==='outside_transaction')$pdo->transaction=false;
try{
    $db=new \Mosa2\MarketPerformance\ReadOnlyPDO($pdo,$meter);
    if($in['action']==='sql'){$db->query($in['sql']);$result='allowed';}
    elseif($in['action']==='prepare_sql'){$db->prepare($in['sql']);$result='allowed';}
    elseif($in['action']==='forbidden_api'){$method=$in['method'];$method==='exec'?$db->exec('DELETE FROM test'):$db->$method();$result='allowed';}
    elseif($in['action']==='phase'){
        [$value,$phase]=\Mosa2\MarketPerformance\summarizePhase('synthetic',$pdo,static function($db)use($in){
            if($in['prepared']){$q=$db->prepare('SELECT 1 AS probe');$q->execute(['not_logged']);}else $q=$db->query('SELECT 1 AS probe');
            return $q->fetchColumn();
        });$result=['value'=>$value,'phase'=>$phase];
    }else $result='unexpected';
    echo json_encode(['result'=>$result,'calls'=>$pdo->calls,'writes'=>$pdo->writes],JSON_THROW_ON_ERROR);
}catch(Throwable $e){echo json_encode(['rejected'=>true,'reason'=>$e->getMessage(),'calls'=>$pdo->calls,'writes'=>$pdo->writes],JSON_THROW_ON_ERROR);}
