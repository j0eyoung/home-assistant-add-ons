"""Draws the add-on's icon.png (256px) and logo.png (500x200) to match web/public/icon.svg:
a clay rounded square holding a white chat bubble with a house and a spark in it.

Run from the claude_chat folder: python scripts/make_icon.py  (needs Pillow)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

S = 8  # draw large, then downsample for smooth edges
ROOT = Path(__file__).resolve().parent.parent
CLAY_TOP = (0xCB, 0x6A, 0x43)
CLAY_BOTTOM = (0xA9, 0x4F, 0x2F)
CLAY = "#b8572f"
WHITE = "#ffffff"


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    names = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def p(v: float) -> int:
    return round(v * S)


def icon(base: int = 128) -> Image.Image:
    size = base * S
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / (size - 1)
        gd.line([(0, y), (size, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(CLAY_TOP, CLAY_BOTTOM)) + (255,))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=p(28), fill=255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # chat bubble with a tail at the lower left
    d.rounded_rectangle([p(18), p(24), p(110), p(94)], radius=p(20), fill=WHITE)
    d.polygon([(p(30), p(88)), (p(26), p(110)), (p(52), p(92))], fill=WHITE)

    # house inside the bubble
    w = p(6.5)
    d.line([(p(41), p(64)), (p(64), p(42)), (p(87), p(64))], fill=CLAY, width=w, joint="curve")
    for x, y in ((41, 64), (87, 64), (64, 42)):
        d.ellipse([p(x - 3.2), p(y - 3.2), p(x + 3.2), p(y + 3.2)], fill=CLAY)
    d.rounded_rectangle([p(48), p(60), p(80), p(84)], radius=p(4), outline=CLAY, width=w)
    d.rounded_rectangle([p(59), p(70), p(69), p(84)], radius=p(2), fill=CLAY)

    # four-point spark on the bubble's upper right corner
    cx, cy, r, k = 101, 27, 15, 3.6
    d.polygon([(p(cx), p(cy - r)), (p(cx + k), p(cy - k)), (p(cx + r), p(cy)), (p(cx + k), p(cy + k)), (p(cx), p(cy + r)), (p(cx - k), p(cy + k)), (p(cx - r), p(cy)), (p(cx - k), p(cy - k))], fill=CLAY, outline=WHITE, width=p(2.5))
    return img


def main() -> None:
    big = icon(128)
    big.resize((256, 256), Image.LANCZOS).save(ROOT / "icon.png")

    logo = Image.new("RGBA", (500 * 2, 200 * 2), (0, 0, 0, 0))
    mark = big.resize((300, 300), Image.LANCZOS)
    logo.paste(mark, (40, 50), mark)
    d = ImageDraw.Draw(logo)
    size = 118
    while size > 40 and d.textlength("Claude Chat", font=font(size)) > 580:
        size -= 2
    d.text((370, 200 - size), "Claude Chat", font=font(size), fill="#b8572f")
    d.text((374, 222), "for Home Assistant", font=font(round(size * 0.48), bold=False), fill="#8a857c")
    logo.resize((500, 200), Image.LANCZOS).save(ROOT / "logo.png")
    print("wrote icon.png and logo.png")


if __name__ == "__main__":
    main()
