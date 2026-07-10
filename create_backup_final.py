# -*- coding: utf-8 -*-
"""Create OAK source + profile backup zips.

- OAK Source {VERSION}.zip  — code, docs, dashboard (no secrets / runtime state)
- OAK_Profile_Backup.zip    — local profiles, settings, caches, session state
"""
import glob
import os
import re
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure") and (sys.stdout.encoding or "").lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def read_version():
    version = "v3.16.0"
    for path in ("domain/constants.py", "OAK_Hidden_SLTP_Manager.py"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r'VERSION\s*=\s*"(.*?)"', content)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"Warning: Could not read version from {path}: {e}")
    return version


# Always pack these if present (root essentials)
ROOT_ALWAYS = {
    "OAK_Hidden_SLTP_Manager.py",
    "requirements.txt",
    "requirements-dev.txt",
    "icon.ico",
    "CHAY_ROBOT.bat",
    "oak_trading_reminders.py",
    "create_backup_final.py",
    "build_exe.py",
    "installer.nsi",
    "LICENSE.txt",
    "oak_response_dict.py",
    "MT4_Data_Feeder.mq4",
    "README.md",
    "GUIDE.md",
    "GUIDE.en.md",
    "RELEASE_NOTES.md",
    "RELEASE_NOTES.en.md",
    "README.en.md",
    "QUICKSTART.md",
    "profiles.example.json",
    "settings.example.json",
    ".gitignore",
    "AGENTS.md",
    "app.py",
    "mimo_bot.py",
    "mimo_worker.py",
    "mt4_mt5_server.py",
    "mt5_signal_bot.py",
    "factcheck_worker.py",
    "telegram_client.py",
    "secret_store.py",
    "oak_logger.py",
    "utils.py",
}

EXCLUDE_DIRS = {
    ".git",
    ".next",
    ".venv",
    ".vercel",
    "__pycache__",
    "build",
    "dist",
    "logs",
    "node_modules",
    "venv",
    "mcps",
    "sent_locks",
    ".agents",
    ".grok",
}

# Never put secrets / live state into SOURCE zip
EXCLUDE_FILES = {
    "Objective.txt",
    "build_exe.bat",
    "CHAY_ALL.bat",
    "CHAY_DASHBOARD.bat",
    "CHAY_MIMO_BOT.bat",
    "CHAY_SERVER.bat",
    "diff_details.txt",
    "diff_summary.txt",
    "recent_changes.diff",
    "test_run_output.txt",
    "fix_b87fe05.patch",
    "fix_round2.patch",
    "fix_round3.patch",
    "oak_state.db",
    "config.json",
    "profiles.json",
    "settings.json",
    "trades.json",
    "pending_partials.json",
    "manual_trends.json",
    "session_state.json",
    "bot_state.json",
    "signals_log.json",
    "OAK_Profile_Backup.zip",
}

EXCLUDE_SUFFIXES = (
    ".bak",
    ".pyc",
    ".pyo",
    ".log",
    ".lock",
    ".db",
    ".zip",
)

# Code trees to walk
INCLUDE_ROOTS = (
    "app.py",  # also via ROOT / glob; listed for clarity
    "controllers",
    "domain",
    "dashboard",
    "docs",
    "models",
    "repositories",
    "services",
    "tests",
    "ui",
)

# Profile / runtime state (user machine)
PROFILE_STATIC = [
    "profiles.json",
    "settings.json",
    "trades.json",
    "pending_partials.json",
    "manual_trends.json",
    "session_state.json",
    "bot_state.json",
    "signals_log.json",
    "config.json",
    "oak_state.db",
]

PROFILE_GLOBS = [
    "tele_*.json",
    "copy_map_*.json",
    "waiting_*.json",
    "scheduled_close_*.json",
    "scheduled_trades*.json",
    "pending_partials_*.json",
    "trades_*.json",
    "ignored_*.json",
    "news_cache*.json",
    "*_snapshot.json",
    "monday_snapshot.json",
    "tuesday_snapshot.json",
    "wednesday_snapshot.json",
    "thursday_snapshot.json",
    "friday_snapshot.json",
]


def _should_skip_file(name: str) -> bool:
    base = os.path.basename(name)
    if base.startswith(".env"):
        return True
    if base in EXCLUDE_FILES:
        return True
    if base.startswith("OAK Source ") and base.endswith(".zip"):
        return True
    if base.endswith(EXCLUDE_SUFFIXES):
        return True
    if ".bak_" in base or base.endswith(".bak"):
        return True
    return False


def _norm(path: str) -> str:
    """Stable relative path for zip members (forward slashes, no dupes on Windows)."""
    return os.path.normpath(path).replace("\\", "/")


def collect_source_files():
    files = set()

    for path in ROOT_ALWAYS:
        files.add(_norm(path))

    # All root-level .py (bots, helpers, ad-hoc tests next to app)
    for path in glob.glob("*.py"):
        if not _should_skip_file(path):
            files.add(_norm(path))

    for path in glob.glob("*.md"):
        if not _should_skip_file(path):
            files.add(_norm(path))

    for base in INCLUDE_ROOTS:
        if os.path.isfile(base):
            if not _should_skip_file(base):
                files.add(_norm(base))
            continue
        if not os.path.isdir(base):
            continue
        for root, dirs, names in os.walk(base):
            dirs[:] = [
                d for d in dirs
                if d not in EXCLUDE_DIRS and not d.startswith(".")
            ]
            for f in names:
                rel = _norm(os.path.join(root, f))
                if _should_skip_file(f) or _should_skip_file(rel):
                    continue
                files.add(rel)

    # Only keep paths that exist (or keep missing essentials for warning)
    existing = []
    missing = []
    for p in sorted(files):
        # exists() accepts both separators
        if os.path.exists(p) or os.path.exists(p.replace("/", os.sep)):
            existing.append(p)
        else:
            missing.append(p)
    return existing, missing


def collect_profile_files():
    files = list(PROFILE_STATIC)
    for pattern in PROFILE_GLOBS:
        files.extend(glob.glob(pattern))
    # de-dupe, only existing
    out = []
    seen = set()
    for p in sorted(files):
        p = _norm(p)
        if p in seen:
            continue
        seen.add(p)
        disk = p.replace("/", os.sep)
        if os.path.exists(disk):
            out.append(p)
    return out


def _zip_write(zip_name: str, files_to_include, warn_missing=False):
    print(f"--- Tao backup: {zip_name} ---")
    if os.path.exists(zip_name):
        os.remove(zip_name)
    count = 0
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in files_to_include:
            disk = file.replace("/", os.sep)
            arc = _norm(file)
            if os.path.exists(disk):
                zipf.write(disk, arcname=arc)
                print(f"  + {arc}")
                count += 1
            elif warn_missing:
                print(f"  ! Khong tim thay: {arc}")
    size_mb = os.path.getsize(zip_name) / (1024 * 1024)
    print(f"--- Hoan tat: {os.path.abspath(zip_name)} ({count} files, {size_mb:.2f} MB) ---\n")
    return count


def create_backup():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    version = read_version()
    source_zip = f"OAK Source {version}.zip"
    profile_zip = "OAK_Profile_Backup.zip"

    source_files, missing_essentials = collect_source_files()
    profile_files = collect_profile_files()

    try:
        _zip_write(source_zip, source_files, warn_missing=False)
        if missing_essentials:
            print("Thieu (khong co tren disk, bo qua):")
            for m in missing_essentials:
                print(f"  ! {m}")
            print()

        _zip_write(profile_zip, profile_files, warn_missing=False)
        if not profile_files:
            print("(Profile backup rong — chua co profiles.json / settings tren may nay)\n")

        print(f"Version: {version}")
        print(f"Source files: {len(source_files)}")
        print(f"Profile files: {len(profile_files)}")
    except Exception as e:
        print(f"Loi: {e}")
        raise


if __name__ == "__main__":
    create_backup()
