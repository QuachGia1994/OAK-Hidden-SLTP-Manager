import os
import re
import shutil
import subprocess
import zipfile

import PyInstaller.__main__
import customtkinter


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "OAK MANAGER"
ICON_PATH = "icon.ico"
BUILD_ROOT = os.path.join(PROJECT_ROOT, "build")
DIST_ROOT = os.path.join(PROJECT_ROOT, "dist")
WINDOW_UNPACK_ROOT = os.path.join(DIST_ROOT, "window-unpack")
EXTRA_PACKAGE_FILES = [
    "LICENSE.txt",
    "profiles.example.json",
    "settings.example.json",
    "README.md",
    "README.en.md",
    "GUIDE.md",
    "GUIDE.en.md",
    "RELEASE_NOTES.md",
    "RELEASE_NOTES.en.md",
]


def read_version():
    version = "v3.15.0"
    main_file = os.path.join(PROJECT_ROOT, "OAK_Hidden_SLTP_Manager.py")
    try:
        with open(main_file, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'VERSION\s*=\s*"(.*?)"', content)
        if match:
            version = match.group(1)
    except Exception as e:
        print(f"Warning: Could not read version from file: {e}")
    return version


VERSION = read_version()
PACKAGE_DIR_NAME = f"{APP_NAME}_{VERSION}"
APP_EXE_NAME = f"{PACKAGE_DIR_NAME}.exe"
PACKAGE_DIR = os.path.join(WINDOW_UNPACK_ROOT, PACKAGE_DIR_NAME)
WINDOW_UNPACK_ZIP = os.path.join(DIST_ROOT, f"{PACKAGE_DIR_NAME}_window-unpack.zip")


def build_args():
    ctk_path = os.path.dirname(customtkinter.__file__)
    icon_file = os.path.join(PROJECT_ROOT, ICON_PATH)
    response_dict_file = os.path.join(PROJECT_ROOT, "oak_response_dict.py")
    main_script = os.path.join(PROJECT_ROOT, "OAK_Hidden_SLTP_Manager.py")
    args = [
        main_script,
        f"--name={PACKAGE_DIR_NAME}",
        "--onedir",
        "--windowed",
        f"--icon={icon_file}",
        f"--add-data={icon_file};.",
        f"--add-data={response_dict_file};.",
        f"--add-data={ctk_path};customtkinter/",
        f"--distpath={WINDOW_UNPACK_ROOT}",
        f"--workpath={os.path.join(BUILD_ROOT, 'pyinstaller')}",
        f"--specpath={os.path.join(BUILD_ROOT, 'spec')}",
        "--clean",
        "--noconfirm",
        "--hidden-import=numpy",
        "--hidden-import=numpy.core",
        "--hidden-import=numpy.core.multiarray",
        "--hidden-import=numpy.core.numerictypes",
        "--hidden-import=numpy.core.umath",
        "--hidden-import=numpy.core.defchararray",
        "--hidden-import=numpy.lib",
        "--hidden-import=numpy.lib._version",
        "--hidden-import=numpy.lib.arraysetops",
        "--hidden-import=numpy.lib.function_base",
        "--hidden-import=numpy.lib.index_tricks",
        "--hidden-import=numpy.lib.shape_base",
        "--hidden-import=numpy.lib.stride_tricks",
        "--hidden-import=numpy.lib.type_check",
        "--hidden-import=numpy.lib.ufunclike",
        "--hidden-import=numpy.lib.utils",
        "--hidden-import=numpy.ma",
        "--hidden-import=numpy.ma.core",
        "--hidden-import=numpy.ma.extras",
        "--collect-all=MetaTrader5",
        "--hidden-import=secret_store",
        "--hidden-import=oak_logger",
        "--hidden-import=oak_response_dict",
        "--hidden-import=oak_trading_reminders",
        "--hidden-import=utils",
        "--hidden-import=mt5_signal_bot",
        "--hidden-import=app",
        "--hidden-import=domain",
        "--hidden-import=domain.constants",
        "--hidden-import=domain.i18n",
        "--hidden-import=domain.copy_trade_manager",
        "--hidden-import=domain.monitor_worker",
        "--hidden-import=domain.ticket_manager",
        "--hidden-import=controllers",
        "--hidden-import=controllers.runtime",
        "--hidden-import=repositories.sqlite_store",
        "--hidden-import=services.auto_update",
        "--hidden-import=services.error_reporter",
        "--hidden-import=packaging",
        "--hidden-import=packaging.version",
    ]
    if os.path.exists(os.path.join(PROJECT_ROOT, "upx")):
        args.append("--upx-dir=upx")
        print("UPX: ON")
    else:
        print("UPX: OFF")
    return args


def copy_extra_files():
    for name in EXTRA_PACKAGE_FILES:
        src = os.path.join(PROJECT_ROOT, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(PACKAGE_DIR, name))


def zip_window_unpack():
    if os.path.exists(WINDOW_UNPACK_ZIP):
        os.remove(WINDOW_UNPACK_ZIP)
    with zipfile.ZipFile(WINDOW_UNPACK_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(PACKAGE_DIR):
            for file_name in files:
                full_path = os.path.join(root, file_name)
                arcname = os.path.relpath(full_path, WINDOW_UNPACK_ROOT)
                zipf.write(full_path, arcname)
    print(f"Created: {WINDOW_UNPACK_ZIP}")


def find_makensis():
    candidates = [
        shutil.which("makensis"),
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


def build_installer():
    makensis = find_makensis()
    if not makensis:
        print("NSIS not found. Skipping installer build.")
        return
    installer_script = os.path.join(PROJECT_ROOT, "installer.nsi")
    command = [
        makensis,
        f"/DVERSION={VERSION}",
        f"/DPACKAGE_DIR_NAME={PACKAGE_DIR_NAME}",
        f"/DAPP_EXE_NAME={APP_EXE_NAME}",
        installer_script,
    ]
    print("Building installer...")
    subprocess.check_call(command, cwd=PROJECT_ROOT)


def main():
    if os.path.exists(PACKAGE_DIR):
        shutil.rmtree(PACKAGE_DIR)
    os.makedirs(WINDOW_UNPACK_ROOT, exist_ok=True)

    print(f"Building window-unpack package for {PACKAGE_DIR_NAME}...")
    PyInstaller.__main__.run(build_args())
    copy_extra_files()
    zip_window_unpack()
    build_installer()
    print(f"Done. Outputs are in: {DIST_ROOT}")


if __name__ == "__main__":
    main()
