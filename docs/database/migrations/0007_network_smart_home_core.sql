-- MOSA 2 network / smart-home schema v0007. Additive, MySQL 8.0.26+.
-- Depends on exact applied versions 0001..0006. UTF8MB4 / UTC DATETIME(6).
-- Schema artifact only: no USE, ALTER, DROP, GRANT, TRIGGER, seed or collector.
-- All rows and module-state/ledger writes are a separately controlled apply.

CREATE TABLE m2_network_sites (
    entity_id BIGINT UNSIGNED NOT NULL,
    site_key VARCHAR(96) COLLATE utf8mb4_0900_bin NOT NULL,
    timezone_name VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    description VARCHAR(255) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (entity_id),
    UNIQUE KEY uq_net_site_key (site_key),
    CONSTRAINT fk_net_site_entity FOREIGN KEY (entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_site_key CHECK (site_key <> '' AND timezone_name <> '')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_domains (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    site_entity_id BIGINT UNSIGNED NOT NULL,
    domain_key VARCHAR(96) COLLATE utf8mb4_0900_bin NOT NULL,
    domain_type VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_net_domain_site_key (site_entity_id, domain_key),
    CONSTRAINT fk_net_domain_site FOREIGN KEY (site_entity_id) REFERENCES m2_network_sites (entity_id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_domain_keys CHECK (domain_key <> '' AND domain_type <> '' AND display_name <> '')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_segments (
    entity_id BIGINT UNSIGNED NOT NULL,
    domain_id BIGINT UNSIGNED NOT NULL,
    segment_key VARCHAR(96) COLLATE utf8mb4_0900_bin NOT NULL,
    segment_type VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL,
    vlan_id SMALLINT UNSIGNED NULL,
    ssid VARCHAR(128) NULL,
    description VARCHAR(255) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (entity_id),
    UNIQUE KEY uq_net_segment_domain_key (domain_id, segment_key),
    UNIQUE KEY uq_net_segment_domain_fk (entity_id, domain_id),
    CONSTRAINT fk_net_segment_entity FOREIGN KEY (entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_segment_domain FOREIGN KEY (domain_id) REFERENCES m2_network_domains (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_segment_valid CHECK (segment_key <> '' AND segment_type <> '' AND (vlan_id IS NULL OR vlan_id BETWEEN 1 AND 4094))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_prefixes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    domain_id BIGINT UNSIGNED NOT NULL,
    segment_entity_id BIGINT UNSIGNED NOT NULL,
    address_family TINYINT UNSIGNED NOT NULL,
    network_bin VARBINARY(16) NOT NULL,
    prefix_length TINYINT UNSIGNED NOT NULL,
    description VARCHAR(255) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_net_prefix_scope (domain_id, address_family, network_bin, prefix_length),
    UNIQUE KEY uq_net_prefix_domain_fk (id, domain_id),
    KEY ix_net_prefix_segment (segment_entity_id, domain_id),
    CONSTRAINT fk_net_prefix_segment FOREIGN KEY (segment_entity_id, domain_id) REFERENCES m2_network_segments (entity_id, domain_id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_prefix_ip CHECK ((address_family = 4 AND OCTET_LENGTH(network_bin) = 4 AND prefix_length <= 32) OR (address_family = 6 AND OCTET_LENGTH(network_bin) = 16 AND prefix_length <= 128))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_devices (
    entity_id BIGINT UNSIGNED NOT NULL,
    site_entity_id BIGINT UNSIGNED NOT NULL,
    device_type VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    manufacturer VARCHAR(128) NULL,
    model VARCHAR(128) NULL,
    hostname VARCHAR(255) COLLATE utf8mb4_0900_bin NULL,
    firmware_version VARCHAR(128) NULL,
    management_mode VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL DEFAULT 'inventory',
    first_seen_at DATETIME(6) NULL,
    last_seen_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (entity_id),
    KEY ix_net_device_site_kind (site_entity_id, device_type, entity_id),
    KEY ix_net_device_host (hostname, entity_id),
    CONSTRAINT fk_net_device_entity FOREIGN KEY (entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_device_site FOREIGN KEY (site_entity_id) REFERENCES m2_network_sites (entity_id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_device_valid CHECK (device_type <> '' AND management_mode <> '' AND (first_seen_at IS NULL OR last_seen_at IS NULL OR last_seen_at >= first_seen_at))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_device_identifiers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    device_entity_id BIGINT UNSIGNED NOT NULL,
    identifier_type VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL,
    normalized_value VARCHAR(255) COLLATE utf8mb4_0900_bin NOT NULL,
    scope_key VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL DEFAULT '',
    source_id BIGINT UNSIGNED NULL,
    observed_at DATETIME(6) NOT NULL,
    valid_to DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_net_identifier_per_device (device_entity_id, identifier_type, normalized_value, scope_key),
    KEY ix_net_identifier_lookup (identifier_type, normalized_value, scope_key, valid_to),
    KEY ix_net_identifier_source (source_id, observed_at),
    CONSTRAINT fk_net_ident_device FOREIGN KEY (device_entity_id) REFERENCES m2_network_devices (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_ident_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_ident_nonempty CHECK (identifier_type <> '' AND normalized_value <> '' AND (valid_to IS NULL OR valid_to >= observed_at))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_interfaces (
    entity_id BIGINT UNSIGNED NOT NULL,
    device_entity_id BIGINT UNSIGNED NOT NULL,
    interface_key VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    interface_type VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL,
    parent_interface_entity_id BIGINT UNSIGNED NULL,
    mac_eui VARBINARY(8) NULL,
    admin_enabled TINYINT(1) NOT NULL DEFAULT 1,
    description VARCHAR(255) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (entity_id),
    UNIQUE KEY uq_net_interface_device_key (device_entity_id, interface_key),
    KEY ix_net_interface_mac (mac_eui, device_entity_id, entity_id),
    KEY ix_net_interface_parent (parent_interface_entity_id),
    CONSTRAINT fk_net_if_entity FOREIGN KEY (entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_if_device FOREIGN KEY (device_entity_id) REFERENCES m2_network_devices (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_if_parent FOREIGN KEY (parent_interface_entity_id) REFERENCES m2_network_interfaces (entity_id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_if_valid CHECK (interface_key <> '' AND interface_type <> '' AND admin_enabled IN (0,1) AND (mac_eui IS NULL OR OCTET_LENGTH(mac_eui) IN (6,8)) AND (parent_interface_entity_id IS NULL OR parent_interface_entity_id <> entity_id))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_interface_segments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    interface_entity_id BIGINT UNSIGNED NOT NULL,
    segment_entity_id BIGINT UNSIGNED NOT NULL,
    attachment_role VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL,
    source_id BIGINT UNSIGNED NULL,
    valid_from DATETIME(6) NOT NULL,
    valid_to DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_net_membership_if (interface_entity_id, valid_to, segment_entity_id),
    KEY ix_net_membership_segment (segment_entity_id, valid_to, interface_entity_id),
    KEY ix_net_membership_source (source_id, created_at),
    CONSTRAINT fk_net_member_if FOREIGN KEY (interface_entity_id) REFERENCES m2_network_interfaces (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_member_segment FOREIGN KEY (segment_entity_id) REFERENCES m2_network_segments (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_member_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_member_valid CHECK (attachment_role <> '' AND (valid_to IS NULL OR valid_to >= valid_from))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_links (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    interface_a_entity_id BIGINT UNSIGNED NOT NULL,
    interface_b_entity_id BIGINT UNSIGNED NOT NULL,
    link_type VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL,
    link_state VARCHAR(24) COLLATE utf8mb4_0900_bin NOT NULL,
    source_id BIGINT UNSIGNED NULL,
    last_observed_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_net_link_pair (interface_a_entity_id, interface_b_entity_id, link_type),
    KEY ix_net_link_peer (interface_b_entity_id, link_state, id),
    KEY ix_net_link_source (source_id, last_observed_at),
    CONSTRAINT fk_net_link_a FOREIGN KEY (interface_a_entity_id) REFERENCES m2_network_interfaces (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_link_b FOREIGN KEY (interface_b_entity_id) REFERENCES m2_network_interfaces (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_link_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_link_pair CHECK (interface_a_entity_id < interface_b_entity_id AND link_type <> ''),
    CONSTRAINT ck_net_link_state CHECK (link_state IN ('up','down','unknown'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_ip_current (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    domain_id BIGINT UNSIGNED NOT NULL,
    address_family TINYINT UNSIGNED NOT NULL,
    address_bin VARBINARY(16) NOT NULL,
    interface_entity_id BIGINT UNSIGNED NOT NULL,
    prefix_id BIGINT UNSIGNED NULL,
    assignment_type VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    source_id BIGINT UNSIGNED NULL,
    first_seen_at DATETIME(6) NOT NULL,
    last_seen_at DATETIME(6) NOT NULL,
    lease_expires_at DATETIME(6) NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_net_ip_domain_address (domain_id, address_family, address_bin),
    KEY ix_net_ip_interface (interface_entity_id, address_family, id),
    KEY ix_net_ip_prefix_domain (prefix_id, domain_id),
    KEY ix_net_ip_source (source_id, last_seen_at),
    CONSTRAINT fk_net_ip_domain FOREIGN KEY (domain_id) REFERENCES m2_network_domains (id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_ip_interface FOREIGN KEY (interface_entity_id) REFERENCES m2_network_interfaces (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_ip_prefix FOREIGN KEY (prefix_id, domain_id) REFERENCES m2_network_prefixes (id, domain_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_ip_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_ip_family CHECK ((address_family = 4 AND OCTET_LENGTH(address_bin) = 4) OR (address_family = 6 AND OCTET_LENGTH(address_bin) = 16)),
    CONSTRAINT ck_net_ip_valid CHECK (assignment_type <> '' AND last_seen_at >= first_seen_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_ip_observations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    domain_id BIGINT UNSIGNED NOT NULL,
    address_family TINYINT UNSIGNED NOT NULL,
    address_bin VARBINARY(16) NOT NULL,
    interface_entity_id BIGINT UNSIGNED NULL,
    observation_type VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    assignment_type VARCHAR(32) COLLATE utf8mb4_0900_bin NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    dedupe_key BINARY(32) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_net_ip_obs_dedupe (dedupe_key),
    KEY ix_net_ip_obs_address (domain_id, address_family, address_bin, observed_at, id),
    KEY ix_net_ip_obs_interface (interface_entity_id, observed_at, id),
    KEY ix_net_ip_obs_source (source_id, observed_at, id),
    CONSTRAINT fk_net_ip_obs_domain FOREIGN KEY (domain_id) REFERENCES m2_network_domains (id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_ip_obs_interface FOREIGN KEY (interface_entity_id) REFERENCES m2_network_interfaces (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_ip_obs_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_ip_obs_family CHECK ((address_family = 4 AND OCTET_LENGTH(address_bin) = 4) OR (address_family = 6 AND OCTET_LENGTH(address_bin) = 16)),
    CONSTRAINT ck_net_ip_obs_type CHECK (observation_type IN ('assigned','released','seen','conflict'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_services (
    entity_id BIGINT UNSIGNED NOT NULL,
    device_entity_id BIGINT UNSIGNED NOT NULL,
    service_key VARCHAR(96) COLLATE utf8mb4_0900_bin NOT NULL,
    service_type VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL,
    transport VARCHAR(16) COLLATE utf8mb4_0900_bin NOT NULL,
    listen_port SMALLINT UNSIGNED NULL,
    endpoint_path VARCHAR(255) NULL,
    source_id BIGINT UNSIGNED NULL,
    enabled TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (entity_id),
    UNIQUE KEY uq_net_service_device_key (device_entity_id, service_key),
    KEY ix_net_service_port (transport, listen_port, device_entity_id),
    KEY ix_net_service_source (source_id, entity_id),
    CONSTRAINT fk_net_service_entity FOREIGN KEY (entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_service_device FOREIGN KEY (device_entity_id) REFERENCES m2_network_devices (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_service_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_service_valid CHECK (service_key <> '' AND service_type <> '' AND transport <> '' AND enabled IN (0,1) AND (listen_port IS NULL OR listen_port BETWEEN 1 AND 65535))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_integrations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    site_entity_id BIGINT UNSIGNED NOT NULL,
    integration_key VARCHAR(96) COLLATE utf8mb4_0900_bin NOT NULL,
    integration_type VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    source_id BIGINT UNSIGNED NULL,
    enabled TINYINT(1) NOT NULL DEFAULT 0,
    status VARCHAR(24) COLLATE utf8mb4_0900_bin NOT NULL DEFAULT 'disabled',
    last_sync_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_net_integration_site (site_entity_id, integration_key),
    KEY ix_net_integration_source (source_id, status, id),
    CONSTRAINT fk_net_integr_site FOREIGN KEY (site_entity_id) REFERENCES m2_network_sites (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_integr_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_integr_valid CHECK (integration_key <> '' AND integration_type <> '' AND enabled IN (0,1) AND status IN ('disabled','ready','error','unavailable'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_metric_definitions (
    metric_key VARCHAR(96) COLLATE utf8mb4_0900_bin NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    category VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    value_type VARCHAR(16) COLLATE utf8mb4_0900_bin NOT NULL,
    unit_key VARCHAR(32) COLLATE utf8mb4_0900_bin NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (metric_key),
    UNIQUE KEY uq_net_metric_type (metric_key, value_type),
    CONSTRAINT ck_net_metric_valid CHECK (metric_key <> '' AND display_name <> '' AND category <> '' AND value_type IN ('decimal','boolean','text') AND (unit_key IS NULL OR unit_key <> ''))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_metric_observations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    subject_entity_id BIGINT UNSIGNED NOT NULL,
    metric_key VARCHAR(96) COLLATE utf8mb4_0900_bin NOT NULL,
    value_type VARCHAR(16) COLLATE utf8mb4_0900_bin NOT NULL,
    value_decimal DECIMAL(28,10) NULL,
    value_boolean TINYINT(1) NULL,
    value_text VARCHAR(512) NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    measured_at DATETIME(6) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    dedupe_key BINARY(32) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_net_metric_obs_dedupe (dedupe_key),
    UNIQUE KEY uq_net_metric_obs_origin (id, subject_entity_id, metric_key, source_id),
    KEY ix_net_metric_obs_subject (subject_entity_id, metric_key, measured_at, id),
    KEY ix_net_metric_obs_source (source_id, observed_at, id),
    KEY ix_net_metric_obs_metric_type (metric_key, value_type),
    CONSTRAINT fk_net_metric_obs_entity FOREIGN KEY (subject_entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_metric_obs_definition FOREIGN KEY (metric_key, value_type) REFERENCES m2_network_metric_definitions (metric_key, value_type) ON DELETE RESTRICT,
    CONSTRAINT fk_net_metric_obs_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_metric_obs_value CHECK ((value_type = 'decimal' AND value_decimal IS NOT NULL AND value_boolean IS NULL AND value_text IS NULL) OR (value_type = 'boolean' AND value_decimal IS NULL AND value_boolean IS NOT NULL AND value_boolean IN (0,1) AND value_text IS NULL) OR (value_type = 'text' AND value_decimal IS NULL AND value_boolean IS NULL AND value_text IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_network_metric_current (
    subject_entity_id BIGINT UNSIGNED NOT NULL,
    metric_key VARCHAR(96) COLLATE utf8mb4_0900_bin NOT NULL,
    observation_id BIGINT UNSIGNED NOT NULL,
    value_type VARCHAR(16) COLLATE utf8mb4_0900_bin NOT NULL,
    value_decimal DECIMAL(28,10) NULL,
    value_boolean TINYINT(1) NULL,
    value_text VARCHAR(512) NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    measured_at DATETIME(6) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (subject_entity_id, metric_key),
    KEY ix_net_metric_current_observation (observation_id, subject_entity_id, metric_key, source_id),
    KEY ix_net_metric_current_type (metric_key, value_type),
    CONSTRAINT fk_net_metric_current_entity FOREIGN KEY (subject_entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_net_metric_current_definition FOREIGN KEY (metric_key, value_type) REFERENCES m2_network_metric_definitions (metric_key, value_type) ON DELETE RESTRICT,
    CONSTRAINT fk_net_metric_current_origin FOREIGN KEY (observation_id, subject_entity_id, metric_key, source_id) REFERENCES m2_network_metric_observations (id, subject_entity_id, metric_key, source_id) ON DELETE RESTRICT,
    CONSTRAINT ck_net_metric_current_value CHECK ((value_type = 'decimal' AND value_decimal IS NOT NULL AND value_boolean IS NULL AND value_text IS NULL) OR (value_type = 'boolean' AND value_decimal IS NULL AND value_boolean IS NOT NULL AND value_boolean IN (0,1) AND value_text IS NULL) OR (value_type = 'text' AND value_decimal IS NULL AND value_boolean IS NULL AND value_text IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
