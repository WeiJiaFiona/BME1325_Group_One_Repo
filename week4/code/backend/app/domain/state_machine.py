class EncounterStateMachine:
    _graph = {
        'arrival': {'triaged': 'zone_routed'},
        'zone_routed': {'doctor_assessed': 'assessment_done'},
        'assessment_done': {
            'test_ordered': 'waiting_result',
            'disposition_discharge': 'discharged',
        },
        'waiting_result': {'result_received': 'assessment_done'},
    }

    def start(self) -> str:
        return 'arrival'

    def transition(self, state: str, event: str) -> str:
        if state not in self._graph or event not in self._graph[state]:
            raise ValueError(f'invalid transition: {state} + {event}')
        return self._graph[state][event]
