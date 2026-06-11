from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = REPO_ROOT / "analysis"
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

from bedside_nurse_mechanism_audit import build_audit, parse_reinsert_counts_from_text


def test_synthetic_log_parses_reinsert_count():
    text = "\n".join(
        [
            "(reverie): Re-inserted Patient 1 into bedside_nurse_waiting",
            "(reverie): Re-inserted Patient 1 into bedside_nurse_waiting",
            "(reverie): Re-inserted Patient 2 into bedside_nurse_waiting",
        ]
    )
    assert parse_reinsert_counts_from_text(text) == {"Patient 1": 2, "Patient 2": 1}


def _write_cluster_scenario(root: Path, sim_root: Path, scenario_id: str, bedside_count: int, exposed_patient: str):
    scenario_dir = root / "nurse_capacity_sweep" / scenario_id
    scenario_dir.mkdir(parents=True)
    sim_dir = sim_root / scenario_id
    (sim_dir / "reverie").mkdir(parents=True)
    data_collection = {
        "Patient": {
            "Patient 1": {
                "ed_arrival_minute": 0,
                "triage_completed_minute": 5,
                "CTAS_score": 3,
                "bedside_reinsert_count": 2,
                "queue_exposure": {"bedside_nurse": {"exposure_minutes": 50}},
            },
            "Patient 2": {
                "ed_arrival_minute": None,
                "triage_completed_minute": 5,
                "CTAS_score": None,
                "queue_exposure": {"bedside_nurse": {"exposure_minutes": 0}},
            },
        },
        "Bedside Nurse": {
            "Bedside Nurse 1": {"Patients_Attended": [[exposed_patient, 1]]}
        },
    }
    (sim_dir / "reverie" / "data_collection.json").write_text(json.dumps(data_collection), encoding="utf-8")
    log_path = scenario_dir / "backend.log"
    log_path.write_text("(reverie): Re-inserted Patient 1 into bedside_nurse_waiting\n", encoding="utf-8")
    status = {
        "scenario_id": scenario_id,
        "sim_dir": str(sim_dir),
        "backend_log_path": str(log_path),
        "scenario": {
            "scenario_id": scenario_id,
            "experiment_group": "nurse_capacity_sweep",
            "bedside_nurse_count": bedside_count,
        },
    }
    (scenario_dir / "scenario_status.json").write_text(json.dumps(status), encoding="utf-8")
    (scenario_dir / "success_failure_report.json").write_text(
        json.dumps({"queue_success_rate": 0.5}),
        encoding="utf-8",
    )


def test_mechanism_audit_builds_json_and_md_from_synthetic_cluster_outputs(tmp_path: Path):
    root = tmp_path / "cluster_outputs" / "ed_bottleneck_v1"
    sim_root = tmp_path / "storage"
    _write_cluster_scenario(root, sim_root, "b3", 3, "Patient 1")
    _write_cluster_scenario(root, sim_root, "b6", 6, "Patient 1")

    audit = build_audit(root, tmp_path / "analysis")

    assert audit["scenario_count"] == 2
    assert audit["pairwise_exposed_set_same"]["3_vs_6"] is True
    assert audit["scenarios"][0]["reinsert_count_by_patient"]["Patient 1"] >= 1
    assert audit["scenarios"][0]["patients_served_but_still_exposed"] == ["Patient 1"]
    assert (tmp_path / "analysis" / "bedside_nurse_mechanism_audit.json").exists()
    assert (tmp_path / "analysis" / "bedside_nurse_mechanism_audit.md").exists()
