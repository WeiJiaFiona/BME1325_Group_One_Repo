CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    mrn TEXT,
    full_name TEXT NOT NULL,
    sex TEXT,
    date_of_birth TEXT,
    phone TEXT,
    identifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
    provider_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    department_id TEXT,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS departments (
    department_id TEXT PRIMARY KEY,
    department_name TEXT NOT NULL,
    zone TEXT,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    room_id TEXT PRIMARY KEY,
    department_id TEXT,
    room_name TEXT NOT NULL,
    room_type TEXT
);

CREATE TABLE IF NOT EXISTS beds (
    bed_id TEXT PRIMARY KEY,
    room_id TEXT,
    bed_label TEXT NOT NULL,
    occupancy_status TEXT NOT NULL DEFAULT 'available'
);

CREATE TABLE IF NOT EXISTS terminology_dictionary (
    term_id TEXT PRIMARY KEY,
    system_name TEXT NOT NULL,
    term_code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
