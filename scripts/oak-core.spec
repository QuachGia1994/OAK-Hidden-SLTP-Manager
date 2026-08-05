# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for oak-core (Edit prompt.txt §10).

Build:
    venv\Scripts\pyinstaller.exe --noconfirm scripts\oak-core.spec

Produces dist/oak-core/ with oak-core-x86_64-pc-windows-msvc.exe (onedir),
named with the target triple so Tauri bundle.externalBin picks it up.
The worker imports repositories/ + services/ from the repo root, so those
package dirs are collected as data + hidden imports.
"""
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

REPO_ROOT = Path(SPECPATH).parent  # SPECPATH = scripts/ -> repo root

block_cipher = None

_mt5_datas, _mt5_binaries, _mt5_hidden = collect_all("MetaTrader5")

a = Analysis(
    [str(REPO_ROOT / "python" / "oak_core_launcher.py")],
    pathex=[str(REPO_ROOT / "python"), str(REPO_ROOT)],
    binaries=[] + _mt5_binaries,
    datas=[
        # Worker imports the repo-root packages (repositories/, services/).
        (str(REPO_ROOT / "repositories"), "repositories"),
        (str(REPO_ROOT / "services"), "services"),
        (str(REPO_ROOT / "domain"), "domain"),
        (str(REPO_ROOT / "secret_store.py"), "."),
        (str(REPO_ROOT / "oak_logger.py"), "."),
        (str(REPO_ROOT / "eod_collector"), "eod_collector"),
    ] + _mt5_datas,
    hiddenimports=[
        "repositories.trade_audit_store",
        "services.mt5_deal_reconciler",
        "services.checkpoint_engine",
        "services.equity_sampler",
        "services.performance_calculator",
        "services.audit_dashboard_publisher",
        "services.account_audit_service",
        "services.mt5_terminal_service",
        "eod_collector",
        "eod_collector.cli",
        "eod_collector.config",
        "eod_collector.database",
        "eod_collector.models",
        "eod_collector.normalizer",
        "eod_collector.repository",
        "eod_collector.validator",
        "eod_collector.services.collector",
        "eod_collector.sources.base",
        "eod_collector.sources.http_client",
        "eod_collector.sources.hose",
        "eod_collector.sources.hnx",
        "eod_collector.sources.upcom",
        "eod_collector.sources.vps_market",
    ] + _mt5_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6", "customtkinter", "tkinter", "PIL", "matplotlib",
        "pytest", "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onefile: externalBin needs a SINGLE executable (Tauri copies only the exe,
# not an _internal/ folder). All deps are embedded into one binary.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="oak-core-x86_64-pc-windows-msvc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,           # sidecar IPC qua JSONL stdin/stdout — BẮT BUỘC có console stdio (§3)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
