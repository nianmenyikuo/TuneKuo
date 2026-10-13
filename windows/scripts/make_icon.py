"""把一张 PNG 转成 Windows 多尺寸 .ico（窗口图标 + exe 图标）。

    python scripts/make_icon.py [源PNG] [目标ICO]
默认：assets/icon-source.png -> app/assets/icon.ico
"""
from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(ROOT, "assets", "icon-source.png")
DEFAULT_DST = os.path.join(ROOT, "app", "assets", "icon.ico")
SIZES = [256, 128, 96, 64, 48, 32, 24, 16]


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    dst = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DST
    if not os.path.isfile(src):
        print(f"找不到源图：{src}")
        return 1
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side))
    if side < 256:
        img = img.resize((256, 256), Image.LANCZOS)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    img.save(dst, format="ICO", sizes=[(s, s) for s in SIZES if s <= max(img.size)])
    print(f"已生成 {dst}  ({os.path.getsize(dst)} 字节, 尺寸 {SIZES})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
