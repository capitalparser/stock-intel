from pathlib import Path

from fastapi.testclient import TestClient

from alert_server import app


FIXTURES = Path(__file__).parent / "fixtures"


class FakePipeline:
    def __init__(self):
        self.payloads = []

    async def handle_payload(self, payload):
        self.payloads.append(payload)


def test_tradingview_webhook_rejects_invalid_secret(monkeypatch):
    monkeypatch.setattr("alert_server._WEBHOOK_SECRET", "secret")
    client = TestClient(app)
    payload = (FIXTURES / "tradingview_v6_2_buy_aapl.json").read_text()
    response = client.post(
        "/webhook/tradingview?secret=wrong",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_tradingview_webhook_rejects_invalid_payload(monkeypatch):
    monkeypatch.setattr("alert_server._WEBHOOK_SECRET", "secret")
    client = TestClient(app)
    response = client.post("/webhook/tradingview?secret=secret", json={"ticker": "AAPL"})
    assert response.status_code == 422


def test_tradingview_webhook_accepts_valid_payload(monkeypatch):
    monkeypatch.setattr("alert_server._WEBHOOK_SECRET", "secret")
    fake = FakePipeline()
    app.state.signal_pipeline = fake
    client = TestClient(app)
    payload = (FIXTURES / "tradingview_v6_2_buy_aapl.json").read_text()

    response = client.post(
        "/webhook/tradingview?secret=secret",
        content=payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"received": True, "ticker": "AAPL"}

