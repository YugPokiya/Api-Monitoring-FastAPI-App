from fastapi.testclient import TestClient

from New1 import monitoring


client = TestClient(monitoring.app)


def test_conftest_resets_monitoring_state_before_each_test():
    assert not monitoring._requests
    assert not monitoring._latencies
    assert not monitoring._events
    assert not monitoring._rate_limit


def test_health_endpoint_returns_healthy_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "Sample FastAPI"


def test_sample_endpoints_return_expected_data():
    assert client.get("/users").json()["users"][0]["name"] == "Avery Chen"
    assert client.get("/products").json()["products"][0]["price"] == 79.99


def test_simulated_error_is_recorded_in_monitoring_summary():
    response = client.get("/simulate-error")
    summary = client.get("/api/monitoring/summary").json()

    assert response.status_code == 500
    assert summary["server_errors"] == 1
    assert summary["events"][-1]["route"] == "/simulate-error"
    assert "Intentional server failure" in summary["events"][-1]["cause"]
    assert any(alert["title"] == "API server error" for alert in summary["alerts"])


def test_invalid_authentication_is_identified_and_alerted():
    response = client.get("/simulate-auth")
    summary = client.get("/api/monitoring/summary").json()

    assert response.status_code == 401
    assert summary["events"][-1]["event_type"] == "authentication_error"
    assert any(alert["title"] == "API authentication failure" for alert in summary["alerts"])


def test_timeout_is_identified_and_alerted(monkeypatch):
    monkeypatch.setattr(monitoring, "ALERT_LATENCY_MS", 1)
    response = client.get("/simulate-timeout?delay=0.01")
    summary = client.get("/api/monitoring/summary").json()

    assert response.status_code == 504
    assert summary["events"][-1]["event_type"] == "timeout"
    assert any(alert["title"] == "API request timeout" for alert in summary["alerts"])


def test_rate_limit_allows_five_requests_then_returns_429():
    responses = [client.get("/simulate-rate-limit") for _ in range(6)]

    assert [response.status_code for response in responses] == [200] * 5 + [429]
    assert responses[-1].json()["error"] == "TooManyRequests"
    summary = client.get("/api/monitoring/summary").json()
    assert summary["events"][-1]["event_type"] == "rate_limit"
    assert any(alert["title"] == "API rate limit exceeded" for alert in summary["alerts"])


def test_metrics_endpoint_exposes_request_counter():
    client.get("/health")

    response = client.get("/metrics")
    metric_line = next(
        line for line in response.text.splitlines()
        if line.startswith('api_http_requests_total{method="GET",path="/health",status="200"}')
    )

    assert response.status_code == 200
    assert float(metric_line.rsplit(" ", 1)[1]) >= 1
