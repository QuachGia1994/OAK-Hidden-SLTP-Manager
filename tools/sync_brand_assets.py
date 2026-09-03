from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
source = root / "ios-native" / "Resources" / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon.png"
if not source.is_file():
    raise SystemExit(f"Missing source icon: {source}")

targets = [
    root / "android-native" / "app" / "src" / "main" / "res" / "drawable-nodpi" / "oak_app_icon_exact.png",
    root / "dashboard" / "public" / "oak-app-icon.png",
    root / "ios-native" / "Resources" / "Assets.xcassets" / "OAKLogo.imageset" / "OAKLogo.png",
]
for target in targets:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    print(f"synced {source.name} -> {target.relative_to(root)}")
