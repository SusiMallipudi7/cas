-- CAS Phase 2 database schema
-- Applied automatically on first PostgreSQL container boot via docker-entrypoint-initdb.d

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Enumerations
-- ---------------------------------------------------------------------------

CREATE TYPE transformation_phase AS ENUM (
    'CONTEXT_ESTABLISHMENT',
    'WORKFLOW_INTEGRATION',
    'AI_NATIVE_OPERATION'
);

CREATE TYPE phase_transition_direction AS ENUM (
    'forward',
    'rollback'
);

CREATE TYPE autonomy_zone AS ENUM (
    'ZONE_1',
    'ZONE_2',
    'ZONE_3',
    'ZONE_4'
);

CREATE TYPE risk_band AS ENUM (
    'LOW',
    'MODERATE',
    'HIGH'
);

CREATE TYPE complexity_level AS ENUM (
    'LOW',
    'MODERATE',
    'HIGH'
);

CREATE TYPE calibration_signal_type AS ENUM (
    'outcome',
    'human_feedback'
);

CREATE TYPE calibration_outcome AS ENUM (
    'success',
    'failure',
    'correction',
    'escalation'
);

-- ---------------------------------------------------------------------------
-- Configuration cache (system area risk + formula weights)
-- ---------------------------------------------------------------------------

CREATE TABLE system_area_risk (
    target_scope    TEXT PRIMARY KEY,
    risk_score      DOUBLE PRECISION NOT NULL CHECK (risk_score >= 0.0 AND risk_score <= 1.0),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE formula_config (
    formula_version TEXT PRIMARY KEY,
    weights         JSONB NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX formula_config_one_active
    ON formula_config (is_active)
    WHERE is_active = TRUE;

-- ---------------------------------------------------------------------------
-- Transformation posture / phase state (multi-replica sync source of truth)
-- ---------------------------------------------------------------------------

CREATE TABLE phase_state (
    id                  BIGSERIAL PRIMARY KEY,
    active_phase        transformation_phase NOT NULL,
    phase_version       INTEGER NOT NULL CHECK (phase_version >= 1),
    previous_phase      transformation_phase,
    transition_id       UUID NOT NULL,
    direction           phase_transition_direction NOT NULL DEFAULT 'forward',
    applied_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (phase_version),
    UNIQUE (transition_id)
);

CREATE TABLE replica_sync_status (
    replica_id          TEXT PRIMARY KEY,
    sync_status         TEXT NOT NULL CHECK (sync_status IN ('SYNCED', 'PENDING_RELOAD', 'UNKNOWN')),
    last_transition_id  UUID,
    phase_version       INTEGER,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE control_plane_events (
    id                      BIGSERIAL PRIMARY KEY,
    event_type              TEXT NOT NULL,
    transition_id           UUID NOT NULL,
    target_phase            transformation_phase NOT NULL,
    previous_phase          transformation_phase NOT NULL,
    direction               phase_transition_direction NOT NULL,
    source_replica_count    INTEGER NOT NULL CHECK (source_replica_count >= 1),
    payload                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    applied_at              TIMESTAMPTZ NOT NULL,
    received_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX control_plane_events_transition_id_idx
    ON control_plane_events (transition_id);

CREATE INDEX control_plane_events_applied_at_idx
    ON control_plane_events (applied_at DESC);

-- ---------------------------------------------------------------------------
-- Calibration signal ingestion (0–20 threshold per domain)
-- ---------------------------------------------------------------------------

CREATE TABLE calibration_signals (
    id                  BIGSERIAL PRIMARY KEY,
    knowledge_domain    TEXT NOT NULL,
    action_type         TEXT NOT NULL,
    signal_type         calibration_signal_type NOT NULL,
    outcome             calibration_outcome NOT NULL,
    request_id          TEXT NOT NULL,
    trace_id            TEXT,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX calibration_signals_domain_action_idx
    ON calibration_signals (knowledge_domain, action_type);

CREATE INDEX calibration_signals_ingested_at_idx
    ON calibration_signals (ingested_at DESC);

CREATE TABLE calibration_counters (
    knowledge_domain    TEXT NOT NULL,
    action_type         TEXT NOT NULL,
    signal_count        INTEGER NOT NULL DEFAULT 0 CHECK (signal_count >= 0),
    threshold           INTEGER NOT NULL DEFAULT 20 CHECK (threshold > 0),
    ready_for_progression BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (knowledge_domain, action_type)
);

CREATE TABLE calibration_readiness_events (
    id                  BIGSERIAL PRIMARY KEY,
    knowledge_domain    TEXT NOT NULL UNIQUE,
    total_signals       INTEGER NOT NULL CHECK (total_signals >= 0),
    threshold           INTEGER NOT NULL DEFAULT 20,
    emitted_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Assessment audit fragments (fail-closed synchronous audit persistence)
-- ---------------------------------------------------------------------------

CREATE TABLE audit_fragments (
    id                  BIGSERIAL PRIMARY KEY,
    request_id          TEXT NOT NULL,
    trace_id            TEXT,
    workflow_instance_id TEXT,
    active_phase        transformation_phase,
    base_zone           autonomy_zone,
    final_zone          autonomy_zone NOT NULL,
    rule_matched        INTEGER NOT NULL,
    risk_score          DOUBLE PRECISION,
    risk_band           risk_band,
    cognitive_complexity complexity_level,
    operational_complexity complexity_level,
    platform_confidence DOUBLE PRECISION,
    transformation_phase_modifier TEXT,
    formula_version     TEXT,
    formula_weights     JSONB NOT NULL DEFAULT '{}'::jsonb,
    posture_metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    request_payload     JSONB NOT NULL,
    response_payload    JSONB NOT NULL,
    published_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX audit_fragments_request_id_idx
    ON audit_fragments (request_id);

CREATE INDEX audit_fragments_published_at_idx
    ON audit_fragments (published_at DESC);

CREATE INDEX audit_fragments_final_zone_idx
    ON audit_fragments (final_zone);

-- ---------------------------------------------------------------------------
-- Seed data aligned with Phase 1/2 defaults
-- ---------------------------------------------------------------------------

INSERT INTO formula_config (formula_version, weights, is_active)
VALUES (
    '1.0.0',
    '{
        "system_area_risk": 0.30,
        "action_consequence_scope": 0.25,
        "reversibility": 0.15,
        "precedent_availability": 0.15,
        "stakeholder_visibility": 0.15
    }'::jsonb,
    TRUE
);

INSERT INTO system_area_risk (target_scope, risk_score) VALUES
    ('core_db', 0.9),
    ('auth_service', 0.8),
    ('reporting_ui', 0.2),
    ('single-requirement', 0.2),
    ('intra-step', 0.1);

INSERT INTO phase_state (
    active_phase,
    phase_version,
    previous_phase,
    transition_id,
    direction,
    applied_at
) VALUES (
    'CONTEXT_ESTABLISHMENT',
    1,
    NULL,
    gen_random_uuid(),
    'forward',
    NOW()
);

INSERT INTO replica_sync_status (replica_id, sync_status, phase_version)
VALUES
    ('cas-replica-01', 'SYNCED', 1),
    ('cas-replica-02', 'SYNCED', 1),
    ('cas-replica-03', 'SYNCED', 1);
