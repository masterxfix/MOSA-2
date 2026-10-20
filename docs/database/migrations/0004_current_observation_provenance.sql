-- Apply only after preview/check/explicit isolated-test approval.
-- Existing observations and immutable routes are not modified.
ALTER TABLE m2_market_current
    ADD COLUMN observation_id BIGINT UNSIGNED NULL,
    ADD COLUMN observation_format_version TINYINT UNSIGNED NULL,
    ADD COLUMN observation_dedupe_key BINARY(32) NULL,
    ADD COLUMN route_revision INT UNSIGNED NULL,
    ADD KEY ix_market_current_observation (observation_id),
    ADD CONSTRAINT fk_market_current_observation FOREIGN KEY (observation_id) REFERENCES m2_market_observations (id) ON DELETE RESTRICT,
    ADD CONSTRAINT ck_market_current_provenance CHECK (((observation_id IS NULL AND observation_format_version IS NULL AND observation_dedupe_key IS NULL AND route_revision IS NULL) OR (observation_id IS NOT NULL AND observation_format_version = 2 AND observation_dedupe_key IS NOT NULL AND route_revision > 0)) IS TRUE);
