from __future__ import annotations

import os
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "dist", "TuneKuo")
DEFAULT_OUT = os.path.join(os.path.expanduser("~"), "Desktop", "TuneKuo-Windows-1.0.0.zip")

def main() -> int:
    out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    if not os.path.isfile(os.path.join(SRC, "TuneKuo.exe")):
        print(f"没有找到 {SRC}\\TuneKuo.exe，先运行 build.ps1")
        return 1
    if os.path.exists(out):
        os.remove(out)

    t0 = time.time()
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for dirpath, _dirs, files in os.walk(SRC):
            for name in files:
                full = os.path.join(dirpath, name)
                arc = "TuneKuo/" + os.path.relpath(full, SRC).replace("\\", "/")
                z.write(full, arc)
                n += 1
    mb = os.path.getsize(out) / 1024 / 1024
    print(f"压缩完成：{out}")
    print(f"{n} 个文件 -> {mb:.1f} MB（用时 {time.time() - t0:.1f} 秒）")
    print("解压后是 TuneKuo 文件夹，双击里面的 TuneKuo.exe 即可")
    return 0

if __name__ == "__main__":
    sys.exit(main())
