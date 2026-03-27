from app.domain.state_machine import EncounterStateMachine


def test_user_and_auto_share_same_state_machine_path():
    machine = EncounterStateMachine()
    s = machine.start()
    s = machine.transition(s, 'triaged')
    s = machine.transition(s, 'doctor_assessed')
    s = machine.transition(s, 'test_ordered')
    s = machine.transition(s, 'result_received')
    s = machine.transition(s, 'disposition_discharge')
    assert s == 'discharged'
