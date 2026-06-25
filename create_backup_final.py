import zipfile
import os
import sys
import glob
import re

# Force UTF-8 encoding for output to handle emojis on Windows
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
        print(f"Warning: Could not read version from file: {e}")

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
        "oak_response_dict.py"
    ]

    doc_patterns = [
        "*huong_dan*.*",
        "*huongdan*.*",
        "*README*",
        "*readme*",
        "*GUIDE*",
        "*guide*",
        "*note*.*",
        "*notes*.*"
    ]
    spec_files = glob.glob("*.spec")
    doc_files = []
    for pattern in doc_patterns:
        doc_files.extend(glob.glob(pattern))
    source_files = sorted(list(set(source_files + doc_files + spec_files)))
    doc_files = set(doc_files)

    profile_zip = "OAK_Profile_Backup.zip"
    profile_files = [
        "profiles.json",
        "settings.json",
        "trades.json",
        "pending_partials.json",
        "manual_trends.json",
        "news_cache.json",
        "session_state.json"
    ]
    
    # Add dynamic files (Tele logs, Copy maps, Waiting lists, Snapshots)
    # This ensures we capture all profile-specific files without hardcoding names
    dynamic_patterns = [
        "tele_*.json",       # tele_inbox, tele_offset, tele_sent_log, etc.
        "copy_map_*.json",   # copy_map_Darwinex.json, etc.
        "waiting_*.json",    # waiting_Darwinex.json, etc.
        "news_cache*.json"
    ]
    
    for pattern in dynamic_patterns:
        found = glob.glob(pattern)
        profile_files.extend(found)
    
    # Deduplicate list
    profile_files = sorted(list(set(profile_files)))
    
    try:
        for zip_name, files_to_include in [
            (source_zip, source_files),
            (profile_zip, profile_files),
        ]:
            print(f"--- Đang tạo bản sao lưu (Updated): {zip_name} ---")

            if os.path.exists(zip_name):
                os.remove(zip_name)
                print(f"Đã xóa bản cũ: {zip_name}")
            
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in files_to_include:
                    if os.path.exists(file):
                        zipf.write(file)
                        print(f" + Đã thêm: {file}")
                    else:
                        if zip_name == source_zip and file not in doc_files:
                            print(f" ! Cảnh báo: Không tìm thấy {file}")
            
            print(f"--- Hoàn tất: {os.path.abspath(zip_name)} ---\n")
        
    except Exception as e:
        print(f"Lỗi khi tạo backup: {e}")

if __name__ == "__main__":
    create_backup()
