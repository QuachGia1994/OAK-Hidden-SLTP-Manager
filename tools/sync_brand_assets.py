from pathlib import Path
import math
import shutil

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ios-native/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png"
BG = (7, 17, 15, 255)
MINT = (122, 234, 198, 255)
MINT_SOFT = (122, 234, 198, 150)
MINT_FAINT = (122, 234, 198, 72)


def add_rotated_ellipse(canvas, box, angle, color, width, phase):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse(box, outline=color, width=width)
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    x = cx + rx * math.cos(phase)
    y = cy + ry * math.sin(phase)
    r = max(7, width * 2)
    draw.ellipse((x-r, y-r, x+r, y+r), fill=MINT)
    rotated = layer.rotate(angle, resample=Image.Resampling.BICUBIC, center=(canvas.width // 2, canvas.height // 2))
    return Image.alpha_composite(canvas, rotated)


def render_orbit_icon(size=1024):
    scale = 2
    n = size * scale
    canvas = Image.new("RGBA", (n, n), BG)
    cx = cy = n // 2

    glow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    radius = int(n * 0.25)
    gd.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=(70, 255, 200, 44))
    canvas = Image.alpha_composite(canvas, glow.filter(ImageFilter.GaussianBlur(int(n * 0.08))))

    span = n * 0.72
    orbit_h = n * 0.22
    box = (cx-span/2, cy-orbit_h/2, cx+span/2, cy+orbit_h/2)
    width = max(4, n // 260)
    canvas = add_rotated_ellipse(canvas, box, 0, MINT_SOFT, width, 0.55)
    canvas = add_rotated_ellipse(canvas, box, 90, MINT_SOFT, width, 2.1)
    canvas = add_rotated_ellipse(canvas, box, 38, MINT_FAINT, max(3, n // 320), 4.0)
    canvas = add_rotated_ellipse(canvas, box, -38, MINT_FAINT, max(3, n // 320), 5.2)

    draw = ImageDraw.Draw(canvas)
    sphere = n * 0.18
    draw.ellipse((cx-sphere, cy-sphere, cx+sphere, cy+sphere), outline=MINT_SOFT, width=width)
    for fraction in (0.22, 0.45, 0.68):
        rx = sphere * fraction
        draw.ellipse((cx-rx, cy-sphere, cx+rx, cy+sphere), outline=MINT_FAINT, width=max(2, n // 420))
    draw.ellipse((cx-sphere, cy-sphere*0.34, cx+sphere, cy+sphere*0.34), outline=MINT_FAINT, width=max(2, n // 420))

    core = n * 0.055
    draw.ellipse((cx-core*1.9, cy-core*1.9, cx+core*1.9, cy+core*1.9), outline=MINT_SOFT, width=width)
    draw.ellipse((cx-core, cy-core, cx+core, cy+core), fill=MINT)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def transparent_foreground(source):
    rgba = source.convert("RGBA").copy()
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = pixels[x, y]
            distance = abs(red - BG[0]) + abs(green - BG[1]) + abs(blue - BG[2])
            if distance < 18:
                pixels[x, y] = (red, green, blue, 0)
            elif distance < 70:
                pixels[x, y] = (red, green, blue, min(alpha, int((distance - 18) / 52 * 180)))
    safe = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    scaled = rgba.resize((800, 800), Image.Resampling.LANCZOS)
    safe.alpha_composite(scaled, ((rgba.width - 800) // 2, (rgba.height - 800) // 2))
    return safe


def main():
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    icon = render_orbit_icon(1024)
    icon.save(SOURCE, "PNG", optimize=True)

    exact_targets = [
        ROOT / "dashboard/public/oak-app-icon.png",
        ROOT / "ios-native/Resources/Assets.xcassets/OAKLogo.imageset/OAKLogo.png",
    ]
    for target in exact_targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE, target)
        print(f"synced Orbit 3D brand -> {target.relative_to(ROOT)}")

    foreground = transparent_foreground(icon)
    foreground.save(ROOT / "android-native/app/src/main/res/drawable-nodpi/oak_launcher_foreground.png", "PNG", optimize=True)
    mono = Image.new("RGBA", foreground.size, (255, 255, 255, 0))
    mono.putalpha(foreground.getchannel("A"))
    mono.save(ROOT / "android-native/app/src/main/res/drawable-nodpi/oak_launcher_monochrome.png", "PNG", optimize=True)

    for size in (192, 512):
        target = ROOT / "dashboard/public" / f"oak-app-icon-{size}.png"
        icon.resize((size, size), Image.Resampling.LANCZOS).save(target, "PNG", optimize=True)
    icon.save(ROOT / "dashboard/src/app/favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("Orbit 3D brand assets synchronized across iOS, Android and web.")


if __name__ == "__main__":
    main()
