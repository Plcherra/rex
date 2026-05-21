from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
MASTER_SIZE = 1024
MASTER_PATH = ROOT / "assets" / "brand" / "rex_app_icon_1024.png"

ANDROID_SIZES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}


def main() -> None:
    master = create_master_icon()
    MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    master.save(MASTER_PATH)
    write_android_icons(master)
    write_ios_icons(master)


def create_master_icon() -> Image.Image:
    canvas = Image.new("RGB", (MASTER_SIZE, MASTER_SIZE), "#07110f")
    draw_background(canvas)

    diamond_size = 602
    corner_radius = 90
    diamond = Image.new("RGBA", (diamond_size, diamond_size), (0, 0, 0, 0))
    mask = Image.new("L", (diamond_size, diamond_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        (0, 0, diamond_size - 1, diamond_size - 1),
        radius=corner_radius,
        fill=255,
    )

    fill = vertical_gradient(
        diamond_size,
        [
            (0.00, (9, 13, 68)),
            (0.38, (11, 62, 81)),
            (0.70, (28, 113, 98)),
            (1.00, (102, 196, 141)),
        ],
    )
    fill.putalpha(mask)
    add_surface_depth(fill, mask)

    rotated = fill.rotate(45, resample=Image.Resampling.BICUBIC, expand=True)
    rotated_alpha = rotated.getchannel("A")

    shadow = Image.new("RGBA", rotated.size, (0, 0, 0, 0))
    shadow.putalpha(rotated_alpha.filter(ImageFilter.GaussianBlur(28)))
    shadow_tint = Image.new("RGBA", rotated.size, (0, 0, 0, 116))
    shadow = Image.alpha_composite(Image.new("RGBA", rotated.size, (0, 0, 0, 0)), shadow_tint)
    shadow.putalpha(rotated_alpha.filter(ImageFilter.GaussianBlur(34)))

    x = (MASTER_SIZE - rotated.width) // 2
    y = (MASTER_SIZE - rotated.height) // 2 + 6
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.alpha_composite(shadow, (x, y + 28))
    canvas_rgba.alpha_composite(rotated, (x, y))

    return canvas_rgba.convert("RGB")


def draw_background(canvas: Image.Image) -> None:
    pixels = canvas.load()
    center_x = MASTER_SIZE * 0.48
    center_y = MASTER_SIZE * 0.54
    max_distance = math.hypot(center_x, center_y)
    for y in range(MASTER_SIZE):
        for x in range(MASTER_SIZE):
            distance = math.hypot(x - center_x, y - center_y) / max_distance
            glow = max(0.0, 1.0 - distance * 1.85)
            top_bias = max(0.0, 1.0 - y / MASTER_SIZE)
            r = int(7 + glow * 9 + top_bias * 2)
            g = int(17 + glow * 20 + top_bias * 2)
            b = int(15 + glow * 18 + top_bias * 8)
            pixels[x, y] = (r, g, b)


def vertical_gradient(size: int, stops: list[tuple[float, tuple[int, int, int]]]) -> Image.Image:
    image = Image.new("RGBA", (size, size))
    pixels = image.load()
    for y in range(size):
        t = y / max(size - 1, 1)
        lower, upper = stops[0], stops[-1]
        for index in range(len(stops) - 1):
            if stops[index][0] <= t <= stops[index + 1][0]:
                lower, upper = stops[index], stops[index + 1]
                break
        span = max(upper[0] - lower[0], 0.0001)
        local = (t - lower[0]) / span
        color = tuple(
            int(lower[1][channel] + (upper[1][channel] - lower[1][channel]) * local)
            for channel in range(3)
        )
        for x in range(size):
            edge = abs((x / max(size - 1, 1)) - 0.5) * 2
            shade = 1.0 - edge * 0.10
            pixels[x, y] = (
                int(color[0] * shade),
                int(color[1] * shade),
                int(color[2] * shade),
                255,
            )
    return image


def add_surface_depth(image: Image.Image, mask: Image.Image) -> None:
    size = image.width
    highlight = Image.new("RGBA", image.size, (255, 255, 255, 0))
    highlight_pixels = highlight.load()
    for y in range(size):
        for x in range(size):
            if mask.getpixel((x, y)) == 0:
                continue
            t = y / max(size - 1, 1)
            diagonal = max(0.0, 1.0 - abs((x - y) / size) * 2.2)
            alpha = int(max(0, (0.18 - t * 0.16) * 255) + diagonal * 8)
            highlight_pixels[x, y] = (255, 255, 255, min(alpha, 42))
    image.alpha_composite(highlight.filter(ImageFilter.GaussianBlur(18)))


def write_android_icons(master: Image.Image) -> None:
    for directory, size in ANDROID_SIZES.items():
        path = ROOT / "android" / "app" / "src" / "main" / "res" / directory / "ic_launcher.png"
        resize(master, size).save(path)


def write_ios_icons(master: Image.Image) -> None:
    icon_dir = ROOT / "ios" / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"
    contents = json.loads((icon_dir / "Contents.json").read_text())
    for item in contents["images"]:
        filename = item.get("filename")
        if not filename:
            continue
        size = int(float(item["size"].split("x")[0]) * int(item["scale"].replace("x", "")))
        resize(master, size).save(icon_dir / filename)


def resize(image: Image.Image, size: int) -> Image.Image:
    return image.resize((size, size), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    main()
