<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/market_collector/mosa_tick.php';

use function Mosa2\MosaMarket\dueRoundRobin;

function assertBatch(array $expected,array $actual,string $label):void {
    if($expected!==array_keys($actual))
        throw new RuntimeException($label.': '.json_encode(['expected'=>$expected,'actual'=>array_keys($actual)]));
}
$dir=sys_get_temp_dir().'/m2-rotation-'.bin2hex(random_bytes(8));
if(!mkdir($dir,0700))throw new RuntimeException('test_dir_creation');
$files=[];
try{
    $four=array_fill_keys(['A','B','C','D'],['asset_class'=>'equity']);
    $file=$dir.'/round-robin-four.txt';$files[]=$file;
    // A completed run can make the following cron minute skip the DB lock.
    // The next successful run must still target the other two ISINs.
    assertBatch(['A','B'],dueRoundRobin($four,$file),'four_first');
    if(file_get_contents($file)!=="2\n")throw new RuntimeException('first_cursor_readback');
    assertBatch(['C','D'],dueRoundRobin($four,$file),'four_after_skipped_minute');
    assertBatch(['A','B'],dueRoundRobin($four,$file),'four_repeat');
    assertBatch(['C','D'],dueRoundRobin($four,$file),'four_repeat_second');
    $three=array_fill_keys(['A','B','C'],true);
    $file=$dir.'/round-robin-three.txt';$files[]=$file;
    assertBatch(['A','B'],dueRoundRobin($three,$file),'three_first');
    assertBatch(['C','A'],dueRoundRobin($three,$file),'three_wrapped');
    assertBatch(['B','C'],dueRoundRobin($three,$file),'three_last');
    $one=['A'=>true];
    $file=$dir.'/round-robin-one.txt';$files[]=$file;
    assertBatch(['A'],dueRoundRobin($one,$file),'single_asset');
    assertBatch(['A'],dueRoundRobin($one,$file),'single_asset_again');
    $empty=$dir.'/empty.txt';
    if(dueRoundRobin([],$empty)!==[]||file_exists($empty))throw new RuntimeException('empty_register_creates_state');
    $file=$dir.'/tampered.txt';$files[]=$file;
    file_put_contents($file,"invalid\n");chmod($file,0600);
    try{dueRoundRobin($four,$file);throw new RuntimeException('malformed_cursor_accepted');}
    catch(RuntimeException $e){
        if($e->getMessage()!=='scheduler_cursor_invalid')throw $e;
    }
    $file=$dir.'/wrongmode.txt';$files[]=$file;
    file_put_contents($file,"0\n");chmod($file,0644);
    try{dueRoundRobin($four,$file);throw new RuntimeException('unprotected_cursor_accepted');}
    catch(RuntimeException $e){
        if($e->getMessage()!=='scheduler_cursor_permissions')throw $e;
    }
    $file=$dir.'/symlink.txt';$files[]=$file;
    if(symlink($dir.'/round-robin-four.txt',$file)){
        try{dueRoundRobin($four,$file);throw new RuntimeException('symlink_accepted');}
        catch(RuntimeException $e){
            if($e->getMessage()!=='scheduler_cursor_symlink')throw $e;
        }
    }
    echo "PASS durable M2 round-robin: 4/3/1 ISINs, skipped minutes, persistent cursor, fail-closed state\n";
}finally{
    foreach($files as $file)if(is_link($file)||is_file($file))unlink($file);
    rmdir($dir);
}
