from pathlib import Path
import shutil

from PIL import Image

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

# Android adaptive icons must not embed the opaque iOS square as their
# foreground. Strip the flat corner/background color and let Android apply its
# own launcher mask over a separate navy background layer.
foreground = root / "android-native" / "app" / "src" / "main" / "res" / "drawable-nodpi" / "oak_launcher_foreground.png"
image = Image.open(source).convert("RGBA")
background = image.getpixel((0, 0))[:3]
pixels = image.load()
for y in range(image.height):
    for x in range(image.width):
        red, green, blue, alpha = pixels[x, y]
        if (red, green, blue) == background:
            pixels[x, y] = (red, green, blue, 0)
foreground.parent.mkdir(parents=True, exist_ok=True)
image.save(foreground, "PNG", optimize=True)
print(f"generated transparent adaptive foreground -> {foreground.relative_to(root)}")
