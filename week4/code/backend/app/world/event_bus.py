class EventBus:
    def __init__(self):
        self._events = []

    def emit(self, event_type: str, payload: dict):
        self._events.append({'type': event_type, 'payload': payload})

    def read_all(self):
        return self._events
