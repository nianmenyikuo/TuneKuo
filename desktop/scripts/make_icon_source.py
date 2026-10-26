from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "icon-source.png")
S = 1024
BG_TOP = (26, 26, 38)
BG_BOT = (16, 16, 24)
CYAN = (96, 205, 255)
WHITE = (255, 255, 255)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def background():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(grad)
    for y in range(S):
        d.line([(0, y), (S, y)], fill=lerp(BG_TOP, BG_BOT, y / (S - 1)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)
    return img


def draw_note(img):
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse(
        [S * 0.18, S * 0.18, S * 0.82, S * 0.82],
        outline=CYAN + (70,),
        width=max(2, int(S * 0.012)),
    )
    img = Image.alpha_composite(img, ring)
    d = ImageDraw.Draw(img)
    hx1, hy1, hr = S * 0.335, S * 0.735, S * 0.082
    hx2, hy2 = S * 0.645, S * 0.685
    d.ellipse([hx1 - hr, hy1 - hr * 0.82, hx1 + hr, hy1 + hr * 0.82], fill=WHITE + (255,))
    d.ellipse([hx2 - hr, hy2 - hr * 0.82, hx2 + hr, hy2 + hr * 0.82], fill=WHITE + (255,))
    sw = S * 0.045
    d.rounded_rectangle(
        [hx1 + hr - sw / 2, S * 0.245, hx1 + hr + sw / 2, hy1],
        radius=sw / 2,
        fill=WHITE + (255,),
    )
    d.rounded_rectangle(
        [hx2 + hr - sw / 2, S * 0.195, hx2 + hr + sw / 2, hy2],
        radius=sw / 2,
        fill=WHITE + (255,),
    )
    d.polygon(
        [
            (hx1 + hr - sw / 2, S * 0.245),
            (hx2 + hr + sw / 2, S * 0.195),
            (hx2 + hr + sw / 2, S * 0.305),
            (hx1 + hr - sw / 2, S * 0.355),
        ],
        fill=CYAN + (255,),
    )
    return img


def main() -> int:
    img = draw_note(background())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, format="PNG")
    print(f"已生成 {OUT}  ({os.path.getsize(OUT)} 字节, {S}x{S})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
