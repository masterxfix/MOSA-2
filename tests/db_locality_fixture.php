<?php
declare(strict_types=1);
define('MOSA_LOCALITY_LIBRARY_ONLY',true);
require dirname(__DIR__).'/scripts/market_collector/db_locality_probe.php';
class LocalityFakeStatement extends PDOStatement {
    public function __construct(private LocalityFakePDO $db,private string $sql){}
    public function execute(?array $params=null): bool {$this->db->record($this->sql);return true;}
    public function fetch(int $mode=PDO::FETCH_DEFAULT,int $orientation=PDO::FETCH_ORI_NEXT,int $offset=0): mixed {
        return ['db'=>'h29077_mosa2_test','account'=>$this->db->fault==='identity'?'wrong':'h29077_mosa2_test@localhost','version'=>'8.0.26-16','port'=>3307];
    }
    public function fetchColumn(int $column=0): mixed {return $this->db->fault==='value'&&str_contains($this->sql,'AS probe')?0:1;}
}
class LocalityFakePDO extends PDO {
    public array $sql=[];public bool $transaction=false;public int $writes=0,$rollbacks=0;public array $options=[];
    public function __construct(public string $fault=''){}
    public function record(string $sql): void {
        if(!$this->transaction)throw new RuntimeException('select_outside_transaction');
        if(!str_starts_with($sql,'SELECT ')){$this->writes++;throw new RuntimeException('business_write_forbidden');}
        $this->sql[]=$sql;if($this->fault==='exception')throw new PDOException('synthetic-secret-from-exception');
    }
    public function exec(string $statement): int|false {
        if(!str_starts_with($statement,'SET SESSION ')&&!str_starts_with($statement,'SET NAMES ')){$this->writes++;throw new RuntimeException('not_session_control');}
        $this->sql[]=$statement;return 0;
    }
    public function prepare(string $query,array $options=[]): PDOStatement|false {return new LocalityFakeStatement($this,$query);}
    public function query(string $query,?int $fetchMode=null,mixed ...$args): PDOStatement|false {$s=$this->prepare($query);$s->execute();return $s;}
    public function beginTransaction(): bool {$this->transaction=true;return true;}
    public function inTransaction(): bool {return $this->transaction;}
    public function rollBack(): bool {$this->transaction=false;$this->rollbacks++;return true;}
    public function getAttribute(int $attribute): mixed {return $attribute===PDO::ATTR_CLIENT_VERSION?'fake-client':false;}
}
$in=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);$db=new LocalityFakePDO($in['fault']??'');$called=0;
$factory=static function($dsn,$user,$password,$options)use($db,&$called){
    $called++;if($dsn!=='mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4'||$user!=='h29077_mosa2_test')throw new RuntimeException('wrong_target');
    $db->options=$options;return $db;
};
$r=localityProbe(['port'=>$in['port']??3307,'password'=>$in['password']??'synthetic-secret'],$factory);
echo json_encode(['result'=>$r,'sql'=>$db->sql,'writes'=>$db->writes,'rollbacks'=>$db->rollbacks,'factory_calls'=>$called],JSON_THROW_ON_ERROR);
