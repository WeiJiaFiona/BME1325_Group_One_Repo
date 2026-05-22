import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SERVER_DIR = REPO_ROOT / "reverie" / "backend_server"
if str(BACKEND_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_SERVER_DIR))

from reverie import _build_dialogue_provenance_payload, _coerce_step_movement_path, _resolve_role_schema


def test_movement_path_stationary_keeps_single_tile():
    maze = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ]
    path = _coerce_step_movement_path(maze, (1, 1), (1, 1))
    assert path == [[1, 1]]


def test_movement_path_changed_target_is_multi_tile_even_when_pathfinder_fails():
    maze = [
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0],
    ]
    path = _coerce_step_movement_path(maze, (0, 0), (2, 2))
    assert len(path) >= 2
    assert path[0] == [0, 0]
    assert path[-1] == [2, 2]


def test_role_schema_mapping_matches_expected_keys():
    assert _resolve_role_schema("Doctor") == {"role_key": "doctor", "badge": "DR"}
    assert _resolve_role_schema("TriageNurse") == {"role_key": "triage_nurse", "badge": "TN"}
    assert _resolve_role_schema("BedsideNurse") == {"role_key": "bed_nurse", "badge": "BN"}
    assert _resolve_role_schema("Patient") == {"role_key": "patient", "badge": "PT"}
    assert _resolve_role_schema("UnknownRole") == {"role_key": "other", "badge": "OT"}


def test_dialogue_provenance_uses_runtime_metadata_when_chat_exists():
    class _PersonaStub:
        role = "Doctor"
        runtime_dialogue_provenance = {
            "source_type": "agent_chat_v2_iterative",
            "llm_mode": "hybrid",
            "generator": "agent_chat_v2",
            "prompt_template_path": "persona/prompt_template/ED/v3_ChatGPT/Doctor/iterative_convo_v1.txt",
            "summary_template_path": "persona/prompt_template/ED/v3_ChatGPT/Doctor/summarize_conversation_v1.txt",
            "fallback_used": False,
            "fallback_reason": None,
            "local_library_paths": ["persona/prompt_template/ED/v3_ChatGPT/Doctor/iterative_convo_v1.txt"],
        }

    payload = _build_dialogue_provenance_payload(_PersonaStub(), [["Doctor 1", "hello"]])
    assert payload["chat_present"] is True
    assert payload["source_type"] == "agent_chat_v2_iterative"
    assert payload["llm_mode"] == "hybrid"
    assert payload["generator"] == "agent_chat_v2"


def test_dialogue_provenance_defaults_to_none_when_chat_absent():
    class _PersonaStub:
        role = "Patient"
        runtime_dialogue_provenance = {"source_type": "agent_chat_v2_iterative", "llm_mode": "hybrid"}

    payload = _build_dialogue_provenance_payload(_PersonaStub(), None)
    assert payload["chat_present"] is False
    assert payload["source_type"] == "none"
    assert payload["fallback_used"] is False
