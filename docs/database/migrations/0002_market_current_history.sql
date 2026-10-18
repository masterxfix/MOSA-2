-- Phase 3A, version 2: repository artifact, NOT applied live.
-- Target MySQL 8.0.26-16; requires migration 0001, strict SQL mode and UTC.
-- All DATETIME(6) inputs must be UTC; no implicit local-time defaults.
-- Route/asset/source consistency, append-only writes, dedupe construction and
-- monotone Current updates are later application rules, not enforced by DDL.
-- No collector, trigger, procedure, data or migration-ledger write.

CREATE TABLE m2_market_current (
    asset_id BIGINT UNSIGNED NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    route_id BIGINT UNSIGNED NOT NULL,
    currency CHAR(3) COLLATE utf8mb4_0900_bin NOT NULL,
    price DECIMAL(28,10) NOT NULL,
    bid DECIMAL(28,10) NULL,
    ask DECIMAL(28,10) NULL,
    day_open DECIMAL(28,10) NULL,
    day_high DECIMAL(28,10) NULL,
    day_low DECIMAL(28,10) NULL,
    previous_close DECIMAL(28,10) NULL,
    day_volume DECIMAL(32,8) NULL,
    market_at DATETIME(6) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (asset_id),
    KEY ix_market_current_source (source_id, observed_at, asset_id),
    KEY ix_market_current_route (route_id),
    CONSTRAINT fk_market_current_asset FOREIGN KEY (asset_id) REFERENCES m2_assets (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_market_current_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT fk_market_current_route FOREIGN KEY (route_id) REFERENCES m2_asset_source_routes (id) ON DELETE RESTRICT,
    CONSTRAINT ck_market_current_price CHECK (price > 0),
    CONSTRAINT ck_market_current_bid_ask CHECK (bid <= ask),
    CONSTRAINT ck_market_current_day_range CHECK (day_low <= day_high)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_market_observations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    asset_id BIGINT UNSIGNED NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    route_id BIGINT UNSIGNED NOT NULL,
    currency CHAR(3) COLLATE utf8mb4_0900_bin NOT NULL,
    price DECIMAL(28,10) NOT NULL,
    bid DECIMAL(28,10) NULL,
    ask DECIMAL(28,10) NULL,
    volume DECIMAL(32,8) NULL,
    market_at DATETIME(6) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    dedupe_key BINARY(32) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_market_observations_dedupe (dedupe_key),
    KEY ix_market_observations_asset_time (asset_id, market_at, id),
    KEY ix_market_observations_asset_source (asset_id, source_id, market_at, id),
    KEY ix_market_observations_source (source_id, observed_at, id),
    KEY ix_market_observations_route (route_id),
    CONSTRAINT fk_market_observations_asset FOREIGN KEY (asset_id) REFERENCES m2_assets (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_market_observations_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT fk_market_observations_route FOREIGN KEY (route_id) REFERENCES m2_asset_source_routes (id) ON DELETE RESTRICT,
    CONSTRAINT ck_market_observations_price CHECK (price > 0),
    CONSTRAINT ck_market_observations_bid_ask CHECK (bid <= ask)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE m2_market_bars (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    asset_id BIGINT UNSIGNED NOT NULL,
    source_id BIGINT UNSIGNED NOT NULL,
    route_id BIGINT UNSIGNED NOT NULL,
    interval_key VARCHAR(16) COLLATE utf8mb4_0900_bin NOT NULL,
    currency CHAR(3) COLLATE utf8mb4_0900_bin NOT NULL,
    starts_at DATETIME(6) NOT NULL,
    ends_at DATETIME(6) NOT NULL,
    open_price DECIMAL(28,10) NOT NULL,
    high_price DECIMAL(28,10) NOT NULL,
    low_price DECIMAL(28,10) NOT NULL,
    close_price DECIMAL(28,10) NOT NULL,
    volume DECIMAL(32,8) NULL,
    trade_count BIGINT UNSIGNED NULL,
    observed_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_market_bars_identity (asset_id, route_id, interval_key, starts_at),
    KEY ix_market_bars_asset_time (asset_id, interval_key, starts_at, id),
    KEY ix_market_bars_asset_source (asset_id, source_id, interval_key, starts_at, id),
    KEY ix_market_bars_source (source_id, observed_at, id),
    KEY ix_market_bars_route (route_id),
    CONSTRAINT fk_market_bars_asset FOREIGN KEY (asset_id) REFERENCES m2_assets (entity_id) ON DELETE RESTRICT,
    CONSTRAINT fk_market_bars_source FOREIGN KEY (source_id) REFERENCES m2_sources (id) ON DELETE RESTRICT,
    CONSTRAINT fk_market_bars_route FOREIGN KEY (route_id) REFERENCES m2_asset_source_routes (id) ON DELETE RESTRICT,
    CONSTRAINT ck_market_bars_interval CHECK (interval_key IN ('1m', '5m', '1h', '1d')),
    CONSTRAINT ck_market_bars_time CHECK (starts_at < ends_at),
    CONSTRAINT ck_market_bars_prices CHECK (open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0),
    CONSTRAINT ck_market_bars_low CHECK (low_price <= open_price AND low_price <= close_price AND low_price <= high_price),
    CONSTRAINT ck_market_bars_high CHECK (high_price >= open_price AND high_price >= close_price AND high_price >= low_price)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
