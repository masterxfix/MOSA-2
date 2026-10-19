<?php
declare(strict_types=1);
// Scripted PDO without a driver/connection. Exercises PHP transaction cleanup,
// parameter arity and exact errno/constraint discrimination, not MySQL execution.
final class UnitProbeStatement extends PDOStatement {
    public function __construct(private UnitProbePDO $owner,private string $sql,private mixed $column=null){}
    public function execute(?array $params=null): bool {
        if(substr_count($this->sql,'?')!==count($params??[]))throw new RuntimeException('parameter_arity');
        if($this->owner->failInsert)throw new RuntimeException('injected_insert_failure');
        if(count($params)!==8||strlen($params[7])!==32)throw new RuntimeException('unit_insert_values');
        $this->owner->insertions[]=$params;return true;
    }
    public function fetchColumn(int $column=0): mixed {return $this->column;}
}
final class UnitProbePDO extends PDO {
    public bool $active=false;
    public bool $rolledBack=false;
    public array $insertions=[];
    public array $updates=[];
    public function __construct(public bool $failInsert=false){}
    public function beginTransaction(): bool {$this->active=true;return true;}
    public function inTransaction(): bool {return $this->active;}
    public function rollBack(): bool {$this->active=false;$this->rolledBack=true;return true;}
    public function prepare(string $query,array $options=[]): PDOStatement|false {
        if(!str_starts_with($query,'INSERT INTO m2_units '))throw new RuntimeException('unexpected_insert');
        return new UnitProbeStatement($this,$query);
    }
    public function query(string $query,?int $fetchMode=null,mixed ...$fetchModeArgs): PDOStatement|false {
        $value=$query==='SELECT COUNT(*) FROM m2_units'?count($this->insertions):1;
        return new UnitProbeStatement($this,$query,$value);
    }
    public function exec(string $statement): int|false {
        $constraint=null;$errno=3819;
        if(str_contains($statement,'scale_denominator=0'))$constraint='ck_units_scale';
        elseif(str_contains($statement,'unit_version=0 WHERE unit_key'))$constraint='ck_units_versions';
        elseif(str_contains($statement,'TEST_UNKNOWN')){$constraint='fk_routes_quote_unit';$errno=1452;}
        elseif(str_contains($statement,'UPDATE m2_asset_source_routes SET quote_unit_version=NULL'))$constraint='ck_routes_units';
        elseif(str_contains($statement,'UPDATE m2_asset_source_routes SET quantity_basis_unit_key'))$constraint='ck_routes_quantity';
        elseif(str_contains($statement,'route_revision=0'))$constraint='ck_routes_revision';
        elseif(str_contains($statement,'UPDATE m2_market_observations SET quote_unit_key=NULL')||str_contains($statement,'observation_format_version=NULL'))$constraint='ck_market_observations_units';
        if($constraint!==null){$error=new PDOException('synthetic');$error->errorInfo=['23000',$errno,"Constraint '$constraint' violated"];throw $error;}
        if(!str_starts_with($statement,'UPDATE m2_asset_source_routes SET ')&&!str_starts_with($statement,'UPDATE m2_market_observations SET '))throw new RuntimeException('unexpected_update');
        $this->updates[]=$statement;return 1;
    }
}
