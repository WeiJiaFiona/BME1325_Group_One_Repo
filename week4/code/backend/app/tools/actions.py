from app.world.event_bus import EventBus


def order_test(bus: EventBus, patient_id: str, test_type: str):
    bus.emit('test_ordered', {'patient_id': patient_id, 'test_type': test_type})
