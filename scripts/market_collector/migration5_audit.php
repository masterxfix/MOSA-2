<?php
declare(strict_types=1);
namespace Mosa2\CollectorMigration5;
use PDO;
use PDOStatement;
require_once __DIR__.'/schema5.php';

/** Offline replay of captured SELECT metadata into the existing exact schema checker. */
class InventoryStatement extends PDOStatement {
    private array $rows=[];
    public function __construct(private array $inventory,private string $sql){}
    public function execute(?array $params=null):bool {
        foreach($this->inventory as $r)if($r['sql']===$this->sql&&$r['args']===($params??[])){$this->rows=$r['rows'];return true;}
        throw new \RuntimeException('metadata_query_missing');
    }
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array {
        return $mode===PDO::FETCH_COLUMN?array_map(static fn($r)=>array_values($r)[0],$this->rows):$this->rows;
    }
    public function fetch(int $mode=PDO::FETCH_DEFAULT,int $orientation=PDO::FETCH_ORI_NEXT,int $offset=0):mixed {
        $r=$this->rows[0]??false;return $r!==false&&$mode===PDO::FETCH_NUM?array_values($r):$r;
    }
}
class Inventory extends PDO {
    public function __construct(private array $inventory){}
    public function prepare(string $query,array $options=[]):PDOStatement|false{return new InventoryStatement($this->inventory,$query);}
    public function query(string $query,?int $fetchMode=null,mixed ...$fetchModeArgs):PDOStatement|false{$q=$this->prepare($query);$q->execute();return $q;}
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    try{
        $request=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);$root=$argv[1];
        if($request['operation']==='contract')$result=['schemas4'=>\Mosa2\CollectorSchema5\schemas($root,4),'schemas5'=>\Mosa2\CollectorSchema5\schemas($root,5),
            'envelope4'=>\Mosa2\CollectorSchema5\envelope(4),'envelope5'=>\Mosa2\CollectorSchema5\envelope(5),'statements'=>\Mosa2\CollectorSchema5\statements()];
        else{$schema=\Mosa2\CollectorSchema5\schemas($root,$request['version']);$result=\Mosa2\Phase3K\structure(new Inventory($request['inventory']),$schema);unset($result['metadata']);}
        echo json_encode(['ok'=>true,'result'=>$result],JSON_THROW_ON_ERROR);
    }catch(\Throwable $e){
        $code=preg_match('/^[a-z0-9_:]+$/iD',$e->getMessage())===1?$e->getMessage():'EXACT_SCHEMA_REJECTED';
        echo json_encode(['ok'=>false,'code'=>$code],JSON_THROW_ON_ERROR);
    }
}
