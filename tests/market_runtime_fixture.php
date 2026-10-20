<?php
declare(strict_types=1);
require dirname(__DIR__).'/scripts/market_collector/live_batch.php';
// In-memory SQL contract double: no PDO driver, socket, credentials or provider network.
class MemoryDatabase {
    public array $rows,$sql=[],$events=[];public int $returned=0,$last=1000;
    public function __construct(array $rows){$this->rows=$rows;}
}
class MemoryStatement extends PDOStatement {
    private array $rows=[];private int $affected=0;
    public function __construct(private MemoryConnection $db,private string $sql){}
    public function execute(?array $params=null):bool {
        $params??=[];$sql=$this->sql;$this->db->state->sql[]=$sql;$this->affected=0;
        if(str_contains($sql,'GET_LOCK')||str_contains($sql,'RELEASE_LOCK')){$this->rows=[['value'=>'1']];return true;}
        if(str_contains($sql,'information_schema.tables')){$names=array_keys($this->db->state->rows);sort($names);$this->rows=array_map(static fn($n)=>['TABLE_NAME'=>$n],$names);return true;}
        if(preg_match('/SHOW (?:INDEX|KEYS) FROM `?(\w+)`?/',$sql,$m)){
            $groups=match($m[1]){'m2_asset_source_routes'=>[['source_id','route_type','external_key','route_revision'],['asset_id','source_id','route_type','route_revision']],
                'm2_market_observations'=>[['id'],['dedupe_key']],'m2_asset_identifiers'=>[['identifier_type','normalized_value','scope_key']],default=>[['id']]};
            $this->rows=[];foreach($groups as $i=>$cols)foreach($cols as $j=>$col)$this->rows[]=['Non_unique'=>0,'Key_name'=>'key'.$i,'Seq_in_index'=>$j+1,'Column_name'=>$col];
            if(str_contains($sql,"Key_name='PRIMARY'"))$this->rows=[['Column_name'=>$m[1]==='m2_assets'?'entity_id':'id']];return true;
        }
        if(preg_match('/SHOW COLUMNS FROM `(\w+)`/',$sql,$m)){
            $row=$this->db->state->rows[$m[1]][0]??['id'=>'1'];$this->rows=[];
            foreach($row as $key=>$unused)$this->rows[]=['Field'=>$key,'Type'=>in_array($key,['checksum','definition_sha256','dedupe_key'],true)?'binary(32)':'varchar(100)'];return true;
        }
        if(preg_match('/INSERT INTO m2_market_observations \(([^)]+)\)/',$sql,$m)){
            $columns=array_map(static fn($s)=>trim($s,'`'),explode(',',$m[1]));$row=array_combine($columns,$params);$row['dedupe_key']=strtoupper(bin2hex($row['dedupe_key']));$row['id']=(string)++$this->db->state->last;
            $this->db->state->rows['m2_market_observations'][]=\Mosa2\MarketLive\strings($row);$this->affected=1;return true;
        }
        if(preg_match('/INSERT INTO `(m2_[a-z_]+)` \(([^)]+)\)/',$sql,$m)){
            $columns=array_map(static fn($s)=>trim($s,'`'),explode(',',$m[2]));$row=array_combine($columns,$params);$row['id']=(string)++$this->db->state->last;
            $this->db->state->rows[$m[1]][]=\Mosa2\MarketLive\strings($row);$this->affected=1;return true;
        }
        if(!preg_match('/ FROM `?(m2_\w+)`?/',$sql,$m))throw new RuntimeException('unsupported SQL: '.$sql);
        $rows=$this->db->state->rows[$m[1]];
        if(str_contains($sql,' WHERE ')){
            $where=explode(' WHERE ',$sql,2)[1];preg_match_all('/`?(\w+)`?\s*(<=>|<>|=)\s*\?/',$where,$matches,PREG_SET_ORDER);
            $rows=array_values(array_filter($rows,static function($row)use($matches,$params){foreach($matches as $i=>$match){$value=$params[$i];if($match[1]==='dedupe_key')$value=strtoupper(bin2hex($value));$equal=($row[$match[1]]??null)===$value;if(($match[2]==='<>'&&$equal)||($match[2]!=='<>'&&!$equal))return false;}return true;}));
        }
        if(str_contains($sql,'ORDER BY route_revision DESC'))usort($rows,static fn($a,$b)=>(int)$b['route_revision']<=>(int)$a['route_revision']);
        if(str_contains($sql,'ORDER BY unit_key'))usort($rows,static fn($a,$b)=>strcmp($a['unit_key'],$b['unit_key']));
        if(preg_match('/ LIMIT (\d+)/',$sql,$limit))$rows=array_slice($rows,0,(int)$limit[1]);
        if(str_starts_with($sql,'SELECT version,HEX'))$rows=array_map(static fn($r)=>array_intersect_key($r,array_flip(['version','checksum'])),$rows);
        $this->rows=$rows;$this->db->state->returned+=count($rows);return true;
    }
    public function fetchAll(int $mode=PDO::FETCH_DEFAULT,mixed ...$args):array {return $mode===PDO::FETCH_COLUMN?array_column($this->rows,array_key_first($this->rows[0]??['x'=>null])):$this->rows;}
    public function fetchColumn(int $column=0):mixed{return array_values($this->rows[0]??[] )[$column]??false;}
    public function rowCount():int{return $this->affected;}
}
class MemoryConnection extends PDO {
    private ?array $before=null;
    public function __construct(public MemoryDatabase $state){}
    public function prepare(string $query,array $options=[]):PDOStatement|false{return new MemoryStatement($this,$query);}
    public function query(string $query,?int $fetchMode=null,mixed ...$fetchModeArgs):PDOStatement|false{$q=$this->prepare($query);$q->execute();return $q;}
    public function exec(string $statement):int|false{$this->state->events[]=$statement;return 0;}
    public function beginTransaction():bool{$this->before=$this->state->rows;$this->state->events[]='BEGIN';return true;}
    public function inTransaction():bool{return $this->before!==null;}
    public function rollBack():bool{$this->state->rows=$this->before;$this->before=null;$this->state->events[]='ROLLBACK';return true;}
    public function commit():bool{$this->before=null;$this->state->events[]='COMMIT';return true;}
    public function lastInsertId(?string $name=null):string|false{return (string)$this->state->last;}
}
$in=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);$state=$in['state'];
$tables=array_merge(\Mosa2\Phase2\TABLES,\Mosa2\Phase3B\MARKET,['m2_units']);foreach($tables as $table)$state[$table]??=[];
$seed=json_decode(file_get_contents(dirname(__DIR__).'/docs/database/seeds/0001_market_units_v1.json'),true,32,JSON_THROW_ON_ERROR);
$state['m2_units']=array_map(static function($d){unset($d['definition_reference']);$d['definition_sha256']=strtoupper($d['definition_sha256']);return $d;},$seed['definitions']);
$hashes=[\Mosa2\Phase2\DIGEST,\Mosa2\Phase3B\DIGEST,\Mosa2\Phase3K\DIGEST,hash_file('sha256',dirname(__DIR__).'/docs/database/migrations/0004_current_observation_provenance.sql')];
foreach($hashes as $i=>$hash)$state['m2_schema_migrations'][]=['version'=>(string)($i+1),'checksum'=>strtoupper($hash),'applied_at'=>'2001-01-01 00:00:00.000000'];
$state['m2_market_observations']=$in['observations']??[];
for($i=0;$i<($in['history_size']??0);$i++)$state['m2_market_observations'][]=['id'=>(string)($i+2000),'asset_id'=>'999','source_id'=>'998','market_at'=>'1999-01-01 00:00:00.000000','observed_at'=>'1999-01-01 00:00:01.000000','dedupe_key'=>str_pad(dechex($i),64,'0',STR_PAD_LEFT)];
if(isset($in['bad_ledger']))$state['m2_schema_migrations'][2]['checksum']=str_repeat('0',64);
if(isset($in['bad_unit']))$state['m2_units'][0]['scale_numerator']='99';
$memory=new MemoryDatabase($state);$connections=0;$providers=0;
$connect=static function()use($memory,&$connections,$in){$connections++;if(($in['fault']??'')==='readback'&&$connections===2)throw new RuntimeException('synthetic_readback_failure');return new MemoryConnection($memory);};
$invoke=static function($config,$request)use($in,$memory,&$providers){
    if($request['action']==='fetch'){$providers++;if(($in['fault']??'')==='provider'||($in['batch_fault_index']??-1)===$providers-1)throw new RuntimeException('synthetic_provider_failure');if(($in['fault']??'')==='drift')$memory->rows['m2_sources'][0]['enabled']='0';if(($in['fault']??'')==='ledger_drift')$memory->rows['m2_schema_migrations'][0]['applied_at']='2002-01-01 00:00:00.000000';return $in['acquired_batch'][$providers-1]??$in['acquired'];}
    $reply=\Mosa2\MarketLive\bridge($config,$request);
    if(($in['fault']??'')==='replay'&&$request['action']==='replay')$reply['plan']['decision']='INSERT';return $reply;
};
if(($in['action']??'')==='acceptance'){
    require dirname(__DIR__).'/scripts/market_collector/actions_acceptance.php';
    $connect=static function()use($memory,&$connections,$in){$connections++;if(($in['fault']??'')==='authentication')throw new PDOException('synthetic');return new MemoryConnection($memory);};
    $invoke=static function($config,$request)use($in,$memory,&$providers){
        if($request['action']==='fetch'){
            $providers++;$dir=$request['private_root'];touch($dir.'/provider-consumed.lock');
            if(($in['fail_provider']??0)===$providers)throw new RuntimeException('synthetic');
            $m=json_decode(file_get_contents($dir.'/live-manifest.json'),true);return $in['acquired_by_isin'][$m['instrument']];
        }
        return \Mosa2\MarketLive\bridge($config,$request);
    };
    $reports=[\Mosa2\MarketAcceptance\acceptance($in['scope'],$in['private_root'],$in['config'],$connect,$invoke)];
}elseif(($in['action']??'')==='proof'){
    $p=new MemoryConnection($memory);$before=\Mosa2\MarketLive\snapshot($p,['schema_version'=>4]);
    $memory->rows['m2_jobs'][]=['id'=>'999','job_key'=>'unexpected'];$after=\Mosa2\MarketLive\snapshot($p,['schema_version'=>4]);
    try{\Mosa2\MarketLive\compareDelta($before,$after,['deltas'=>[]],[]);$detected=false;}catch(Throwable){$detected=true;}
    $reports=[['global_change_detected'=>$detected]];
}elseif(isset($in['batch'])){
    $reports=[\Mosa2\MarketBatch\execute($in['batch'],static fn($entry)=>\Mosa2\MarketLive\runtimeRun('unused',$in['config'],$entry['manifest'],$connect,$invoke))];unset($reports[0]['private_evidence']);
}else{
    $reports=[];for($i=0;$i<($in['runs']??1);$i++)$reports[]=\Mosa2\MarketLive\runtimeRun('unused',$in['config'],$in['manifest'],$connect,$invoke);
}
echo json_encode(['reports'=>$reports,'queries'=>$memory->sql,'returned_rows'=>$memory->returned,'events'=>$memory->events,'providers'=>$providers,'state'=>$memory->rows],JSON_THROW_ON_ERROR);
