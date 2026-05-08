"""
Unit tests for SymptoGuide AI core logic.

These tests cover the deterministic, non-LLM parts of the application:
- Emergency detection (keyword + regex matching)
- Context request detection
- Symptom extraction from chat history
"""

import pytest
from src.app.medical_logic import (
    fast_emergency_check,
    detect_context_request,
    extract_symptoms_from_history,
)


# ============================================================================
#  EMERGENCY DETECTION TESTS
# ============================================================================

class TestFastEmergencyCheck:
    """Tests for the fast_emergency_check function."""

    # --- True Positives: should trigger ---
    def test_chest_pain_triggers(self):
        assert fast_emergency_check("I have severe chest pain") is not None

    def test_choking_triggers(self):
        assert fast_emergency_check("my child is choking") is not None

    def test_seizure_triggers(self):
        assert fast_emergency_check("she had a seizure") is not None

    def test_heart_attack_triggers(self):
        assert fast_emergency_check("I think it's a heart attack") is not None

    def test_suicide_triggers(self):
        result = fast_emergency_check("I want to kill myself")
        assert result is not None
        assert result == "Mental Health Crisis"

    def test_hemorrhage_triggers(self):
        assert fast_emergency_check("there is hemorrhage") is not None

    def test_severe_bleeding_triggers(self):
        assert fast_emergency_check("there is severe bleeding") is not None

    def test_unconscious_triggers(self):
        assert fast_emergency_check("he is unconscious") is not None

    def test_fuzzy_chest_pain(self):
        """Fuzzy regex pattern for chest + pain variants."""
        assert fast_emergency_check("I feel chest pressure") is not None

    def test_fuzzy_breathing_difficulty(self):
        """Fuzzy regex pattern for breathing difficulty."""
        assert fast_emergency_check("I can't breathe properly") is not None

    def test_difficulty_breathing(self):
        """Direct keyword match for 'difficulty breathing'."""
        assert fast_emergency_check("I have difficulty breathing") is not None

    # --- True Negatives: should NOT trigger ---
    def test_breathing_normally_no_trigger(self):
        """'breathing' in a benign context should not trigger."""
        assert fast_emergency_check("I was breathing normally during exercise") is None

    def test_unrelated_text_no_trigger(self):
        assert fast_emergency_check("I have a headache and runny nose") is None

    def test_weather_query_no_trigger(self):
        assert fast_emergency_check("What's the weather like today?") is None

    def test_empty_input(self):
        assert fast_emergency_check("") is None

    def test_greeting_no_trigger(self):
        assert fast_emergency_check("Hello, how are you?") is None

    # --- Alert type checks ---
    def test_returns_correct_alert_airway(self):
        result = fast_emergency_check("the patient is choking")
        assert result == "Airway Emergency"

    def test_returns_correct_alert_cardiac(self):
        result = fast_emergency_check("I think it is a heart attack")
        assert result == "Possible Cardiac Event"

    def test_returns_correct_alert_bleeding(self):
        result = fast_emergency_check("there is severe bleeding")
        assert result == "Severe Bleeding"

    def test_returns_correct_alert_neuro(self):
        result = fast_emergency_check("he had a stroke yesterday")
        assert result == "Neurological Emergency"


# ============================================================================
#  CONTEXT REQUEST DETECTION TESTS
# ============================================================================

class TestDetectContextRequest:
    """Tests for the detect_context_request function."""

    # --- True Positives: should detect as context request ---
    def test_chat_history(self):
        assert detect_context_request("show me my chat history") is True

    def test_summarize_my_symptoms(self):
        assert detect_context_request("can you summarize my symptoms?") is True

    def test_what_did_i_tell_you(self):
        assert detect_context_request("what did i tell you earlier?") is True

    def test_do_you_remember(self):
        assert detect_context_request("do you remember what I said?") is True

    def test_all_my_symptoms(self):
        assert detect_context_request("list all my symptoms") is True

    def test_from_chat(self):
        assert detect_context_request("what do you have from chat?") is True

    # --- True Negatives: should NOT detect as context request ---
    def test_symptom_with_before(self):
        """'before' alone should not trigger context detection."""
        assert detect_context_request("I had this pain before lunch") is False

    def test_tell_me_about_diabetes(self):
        """'tell me about' is a normal medical query, not context request."""
        assert detect_context_request("tell me about diabetes") is False

    def test_normal_symptom(self):
        assert detect_context_request("I have a headache and fever") is False

    def test_earlier_in_symptom(self):
        """'earlier' in a symptom context should not trigger."""
        assert detect_context_request("the pain started earlier today") is False

    def test_past_in_symptom(self):
        """'past' in a symptom context should not trigger."""
        assert detect_context_request("I've had this for the past week") is False

    def test_empty_input(self):
        assert detect_context_request("") is False

    def test_greeting(self):
        assert detect_context_request("hello there") is False


# ============================================================================
#  SYMPTOM EXTRACTION TESTS
# ============================================================================

class TestExtractSymptomsFromHistory:
    """Tests for the extract_symptoms_from_history function."""

    def test_extracts_single_symptom(self):
        messages = [
            {"role": "user", "content": "I have a bad headache"},
            {"role": "assistant", "content": "Let me help you with that."},
        ]
        result = extract_symptoms_from_history(messages)
        assert "Headache" in result

    def test_extracts_multiple_symptoms(self):
        messages = [
            {"role": "user", "content": "I have a headache"},
            {"role": "assistant", "content": "Tell me more."},
            {"role": "user", "content": "Also feeling nausea and fever"},
        ]
        result = extract_symptoms_from_history(messages)
        assert "Headache" in result
        assert "Nausea" in result
        assert "Fever" in result

    def test_no_symptoms_found(self):
        messages = [
            {"role": "user", "content": "hello"},
        ]
        result = extract_symptoms_from_history(messages)
        assert "No specific symptoms" in result

    def test_shorthand_head_maps_to_headache(self):
        """User typing 'head' should be captured as 'Headache'."""
        messages = [
            {"role": "user", "content": "head 2 day fever"},
        ]
        result = extract_symptoms_from_history(messages)
        assert "Headache" in result
        assert "Fever" in result

    def test_shorthand_stomach(self):
        messages = [
            {"role": "user", "content": "my stomach hurts"},
        ]
        result = extract_symptoms_from_history(messages)
        assert "Stomach Issues" in result

    def test_empty_messages(self):
        result = extract_symptoms_from_history([])
        assert "No specific symptoms" in result

    def test_compound_symptoms(self):
        messages = [
            {"role": "user", "content": "I have a sore throat and runny nose"},
        ]
        result = extract_symptoms_from_history(messages)
        assert "Sore Throat" in result

    def test_deduplication(self):
        """Repeated mentions of the same symptom should appear only once."""
        messages = [
            {"role": "user", "content": "I have pain"},
            {"role": "user", "content": "the pain is getting worse"},
            {"role": "user", "content": "pain pain pain"},
        ]
        result = extract_symptoms_from_history(messages)
        # "Pain" should appear exactly once in the symptom list line
        symptom_line = result.split("\n")[1]  # second line has the symptoms
        assert symptom_line.count("Pain") == 1

    def test_includes_raw_user_messages(self):
        """The output should include raw user messages for LLM context."""
        messages = [
            {"role": "user", "content": "head 3 days"},
        ]
        result = extract_symptoms_from_history(messages)
        assert "head 3 days" in result


# ============================================================================
#  COMPOUND EMERGENCY DETECTION TESTS
# ============================================================================

from src.app.symptom_accumulator import check_compound_emergency


class TestCompoundEmergencyDetection:
    """Tests for cross-turn compound red flag detection."""

    def test_cardiac_three_symptoms_across_turns(self):
        """Left arm + jaw + sweating across multiple turns = heart attack alert."""
        messages = [
            {"role": "user", "content": "My left arm feels a bit heavy today."},
            {"role": "assistant", "content": "Tell me more."},
            {"role": "user", "content": "Yeah, and my jaw has been aching for the last hour."},
            {"role": "assistant", "content": "I see."},
            {"role": "user", "content": "Also I'm sweating a lot, even though it's cold."},
        ]
        result = check_compound_emergency(messages)
        assert result is not None
        assert "Cardiac" in result["name"]

    def test_cardiac_single_symptom_no_alert(self):
        """A single symptom like arm heaviness should NOT trigger cardiac alert."""
        messages = [
            {"role": "user", "content": "My left arm feels heavy."},
        ]
        result = check_compound_emergency(messages)
        assert result is None

    def test_cardiac_two_symptoms_no_alert(self):
        """Two of three required groups should NOT trigger (min_match=3)."""
        messages = [
            {"role": "user", "content": "My left arm feels heavy."},
            {"role": "user", "content": "My jaw is aching."},
        ]
        result = check_compound_emergency(messages)
        assert result is None

    def test_stroke_detection(self):
        """Face drooping + arm weakness + speech slurring = stroke alert."""
        messages = [
            {"role": "user", "content": "My face feels droopy on one side."},
            {"role": "user", "content": "I can't lift my arm properly."},
            {"role": "user", "content": "My speech is slurring."},
        ]
        result = check_compound_emergency(messages)
        assert result is not None
        assert "Stroke" in result["name"]

    def test_no_alert_for_normal_symptoms(self):
        """Normal symptoms like headache and cough should not trigger alerts."""
        messages = [
            {"role": "user", "content": "I have a headache and a cough."},
            {"role": "user", "content": "Also some mild nausea."},
        ]
        result = check_compound_emergency(messages)
        assert result is None

    def test_empty_messages_no_alert(self):
        """Empty message list should return None."""
        result = check_compound_emergency([])
        assert result is None

    def test_cardiac_alert_has_call_to_action(self):
        """The alert should contain actionable emergency instructions."""
        messages = [
            {"role": "user", "content": "left arm heavy"},
            {"role": "user", "content": "jaw aching"},
            {"role": "user", "content": "sweating a lot"},
        ]
        result = check_compound_emergency(messages)
        assert result is not None
        assert "911" in result["call_to_action"] or "999" in result["call_to_action"]
        assert "EMERGENCY" in result["call_to_action"]

    def test_accumulator_file_exists(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        assert (repo_root / "src" / "app" / "symptom_accumulator.py").exists()


# ============================================================================
#  FILE EXISTENCE TESTS
# ============================================================================

class TestProjectStructure:
    """Basic smoke tests for project structure."""

    def test_app_file_exists(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        assert (repo_root / "src" / "app" / "app.py").exists()

    def test_config_file_exists(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        assert (repo_root / "src" / "app" / "config.py").exists()

    def test_vector_db_creator_exists(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        assert (repo_root / "src" / "vector_db" / "create_vector_db.py").exists()

    def test_requirements_exists(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        assert (repo_root / "requirements.txt").exists()

