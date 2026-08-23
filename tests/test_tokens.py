from pathlib import Path

from portway.tokens import (
    TokenStore,
    apply_token_to_url,
    looks_protected,
    mask_secret,
    normalize_target,
)


def test_normalize_and_lookup(tmp_path: Path):
    store = TokenStore(tmp_path / "tokens.json")
    store.upsert("127.0.0.1:8888", "abc123secret", style="query")
    rec = store.get("127.0.0.1", 8888)
    assert rec is not None
    assert rec.token == "abc123secret"
    assert store.get("127.0.0.1") is None


def test_ip_level_token_applies_to_ports(tmp_path: Path):
    store = TokenStore(tmp_path / "tokens.json")
    store.upsert("10.0.0.9", "host-token")
    assert store.get("10.0.0.9", 5000).token == "host-token"


def test_apply_query_token():
    from portway.tokens import AccessToken

    rec = AccessToken(target="127.0.0.1:8888", token="s3cret", style="query")
    url = apply_token_to_url("http://127.0.0.1:8888/", rec)
    assert url == "http://127.0.0.1:8888/?token=s3cret"


def test_jupyter_is_protected():
    assert looks_protected(8888, "jupyter")
    assert looks_protected(80, "http", {"status": 401})
    assert not looks_protected(5000, "flask", {"status": 200})


def test_mask_and_normalize():
    assert "*" in mask_secret("supersecret")
    assert normalize_target("192.168.1.4:80") == "192.168.1.4:80"
