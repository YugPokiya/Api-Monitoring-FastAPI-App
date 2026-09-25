import pytest

from New1 import monitoring


@pytest.fixture(autouse=True)
def reset_monitoring_state():
    with monitoring._lock:
        monitoring._requests.clear()
        monitoring._latencies.clear()
        monitoring._events.clear()
        monitoring._rate_limit.clear()
    yield

