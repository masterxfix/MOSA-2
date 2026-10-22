<?php
declare(strict_types=1);
/** One bounded metadata-only inspection through the existing verified connection. */
require_once __DIR__.'/phase2/postcheck.php';
use function Mosa2\Phase2\{check,connection};
$stage='PERMISSIONS_INPUT_REJECTED';$p=null;$result=[];
try {
    $input=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);
    check(($input['attempt']??null)==='1','first_attempt');
    $stage='PERMISSIONS_CONNECTION_OR_IDENTITY_REJECTED';
    $p=connection($input['password'],'127.0.0.1',$input['port']);unset($input['password']);
    $p->exec('SET SESSION TRANSACTION READ ONLY');
    check($p->beginTransaction()&&$p->inTransaction(),'transaction');
    check((string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn()==='1','readonly');
    $stage='PERMISSIONS_GRANTS_REJECTED';
    check($p->query('SELECT CURRENT_ROLE()')->fetchColumn()==='NONE','unresolved_roles');
    $literal=(string)$p->query('SELECT @@partial_revokes')->fetchColumn()==='1';
    $global=[];$schema=[];
    foreach($p->query('SHOW GRANTS FOR CURRENT_USER')->fetchAll(PDO::FETCH_COLUMN) as $grant){
        check(preg_match('/^GRANT ([A-Z_ ,]+) ON (\*\.\*|`[^`]+`\.\*) TO `h29077_mosa2_test`@`localhost`(?: WITH GRANT OPTION)?$/D',$grant,$m)===1,'grant_shape');
        $target=$m[2];$rights=explode(', ',$m[1]);
        if($target==='*.*')$global=array_merge($global,$rights);
        else {
            check($target==='`h29077\\_mosa2\\_test`.*'||($literal&&$target==='`h29077_mosa2_test`.*'),'grant_scope');
            $schema=array_merge($schema,$rights);
        }
    }
    $has=static fn(string $right,bool $globalOnly=false):bool=>in_array($right,$global,true)||in_array('ALL PRIVILEGES',$global,true)
        ||(!$globalOnly&&(in_array($right,$schema,true)||in_array('ALL PRIVILEGES',$schema,true)));
    $rights=[];foreach(['SELECT','SHOW VIEW','TRIGGER','EVENT','CREATE ROUTINE','ALTER ROUTINE','EXECUTE','LOCK TABLES'] as $right)$rights[$right]=$has($right);
    foreach(['RELOAD','FLUSH_TABLES','SHOW_ROUTINE'] as $right)$rights[$right]=$has($right,true);
    $rights['GLOBAL SELECT']=$has('SELECT',true);
    $enumeration=['TRIGGER'=>$rights['TRIGGER'],'EVENT'=>$rights['EVENT'],
        'ROUTINE'=>$rights['SHOW_ROUTINE']||$rights['GLOBAL SELECT']||$rights['CREATE ROUTINE']||$rights['ALTER ROUTINE']||$rights['EXECUTE']];
    $stage='PERMISSIONS_OBJECT_METADATA_REJECTED';$objects=[];
    $queries=[
        'TRIGGER'=>'SELECT TRIGGER_NAME AS name FROM information_schema.triggers WHERE TRIGGER_SCHEMA=DATABASE() ORDER BY TRIGGER_NAME LIMIT 33',
        'ROUTINE'=>'SELECT ROUTINE_NAME AS name,ROUTINE_TYPE AS kind FROM information_schema.routines WHERE ROUTINE_SCHEMA=DATABASE() ORDER BY ROUTINE_TYPE,ROUTINE_NAME LIMIT 33',
        'EVENT'=>'SELECT EVENT_NAME AS name FROM information_schema.events WHERE EVENT_SCHEMA=DATABASE() ORDER BY EVENT_NAME LIMIT 33'];
    foreach($queries as $type=>$sql){
        $rows=$p->query($sql)->fetchAll();check(count($rows)<=32,'object_bound');$definitions=true;
        foreach($rows as $row){
            $kind=$type==='ROUTINE'?$row['kind']:$type;check(in_array($kind,['TRIGGER','EVENT','FUNCTION','PROCEDURE'],true),'object_kind');
            $name='`h29077_mosa2_test`.`'.str_replace('`','``',$row['name']).'`';
            try{
                $definition=$p->query('SHOW CREATE '.$kind.' '.$name)->fetch();$key=$kind==='TRIGGER'?'SQL Original Statement':'Create '.ucfirst(strtolower($kind));
                if(!is_array($definition)||!is_string($definition[$key]??null)||$definition[$key]===''||strlen($definition[$key])>1048576)$definitions=false;
            }catch(PDOException){$definitions=false;}
            unset($definition,$name);
        }
        $objects[$type]=['metadata_query'=>'PASS','visible_count'=>count($rows),'enumeration_proven'=>$enumeration[$type],
            'visible_definitions_readable'=>$definitions,'complete'=>$enumeration[$type]&&$definitions];
    }
    $complete=!in_array(false,array_column($objects,'complete'),true);
    $required=['SELECT','SHOW VIEW','TRIGGER','EVENT','RELOAD'];$missing=[];
    foreach($required as $right)if(!$rights[$right])$missing[]=$right;
    // Existing backup implementation explicitly requires global SELECT for routine definitions.
    if(!$rights['GLOBAL SELECT'])$missing[]='GLOBAL SELECT (existing backup visibility guard)';
    $result=['status'=>'BACKUP_PERMISSIONS_INSPECTED','database_identity'=>'PASS','mysql_version'=>'8.0.26-16',
        'read_only_confirmed'=>true,'rights'=>$rights,'objects'=>$objects,'complete_object_visibility'=>$complete?'JA':'NICHT NACHWEISBAR',
        'existing_backup_rights'=>count($missing)>0?'NEIN':($complete?'JA':'NICHT NACHWEISBAR'),'missing'=>$missing,
        'global_lock_requires'=>'Global RELOAD or FLUSH_TABLES; existing backup guard requires RELOAD; schema LOCK TABLES is insufficient',
        'business_writes'=>0,'lock_operations'=>0,'backup_operations'=>0];
    check($p->inTransaction(),'transaction_lost');$p->rollBack();
}catch(Throwable){$result=['status'=>$stage,'business_writes'=>0,'lock_operations'=>0,'backup_operations'=>0];}
finally{if($p!==null&&$p->inTransaction()){try{$p->rollBack();}catch(Throwable){$result=['status'=>'PERMISSIONS_ROLLBACK_REJECTED'];}}$p=null;}
echo json_encode($result,JSON_THROW_ON_ERROR);
exit(($result['status']??null)==='BACKUP_PERMISSIONS_INSPECTED'?0:1);
