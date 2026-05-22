INSERT INTO departments (department_id, department_name, zone, created_at)
VALUES
    ('DEPT-ED', 'Emergency Department', 'red', NOW()),
    ('DEPT-OBS', 'Observation Unit', 'yellow', NOW())
ON CONFLICT (department_id) DO NOTHING;

INSERT INTO rooms (room_id, department_id, room_name, room_type)
VALUES
    ('ROOM-TRIAGE', 'DEPT-ED', 'Triage Room', 'triage'),
    ('ROOM-OBS-1', 'DEPT-OBS', 'Observation Room 1', 'observation')
ON CONFLICT (room_id) DO NOTHING;

INSERT INTO beds (bed_id, room_id, bed_label, occupancy_status)
VALUES
    ('BED-OBS-01', 'ROOM-OBS-1', 'OBS-01', 'available'),
    ('BED-OBS-02', 'ROOM-OBS-1', 'OBS-02', 'available')
ON CONFLICT (bed_id) DO NOTHING;
