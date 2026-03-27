from app.world.event_bus import EventBus
from app.tools.actions import order_test


def test_order_test_emits_event():
    bus = EventBus()
    order_test(bus, patient_id='p1', test_type='ct')
    events = bus.read_all()
    assert events[-1]['type'] == 'test_ordered'
    assert events[-1]['payload']['test_type'] == 'ct'
