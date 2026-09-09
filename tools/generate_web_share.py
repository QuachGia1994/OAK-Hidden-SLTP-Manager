"""Generate the public social card from the canonical Orbit 3D OAK artwork."""
from pathlib import Path
import hashlib
import math

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ios-native/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png"
PUBLIC = ROOT / "dashboard/public"
CARD = PUBLIC / "oak-share-v4.png"
BG = "#07110f"
SURFACE = "#0c1916"
LINE = "#24463c"
MINT = "#7aeac6"
TEXT = "#eef8f4"
MUTED = "#9ab7ad"


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
    artwork = Image.open(SOURCE).convert("RGBA")
    card = Image.new("RGB", (1200, 630), BG)
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((28, 28, 1172, 602), radius=30, fill=SURFACE, outline=LINE, width=2)

    for x in range(60, 1140, 80):
        draw.line((x, 70, x, 560), fill="#10251f", width=1)
    for y in range(80, 560, 80):
        draw.line((60, y, 1140, y), fill="#10251f", width=1)

    icon = artwork.resize((440, 440), Image.Resampling.LANCZOS)
    card.paste(icon.convert("RGB"), (70, 95))

    draw.text((555, 130), "OAK GATEKEEPER", font=font(50, True), fill=TEXT)
    draw.text((558, 208), "H1 LIVE · NEOTECH · TOOLS", font=font(23, True), fill=MINT)
    draw.text((558, 274), "Algorithmic trading command system", font=font(28, False), fill=TEXT)
    draw.text((558, 318), "with broker-aligned evidence and discipline.", font=font(24, False), fill=MUTED)
    draw.line((558, 390, 1080, 390), fill=LINE, width=2)
    draw.text((558, 425), "ORBIT 3D IDENTITY", font=font(18, True), fill=MINT)
    draw.text((558, 466), "oakgatekeeper.uk", font=font(25, True), fill=TEXT)

    card.save(CARD, "PNG", optimize=True)
    saved = Image.open(CARD)
    assert saved.size == (1200, 630) and saved.format == "PNG"
    print(f"{CARD.relative_to(ROOT)}: {saved.size}, {CARD.stat().st_size} bytes")
    print(f"canonical Orbit icon SHA-256: {hashlib.sha256(SOURCE.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
