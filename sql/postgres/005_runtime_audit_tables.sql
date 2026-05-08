CREATE TABLE IF NOT EXISTS memory_events (
    memory_event_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS current_encounter_summaries (
    summary_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    current_state TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_memory_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    patient_id TEXT,
    encounter_id TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox_events (
    outbox_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key_id TEXT PRIMARY KEY,
    request_scope TEXT NOT NULL,
    encounter_id TEXT,
    response_fingerprint TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_exports (
    replay_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);
