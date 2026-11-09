<?php
declare(strict_types=1);
require __DIR__.'/fundamentals_offline.php';
use function Mosa2\Fundamentals\{beginIndependentReadback,fundamentalBaseline,readback,transaction,validate};

function expectIssue47(bool $ok):void {if(!$ok)throw new RuntimeException('assertion');}
function rejectIssue47(callable $call,string $code):void {
    try{$call();}catch(RuntimeException $e){expectIssue47($e->getMessage()===$code);return;}
    throw new RuntimeException('expected rejection: '.$code);
}
class ReadbackPDO extends MemoryPDO {
    private bool $readOnly=false;
    public function __construct(private int $connectionId){parent::__construct();}
    public function exec(string $statement):int|false {
        if($statement!=='SET SESSION TRANSACTION READ ONLY')throw new RuntimeException('unexpected exec');
        $this->readOnly=true;return 0;
    }
    public function run(string $sql,array $args):array {
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
expectIssue47($writer->commits===3&&$writer->rollbacks===0&&$writer->data===$committed);
$r=transaction($writer,$balances,'42',fn()=>null,fundamentalBaseline($writer));
expectIssue47($r['observations']===0&&$r['current']===0&&$r['facts_reused']===5);
$r=transaction($writer,$shares,'42',fn()=>null,fundamentalBaseline($writer));
expectIssue47($r['observations']===1&&$r['current']===0);
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
