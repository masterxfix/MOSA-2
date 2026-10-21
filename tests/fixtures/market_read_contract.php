<?php
declare(strict_types=1);
require $argv[1].'/api/read_model.php';
require $argv[1].'/scripts/market_current/read_access.php';
class ReadStatement extends PDOStatement {
    public function __construct(public ReadConnection $connection){}
    public function execute(?array $params=null):bool {$this->connection->parameters[]=$params;return true;}
    public function fetch(int $mode=PDO::FETCH_DEFAULT,int $cursorOrientation=PDO::FETCH_ORI_NEXT,int $cursorOffset=0):mixed {
        return ['display_name'=>'Synthetic','source_name'=>'Synthetic source','price'=>'1.2300000000','currency'=>'EUR','quote_unit_key'=>'EUR','quote_unit_version'=>'1','quantity_basis_unit_key'=>null,'quantity_basis_amount'=>null,'market_at'=>'2026-01-01 00:00:00.000000','observed_at'=>'2026-01-01 00:00:01.000000','valid_binding'=>'1'];
    }
}
class ReadConnection extends PDO {
    public array $sql=[],$parameters=[],$events=[];private bool $transaction=false;
    public function __construct(){}
    public function prepare(string $query,array $options=[]):PDOStatement|false {$this->sql[]=$query;return new ReadStatement($this);}
    public function exec(string $statement):int|false {$this->events[]=$statement;return 0;}
    public function beginTransaction():bool {$this->transaction=true;$this->events[]='BEGIN';return true;}
    public function inTransaction():bool{return $this->transaction;}
    public function rollBack():bool{$this->transaction=false;$this->events[]='ROLLBACK';return true;}
}
class ScalarStatement extends PDOStatement {
    public function __construct(public mixed $value){}
    public function execute(?array $params=null):bool{$this->value=$params[0];return true;}
    public function fetchColumn(int $column=0):mixed{return $this->value;}
}
class ProvisionConnection extends ReadConnection {
    public function query(string $query,?int $fetchMode=null,mixed ...$fetchModeArgs):PDOStatement|false{
        $this->sql[]=$query;return new ScalarStatement(str_contains($query,'MAX(version)')?'3':'0');
    }
    public function prepare(string $query,array $options=[]):PDOStatement|false{$this->sql[]=$query;return new ScalarStatement(null);}
}
require_once $argv[1].'/tests/fixtures/current_web.php';
$p=new WebCurrentConnection();$config=['assets'=>[['asset_id'=>'101','route_id'=>'301','venue'=>'Venue'],['asset_id'=>'102','route_id'=>'302','venue'=>'Venue']],'stale_seconds'=>1800];
$result=\Mosa2\MarketRead\read($p,$config,'2026-01-01 00:00:02.000000');
$failures=[];foreach(['GRANT ALL PRIVILEGES ON `h29077_mosa2_test`.* TO x','GRANT SELECT ON *.* TO x','GRANT SELECT ON `h29077_mosa2_test`.* TO x WITH GRANT OPTION','GRANT EXECUTE ON `h29077_mosa2_test`.* TO x','GRANT SELECT ON `h29077_mosa2_test`.* TO x'] as $grant){try{\Mosa2\MarketReadAccess\grants([[$grant]]);$failures[]=false;}catch(Throwable){$failures[]=true;}}
\Mosa2\MarketReadAccess\grants([['GRANT USAGE ON *.* TO x'],['GRANT SELECT, SHOW VIEW ON `h29077\\_mosa2\\_test`.* TO x']]);
\Mosa2\MarketReadAccess\grants([['GRANT SELECT ON `h29077_mosa2_test`.* TO x']],true);
$provision=new ProvisionConnection();$probe=\Mosa2\MarketReadAccess\preflight($provision,$config,'2026-01-01 00:00:02.000000');
echo json_encode(['result'=>$result,'sql'=>$p->sql,'parameters'=>$p->parameters,'events'=>$p->events,'unsafe_grants_rejected'=>$failures,'provision'=>['probe'=>$probe,'sql'=>$provision->sql,'events'=>$provision->events]]);
