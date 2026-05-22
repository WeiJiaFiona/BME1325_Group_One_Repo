ROLE_PERMISSIONS = {
    "doctor": {"encounter.read", "encounter.write", "order.write", "document.write"},
    "triage_nurse": {"encounter.read", "triage.write", "vitals.write"},
    "calling_nurse": {"encounter.read", "vitals.write"},
    "bed_nurse": {"encounter.read", "handoff.write"},
    "admin": {"*"},
    "auditor": {"audit.read"},
}
