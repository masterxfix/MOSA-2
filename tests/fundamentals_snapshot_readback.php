<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{beginIndependentReadback,fundamentalBaseline,readback,timings,transaction,validate};

function expectIssue47(bool $ok):void {if(!$ok)throw new RuntimeException('assertion');}
function rejectIssue47(callable $call,string $code):void {
    try{$call();}catch(RuntimeException $e){expectIssue47($e->getMessage()===$code);return;}
    throw new RuntimeException('expected rejection: '.$code);
}
class ReadbackPDO extends MemoryPDO {
    private bool $readOnly=false;
    public array $timingQueries=[];
    public ?array $currentPlan=null;
    public ?array $historyPlan=null;
    public ?array $historyTiming=null;
    public bool $failHistoryQuery=false;
    public function __construct(private int $connectionId){parent::__construct();}
    public function exec(string $statement):int|false {
        if($statement!=='SET SESSION TRANSACTION READ ONLY')throw new RuntimeException('unexpected exec');
        $this->readOnly=true;return 0;
    }
    public function run(string $sql,array $args):array {
        if(preg_match('/^(EXPLAIN ANALYZE |EXPLAIN )?SELECT (?:id,)?value_decimal,.* FROM (m2_fundamental_current|m2_fundamental_observations)\b/',$sql,$match)){
            $this->timingQueries[]=$sql;
            [$operation,$table]=[$match[1],$match[2]];
            $rows=array_values(array_filter($this->data[$table]??[],static fn($row)=>
                [$row['asset_id'],$row['metric_key'],$row['period_type']]===array_slice($args,0,3)));
            if($table==='m2_fundamental_current'){
                return match($operation){
                    'EXPLAIN '=>$this->currentPlan??[['key'=>$rows===[]?null:'PRIMARY','type'=>$rows===[]?null:'const']],
                    'EXPLAIN ANALYZE '=>[['EXPLAIN'=>'-> Rows fetched before execution (actual time=0.001..0.002 rows=1 loops=1)']],
                    default=>$rows,
                };
            }
            if($this->failHistoryQuery)throw new PDOException('injected_history_query');
            return match($operation){
                'EXPLAIN '=>$this->historyPlan??[['key'=>'ix_fund_obs_timeline','type'=>'ref']],
                'EXPLAIN ANALYZE '=>$this->historyTiming??[['EXPLAIN'=>'-> Index lookup (actual time=0.001..0.002 rows=1 loops=1)']],
                default=>$rows,
            };
        }
        return match($sql){
            'SELECT CONNECTION_ID()'=>[['id'=>$this->connectionId]],
            'SELECT @@session.transaction_read_only'=>[['ro'=>(int)$this->readOnly]],
            default=>parent::run($sql,$args),
        };
    }
}
[$annual,$other,$balances,$shares]=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
$writer=new ReadbackPDO(1);
transaction($writer,$annual,'42',fn()=>null);
transaction($writer,$other,'99',fn()=>null);
$before=fundamentalBaseline($writer);
$receipt=transaction($writer,$balances,'42',fn()=>null,$before);
expectIssue47($receipt['observations']===5&&$receipt['current']===5&&$receipt['current_updates']===0);
$reader=new ReadbackPDO(2);$reader->data=$writer->data;
beginIndependentReadback($writer,$reader);
expectIssue47(count(readback($reader,$receipt,$before))===5);
rejectIssue47(fn()=>beginIndependentReadback($writer,$writer),'independent');
rejectIssue47(fn()=>beginIndependentReadback($writer,new ReadbackPDO(1)),'independent');
$committed=$writer->data;
$old=$committed['m2_fundamental_observations'];
foreach($old as $i=>$row){
    if($row['asset_id']==='99'||$row['period_type']==='fy'){
        $reader->data=$committed;$reader->data['m2_fundamental_observations'][$i]['field_path']='tampered';
        rejectIssue47(fn()=>readback($reader,$receipt,$before),'fundamental_baseline_changed');
    }
}
$reader->data=$committed;
$reader->data['m2_fundamental_observations'][array_key_last($old)]['value_decimal']='100';
rejectIssue47(fn()=>readback($reader,$receipt,$before),'readback_decimal');
$reader->data=$committed;$reader->data['m2_fundamental_observations'][]=end($old);
rejectIssue47(fn()=>readback($reader,$receipt,$before),'readback_unique');
$reader->data=$committed;
$requiredMetric=$balances['observations'][0]['metric_key'];
$reader->data['m2_fundamental_current']=array_values(array_filter(
    $committed['m2_fundamental_current'],static fn($row)=>$row['metric_key']!==$requiredMetric
));
rejectIssue47(fn()=>readback($reader,$receipt,$before),'readback_unique');
expectIssue47($writer->commits===3&&$writer->rollbacks===0&&$writer->data===$committed);
$r=transaction($writer,$balances,'42',fn()=>null,fundamentalBaseline($writer));
expectIssue47($r['observations']===0&&$r['current']===0&&$r['facts_reused']===5);
$beforeShares=fundamentalBaseline($writer);
$r=transaction($writer,$shares,'42',fn()=>null,$beforeShares);
expectIssue47($r['observations']===1&&$r['current']===0);
$historyReader=new ReadbackPDO(3);$historyReader->data=$writer->data;
beginIndependentReadback($writer,$historyReader);
expectIssue47(count(readback($historyReader,$r,$beforeShares))===1);
$historyMetric=$shares['observations'][0]['metric_key'];
$historySample=fn()=>timings($historyReader,'42',$historyMetric,'snapshot',null,false,false);
$timing=$historySample();
expectIssue47(array_keys($timing)===['history']&&$timing['history']['rows']===1
    &&$timing['history']['index_access']==='ix_fund_obs_timeline'&&$timing['history']['server_explain_actual_end_ms']===0.002);
expectIssue47(count($historyReader->timingQueries)===3);
foreach($historyReader->timingQueries as $sql)expectIssue47(!str_contains($sql,'m2_fundamental_current'));
rejectIssue47(fn()=>timings($historyReader,'42',$historyMetric,'snapshot'),'current_projection_missing');
$currentSample=fn()=>timings($historyReader,'42',$requiredMetric,'snapshot');
$timing=$currentSample();
expectIssue47($timing['current']['rows']===1&&$timing['current']['index_access']==='PRIMARY');
$historyReader->currentPlan=[['key'=>'wrong_index','type'=>'ref']];
rejectIssue47($currentSample,'required_index');
$historyReader->currentPlan=null;

$committedShares=$writer->data;$commits=$writer->commits;$writes=$writer->writes;
$historyReader->historyPlan=[];
rejectIssue47($historySample,'explain_access');
$historyReader->historyPlan=[['key'=>'wrong_index','type'=>'ref']];
rejectIssue47($historySample,'required_index');
$historyReader->historyPlan=null;$historyReader->historyTiming=[];
rejectIssue47($historySample,'server_timing');
$historyReader->historyTiming=null;$historyReader->failHistoryQuery=true;
rejectIssue47($historySample,'injected_history_query');
expectIssue47($writer->data===$committedShares&&$writer->commits===$commits
    &&$writer->writes===$writes&&$writer->rollbacks===0&&$historyReader->writes===0);
$r=transaction($writer,$shares,'42',fn()=>null,fundamentalBaseline($writer));
expectIssue47($r['observations']===0&&$r['facts_reused']===1);
$bad=$balances;$bad['observations'][0]['as_of_at']=null;
rejectIssue47(fn()=>validate($bad),'snapshot_as_of');
$bad=$balances;$bad['observations'][0]['period_start']='2026-04-01';
rejectIssue47(fn()=>validate($bad),'snapshot_period');
$bad=$balances;$bad['observations'][0]['as_of_at']='2099-01-01 00:00:00.000000';
rejectIssue47(fn()=>validate($bad),'snapshot_as_of_future');
$bad=$balances;$bad['observations'][0]['value_decimal']='1';
rejectIssue47(fn()=>transaction($writer,$bad,'42',fn()=>null),'curated_value');

// Replace an allowed Current slot while retaining its previous Observation.
$new=$annual;$new['observations']=[$annual['observations'][0]];
$new['observations'][0]['fiscal_year']='2027';
$new['observations'][0]['period_start']='2027-01-01';
$new['observations'][0]['period_end']='2027-12-31';
$before=fundamentalBaseline($writer);
$r=transaction($writer,$new,'42',fn()=>null,$before);
expectIssue47($r['observations']===1&&$r['current_updates']===1&&$r['current']===0);
$reader->data=$writer->data;
expectIssue47(count(readback($reader,$r,$before))===1);
echo "PASS\n";
