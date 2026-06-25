import zipfile
import os
import sys
import glob
import re

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def create_backup():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    version = "v3.0.0"
    try:
        with open("OAK_Hidden_SLTP_Manager.py", "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'VERSION\s*=\s*"(.*?)"', content)
            if match:
                version = match.group(1)
    except Exception as e:
        print(f"Warning: Could not read version: {e}")

    source_zip = f"OAK Source {version}.zip"
    source_files = [
        "OAK_Hidden_SLTP_Manager.py",
        "requirements.txt",
        "icon.ico",
        "CHAY_ROBOT.bat",
        "oak_trading_reminders.py",
        "signal_logic.py",
        "oakschedule.html",
        "oakschedule_en.html",
        "create_backup_final.py",
        "build_exe.py",
        "build_exe.bat",
        "oak_response_dict.py",
        "MT4_Data_Feeder.mq4",
    ]

    signal_files = [
        "mt5_signal_bot.py",
        "mt4_mt5_server.py",
        "mimo_bot.py",
        "mimo_worker.py",
        "CHAY_ALL.bat",
        "CHAY_SERVER.bat",
        "CHAY_MIMO_BOT.bat",
    ]

    doc_patterns = [
        "*README*", "*readme*", "*GUIDE*", "*guide*",
        "*note*.*", "*notes*.*"
    ]
    spec_files = glob.glob("*.spec")
    doc_files = []
    for pattern in doc_patterns:
        doc_files.extend(glob.glob(pattern))
    source_files = sorted(list(set(source_files + signal_files + doc_files + spec_files)))
    doc_files = set(doc_files)

    profile_zip = "OAK_Profile_Backup.zip"
    profile_files = [
        "profiles.json", "settings.json", "trades.json",
        "pending_partials.json", "manual_trends.json",
        "news_cache.json", "session_state.json"
    ]
    dynamic_patterns = [
        "tele_*.json", "copy_map_*.json",
        "waiting_*.json", "news_cache*.json"
    ]
    for pattern in dynamic_patterns:
        profile_files.extend(glob.glob(pattern))
    profile_files = sorted(list(set(profile_files)))

    try:
        for zip_name, files_to_include in [
            (source_zip, source_files),
            (profile_zip, profile_files),
        ]:
            print(f"--- Tao backup: {zip_name} ---")
            if os.path.exists(zip_name):
                os.remove(zip_name)
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in files_to_include:
                    if os.path.exists(file):
                        zipf.write(file)
                        print(f"  + {file}")
                    elif zip_name == source_zip and file not in doc_files:
                        print(f"  ! Khong tim thay: {file}")
            print(f"--- Hoan tat: {os.path.abspath(zip_name)} ---\n")
    except Exception as e:
        print(f"Loi: {e}")

if __name__ == "__main__":
    create_backup()
