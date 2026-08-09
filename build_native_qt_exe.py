# -*- coding: utf-8 -*-
"""Build the lightweight Native Qt shell package."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import zipfile


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "OAK MANAGER NativeQt"
ICON_PATH = os.path.join(PROJECT_ROOT, "icon.ico")
BUILD_ROOT = os.path.join(PROJECT_ROOT, "build", "native-qt")
DIST_ROOT = os.path.join(PROJECT_ROOT, "dist", "native-qt")
EXTRA_PACKAGE_FILES = (
    "LICENSE.txt",
    "THIRD_PARTY_NOTICES.md",
    "DESIGN.md",
    "profiles.example.json",
    "settings.example.json",
    "README.en.md",
    "README.md",
    "GUIDE.en.md",
    "GUIDE.md",
    "RELEASE_NOTES.en.md",
    "RELEASE_NOTES.md",
    "signal_rule_contract.json",
)
HIDDEN_IMPORTS = (
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "shiboken6",
    "utils",
    "oak_logger",
    "oak_trading_reminders",
    "secret_store",
    "telegram_client",
    "domain.monitor_worker",
    "mt5_signal_bot",
    "services.mt5_terminal_service",
    "mimo_bot",
    "mimo_worker",
    "factcheck_worker",
    "repositories.sqlite_store",
    "domain.stock_scanner",
    "services.ssi_market_data",
    "services.stock_advisor_desktop",
    "services.stock_dashboard_publisher",
    "vn_stock_advisor",
    "ssi_sdk",
)
EXCLUDED_MODULES = (
    "customtkinter",
    "pywinauto",
    "Pythonwin",
    "PySide6.Qt3DCore",
    "PySide6.QtDesigner",
    "PySide6.QtMultimedia",
    "PySide6.QtPdf",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
)


def read_version() -> str:
    """Read app version from the source constants."""
    for name in ("domain/constants.py", "OAK_Hidden_SLTP_Manager.py"):
        path = os.path.join(PROJECT_ROOT, name)
        try:
            content = open(path, "r", encoding="utf-8").read()
        except OSError:
            continue
        match = re.search(r'VERSION\s*=\s*"(.*?)"', content)
        if match:
            return match.group(1)
    return "v3.17.0"


VERSION = read_version()
PACKAGE_DIR_NAME = f"{APP_NAME}_{VERSION}"
PACKAGE_DIR = os.path.join(DIST_ROOT, PACKAGE_DIR_NAME)
PACKAGE_ZIP = os.path.join(DIST_ROOT, f"{PACKAGE_DIR_NAME}_window-unpack.zip")
INSTALLER_SCRIPT = os.path.join(PROJECT_ROOT, "installer_native_qt.nsi")
INSTALLER_EXE = os.path.join(PROJECT_ROOT, "dist", f"{APP_NAME}_{VERSION}_Installer.exe")


def build_args() -> list[str]:
    """Return PyInstaller CLI arguments for the Native Qt shell."""
    args = [
        os.path.join(PROJECT_ROOT, "oak_qt_shell.py"),
        f"--name={PACKAGE_DIR_NAME}",
        "--onedir",
        "--windowed",
        "--clean",
        "--noconfirm",
        f"--icon={ICON_PATH}",
        f"--add-data={ICON_PATH};.",
        f"--add-data={os.path.join(PROJECT_ROOT, 'signal_rule_contract.json')};.",
        f"--distpath={DIST_ROOT}",
        f"--workpath={BUILD_ROOT}",
        f"--specpath={BUILD_ROOT}",
        "--collect-all=MetaTrader5",
        "--collect-all=ssi_sdk",
    ]
    for module in HIDDEN_IMPORTS:
        args.append(f"--hidden-import={module}")
    for module in EXCLUDED_MODULES:
        args.append(f"--exclude-module={module}")
    if os.path.exists(os.path.join(PROJECT_ROOT, "upx")):
        args.append("--upx-dir=upx")
    return args


def copy_extra_files() -> None:
    """Copy docs and example config into the package folder."""
    for name in EXTRA_PACKAGE_FILES:
        src = os.path.join(PROJECT_ROOT, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(PACKAGE_DIR, name))


def zip_package() -> None:
    """Zip the Native Qt onedir package."""
    if os.path.exists(PACKAGE_ZIP):
        os.remove(PACKAGE_ZIP)
    with zipfile.ZipFile(PACKAGE_ZIP, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(PACKAGE_DIR):
            for file_name in files:
                full_path = os.path.join(root, file_name)
                arcname = os.path.relpath(full_path, DIST_ROOT)
                zip_file.write(full_path, arcname)


def folder_size_mb(path: str) -> float:
    """Return file or recursive folder size in MB."""
    if os.path.isfile(path):
        return round(os.path.getsize(path) / 1024 / 1024, 1)
    total = 0
    for root, _, files in os.walk(path):
        total += sum(os.path.getsize(os.path.join(root, name)) for name in files)
    return round(total / 1024 / 1024, 1)


def find_makensis() -> str:
    """Return the NSIS compiler path when installed."""
    candidates = (
        shutil.which("makensis"),
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
    )
    return next((item for item in candidates if item and os.path.exists(item)), "")


def build_installer() -> None:
    """Build a separate NativeQt installer when NSIS is available."""
    makensis = find_makensis()
    if not makensis:
        print("NSIS not found. Skipping NativeQt installer build.")
        return
    command = [
        makensis,
        f"/DVERSION={VERSION}",
        f"/DPACKAGE_DIR_NAME={PACKAGE_DIR_NAME}",
        f"/DAPP_EXE_NAME={PACKAGE_DIR_NAME}.exe",
        INSTALLER_SCRIPT,
    ]
    subprocess.check_call(command, cwd=PROJECT_ROOT)
    print(f"NativeQt installer: {folder_size_mb(INSTALLER_EXE)} MB")


def main() -> None:
    """Build Native Qt shell and print package sizes."""
    import PyInstaller.__main__

    if os.path.exists(PACKAGE_DIR):
        shutil.rmtree(PACKAGE_DIR)
    os.makedirs(DIST_ROOT, exist_ok=True)
    PyInstaller.__main__.run(build_args())
    copy_extra_files()
    zip_package()
    build_installer()
    print(f"NativeQt folder: {folder_size_mb(PACKAGE_DIR)} MB")
    print(f"NativeQt zip: {folder_size_mb(PACKAGE_ZIP)} MB")
    print(f"Created: {PACKAGE_ZIP}")


if __name__ == "__main__":
    main()
