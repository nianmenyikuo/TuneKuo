"""命令行方式注册/取消注册默认播放器（开发态用；打包后可用 TuneKuo.exe --register）。

    python app/register.py register     注册为可用播放器并挂进系统默认应用
    python app/register.py unregister   撤销上面的注册
    python app/register.py status       查看每种格式当前默认程序是谁
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import assoc

def main() -> int:
    action = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    if action == "register":
        done = assoc.register()
        print("已注册：")
        for d in done:
            print("  -", d)
        print(f"\n当前有 {assoc.default_count()} / {len(assoc.EXTS)} 种格式的默认程序是 TuneKuo。")
        if assoc.default_count() < len(assoc.EXTS):
            print("Windows 会保护用户已选的默认程序：请打开“设置 → 应用 → 默认应用”，"
                  "在“音乐播放器”里选择 TuneKuo。")
            if "--open" in sys.argv:
                assoc.open_default_apps_settings()
        return 0
    if action == "unregister":
        for d in assoc.unregister():
            print("已移除:", d)
        return 0
    if action == "status":
        for ext in assoc.EXTS:
            cur = assoc.default_progid(ext) or "（未指定）"
            mark = "<= TuneKuo" if assoc.is_default_for(ext) else ""
            print(f"{ext:<7} {cur:<28} {mark}")
        print(f"\n合计 {assoc.default_count()} / {len(assoc.EXTS)}")
        return 0
    print(__doc__)
    return 1

if __name__ == "__main__":
    sys.exit(main())
