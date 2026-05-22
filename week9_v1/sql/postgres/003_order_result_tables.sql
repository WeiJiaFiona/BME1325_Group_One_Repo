CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    order_type TEXT NOT NULL,
    status TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS order_executions (
    execution_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    status TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_requests (
    request_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    test_code TEXT NOT NULL,
    status TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_results (
    result_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES lab_requests(request_id),
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    status TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    resulted_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS imaging_requests (
    request_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    modality TEXT NOT NULL,
    status TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS imaging_results (
    result_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES imaging_requests(request_id),
    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    status TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    resulted_at TIMESTAMPTZ NOT NULL
);
