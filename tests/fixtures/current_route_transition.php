<?php
declare(strict_types=1);
require $argv[1].'/scripts/market_current/refresh.php';

final class TransitionStatement extends PDOStatement {
    private array $rows=[];
    public function __construct(private TransitionDatabase $db,private string $sql){}
    public function execute(?array $params=null): bool {
        $args=$params??[];$this->db->queries[]=['sql'=>$this->sql,'args'=>$args];$d=$this->db->data;
        if(str_contains($this->sql,'FROM m2_asset_source_routes')){
            $this->rows=array_values(array_filter($d['routes'],static fn($r)=>$r['id']===$args[0]
                &&(count($args)===1||($r['asset_id']===$args[1]&&$r['source_id']===$args[2]))));
        }elseif(str_contains($this->sql,'SELECT a.entity_id'))$this->rows=[['entity_id'=>$args[1]]];
        elseif(str_contains($this->sql,'FROM m2_market_current'))$this->rows=[$d['current']];
        elseif(str_contains($this->sql,'ORDER BY market_at'))$this->rows=$d['facts'];
        elseif(str_contains($this->sql,'FROM m2_market_observations WHERE id=?'))$this->rows=[$d['old_fact']];
        else throw new RuntimeException('unexpected_test_query');
        return true;
    }
    public function fetch(int $mode=PDO::FETCH_DEFAULT,int $orientation=PDO::FETCH_ORI_NEXT,int $offset=0): mixed {
        return array_shift($this->rows)??false;
    }
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args): array {return $this->rows;}
    public function fetchColumn(int $column=0): mixed {$row=$this->fetch();return $row===false?false:array_values($row)[$column];}
}
final class TransitionDatabase extends PDO {
    public array $queries=[];
    public function __construct(public array $data){}
    public function prepare(string $query,array $options=[]): PDOStatement|false {return new TransitionStatement($this,$query);}
}
try{
    $data=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);$db=new TransitionDatabase($data);
    $items=\Mosa2\MarketCurrent\inputs($db,[$data['approval']],$data['now'],true);
    echo json_encode(['ok'=>true,'items'=>$items,'queries'=>$db->queries],JSON_THROW_ON_ERROR);
}catch(Throwable $e){echo json_encode(['ok'=>false,'failure'=>$e->getMessage()],JSON_THROW_ON_ERROR);}
