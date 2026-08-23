# -*- mode: python ; coding: utf-8 -*-
"""One-file Portway binary: GUI, Flask, TUI, and CLI."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

SPECDIR = Path(SPECPATH).resolve()
ROOT = SPECDIR.parent

datas = [(str(ROOT / "portway" / "web"), "portway/web")]
binaries = []
hiddenimports = [
    "portway",
    "portway.app",
    "portway.api",
    "portway.cli",
    "portway.discovery",
    "portway.paths",
    "portway.scanner",
    "portway.server",
    "portway.services",
    "portway.session",
    "portway.tokens",
    "portway.tui",
    "flask",
    "jinja2",
    "werkzeug",
    "rich",
    "textual",
    "webview",
]

for package in ("webview", "flask", "jinja2", "werkzeug", "textual", "rich"):
    collected_datas, collected_binaries, collected_hidden = collect_all(package)
    datas += collected_datas
    binaries += collected_binaries
    hiddenimports += collected_hidden

a = Analysis(
    [str(ROOT / "portway" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="portway",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
