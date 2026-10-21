<?php
declare(strict_types=1);
// Assemble only the existing read functions for fileless SSH execution. No upload.
require_once __DIR__.'/preview_read.php';
function functionSource(string $name): string {
    $r=new ReflectionFunction($name);$lines=file($r->getFileName());
    return implode('',array_slice($lines,$r->getStartLine()-1,$r->getEndLine()-$r->getStartLine()+1));
}
function readBundle(): string {
    $groups=[
        'Mosa2\\Phase2'=>['use RuntimeException;', ['check','same']],
        'Mosa2\\MarketLive'=>['', ['strings']],
        'Mosa2\\ObservationRead'=>['const SCOPE='.var_export(\Mosa2\ObservationRead\SCOPE,true).';', ['scopeSql']],
        'Mosa2\\MarketCurrent'=>['use PDO; use function Mosa2\\Phase2\\check;', ['inputs']],
        'Mosa2\\MarketReadAccess'=>['use function Mosa2\\Phase2\\check;', ['grants']],
        'Mosa2\\CurrentPreview'=>['use PDO; use function Mosa2\\Phase2\\{check,same};', ['gather','liveRead']],
    ];
    $source="declare(strict_types=1);\n";
    foreach($groups as $namespace=>[$imports,$names]){
        $source.='namespace '.$namespace." {\n".$imports."\n";
        foreach($names as $name)$source.=functionSource($namespace.'\\'.$name)."\n";
        $source.="}\n";
    }
    return $source.'namespace { echo json_encode(\\Mosa2\\CurrentPreview\\liveRead(),JSON_THROW_ON_ERROR); }';
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)echo readBundle();
