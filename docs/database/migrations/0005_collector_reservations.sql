-- Prepared only. Never applied by the collector. MySQL 8 / UTC session.
-- Reuse disabled m2_jobs identity and m2_module_state version marker.
CREATE TABLE m2_collector_state (
    provider VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    job_id BIGINT UNSIGNED NOT NULL,
    status VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL DEFAULT 'IDLE',
    stop_latched TINYINT NOT NULL DEFAULT 1,
    unresolved TINYINT NOT NULL DEFAULT 0,
    active_cycle VARCHAR(32) COLLATE utf8mb4_0900_bin NULL,
    last_confirmed_cycle VARCHAR(32) COLLATE utf8mb4_0900_bin NULL,
    pending_asset BIGINT UNSIGNED NULL,
    operation_token CHAR(36) COLLATE utf8mb4_0900_bin NULL,
    last_observed_utc DATETIME(6) NULL,
    error_code VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL DEFAULT 'INITIAL_LOCK',
    PRIMARY KEY (provider),
    UNIQUE KEY uq_collector_job (job_id),
    CONSTRAINT fk_collector_job FOREIGN KEY (job_id) REFERENCES m2_jobs(id),
    CONSTRAINT fk_collector_pending FOREIGN KEY (pending_asset) REFERENCES m2_assets(entity_id),
    CONSTRAINT ck_collector_flags CHECK (stop_latched IN (0,1) AND unresolved IN (0,1)),
    CONSTRAINT ck_collector_status CHECK (status IN ('IDLE','RUNNING','COMPLETE','FAILED','PARTIAL_FAILED','OUTCOME_UNKNOWN'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_collector_cycles (
    cycle_id VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    provider VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    owner_token CHAR(36) COLLATE utf8mb4_0900_bin NOT NULL,
    policy_hash CHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    selection_json JSON NOT NULL,
    status VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    started_utc DATETIME(6) NOT NULL,
    finished_utc DATETIME(6) NULL,
    reserved_count INT UNSIGNED NOT NULL DEFAULT 0,
    confirmed_attempts INT UNSIGNED NOT NULL DEFAULT 0,
    error_code VARCHAR(48) COLLATE utf8mb4_0900_bin NOT NULL DEFAULT 'NONE',
    PRIMARY KEY (cycle_id),
    UNIQUE KEY uq_collector_slot (provider, started_utc),
    KEY ix_collector_cycle_status (provider, status, started_utc),
    CONSTRAINT fk_collector_cycle_provider FOREIGN KEY (provider) REFERENCES m2_collector_state(provider),
    CONSTRAINT ck_collector_cycle_status CHECK (status IN ('RUNNING','COMPLETE','FAILED','PARTIAL_FAILED','OUTCOME_UNKNOWN')),
    CONSTRAINT ck_collector_counts CHECK (reserved_count <= 5 AND confirmed_attempts <= reserved_count),
    CONSTRAINT ck_collector_selection CHECK (JSON_TYPE(selection_json) = 'ARRAY' AND JSON_LENGTH(selection_json) = 5),
    CONSTRAINT ck_collector_cycle_time CHECK (finished_utc IS NULL OR finished_utc >= started_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE m2_collector_state
    ADD CONSTRAINT fk_collector_active FOREIGN KEY (active_cycle) REFERENCES m2_collector_cycles(cycle_id),
    ADD CONSTRAINT fk_collector_last FOREIGN KEY (last_confirmed_cycle) REFERENCES m2_collector_cycles(cycle_id);

CREATE TABLE m2_collector_days (
    provider VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    berlin_day DATE NOT NULL,
    reserved_count INT UNSIGNED NOT NULL,
    PRIMARY KEY (provider, berlin_day),
    CONSTRAINT fk_collector_day_provider FOREIGN KEY (provider) REFERENCES m2_collector_state(provider)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_collector_requests (
    cycle_id VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL,
    asset_id BIGINT UNSIGNED NOT NULL,
    ordinal_no TINYINT UNSIGNED NOT NULL,
    provider VARCHAR(64) COLLATE utf8mb4_0900_bin NOT NULL,
    reserved_utc DATETIME(6) NOT NULL,
    berlin_day DATE NOT NULL,
    status VARCHAR(32) COLLATE utf8mb4_0900_bin NOT NULL DEFAULT 'RESERVED',
    attempt_confirmed TINYINT NOT NULL DEFAULT 0,
    finished_utc DATETIME(6) NULL,
    PRIMARY KEY (cycle_id, asset_id),
    UNIQUE KEY uq_collector_request_order (cycle_id, ordinal_no),
    KEY ix_collector_request_window (provider, reserved_utc),
    KEY ix_collector_request_open (provider, status, reserved_utc),
    KEY ix_collector_request_day (provider, berlin_day, reserved_utc),
    CONSTRAINT fk_collector_request_cycle FOREIGN KEY (cycle_id) REFERENCES m2_collector_cycles(cycle_id),
    CONSTRAINT fk_collector_request_asset FOREIGN KEY (asset_id) REFERENCES m2_assets(entity_id),
    CONSTRAINT fk_collector_request_day FOREIGN KEY (provider, berlin_day) REFERENCES m2_collector_days(provider, berlin_day),
    CONSTRAINT ck_collector_request_order CHECK (ordinal_no BETWEEN 1 AND 5),
    CONSTRAINT ck_collector_attempt CHECK (attempt_confirmed IN (0,1)),
    CONSTRAINT ck_collector_request_status CHECK (status IN ('RESERVED','CONFIRMED','FAILED','OUTCOME_UNKNOWN')),
    CONSTRAINT ck_collector_request_time CHECK (finished_utc IS NULL OR finished_utc >= reserved_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Explicit locked bootstrap; no operational grant, scheduler or handler is installed.
INSERT INTO m2_jobs (job_key,module_key,handler_key,enabled,created_at,updated_at)
VALUES ('collector_reservations_v1','collector_reservations','UNWIRED',0,UTC_TIMESTAMP(6),UTC_TIMESTAMP(6));
INSERT INTO m2_module_state (module_key,schema_version,status,updated_at)
VALUES ('collector_reservations',5,'LOCKED',UTC_TIMESTAMP(6));
INSERT INTO m2_collector_state (provider,job_id)
SELECT 'boerse_frankfurt_api_v1',id FROM m2_jobs WHERE job_key='collector_reservations_v1';
