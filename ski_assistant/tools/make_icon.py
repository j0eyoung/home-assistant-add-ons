"""Draws the Ski Assistant icon.png (256px), logo.png (500x200) and a 192px favicon for the web page."""
import math
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "."  # the add-on folder
S = 1024  # draw big, then downscale for smooth edges


def gradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def snowflake(d, cx, cy, r, width, color):
    for k in range(6):
        a = math.radians(90 + 60 * k)
        x, y = cx + r * math.cos(a), cy - r * math.sin(a)
        d.line([(cx, cy), (x, y)], fill=color, width=width)
        for frac in (0.55,):
            bx, by = cx + r * frac * math.cos(a), cy - r * frac * math.sin(a)
            for side in (-1, 1):
                b = a + side * math.radians(40)
                d.line([(bx, by), (bx + r * 0.32 * math.cos(b), by - r * 0.32 * math.sin(b))], fill=color, width=width)
    d.ellipse([cx - width, cy - width, cx + width, cy + width], fill=color)


def icon(size):
    bg = gradient(S, S, (13, 42, 74), (42, 120, 214))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=210, fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(bg, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # Back range
    d.polygon([(40, 900), (330, 430), (470, 600), (640, 360), (990, 900)], fill=(134, 182, 239))
    d.polygon([(640, 360), (585, 440), (615, 430), (642, 462), (672, 432), (700, 445)], fill=(240, 244, 250))
    d.polygon([(330, 430), (285, 503), (312, 494), (334, 520), (357, 496), (378, 508)], fill=(240, 244, 250))
    # Front peak
    d.polygon([(110, 930), (500, 300), (900, 930)], fill=(28, 92, 171))
    d.polygon([(500, 300), (408, 448), (452, 430), (500, 478), (548, 430), (594, 450)], fill=(255, 255, 255))
    # Rolling snow field in front
    d.ellipse([-260, 790, 700, 1300], fill=(240, 244, 250))
    d.ellipse([380, 830, 1300, 1320], fill=(225, 234, 246))
    # Snowflake
    snowflake(d, 800, 215, 95, 22, (255, 255, 255))
    # Clip the snow field to the rounded square
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out.resize((size, size), Image.LANCZOS)


def logo():
    w, h = 1000, 400
    bg = gradient(w, h, (13, 42, 74), (28, 92, 171))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=70, fill=255)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.paste(bg, (0, 0), mask)
    img.alpha_composite(icon(300), (50, 50))
    d = ImageDraw.Draw(img)
    bold = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 110)
    reg = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 46)
    d.text((385, 95), "Ski", font=bold, fill=(255, 255, 255))
    d.text((385, 195), "Assistant", font=bold, fill=(134, 182, 239))
    return img.resize((500, 200), Image.LANCZOS)


icon(256).save(f"{OUT}/icon.png", optimize=True)
icon(192).save(f"{OUT}/static/icon-192.png", optimize=True)
logo().save(f"{OUT}/logo.png", optimize=True)
print("ok")
