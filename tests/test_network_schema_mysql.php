<?php
declare(strict_types=1);

/** Only for isolated disposable MySQL 8 test service. Never point at Dogado. */
$dsn = getenv('NETWORK_TEST_DSN') ?: '';
if ($dsn !== 'mysql:host=127.0.0.1;port=3306;dbname=mosa2_network_schema_test;charset=utf8mb4') {
    throw new RuntimeException('DISPOSABLE_TEST_DB_ONLY');
}
$db = new PDO($dsn, getenv('NETWORK_TEST_USER') ?: 'root', getenv('NETWORK_TEST_PASSWORD') ?: '', [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_EMULATE_PREPARES => false,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
]);
if ($db->query('SELECT DATABASE()')->fetchColumn() !== 'mosa2_network_schema_test') {
    throw new RuntimeException('DATABASE_IDENTITY');
}
$core = file_get_contents(__DIR__.'/../docs/database/migrations/0001_core_asset_identity.sql');
$network = file_get_contents(__DIR__.'/../docs/database/migrations/0007_network_smart_home_core.sql');
if ($core === false || $network === false) {
    throw new RuntimeException('MIGRATION_MISSING');
}
preg_match_all('/CREATE TABLE (?:m2_entities|m2_sources)\s*\(.*?\)\s*ENGINE=InnoDB[^;]*;/s', $core, $coreSql);
if (count($coreSql[0]) !== 2) {
    throw new RuntimeException('CORE_FIXTURE');
}
foreach ($coreSql[0] as $ddl) $db->exec($ddl);
preg_match_all('/CREATE TABLE m2_network_[a-z_]+\s*\(.*?\)\s*ENGINE=InnoDB[^;]*;/s', $network, $networkSql);
if (count($networkSql[0]) !== 16) {
    throw new RuntimeException('NETWORK_TABLE_COUNT');
}
foreach ($networkSql[0] as $ddl) $db->exec($ddl);
$rows = $db->query("SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'm2_network_%'")->fetchColumn();
if ((int)$rows !== 16) {
    throw new RuntimeException('SCHEMA_SHAPE');
}
function execute(PDO $pdo, string $sql, array $bind = []): void {
    $q = $pdo->prepare($sql);
    $q->execute($bind);
}
function rejected(string $label, callable $fn): void {
    try {
        $fn();
    } catch (PDOException $exception) {
        if (str_starts_with((string)$exception->getCode(), '23')) return;
        throw new RuntimeException('WRONG_REJECTION_'.$label, 0, $exception);
    }
    throw new RuntimeException('CONSTRAINT_NOT_ENFORCED_'.$label);
}
$now='2026-11-13 08:00:00.000000';
foreach ([[100,'site'],[101,'segment'],[102,'device'],[103,'interface'],
          [200,'site'],[201,'segment'],[202,'device'],[203,'interface']] as [$id,$type]) {
    execute($db, "INSERT INTO m2_entities
      (id,entity_type,canonical_name,status,created_at,updated_at)
      VALUES (?,?,'isolated-fixture','active',?,?)", [$id,$type,$now,$now]);
}
execute($db,"INSERT INTO m2_sources
  (id,source_key,source_type,display_name,base_url,enabled,created_at,updated_at)
  VALUES (1,'fixture:readonly','test','isolated-only',NULL,0,?,?)",[$now,$now]);
foreach ([[100,'one'],[200,'two']] as [$entity,$key]) {
    execute($db,"INSERT INTO m2_network_sites
      (entity_id,site_key,timezone_name,description,created_at,updated_at)
      VALUES (?,?,'Europe/Berlin',NULL,?,?)",[$entity,$key,$now,$now]);
}
foreach ([[1,100,'home'],[2,200,'lab']] as [$id,$site,$key]) {
    execute($db,"INSERT INTO m2_network_domains
      (id,site_entity_id,domain_key,domain_type,display_name,created_at,updated_at)
      VALUES (?, ?, ?, 'lan', 'scope', ?, ?)",[$id,$site,$key,$now,$now]);
}
foreach ([[101,1,'wired'],[201,2,'wired']] as [$entity,$domain,$key]) {
    execute($db,"INSERT INTO m2_network_segments
      (entity_id,domain_id,segment_key,segment_type,vlan_id,created_at,updated_at)
      VALUES (?,?,?,'ethernet',100,?,?)",[$entity,$domain,$key,$now,$now]);
}
rejected('VLAN_RANGE',static function() use ($db,$now): void {
    execute($db,"UPDATE m2_network_segments SET vlan_id=4095 WHERE entity_id=101");
});
execute($db,"INSERT INTO m2_network_prefixes
  (id,domain_id,segment_entity_id,address_family,network_bin,prefix_length,created_at,updated_at)
  VALUES (1,1,101,4,?,24,?,?)",[inet_pton('192.0.2.0'),$now,$now]);
rejected('PREFIX_FAMILY',static function() use ($db,$now): void {
    execute($db,"INSERT INTO m2_network_prefixes
      (domain_id,segment_entity_id,address_family,network_bin,prefix_length,created_at,updated_at)
      VALUES (1,101,6,?,64,?,?)",[inet_pton('192.0.2.0'),$now,$now]);
});
foreach ([[102,100],[202,200]] as [$entity,$site]) {
    execute($db,"INSERT INTO m2_network_devices
      (entity_id,site_entity_id,device_type,manufacturer,model,hostname,firmware_version,
       management_mode,created_at,updated_at)
      VALUES (?,?,'router',NULL,NULL,NULL,NULL,'inventory',?,?)",[$entity,$site,$now,$now]);
}
foreach ([[103,102],[203,202]] as [$entity,$device]) {
    execute($db,"INSERT INTO m2_network_interfaces
      (entity_id,device_entity_id,interface_key,interface_type,created_at,updated_at)
      VALUES (?,?,'lan0','ethernet',?,?)",[$entity,$device,$now,$now]);
}
execute($db,"INSERT INTO m2_network_interface_segments
  (interface_entity_id,segment_entity_id,attachment_role,valid_from,created_at)
  VALUES (103,101,'untagged',?,?)",[$now,$now]);
execute($db,"INSERT INTO m2_network_links
  (interface_a_entity_id,interface_b_entity_id,link_type,link_state,last_observed_at,updated_at)
  VALUES (103,203,'vpn','up',?,?)",[$now,$now]);
rejected('LINK_ORDER',static function() use ($db,$now): void {
    execute($db,"INSERT INTO m2_network_links
      (interface_a_entity_id,interface_b_entity_id,link_type,link_state,last_observed_at,updated_at)
      VALUES (203,103,'ethernet','up',?,?)",[$now,$now]);
});
$ip=inet_pton('192.0.2.25');
foreach ([[1,103,1],[2,203,null]] as [$domain,$interface,$prefix]) {
    execute($db,"INSERT INTO m2_network_ip_current
      (domain_id,address_family,address_bin,interface_entity_id,prefix_id,assignment_type,
       first_seen_at,last_seen_at,updated_at)
      VALUES (?,4,?,?,?,'static',?,?,?)",[$domain,$ip,$interface,$prefix,$now,$now,$now]);
}
rejected('DUPLICATE_IP_IN_SCOPE',static function() use ($db,$ip,$now): void {
    execute($db,"INSERT INTO m2_network_ip_current
      (domain_id,address_family,address_bin,interface_entity_id,assignment_type,
       first_seen_at,last_seen_at,updated_at)
      VALUES (1,4,?,103,'dhcp',?,?,?)",[$ip,$now,$now,$now]);
});
rejected('PREFIX_WRONG_DOMAIN',static function() use ($db,$ip,$now): void {
    execute($db,"UPDATE m2_network_ip_current SET prefix_id=1 WHERE domain_id=2 AND address_bin=?",[$ip]);
});
execute($db,"INSERT INTO m2_network_ip_observations
  (domain_id,address_family,address_bin,interface_entity_id,observation_type,assignment_type,
   source_id,observed_at,dedupe_key,created_at)
  VALUES (1,4,?,103,'assigned','static',1,?,?,?)",
  [$ip, $now,hex2bin(str_repeat('cd',32)),$now]);
execute($db,"INSERT INTO m2_network_metric_definitions
  (metric_key,display_name,category,value_type,unit_key,created_at,updated_at)
  VALUES ('power_w','Power','energy','decimal','W',?,?)",[$now,$now]);
execute($db,"INSERT INTO m2_network_metric_definitions
  (metric_key,display_name,category,value_type,unit_key,created_at,updated_at)
  VALUES ('online','Reachability','status','boolean',NULL,?,?)",[$now,$now]);
execute($db,"INSERT INTO m2_network_metric_observations
  (id,subject_entity_id,metric_key,value_type,value_decimal,source_id,measured_at,
   observed_at,dedupe_key,created_at)
  VALUES (1,102,'power_w','decimal',11.5,1,?,?,?,?)",
  [$now,$now,hex2bin(str_repeat('ab',32)),$now]);
execute($db,"INSERT INTO m2_network_metric_current
  (subject_entity_id,metric_key,observation_id,value_type,value_decimal,source_id,
   measured_at,observed_at,updated_at)
  VALUES (102,'power_w',1,'decimal',11.5,1,?,?,?)",[$now,$now,$now]);
rejected('CURRENT_PROVENANCE',static function() use ($db,$now): void {
    execute($db,"INSERT INTO m2_network_metric_current
      (subject_entity_id,metric_key,observation_id,value_type,value_decimal,source_id,
       measured_at,observed_at,updated_at)
      VALUES (202,'power_w',1,'decimal',11.5,1,?,?,?)",[$now,$now,$now]);
});
rejected('NULL_BOOLEAN',static function() use ($db,$now): void {
    execute($db,"INSERT INTO m2_network_metric_observations
      (subject_entity_id,metric_key,value_type,value_boolean,source_id,measured_at,observed_at,
       dedupe_key,created_at) VALUES (102,'online','boolean',NULL,1,?,?,?,?)",
       [$now,$now,hex2bin(str_repeat('ba',32)),$now]);
});
execute($db,"INSERT INTO m2_network_metric_observations
  (id,subject_entity_id,metric_key,value_type,value_boolean,source_id,measured_at,
   observed_at,dedupe_key,created_at)
  VALUES (2,102,'online','boolean',1,1,?,?,?,?)",
  [$now,$now,hex2bin(str_repeat('bc',32)),$now]);
execute($db,"INSERT INTO m2_network_metric_current
  (subject_entity_id,metric_key,observation_id,value_type,value_boolean,source_id,
   measured_at,observed_at,updated_at)
  VALUES (102,'online',2,'boolean',1,1,?,?,?)",[$now,$now,$now]);
$plans = [
    "SELECT id FROM m2_network_ip_current WHERE domain_id=1 AND address_family=4 AND address_bin=0xC0000219",
    "SELECT entity_id FROM m2_network_devices WHERE site_entity_id=100 AND device_type='router'",
    "SELECT observation_id FROM m2_network_metric_current WHERE subject_entity_id=102 AND metric_key='power_w'",
    "SELECT id FROM m2_network_metric_observations WHERE subject_entity_id=102 AND metric_key='power_w' ORDER BY measured_at DESC LIMIT 10"
];
foreach ($plans as $query) {
    $plan=$db->query('EXPLAIN '.$query)->fetch();
    if (!is_array($plan) || (($plan['type'] ?? '') === 'ALL' && ($plan['key'] ?? null) === null)) {
        throw new RuntimeException('INDEX_NOT_USED: '.substr($query,0,80));
    }
}
echo 'PASS isolated_mysql_network_schema_0007 tables=16 ip_scopes=2 metric_provenance=PASS typed_checks=PASS fk=PASS index_paths=4'.PHP_EOL;
