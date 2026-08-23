from pathlib import Path

from portway.server import create_app
from portway.tokens import TokenStore


def test_health_and_token_roundtrip(tmp_path: Path):
    store = TokenStore(tmp_path / "tokens.json")
    app = create_app(store)
    client = app.test_client()
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json()["ok"] is True

    saved = client.post(
        "/api/tokens",
        json={"target": "127.0.0.1:8888", "token": "notebook-secret"},
    )
    assert saved.status_code == 200
    listed = client.get("/api/tokens").get_json()["tokens"]
    assert listed[0]["target"] == "127.0.0.1:8888"
    assert listed[0]["has_token"] is True
    assert "notebook-secret" not in listed[0]["token"]

    deleted = client.delete("/api/tokens/127.0.0.1:8888")
    assert deleted.get_json()["ok"] is True


def test_open_protected_needs_token(tmp_path: Path, monkeypatch):
    store = TokenStore(tmp_path / "tokens.json")
    app = create_app(store)
    client = app.test_client()
    monkeypatch.setattr("portway.session.webbrowser.open", lambda _url: True)
    missing = client.post("/api/open", json={"host": "127.0.0.1", "port": 8888, "scheme": "http"})
    body = missing.get_json()
    assert body["needs_token"] is True

    opened = client.post(
        "/api/open",
        json={"host": "127.0.0.1", "port": 8888, "scheme": "http", "token": "abc"},
    )
    assert opened.get_json()["ok"] is True
    assert "token=abc" in opened.get_json()["url"]
