import zipfile
import os
import sys
import glob
import re

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def read_version():
    version = "v3.15.2"
    try:
        with open("OAK_Hidden_SLTP_Manager.py", "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'VERSION\s*=\s*"(.*?)"', content)
        if match:
            version = match.group(1)
    except Exception as e:
        print(f"Warning: Could not read version: {e}")
    return version


def create_backup():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    version = read_version()
    source_zip = f"OAK Source {version}.zip"

    source_files = {
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
        "RELEASE_NOTES.md",
        "QUICKSTART.md",
        "profiles.example.json",
        "settings.example.json",
        ".gitignore",
        "AGENTS.md",
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

    exclude_dirs = {
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
    }
    exclude_files = {
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
    }
    exclude_suffixes = (
        ".bak",
        ".pyc",
        ".pyo",
        ".log",
        ".lock",
    )

    include_roots = [
        "dashboard",
        "docs",
        "models",
        "repositories",
        "services",
        "tests",
        "ui",
    ]
    for base in include_roots:
        if not os.path.exists(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            for f in files:
                if f.startswith(".env") or f in exclude_files:
                    continue
                if f.endswith(exclude_suffixes):
                    continue
                if f.endswith(".bak") or ".bak_" in f:
                    continue
                source_files.add(os.path.join(root, f))

    # Root-level docs helpers
    for name in ("docs/installation.md", "docs/getting_started.md", "docs/usage.md"):
        if os.path.exists(name):
            source_files.add(name)

    source_files = sorted(source_files)

    profile_zip = "OAK_Profile_Backup.zip"
    profile_files = [
        "profiles.json",
        "settings.json",
        "trades.json",
        "pending_partials.json",
        "manual_trends.json",
        "news_cache.json",
        "session_state.json",
        "bot_state.json",
        "signals_log.json",
    ]
    dynamic_patterns = [
        "tele_*.json",
        "copy_map_*.json",
        "waiting_*.json",
        "scheduled_close_*.json",
        "news_cache*.json",
        "friday_snapshot.json",
    ]
    for pattern in dynamic_patterns:
        profile_files.extend(glob.glob(pattern))
    profile_files = sorted(set(profile_files))

    try:
        for zip_name, files_to_include in (
            (source_zip, source_files),
            (profile_zip, profile_files),
        ):
            print(f"--- Tao backup: {zip_name} ---")
            if os.path.exists(zip_name):
                os.remove(zip_name)
            with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file in files_to_include:
                    if os.path.exists(file):
                        zipf.write(file)
                        print(f"  + {file}")
                    elif zip_name == source_zip:
                        print(f"  ! Khong tim thay: {file}")
            print(f"--- Hoan tat: {os.path.abspath(zip_name)} ---\n")
        print(f"Version: {version}")
    except Exception as e:
        print(f"Loi: {e}")
        raise


if __name__ == "__main__":
    create_backup()
