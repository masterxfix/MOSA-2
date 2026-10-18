-- Phase 2, version 1. Repository artifact only; NOT applied.
-- Target: MySQL 8.0.26-16. Caller must select an explicitly authorized empty
-- isolated database and use the qualified strict SQL mode and UTC session.
-- No USE, data writes, migration ledger insertion or server setting changes.

CREATE TABLE m2_entities (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    entity_type VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    canonical_name VARCHAR(255) NOT NULL,
    status VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_entities_type_status (entity_type, status, id),
    KEY ix_entities_name (canonical_name, id),
    CONSTRAINT ck_entities_status CHECK (status IN ('active', 'inactive', 'archived'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_sources (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_key VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    source_type VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    base_url VARCHAR(512) COLLATE utf8mb4_0900_bin NULL,
    enabled TINYINT(1) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_sources_key (source_key),
    CONSTRAINT ck_sources_enabled CHECK (enabled IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_relationships (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    from_entity_id BIGINT UNSIGNED NOT NULL,
    relationship_type VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    to_entity_id BIGINT UNSIGNED NOT NULL,
    source_id BIGINT UNSIGNED NULL,
    valid_from DATETIME(6) NULL,
    valid_to DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_relationships_from (from_entity_id, relationship_type, valid_to, to_entity_id),
    KEY ix_relationships_to (to_entity_id, relationship_type, valid_to, from_entity_id),
    KEY ix_relationships_source (source_id, created_at, id),
    CONSTRAINT fk_relationships_from FOREIGN KEY (from_entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_relationships_to FOREIGN KEY (to_entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_relationships_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_files (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    entity_id BIGINT UNSIGNED NULL,
    source_id BIGINT UNSIGNED NULL,
    storage_backend VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    storage_key VARCHAR(1024) COLLATE utf8mb4_0900_bin NOT NULL,
    mime_type VARCHAR(255) COLLATE utf8mb4_0900_bin NULL,
    byte_size BIGINT UNSIGNED NOT NULL,
    sha256 BINARY(32) NOT NULL,
    observed_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_files_entity (entity_id, created_at, id),
    KEY ix_files_source (source_id, created_at, id),
    KEY ix_files_sha256 (sha256),
    CONSTRAINT fk_files_entity FOREIGN KEY (entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_files_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    event_type VARCHAR(96) COLLATE utf8mb4_0900_bin NOT NULL,
    entity_id BIGINT UNSIGNED NULL,
    source_id BIGINT UNSIGNED NULL,
    occurred_at DATETIME(6) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    metadata_json JSON NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_events_entity (entity_id, occurred_at, id),
    KEY ix_events_type (event_type, occurred_at, id),
    KEY ix_events_source (source_id, observed_at, id),
    CONSTRAINT fk_events_entity FOREIGN KEY (entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT,
    CONSTRAINT fk_events_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_jobs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    job_key VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    module_key VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    handler_key VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    enabled TINYINT(1) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_jobs_key (job_key),
    CONSTRAINT ck_jobs_enabled CHECK (enabled IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_job_runs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    job_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    started_at DATETIME(6) NOT NULL,
    finished_at DATETIME(6) NULL,
    attempt_no INT UNSIGNED NOT NULL,
    summary_json JSON NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_job_runs_job (job_id, started_at, id),
    KEY ix_job_runs_status (status, started_at, id),
    CONSTRAINT fk_job_runs_job FOREIGN KEY (job_id) REFERENCES m2_jobs (id) ON DELETE RESTRICT,
    CONSTRAINT ck_job_runs_status CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT ck_job_runs_attempt CHECK (attempt_no >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_assets (
    entity_id BIGINT UNSIGNED NOT NULL,
    asset_class VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    base_currency CHAR(3) COLLATE utf8mb4_0900_bin NULL,
    status VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (entity_id),
    CONSTRAINT fk_assets_entity FOREIGN KEY (entity_id) REFERENCES m2_entities (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_asset_identifiers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    asset_id BIGINT UNSIGNED NOT NULL,
    identifier_type VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    identifier_value VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    normalized_value VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    scope_key VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL DEFAULT '',
    is_primary TINYINT(1) NOT NULL,
    source_id BIGINT UNSIGNED NULL,
    valid_from DATETIME(6) NULL,
    valid_to DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_identifiers_identity (identifier_type, normalized_value, scope_key),
    KEY ix_identifiers_asset (asset_id, identifier_type, valid_to, id),
    KEY ix_identifiers_source (source_id, created_at, id),
    CONSTRAINT fk_identifiers_asset FOREIGN KEY (asset_id) REFERENCES m2_assets (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_identifiers_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_identifiers_primary CHECK (is_primary IN (0, 1)),
    CONSTRAINT ck_identifiers_ticker_scope CHECK (identifier_type <> 'ticker' OR CHAR_LENGTH(TRIM(scope_key)) > 0),
    CONSTRAINT ck_identifiers_global_scope CHECK (identifier_type NOT IN ('isin', 'wkn', 'figi') OR scope_key = '')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_asset_source_routes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    asset_id BIGINT UNSIGNED NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    route_type VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    external_key VARCHAR(255) COLLATE utf8mb4_0900_bin NOT NULL,
    priority SMALLINT UNSIGNED NOT NULL,
    enabled TINYINT(1) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_routes_external (source_id, route_type, external_key),
    UNIQUE KEY uq_routes_asset_source (asset_id, source_id, route_type),
    KEY ix_routes_preferred (asset_id, enabled, priority, id),
    CONSTRAINT fk_routes_asset FOREIGN KEY (asset_id) REFERENCES m2_assets (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_routes_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT ck_routes_enabled CHECK (enabled IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_schema_migrations (
    version BIGINT UNSIGNED NOT NULL,
    migration_key VARCHAR(160) COLLATE utf8mb4_0900_bin NOT NULL,
    checksum BINARY(32) NOT NULL,
    applied_at DATETIME(6) NOT NULL,
    PRIMARY KEY (version),
    UNIQUE KEY uq_migrations_key (migration_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_sync_checkpoints (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_id BIGINT UNSIGNED NOT NULL,
    stream_key VARCHAR(128) COLLATE utf8mb4_0900_bin NOT NULL,
    cursor_value VARCHAR(512) COLLATE utf8mb4_0900_bin NULL,
    watermark_at DATETIME(6) NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_checkpoints_stream (source_id, stream_key),
    CONSTRAINT fk_checkpoints_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_module_state (
    module_key VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    schema_version BIGINT UNSIGNED NOT NULL,
    status VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (module_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
