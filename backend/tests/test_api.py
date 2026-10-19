import json

from fastapi.testclient import TestClient

from spotwise.main import app

client = TestClient(app)


def test_meta():
    r = client.get("/api/meta").json()
    assert "gold" in r["metals"] and "INR" in r["currencies"]
    assert r["attribution"] == "Prices by metals.dev"


def test_prices_spot_vs_taxed():
    spot = client.get("/api/prices?metal=gold&currency=INR").json()
    rules = json.dumps([{"effective_from": "2000-01-01", "duty_pct": 6, "gst_pct": 3}])
    taxed = client.get("/api/prices", params={"metal": "gold", "currency": "INR", "tax": rules}).json()
    assert len(spot["points"]) > 1000
    ratio = taxed["points"][100]["value"] / spot["points"][100]["value"]
    assert abs(ratio - 1.06 * 1.03) < 1e-3


def test_22k_is_cheaper_than_24k():
    a = client.get("/api/prices?purity=24k").json()["points"][10]["value"]
    b = client.get("/api/prices?purity=22k").json()["points"][10]["value"]
    assert abs(b / a - 0.916) < 1e-3


def test_unknown_currency_404():
    assert client.get("/api/prices?currency=ZZZ").status_code == 404


def test_position_endpoint():
    body = {"trades": [{"date": "2025-01-02", "side": "buy", "grams": 10, "price": 5000}]}
    r = client.post("/api/position", json=body).json()
    assert r["grams_held"] == 10 and r["cost_basis"] == 50000


def test_ask_end_to_end_without_model():
    r = client.post("/api/ask", json={"text": "gold 12000 a month last 3 years"}).json()
    assert r["explained_by"] == "template" and r["params"]["monthly_amount"] == 12000
    assert r["result"]["monthly"]["trades"] and r["result"]["dip"]["trades"]
