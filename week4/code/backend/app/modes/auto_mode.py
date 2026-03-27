import random
from app.world.event_bus import EventBus


def run_auto_tick(seed: int = 0) -> dict:
    random.seed(seed)
    bus = EventBus()
    generated = random.randint(1, 3)
    for i in range(generated):
        bus.emit('patient_arrival', {'patient_id': f'auto_{i}'})
    return {'generated_patients': generated, 'events_emitted': len(bus.read_all())}
