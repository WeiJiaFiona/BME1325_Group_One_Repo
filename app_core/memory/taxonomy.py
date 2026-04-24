from __future__ import annotations


EVENT_TYPES = {
    "encounter_started",
    "calling_nurse_called",
    "vitals_measured",
    "triage_started",
    "triage_completed",
    "doctor_assessment_started",
    "doctor_assessment_checkpoint",
    "test_ordered",
    "test_result_ready",
    "handoff_requested",
    "handoff_completed",
    "disposition_decided",
    "boarding_started",
    "boarding_timeout",
    "patient_deterioration",
    "resource_bottleneck",
    "encounter_closed",
}


CHECKPOINTS = {
    "post_triage",
    "doctor_assessment_start",
    "doctor_assessment_checkpoint",
    "test_result_ready",
    "handoff_requested",
    "handoff_completed",
    "replay_export",
}


MODES = {"auto", "user"}
