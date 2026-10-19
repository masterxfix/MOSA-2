<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/phase3d/import_sample.php';
use Mosa2\Phase3D\Import\Store;
use function Mosa2\Phase3D\Import\{manifest,masterData,objectKey,apply,expectedCounts};
use function Mosa2\Phase3D\json;
final class SyntheticStore implements Store {
    public array $tables=[];private array $next=[];
    public function find(string $table,array $where): array {
        return array_values(array_filter($this->tables[$table]??[],static function($r)use($where){
            foreach($where as $k=>$v)if(($r[$k]??null)!==$v&&(string)($r[$k]??'')!==(string)$v)return false;return true;}));
    }
    public function insert(string $table,array $values): string {
        if(!in_array($table,\Mosa2\Phase3D\Import\WRITABLE,true))throw new RuntimeException('write_table');
        $id=(string)(($this->next[$table]??1000)+1);$this->next[$table]=(int)$id;
        $row=$table==='m2_assets'?$values:['id'=>$id]+$values;$this->tables[$table][]=$row;return $id;
    }
}
function syntheticManifest(): array {
    $rows=[];
    foreach([['A1','US0378331005','Synthetic A','provider:synthetic_one','NOK'],['A2','US5949181045','Synthetic B','provider:synthetic_two','EUR'],['A3','US0378331005','Synthetic A','provider:synthetic_two','EUR']] as [$sample,$isin,$name,$source,$currency]){
        $route='route:'.json(['asset'=>'isin:'.$isin,'source'=>$source,'currency'=>$currency]);
        $rows[]=['sample_id'=>$sample,'source_reference'=>'synthetic:'.$sample,'isin'=>$isin,'proposed_asset_key'=>'isin:'.$isin,
            'proposed_source_key'=>$source,'proposed_route_key'=>$route,'native_market_quote'=>true,'time_semantics_confirmed'=>true,
            'asset'=>['canonical_name'=>$name,'display_name'=>$name,'asset_class'=>'equity','base_currency'=>null,'name_confirmed'=>true,'asset_class_confirmed'=>true],
            'source'=>['source_key'=>$source,'source_type'=>'market_data','display_name'=>'Synthetic source','base_url'=>null,'enabled'=>1],
            'route'=>['route_type'=>'quote','external_key'=>'market-v1:'.hash('sha256',$route),'priority'=>0,'enabled'=>1],
            'observation'=>['currency'=>$currency,'market_at'=>'2026-01-01 12:00:00','observed_at'=>'2026-01-01 12:00:01','price'=>'10.25','bid'=>null,'ask'=>null,'volume'=>null]];
    }
    return ['schema_version'=>2,'import_contract_version'=>'phase3d-market-sample-v1','snapshot_sha256'=>str_repeat('a',64),'mapping_sha256'=>str_repeat('b',64),
        'parent_report_sha256'=>str_repeat('c',64),'import_at'=>'2026-01-02 12:00:00','observations'=>$rows];
}
function syntheticEvidence(): array {
    $name='Synthetic A';$isin='US0378331005';$object=objectKey($name);
    return [
        ['source_type'=>'mosa_invested_instruments','source_sha256'=>str_repeat('a',64),'store_contract'=>'mosa_invested_instrument_store_v1','records'=>[
            ['contract_version'=>'mosa_invested_instrument_v1','user_id'=>1,'object_key'=>$object,'object_name'=>$name,'isin'=>$isin,'origin'=>'explicit_user_input']]],
        ['source_type'=>'mosa_market_identities','source_sha256'=>str_repeat('b',64),'store_contract'=>'mosa_market_identity_store_v1','records'=>[
            ['contract_version'=>'mosa_market_identity_v1','user_id'=>1,'object_key'=>$object,'asset_key'=>'synthetic_asset','asset_label'=>$name,'isin'=>$isin]]],
        ['source_type'=>'mosa_market_sources','source_sha256'=>str_repeat('c',64),'store_contract'=>'mosa_market_source_registry_v1','records'=>[
            ['user_id'=>1,'asset_key'=>'synthetic_asset','isin'=>$isin,'provider_key'=>'yahoo_finance_chart','status'=>'found','technical'=>['quote_type'=>'EQUITY']]]],
        ['source_type'=>'mosa_etf_references','source_sha256'=>str_repeat('d',64),'store_contract'=>'mosa_etf_reference_store_v1','records'=>[]]
    ];
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    $x=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);$scenario=$x['scenario'];
    try{
        if(str_starts_with($scenario,'evidence_')){
            $e=syntheticEvidence();$kind=substr($scenario,9);
            if($kind==='stock')$e[2]['records'][0]['technical']['quote_type']='STOCK';
            if($kind==='missing_name'){$e[0]['records']=[];$e[1]['records']=[];}
            if($kind==='missing_type')$e[2]['records'][0]['technical']=[];
            if($kind==='unknown_type')$e[2]['records'][0]['technical']['quote_type']='MUTUALFUND';
            if($kind==='name_conflict'){$e[1]['records'][0]['asset_label']='Other name';$e[1]['records'][0]['object_key']=objectKey('Other name');}
            if($kind==='asset_mismatch')$e[2]['records'][0]['asset_key']='other_asset';
            if($kind==='user_mismatch')$e[2]['records'][0]['user_id']=2;
            if(in_array($kind,['etf','type_conflict'],true)){
                $e[3]['records'][]=['contract_version'=>'mosa_etf_reference_v1','user_id'=>1,'asset_type'=>'etf','object_key'=>'US0378331005','isin'=>'US0378331005','object_name'=>'Synthetic A'];
                if($kind==='etf')$e[2]['records'][0]['technical']['quote_type']='ETF';
            }
            if($kind==='ticker_name'){$e[0]['records'][0]['object_name']='';$e[0]['records'][0]['symbol']='SYNTH';$e[1]['records']=[];}
            $r=masterData('US0378331005','synthetic_asset',$e);echo json(['ok'=>true,'result'=>$r]);exit;
        }
        $m=syntheticManifest();$s=new SyntheticStore();
        if($scenario==='bad_count')array_pop($m['observations']);
        if($scenario==='bad_currency')$m['observations'][0]['observation']['currency']='GBX';
        if($scenario==='bad_base_currency')$m['observations'][0]['asset']['base_currency']='NOK';
        if($scenario==='missing_asset_evidence')$m['observations'][0]['asset']['asset_class_confirmed']=false;
        if($scenario==='determinism'){$a=manifest($m);$m['observations']=array_reverse($m['observations']);echo json(['ok'=>true,'same'=>json($a)===json(manifest($m))]);exit;}
        $first=apply($s,$m,true);$before=$s->tables;
        $table=match($scenario){'source_conflict'=>'m2_sources','asset_conflict'=>'m2_assets','identifier_conflict'=>'m2_asset_identifiers','route_conflict'=>'m2_asset_source_routes','checkpoint_conflict'=>'m2_sync_checkpoints','dedupe_conflict'=>'m2_market_observations',default=>null};
        if($table!==null){$field=match($table){'m2_sources','m2_assets'=>'display_name','m2_asset_identifiers'=>'identifier_value','m2_asset_source_routes'=>'external_key','m2_sync_checkpoints'=>'updated_at',default=>'price'};$s->tables[$table][0][$field]='synthetic-conflict';}
        $second=apply($s,$m,false);
        $shaSame=true;foreach($first['bindings'] as $i=>$b)$shaSame=$shaSame&&$b['dedupe_hex']===$second['bindings'][$i]['dedupe_hex'];
        echo json(['ok'=>true,'first'=>$first,'second'=>$second,'facts_same'=>$before===$s->tables,'dedupe_same'=>$shaSame,
            'counts'=>array_map('count',$s->tables),'expected_counts'=>expectedCounts($m),'tables'=>array_keys($s->tables)]);
    }catch(Throwable $e){echo json(['ok'=>false,'reason'=>$e->getMessage()]);}
}
