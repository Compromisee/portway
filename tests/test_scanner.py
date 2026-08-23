from portway.scanner import parse_html_title, parse_http_headers
from portway.services import url_for


def test_parse_html_title_strips_whitespace():
    html = "<html><head><title>  Flask  \n App </title></head></html>"
    assert parse_html_title(html) == "Flask App"


def test_parse_http_headers():
    raw = "HTTP/1.0 200 OK\r\nServer: Werkzeug/3.0\r\nContent-Type: text/html\r\n"
    headers = parse_http_headers(raw)
    assert headers["server"] == "Werkzeug/3.0"
    assert headers["content-type"] == "text/html"


def test_openable_url_for_detected_scheme():
    assert url_for("100.88.12.9", 8096, "http") == "http://100.88.12.9:8096/"
