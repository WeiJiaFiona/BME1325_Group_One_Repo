CREATE TABLE IF NOT EXISTS encounters (
    encounter_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    status TEXT NOT NULL,
    arrival_mode TEXT NOT NULL,
    current_zone TEXT,
    ctas_level TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS triage_records (
    triage_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    ctas_level TEXT NOT NULL,
    zone TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    structured_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS vital_signs (
    vital_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    readings JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS clinical_assessments (
    assessment_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    author_role TEXT NOT NULL,
    findings JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS diagnosis_records (
    diagnosis_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    label TEXT NOT NULL,
    diagnosis_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS care_transitions (
    transition_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    from_zone TEXT,
    to_zone TEXT,
    transition_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS admissions (
    admission_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    target_unit TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS discharges (
    discharge_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    disposition TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
