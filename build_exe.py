import PyInstaller.__main__
import os
import customtkinter
import re

# Get version from main file
version = "v3.1.0" # Default
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
exe_name = f"{APP_NAME}_{version}"
args = [
    'OAK_Hidden_SLTP_Manager.py',
    f'--name={exe_name}',
    '--onefile',
    '--windowed',
    f'--icon={ICON_PATH}',
    '--add-data=icon.ico;.',
    '--add-data=oak_response_dict.py;.', # Include Response Dictionary
    f'--add-data={ctk_path};customtkinter/', # Ensure CTK assets are included
    '--clean',
    '--noconfirm',
    '--collect-all=numpy',
    '--collect-all=MetaTrader5',
    '--hidden-import=numpy',
    '--hidden-import=numpy._core',
    '--hidden-import=numpy._core.multiarray',
    # Exclude standard modules that might bloat size if not needed (optional, but safer to keep defaults)
]

print(f"Starting build process for {exe_name}...")
PyInstaller.__main__.run(args)
print(f"Build finished. Check 'dist' folder for {exe_name}.exe")
