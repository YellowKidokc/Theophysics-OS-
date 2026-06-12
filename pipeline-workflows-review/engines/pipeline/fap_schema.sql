-- FAP Schema DDL
-- Run against the configured FAP Postgres database.
-- Creates the fap schema for Folder Automations & Pipelines

CREATE SCHEMA IF NOT EXISTS fap;

CREATE TABLE IF NOT EXISTS fap.stations (
    name            TEXT PRIMARY KEY,
    input_dir       TEXT NOT NULL,
    output_dir      TEXT NOT NULL,
    fail_dir        TEXT,
    review_dir      TEXT,
    threshold_pass  REAL DEFAULT 0.7,
    threshold_fail  REAL DEFAULT 0.3,
    file_extensions TEXT[] DEFAULT '{*}',
    pipeline_name   TEXT,
    station_order   INT DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fap.manifests (
    id              SERIAL PRIMARY KEY,
    file_hash       TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    pipeline_name   TEXT NOT NULL,
    current_station TEXT NOT NULL,
    status          TEXT DEFAULT 'active',
    scores          JSONB DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    history         JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fap.actions (
    id              SERIAL PRIMARY KEY,
    manifest_id     INT REFERENCES fap.manifests(id),
    station_name    TEXT NOT NULL,
    action          TEXT NOT NULL,
    verdict         TEXT,
    score           REAL,
    notes           TEXT,
    file_from       TEXT,
    file_to         TEXT,
    timestamp       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fap.signals (
    id              SERIAL PRIMARY KEY,
    signal_type     TEXT NOT NULL,
    source_station  TEXT NOT NULL,
    message         TEXT NOT NULL,
    payload         JSONB DEFAULT '{}',
    acknowledged    BOOLEAN DEFAULT FALSE,
    timestamp       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_manifests_hash ON fap.manifests(file_hash);
CREATE INDEX IF NOT EXISTS idx_manifests_status ON fap.manifests(status);
CREATE INDEX IF NOT EXISTS idx_manifests_pipeline ON fap.manifests(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_actions_manifest ON fap.actions(manifest_id);
CREATE INDEX IF NOT EXISTS idx_actions_station ON fap.actions(station_name);
CREATE INDEX IF NOT EXISTS idx_signals_unack ON fap.signals(acknowledged) WHERE NOT acknowledged;
CREATE INDEX IF NOT EXISTS idx_signals_type ON fap.signals(signal_type);

-- Useful views
CREATE OR REPLACE VIEW fap.pipeline_summary AS
SELECT
    s.pipeline_name,
    s.name AS station_name,
    s.station_order,
    s.is_active,
    COALESCE(pending.cnt, 0) AS pending_count,
    COALESCE(completed.cnt, 0) AS completed_count,
    COALESCE(failed.cnt, 0) AS failed_count
FROM fap.stations s
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS cnt FROM fap.manifests m
    WHERE m.current_station = s.name AND m.status = 'active'
) pending ON true
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS cnt FROM fap.manifests m
    WHERE m.current_station = s.name AND m.status = 'completed'
) completed ON true
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS cnt FROM fap.manifests m
    WHERE m.current_station = s.name AND m.status = 'failed'
) failed ON true
ORDER BY s.pipeline_name, s.station_order;
