import datetime as dt

from failure_metrics import collect_failure_metrics


class Scratch:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakePatient:
    def __init__(self, name, role="Patient", scratch=None):
        self.name = name
        self.role = role
        self.scratch = scratch or Scratch()


def _patient(name="patient_001", **scratch_kwargs):
    return FakePatient(name=name, scratch=Scratch(**scratch_kwargs))


def _ts(minutes):
    return dt.datetime(2026, 1, 1, 8, 0, 0) + dt.timedelta(minutes=minutes)


def _build_inputs(personas=None, records=None, meta=None, now=None, step=12):
    patient_records = records if records is not None else {}
    return {
        "personas": personas or {},
        "maze": None,
        "data_collection": {"Patient": patient_records},
        "meta": meta or {},
        "curr_time": now or _ts(0),
        "curr_step": step,
    }


def test_empty_failure_metrics():
    result = collect_failure_metrics(**_build_inputs())
    assert result["total_arrived_patients"] == 0
    assert result["failed_patients_count"] == 0
    assert result["failure_rate"] == 0.0
    assert result["system_failed"] is False
    assert result["ctas_compliance_rate"] is None
    assert result["severe_trauma_success_rate"] is None


def test_no_failed_patients():
    p = _patient(ctas="3")
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["total_arrived_patients"] == 1
    assert result["failed_patients_count"] == 0
    assert result["failure_rate"] == 0.0


def test_one_failed_patient():
    p = _patient(walkout_recorded=True)
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["failed_patients_count"] == 1
    assert result["failure_reason_counts"]["walkout_lwbs"] == 1


def test_duplicate_reason_not_repeated():
    p = _patient(walkout_recorded=True)
    records = {"patient_001": {"walkout_event": {"occurred": True}}}
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}, records=records))
    assert result["failed_patients_count"] == 1
    assert result["failure_reason_counts"]["walkout_lwbs"] == 1
    assert result["failure_reasons_by_patient"]["patient_001"] == ["walkout_lwbs"]


def test_multiple_reasons_count_one_patient():
    p = _patient(walkout_recorded=True, boarding_timeout_recorded=True)
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["failed_patients_count"] == 1
    assert set(result["failure_reasons_by_patient"]["patient_001"]) == {
        "walkout_lwbs",
        "boarding_timeout",
    }


def test_failed_at_step_first_only():
    p = _patient(walkout_recorded=True, boarding_timeout_recorded=True)
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}, step=77))
    assert result["failed_at_step"]["patient_001"] == 77


def test_walkout_scratch_counted():
    p = _patient(walkout_recorded=True)
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["lwbs_count"] == 1


def test_lwbs_explicit_event_counted():
    records = {"patient_001": {"lwbs_event": {"occurred": True}}}
    result = collect_failure_metrics(**_build_inputs(records=records))
    assert result["lwbs_count"] == 1


def test_left_department_by_choice_counted():
    records = {"patient_001": {"left_department_by_choice": {"occurred": True}}}
    result = collect_failure_metrics(**_build_inputs(records=records))
    assert result["lwbs_count"] == 1


def test_boarding_timeout_event_counted():
    records = {"patient_001": {"boarding_timeout_event": {"occurred": True}}}
    result = collect_failure_metrics(**_build_inputs(records=records))
    assert result["boarding_timeout_count"] == 1


def test_boarding_timeout_scratch_counted():
    p = _patient(boarding_timeout_recorded=True)
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["boarding_timeout_count"] == 1


def test_admitted_boarding_without_timeout_not_failure():
    p = _patient(state="ADMITTED_BOARDING")
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["boarding_timeout_count"] == 0
    assert result["failed_patients_count"] == 0


def test_ctas2_20min_violation():
    p = _patient(ctas="2", triage_completed_at=_ts(0), first_doctor_contact_at=_ts(20))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["ctas_target_wait_violation_count"] == 1
    assert result["ctas_violations_by_level"] == {"2": 1}


def test_ctas2_10min_compliant():
    p = _patient(ctas="2", triage_completed_at=_ts(0), first_doctor_contact_at=_ts(10))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["ctas_target_wait_violation_count"] == 0


def test_ctas5_130min_violation():
    p = _patient(ctas="5", triage_completed_at=_ts(0), first_doctor_contact_at=_ts(130))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["ctas_target_wait_violation_count"] == 1
    assert result["ctas_violations_by_level"] == {"5": 1}


def test_missing_ctas_timestamps_no_crash():
    p = _patient(ctas="2")
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["ctas_target_wait_violation_count"] == 0
    assert result["ctas_compliance_rate"] is None


def test_ctas_compliance_rate():
    p1 = _patient(ctas="2", triage_completed_at=_ts(0), first_doctor_contact_at=_ts(20))
    p2 = _patient(ctas="2", triage_completed_at=_ts(0), first_doctor_contact_at=_ts(10))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p1, "patient_002": p2}))
    assert result["ctas_target_wait_violation_count"] == 1
    assert result["ctas_compliance_rate"] == 0.5


def test_ed_los_over_threshold():
    p = _patient(ed_arrival_at=_ts(0), ed_exit_at=_ts(721))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["ed_los_over_threshold_count"] == 1


def test_ed_los_missing_exit_no_crash():
    p = _patient(ed_arrival_at=_ts(0))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["ed_los_over_threshold_count"] == 0


def test_queue_overflow_exposure():
    p = _patient(queue_exposure={"doctor": {"max_queue_len": 25, "exposure_minutes": 40}})
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["queue_overflow_exposure_count"] == 1


def test_queue_short_spike_not_failure():
    p = _patient(queue_exposure={"doctor": {"max_queue_len": 25, "exposure_minutes": 5}})
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["queue_overflow_exposure_count"] == 0


def test_severe_trauma_delayed_surgery_violation():
    p = _patient(is_severe_trauma=True, ed_arrival_at=_ts(0), surgery_or_transfer_at=_ts(91))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["severe_trauma_time_to_surgery_violation_count"] == 1


def test_severe_trauma_timely_surgery_success():
    p = _patient(is_severe_trauma=True, ed_arrival_at=_ts(0), surgery_or_transfer_at=_ts(60))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["severe_trauma_time_to_surgery_violation_count"] == 0


def test_severe_trauma_success_rate():
    p1 = _patient(is_severe_trauma=True, ed_arrival_at=_ts(0), surgery_or_transfer_at=_ts(60))
    p2 = _patient(is_severe_trauma=True, ed_arrival_at=_ts(0), surgery_or_transfer_at=_ts(120))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p1, "patient_002": p2}))
    assert result["severe_trauma_success_rate"] == 0.5


def test_critical_outcome_requires_enable_flag():
    records = {"patient_001": {"critical_outcome_event": {"occurred": True}}}
    result = collect_failure_metrics(**_build_inputs(records=records))
    assert result["critical_outcome_event_count"] == 0
    assert result["failed_patients_count"] == 0


def test_explicit_critical_outcome_counted_when_enabled():
    records = {"patient_001": {"mortality_event": {"occurred": True}}}
    meta = {"enable_critical_outcome_failure": True}
    result = collect_failure_metrics(**_build_inputs(records=records, meta=meta))
    assert result["critical_outcome_event_count"] == 1
    assert result["failed_patients_count"] == 1


def test_no_mortality_not_fabricated():
    result = collect_failure_metrics(**_build_inputs(records={"patient_001": {}}))
    assert result["critical_outcome_event_count"] == 0


def test_waiting_timeout_not_treated_as_mortality():
    p = _patient(ctas="2", triage_completed_at=_ts(0), first_doctor_contact_at=_ts(40))
    result = collect_failure_metrics(**_build_inputs(personas={"patient_001": p}))
    assert result["critical_outcome_event_count"] == 0
    assert result["ctas_target_wait_violation_count"] == 1


def test_failure_rate_gt_equal_boundary_false():
    personas = {}
    records = {}
    for idx in range(300):
        patient_id = f"patient_{idx:03d}"
        records[patient_id] = {}
    for idx in range(30):
        patient_id = f"patient_{idx:03d}"
        records[patient_id]["boarding_timeout_event"] = {"occurred": True}
    result = collect_failure_metrics(**_build_inputs(personas=personas, records=records, meta={"system_failed_comparator": "gt"}))
    assert result["failure_rate"] == 0.1
    assert result["system_failed"] is False


def test_failure_rate_gte_boundary_true():
    records = {}
    for idx in range(300):
        patient_id = f"patient_{idx:03d}"
        records[patient_id] = {}
    for idx in range(30):
        patient_id = f"patient_{idx:03d}"
        records[patient_id]["boarding_timeout_event"] = {"occurred": True}
    result = collect_failure_metrics(**_build_inputs(records=records, meta={"system_failed_comparator": "gte"}))
    assert result["failure_rate"] == 0.1
    assert result["system_failed"] is True


def test_failure_rate_gt_above_threshold_true():
    records = {}
    for idx in range(300):
        patient_id = f"patient_{idx:03d}"
        records[patient_id] = {}
    for idx in range(31):
        patient_id = f"patient_{idx:03d}"
        records[patient_id]["boarding_timeout_event"] = {"occurred": True}
    result = collect_failure_metrics(**_build_inputs(records=records, meta={"system_failed_comparator": "gt"}))
    assert result["failure_rate"] > 0.1
    assert result["system_failed"] is True


def test_invalid_comparator_fallback():
    records = {"patient_001": {"boarding_timeout_event": {"occurred": True}}}
    result = collect_failure_metrics(**_build_inputs(records=records, meta={"system_failed_comparator": "bad-value"}))
    assert result["system_failed_comparator"] == "gt"
