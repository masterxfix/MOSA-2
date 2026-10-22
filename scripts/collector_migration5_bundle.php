<?php
declare(strict_types=1);
require __DIR__.'/market_current/read_bundle.php';
require __DIR__.'/market_collector/migration5_capture.php';
$source=file_get_contents(__DIR__.'/phase3k/unit_schema.php');$source=substr($source,strpos($source,'function structure('));
preg_match_all('/rows\(\$p,\x27([^\x27]+)\x27,\$name\)/',$source,$matches);
\Mosa2\Phase2\same(count($matches[1]),6,'six_metadata_queries');
$bundle=readBundle();$end='namespace { echo json_encode(\\Mosa2\\CurrentPreview\\liveRead(),JSON_THROW_ON_ERROR); }';
\Mosa2\Phase2\check(str_ends_with($bundle,$end),'migration5_bundle_tail');
echo substr($bundle,0,-strlen($end)).'namespace Mosa2\\Phase2 {'.functionSource('Mosa2\\Phase2\\qi').'}'.'namespace Mosa2\\CollectorMigration5 { use PDO; use function Mosa2\\Phase2\\{check,qi}; const METADATA_QUERIES='.var_export($matches[1],true).';'.functionSource('Mosa2\\CollectorMigration5\\capture').functionSource('Mosa2\\CollectorMigration5\\packed').'}';
echo 'namespace { echo json_encode(function_exists("gzencode")?\\Mosa2\\CurrentPreview\\liveRead("Mosa2\\\\CollectorMigration5\\\\packed"): ["ok"=>false,"failure"=>"READ_MIGRATION_METADATA_REJECTED"],JSON_THROW_ON_ERROR); }';
