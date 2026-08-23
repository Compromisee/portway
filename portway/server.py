"""Flask API and static GUI server."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from portway import __version__
from portway.paths import web_dir
from portway.session import ScanSession
from portway.tokens import TokenStore, normalize_target

SESSION = ScanSession()


def _web_dir() -> Path:
    return web_dir()


def create_app(store: TokenStore | None = None) -> Flask:
    session = ScanSession(store) if store is not None else SESSION
    web = _web_dir()
    app = Flask(__name__, static_folder=None)
    app.config["SESSION"] = session

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "version": __version__, "name": "portway"})

    @app.get("/api/snapshot")
    def snapshot():
        kinds = request.args.getlist("networks") or None
        data = session.refresh(kinds)
        return jsonify(data)

    @app.post("/api/scan/start")
    def scan_start():
        payload = request.get_json(silent=True) or {}
        return jsonify(session.start(payload))

    @app.post("/api/scan/cancel")
    def scan_cancel():
        return jsonify(session.cancel())

    @app.get("/api/scan/status")
    def scan_status():
        return jsonify(session.status())

    @app.post("/api/open")
    def open_service():
        payload = request.get_json(silent=True) or {}
        host = payload.get("host")
        port = payload.get("port")
        if not host or port is None:
            return jsonify({"ok": False, "error": "host and port are required"}), 400
        result = session.open_service(
            host=str(host),
            port=int(port),
            scheme=payload.get("scheme"),
            token=payload.get("token"),
            style=payload.get("style") or "query",
            query_key=payload.get("query_key") or "token",
            save=bool(payload.get("save", True)),
        )
        return jsonify(result)

    @app.get("/api/tokens")
    def list_tokens():
        return jsonify({"tokens": [item.to_public_dict() for item in session.store.list()]})

    @app.post("/api/tokens")
    def save_token():
        payload = request.get_json(silent=True) or {}
        try:
            record = session.store.upsert(
                target=str(payload.get("target") or ""),
                token=str(payload.get("token") or ""),
                style=str(payload.get("style") or "query"),
                query_key=str(payload.get("query_key") or "token"),
                note=str(payload.get("note") or ""),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "token": record.to_public_dict()})

    @app.delete("/api/tokens/<path:target>")
    def delete_token(target: str):
        try:
            key = normalize_target(target)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        removed = session.store.delete(key)
        return jsonify({"ok": removed, "target": key})

    @app.get("/")
    def index():
        index_path = web / "index.html"
        if not index_path.exists():
            return jsonify({"ok": False, "error": "GUI not built. Run npm run build in gui/"}), 503
        return send_from_directory(web, "index.html")

    @app.get("/<path:asset>")
    def assets(asset: str):
        target = web / asset
        if target.is_file():
            return send_from_directory(web, asset)
        index_path = web / "index.html"
        if index_path.exists() and not asset.startswith("api/"):
            return send_from_directory(web, "index.html")
        return jsonify({"ok": False, "error": "not found"}), 404

    return app


def run_server(host: str = "0.0.0.0", port: int = 5050, debug: bool = False) -> None:
    app = create_app()
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)


def main() -> int:
    host = os.environ.get("PORTWAY_HOST", "0.0.0.0")
    port = int(os.environ.get("PORTWAY_PORT", "5050"))
    run_server(host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
