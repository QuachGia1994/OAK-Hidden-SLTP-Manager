"""Generate the public social card from the canonical OAK app artwork."""
from pathlib import Path
import hashlib
import shutil

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ios-native/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png"
PUBLIC = ROOT / "dashboard/public"
CARD = PUBLIC / "oak-share-v3.png"


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts") / ("arialbd.ttf" if bold else "arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    raise RuntimeError("Install Arial or DejaVu Sans to regenerate the social card.")


def main():
    artwork = Image.open(SOURCE).convert("RGB")
    background = artwork.getpixel((0, 0))
    card = Image.new("RGB", (1200, 630), background)
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((28, 28, 1172, 602), radius=28, outline="#294460", width=2)
    card.paste(artwork.resize((510, 510), Image.Resampling.LANCZOS), (40, 60))
    draw.text((560, 178), "OAK", font=font(84, True), fill="#f7faff")
    draw.text((560, 280), "GATEKEEPER", font=font(43, True), fill="#559bff")
    draw.text((564, 363), "ROBOT SLTP PRO", font=font(24), fill="#c1d1e3")
    draw.line((564, 420, 1068, 420), fill="#294460", width=2)
    draw.text((564, 452), "oakgatekeeper.uk", font=font(24), fill="#c1d1e3")
    card.save(CARD, "PNG", optimize=True)
    shutil.copyfile(SOURCE, PUBLIC / "oak-app-icon.png")
    Image.open(SOURCE).convert("RGBA").save(ROOT / "dashboard/src/app/favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    saved = Image.open(CARD)
    assert saved.size == (1200, 630) and saved.format == "PNG"
    assert (PUBLIC / "oak-app-icon.png").read_bytes() == SOURCE.read_bytes()
    print(f"{CARD.relative_to(ROOT)}: {saved.size}, {CARD.stat().st_size} bytes")
    print(f"canonical logo SHA-256: {hashlib.sha256(SOURCE.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
