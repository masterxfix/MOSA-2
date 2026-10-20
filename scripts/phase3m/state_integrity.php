<?php
declare(strict_types=1);
namespace Mosa2\Phase3M;
use PDO;
use function Mosa2\Phase2\{check,same,qi};
require_once __DIR__.'/../phase3k/live_apply.php';

function decimalCompare(string $a,string $b): int {
    check(preg_match('/\A(?:0|[1-9][0-9]*)\z/D',$a)===1&&preg_match('/\A(?:0|[1-9][0-9]*)\z/D',$b)===1,'counter_integer');
    return strlen($a)<=>strlen($b) ?: strcmp($a,$b);
}
function comparisonDdl(string $ddl): string {
    // Only unquoted table options after the CREATE TABLE body can be counters.
    // Quoted defaults/comments/identifiers and the column attribute stay exact.
    $out='';$depth=0;$body=false;$closed=false;$quote=null;$comment=false;$n=strlen($ddl);
    for($i=0;$i<$n;$i++){
        $c=$ddl[$i];$next=$ddl[$i+1]??'';
        if($comment){$out.=$c;if($c==='*'&&$next==='/'){$out.=$next;$i++;$comment=false;}continue;}
        if($quote!==null){
            $out.=$c;
            if($c==='\\'&&$next!==''){$out.=$next;$i++;}
            elseif($c===$quote){if($next===$quote){$out.=$next;$i++;}else $quote=null;}
            continue;
        }
        if($c==='/'&&$next==='*'){$out.='/*';$i++;$comment=true;continue;}
        if(in_array($c,["'",'"','`'],true)){$quote=$c;$out.=$c;continue;}
        if($c==='('){$body=true;$depth++;}
        elseif($c===')'&&$body){$depth--;if($depth===0)$closed=true;}
        if($closed&&preg_match('/\s/',$c)===1&&preg_match('/\A\s+AUTO_INCREMENT=[0-9]+(?=\s|;|$)/',substr($ddl,$i),$match)===1){
            $i+=strlen($match[0])-1;continue;
        }
        $out.=$c;
    }
    return $out;
}
function comparisonCopies(array $value): array {
    foreach($value as $key=>&$item){
        if(is_array($item))$item=comparisonCopies($item);
        elseif(in_array($key,['show_create','show_create_table'],true)&&is_string($item))$item=comparisonDdl($item);
    }unset($item);return $value;
}
function stableStructure(array $structure): array {
    $structure=comparisonCopies($structure);
    foreach($structure['metadata'] as &$table){
        if(array_key_exists('AUTO_INCREMENT',$table['table']))$table['table']['AUTO_INCREMENT']=null;
    }unset($table);return $structure;
}
function stableState(array $state): array {
    return ['environment'=>$state['environment'],'structure'=>stableStructure($state['structure']),
        'rows'=>$state['rows'],'row_hash'=>$state['row_hash'],'ledger'=>$state['ledger']];
}
function counterColumns(array $structure): array {
    $result=[];
    foreach($structure['metadata'] as $name=>$table)foreach($table['columns'] as $column){
        check(is_string($column['EXTRA']??null)&&is_string($column['COLUMN_NAME']??null),'counter_column_metadata');
        if(in_array('auto_increment',preg_split('/\s+/',strtolower(trim($column['EXTRA']))),true)){
            check(!isset($result[$name]),'counter_multiple_columns');$result[$name]=$column['COLUMN_NAME'];
        }
    }
    return $result;
}
function compareState(array $baseline,array $current,int $expectedUnits=0): array {
    // All rows include every PK and every legacy field, including binary dedupe keys.
    same($current['environment'],$baseline['environment'],'environment_changed');
    same($current['rows'],$baseline['rows'],'legacy_rows_changed');
    same($current['row_hash'],\Mosa2\Phase3K\dataHash($current['rows']),'current_row_hash_invalid');
    same($current['row_hash'],$baseline['row_hash'],'legacy_hash_changed');
    same($current['ledger'],$baseline['ledger'],'ledger_changed');
    same(stableStructure($current['structure']),stableStructure($baseline['structure']),'structure_changed');
    same(count($current['units']),$expectedUnits,'unit_count');
    $drift=[];$columns=counterColumns($current['structure']);$expected=array_keys($columns);
    $names=array_keys($current['counter_diagnostics']);sort($names);sort($expected);same($names,$expected,'counter_table_set');
    foreach($current['counter_diagnostics'] as $name=>$d){
        same($d['column'],$columns[$name],'counter_column');
        $rows=$current['rows'][$name];same($d['count'],count($rows),'counter_row_count');
        same($d['row_hash'],\Mosa2\Phase3K\dataHash($rows),'counter_row_hash');
        $keys=array_map(fn($row)=>(string)$row[$d['column']],$rows);
        same($d['pk_set'],$keys,'counter_pk_set');
        same($d['pk_sha256'],\Mosa2\Phase3K\dataHash($keys),'counter_pk_hash');
        same($d['min_pk'],$keys?minDecimal($keys):null,'counter_min_pk');
        same($d['max_pk'],$keys?maxDecimal($keys):null,'counter_max_pk');
        // Operational metadata only: neither historical equality nor a MAX(PK)
        // relation is an acceptance condition under the Phase-3C contract.
        $historical=$baseline['structure']['metadata'][$name]['table']['AUTO_INCREMENT'];
        if($historical!==null)$historical=(string)$historical;
        if($historical!==$d['value'])$drift[$name]=['historical'=>$historical,'current'=>$d['value']];
    }
    return ['classification'=>'CHECKER_BASELINE_BUG','metadata_only'=>true,'affected_tables'=>count($drift),'drift'=>$drift,
        'rows_same'=>true,'pks_same'=>true,'ledger_same'=>true,'counter_reset'=>false];
}
function minDecimal(array $values): string {usort($values,__NAMESPACE__.'\\decimalCompare');return $values[0];}
function maxDecimal(array $values): string {usort($values,__NAMESPACE__.'\\decimalCompare');return $values[count($values)-1];}

function captureState(PDO $p,string $root): array {
    $schema=\Mosa2\Phase3K\schemas($root);$base=\Mosa2\Phase3K\schemas($root,0);$data=[];
    foreach($base as $name=>$t){
        $select=[];foreach($t['columns'] as $key=>$column)$select[]=($column['type']==='binary(32)'?'HEX('.qi($key).')':qi($key)).' AS '.qi($key);
        $sql='SELECT '.implode(',',$select).' FROM '.qi($name).($name==='m2_schema_migrations'?' WHERE version<=2':'');
        $sql.=' ORDER BY '.implode(',',array_map(__NAMESPACE__.'\\identifier',$t['indexes']['PRIMARY']['columns']));
        $data[$name]=$p->query($sql)->fetchAll();
    }
    $state=['environment'=>\Mosa2\Phase3K\sessionState($p),'rows'=>$data,'row_hash'=>\Mosa2\Phase3K\dataHash($data),
        'ledger'=>$p->query('SELECT version,migration_key,LOWER(HEX(checksum)) AS checksum,applied_at FROM m2_schema_migrations ORDER BY version')->fetchAll(),
        'units'=>readUnits($p),'counter_diagnostics'=>[]];
    $columns=$p->query("SELECT c.TABLE_NAME,c.COLUMN_NAME,t.AUTO_INCREMENT FROM information_schema.columns c JOIN information_schema.tables t ON t.TABLE_SCHEMA=c.TABLE_SCHEMA AND t.TABLE_NAME=c.TABLE_NAME WHERE c.TABLE_SCHEMA=DATABASE() AND c.EXTRA LIKE '%auto_increment%' ORDER BY c.TABLE_NAME")->fetchAll();
    foreach($columns as $c){
        $name=$c['TABLE_NAME'];$column=$c['COLUMN_NAME'];check(isset($base[$name]),'counter_unexpected_table');
        same($base[$name]['indexes']['PRIMARY']['columns'],[$column],'counter_single_primary');
        $r=$p->query('SELECT COUNT(*) AS row_count,MIN('.qi($column).') AS min_pk,MAX('.qi($column).') AS max_pk FROM '.qi($name))->fetch();
        $keys=array_map(fn($row)=>(string)$row[$column],$data[$name]);
        $state['counter_diagnostics'][$name]=['column'=>$column,'value'=>(string)$c['AUTO_INCREMENT'],'count'=>(int)$r['row_count'],
            'min_pk'=>$r['min_pk']===null?null:(string)$r['min_pk'],'max_pk'=>$r['max_pk']===null?null:(string)$r['max_pk'],
            'pk_set'=>$keys,'pk_sha256'=>\Mosa2\Phase3K\dataHash($keys),'row_hash'=>\Mosa2\Phase3K\dataHash($data[$name])];
    }
    // Capture raw data/counters before any comparison can throw.
    \Mosa2\Phase2\save($root.'/latest-capture.json',$state);
    $state['structure']=\Mosa2\Phase3K\structure($p,$schema,$root.'/check-failure.json');
    \Mosa2\Phase3K\addedValues($p,$base,array_diff_key($schema,['m2_units'=>true]));
    $state['auto_increment']=\Mosa2\Phase3K\autoIncrements($state['structure']);
    \Mosa2\Phase2\save($root.'/latest-capture.json',$state);return $state;
}

function diagnose(PDO $p,string $root,array $baseline): array {
    $p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
    try {
        $state=captureState($p,$root);
        \Mosa2\Phase3K\privateFile($root.'/diagnostic-state.json',\Mosa2\Phase3K\jsonBytes($state));
        $result=compareState($baseline,$state,0);
        \Mosa2\Phase3K\ledger($p,3);
    }finally{if($p->inTransaction())$p->rollBack();}
    \Mosa2\Phase2\save($root.'/diagnosis.json',$result);return $result;
}
