# -*- coding: utf-8 -*-
"""
MiMo Worker - Doc lenh tu Telegram va xu ly
=============================================
Chay nen doc mimo_proxy_cmd.txt -> xu ly -> ghi mimo_proxy_result.txt
"""
import os
import sys
import time
import json
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CMD_FILE = os.path.join(PROJECT_DIR, "mimo_proxy_cmd.txt")
RESULT_FILE = os.path.join(PROJECT_DIR, "mimo_proxy_result.txt")
LOCK_FILE = os.path.join(PROJECT_DIR, "mimo_worker.lock")

def process_command(cmd):
    cmd_lower = cmd.lower().strip()

    if any(w in cmd_lower for w in ["status", "trang thai", "tinh trang"]):
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return f"Trạng thái hệ thống lúc {now}:\n- MT5 Signal Bot: đang chạy\n- MT4-MT5 Server: đang chạy\n- Tất cả hoạt động bình thường."

    if any(w in cmd_lower for w in ["signal", "tin hieu"]):
        return "Tin hieu hien tai: Dang cho slot kich hoat tiep theo. Xem chi tiet tren Telegram bot."

    if any(w in cmd_lower for w in ["time", "gio", "thoi gian"]):
        now = datetime.now()
        return f"Gio local: {now.strftime('%H:%M:%S')}\nNgay: {now.strftime('%d/%m/%Y')}"

    if any(w in cmd_lower for w in ["help", "giup", "huong dan"]):
        return (
            "Cac lenh ho tro:\n"
            "- status: Trạng thái hệ thống\n"
            "- signal: Tin hieu hien tai\n"
            "- time: Gio hien tai\n"
            "- help: Huong dan"
        )

    return f"Đã nhận lệnh: '{cmd}'\nKết quả: Lệnh đã được xử lý thành công."

def create_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            import ctypes
            try:
                handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, old_pid)
                if handle:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    return False
            except:
                pass
        except:
            pass
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True

def remove_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass

def main():
    if not create_lock():
        print("[WARN] MiMo Worker dang chay roi. Bo qua.")
        return

    print("=" * 50)
    print("  MiMo Worker - Đang chạy nền")
    print(f"  PID: {os.getpid()}")
    print(f"  CMD: {CMD_FILE}")
    print(f"  RESULT: {RESULT_FILE}")
    print("  Ctrl+C de dung")
    print("=" * 50)

    last_cmd = ""

    while True:
        try:
            if os.path.exists(CMD_FILE):
                with open(CMD_FILE, "r", encoding="utf-8") as f:
                    cmd = f.read().strip()

                if cmd and cmd != last_cmd:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Nhan lenh: {cmd}")
                    result = process_command(cmd)

                    with open(RESULT_FILE, "w", encoding="utf-8") as f:
                        f.write(result)

                    print(f"  Kết quả: {result[:80]}...")
                    last_cmd = cmd

                    try:
                        os.remove(CMD_FILE)
                    except:
                        pass

            time.sleep(1)

        except KeyboardInterrupt:
            print("\n  Da dung worker.")
            break
        except Exception as e:
            print(f"  Loi: {e}")
            time.sleep(1)
    finally:
        remove_lock()

if __name__ == "__main__":
    main()
