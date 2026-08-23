from portway.services import hint_for, parse_port_list, ports_for_profile, url_for


def test_flask_port_is_openable():
    hint = hint_for(5000)
    assert hint.key == "flask"
    assert hint.scheme == "http"
    assert url_for("127.0.0.1", 5000) == "http://127.0.0.1:5000/"


def test_https_omits_default_port():
    assert url_for("home.tailnet.ts.net", 443, "https") == "https://home.tailnet.ts.net/"


def test_ssh_has_no_url():
    assert url_for("192.168.1.10", 22) is None


def test_unknown_http_detected():
    hint = hint_for(12345, http_detected=True)
    assert hint.scheme == "http"
    assert hint.group == "web"


def test_parse_port_list_ranges():
    assert parse_port_list("80, 443, 8000-8002") == [80, 443, 8000, 8001, 8002]


def test_parse_port_list_rejects_out_of_range():
    try:
        parse_port_list("70000")
    except ValueError as exc:
        assert "65535" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_profiles_exist():
    assert 5000 in ports_for_profile("developer")
    assert 22 in ports_for_profile("quick")
    assert len(ports_for_profile("deep")) == 65535
