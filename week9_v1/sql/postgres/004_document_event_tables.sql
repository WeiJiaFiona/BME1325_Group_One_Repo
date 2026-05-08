CREATE TABLE IF NOT EXISTS clinical_documents (
    document_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    document_type TEXT NOT NULL,
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS document_registry (
    registry_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES clinical_documents(document_id),
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    document_type TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS event_registry (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    source TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS handoff_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    handoff_stage TEXT NOT NULL,
    patient_brief TEXT NOT NULL,
    current_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    completed_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    pending_tasks JSONB NOT NULL DEFAULT '[]'::jsonb,
    active_risks JSONB NOT NULL DEFAULT '[]'::jsonb,
    next_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);
