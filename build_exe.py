import PyInstaller.__main__
import os
import customtkinter
import re

# Get version from main file
version = "v3.14.0" # Default
try:
    with open("OAK_Hidden_SLTP_Manager.py", "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'VERSION\s*=\s*"(.*?)"', content)
        if match:
            version = match.group(1)
except Exception as e:
    print(f"Warning: Could not read version from file: {e}")

# --- CONFIG ---
APP_NAME = "OAK MANAGER"
ICON_PATH = 'icon.ico'

# Get customtkinter path for add-data
ctk_path = os.path.dirname(customtkinter.__file__)

# Define the build options
# NOTE: onefile bundles everything into single exe. Child processes (--signal-bot)
# run inside the same exe via argparse. No loose .py scripts needed.
exe_name = f"{APP_NAME}_{version}"
args = [
    'OAK_Hidden_SLTP_Manager.py',
    f'--name={exe_name}',
    '--onefile',
    '--windowed',
    f'--icon={ICON_PATH}',
    '--add-data=icon.ico;.',
    '--add-data=oak_response_dict.py;.',
    f'--add-data={ctk_path};customtkinter/',
    '--clean',
    '--noconfirm',
    # Hidden imports for bundled modules
    '--hidden-import=numpy',
    '--hidden-import=numpy.core',
    '--hidden-import=numpy.core.multiarray',
    '--hidden-import=numpy.core.numerictypes',
    '--hidden-import=numpy.core.umath',
    '--hidden-import=numpy.core.defchararray',
    '--hidden-import=numpy.lib',
    '--hidden-import=numpy.lib._version',
    '--hidden-import=numpy.lib.arraysetops',
    '--hidden-import=numpy.lib.function_base',
    '--hidden-import=numpy.lib.index_tricks',
    '--hidden-import=numpy.lib.shape_base',
    '--hidden-import=numpy.lib.stride_tricks',
    '--hidden-import=numpy.lib.type_check',
    '--hidden-import=numpy.lib.ufunclike',
    '--hidden-import=numpy.lib.utils',
    '--hidden-import=numpy.ma',
    '--hidden-import=numpy.ma.core',
    '--hidden-import=numpy.ma.extras',
    # MetaTrader5
    '--collect-all=MetaTrader5',
    # OAK modules
    '--hidden-import=secret_store',
    '--hidden-import=oak_logger',
    '--hidden-import=oak_response_dict',
    '--hidden-import=oak_trading_reminders',
    '--hidden-import=utils',
    '--hidden-import=mt5_signal_bot',
    '--hidden-import=repositories.sqlite_store',
]

# UPX compression
if os.path.exists("upx"):
    args.append('--upx-dir=upx')
    print("  UPX: ON (compression enabled)")
else:
    print("  UPX: OFF (folder 'upx' not found, install UPX for smaller exe)")

print(f"Starting build process for {exe_name}...")
PyInstaller.__main__.run(args)
print(f"Build finished. Check 'dist' folder for {exe_name}.exe")
