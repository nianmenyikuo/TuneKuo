from __future__ import annotations

import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(ROOT, "assets", "icon-source.png")
ICO = os.path.join(ROOT, "app", "assets", "icon.ico")
PNG = os.path.join(ROOT, "app", "assets", "icon.png")
SIZES = [256, 128, 96, 64, 48, 32, 24, 16]
ANDROID = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
ANDROID_RES = os.path.normpath(os.path.join(ROOT, "..", "app", "src", "main", "res"))

def square(img: Image.Image, side: int) -> Image.Image:
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    return img if s == side else img.resize((side, side), Image.LANCZOS)

def main() -> int:
    argv = sys.argv[1:]
    named = [a for a in argv if not a.startswith("--")]
    src = named[0] if named else DEFAULT_SRC
    if not os.path.isfile(src):
        print(f"找不到源图：{src}")
        return 1

    full = square(Image.open(src).convert("RGBA"), 1024)
    master = full.resize((256, 256), Image.LANCZOS)
    os.makedirs(os.path.dirname(ICO), exist_ok=True)
    master.save(ICO, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"已生成 {ICO}  ({os.path.getsize(ICO)} 字节, 尺寸 {SIZES})")
    master.save(PNG, format="PNG")
    print(f"已生成 {PNG}  ({os.path.getsize(PNG)} 字节, 256x256)")

    if "--android" in argv:
        for d, side in ANDROID.items():
            out = os.path.join(ANDROID_RES, f"mipmap-{d}", "ic_launcher.png")
            if not os.path.isdir(os.path.dirname(out)):
                print(f"跳过 {out}（目录不存在）")
                continue
            full.resize((side, side), Image.LANCZOS).save(out, format="PNG")
            print(f"已生成 {out}  ({os.path.getsize(out)} 字节, {side}x{side})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
