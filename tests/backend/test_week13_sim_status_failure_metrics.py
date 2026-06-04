from reverie import merge_failure_metrics_into_status


def test_merge_failure_metrics_into_status_writes_required_resource_fields():
    status_json = {"resources": {"arrival_profile_mode": "normal"}}
    failure_metrics = {
        "total_arrived_patients": 10,
        "failed_patients_count": 2,
        "failure_rate": 0.2,
        "system_failed": True,
        "failure_threshold": 0.1,
        "system_failed_comparator": "gt",
        "failure_reason_counts": {"boarding_timeout": 2},
        "lwbs_count": 0,
        "boarding_timeout_count": 2,
        "ctas_target_wait_violation_count": 0,
        "ed_los_over_threshold_count": 0,
        "queue_overflow_exposure_count": 0,
        "severe_trauma_time_to_surgery_violation_count": 0,
        "critical_outcome_event_count": 0,
        "ctas_compliance_rate": None,
        "ctas_violations_by_level": {},
        "severe_trauma_success_rate": None,
        "failed_patients": ["patient_001"],
        "failure_reasons_by_patient": {"patient_001": ["boarding_timeout"]},
        "failed_at_step": {"patient_001": 12},
    }

    merged = merge_failure_metrics_into_status(status_json, failure_metrics, curr_step=45)

    assert merged["resources"]["failure_rate"] == 0.2
    assert merged["resources"]["failed_patients_count"] == 2
    assert merged["resources"]["failure_reason_counts"] == {"boarding_timeout": 2}
    assert merged["resources"]["system_failed"] is True
    assert merged["system_health"]["failed"] is True
    assert merged["system_health"]["failed_reason"] == "failure_rate_exceeded_threshold"
    assert merged["system_health"]["failed_at_step"] == 45


def test_merge_failure_metrics_into_status_defaults_exist_without_patient_level_detail():
    merged = merge_failure_metrics_into_status({"resources": {}}, {}, curr_step=3)
    assert merged["resources"]["failure_rate"] == 0.0
    assert merged["resources"]["failed_patients_count"] == 0
    assert merged["resources"]["failure_reason_counts"] == {}
    assert merged["resources"]["system_failed"] is False
    assert merged["system_health"]["failed"] is False
    assert merged["system_health"]["failed_at_step"] is None


def test_merge_failure_metrics_into_status_does_not_write_patient_level_detail():
    merged = merge_failure_metrics_into_status(
        {"resources": {}},
        {
            "failed_patients": ["patient_001"],
            "failure_reasons_by_patient": {"patient_001": ["walkout_lwbs"]},
            "failed_at_step": {"patient_001": 9},
        },
        curr_step=9,
    )
    assert "failed_patients" not in merged["resources"]
    assert "failure_reasons_by_patient" not in merged["resources"]
    assert "failed_at_step" not in merged["resources"]
