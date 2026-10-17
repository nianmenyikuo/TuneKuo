from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import messagebox

APP_NAME = "TuneKuo"

def _ensure_sys_path() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

def collect_paths(argv) -> list:
    args = [str(a).strip().strip('"') for a in argv]
    out = []
    i = 0
    while i < len(args):
        a = args[i]
        if not a or a.startswith("-"):
            i += 1
            continue
        if os.path.isfile(a) or os.path.isdir(a):
            out.append(os.path.abspath(a))
            i += 1
            continue
        joined = a
        for j in range(i + 1, len(args)):
            joined = joined + " " + args[j]
            if os.path.isfile(joined) or os.path.isdir(joined):
                out.append(os.path.abspath(joined))
                i = j
                break
        i += 1
    return out

def run_cli(args) -> "int | None":
    flags = {a.lower() for a in args if a.startswith("--")}
    if not (flags & {"--register", "--unregister", "--status", "--open-defaults"}):
        return None
    import assoc

    if "--open-defaults" in flags and len(flags) == 1:
        assoc.open_default_apps_settings()
        return 0
    if "--register" in flags:
        done = assoc.register()
        body = "已注册：\n- " + "\n- ".join(done)
    elif "--unregister" in flags:
        body = "已撤销注册：\n- " + "\n- ".join(assoc.unregister() or ["（没有需要移除的项）"])
    else:
        lines = [f"{e:<7} {assoc.default_progid(e) or '（未指定）'}"
                 + ("   <= TuneKuo" if assoc.is_default_for(e) else "") for e in assoc.EXTS]
        body = "\n".join(lines)
    n = assoc.default_count()
    if os.name == "nt":
        tip = (f"\n\n当前 {n} / {len(assoc.EXTS)} 种格式的默认程序是 TuneKuo。\n"
               "Windows 不允许程序静默抢占默认程序：如需全部生效，"
               "请在“设置 → 应用 → 默认应用”的音乐播放器一项选择 TuneKuo。")
    else:
        tip = (f"\n\n当前 {n} / {len(assoc.EXTS)} 种格式的默认程序是 TuneKuo。\n"
               "想改回别的播放器：用系统设置里的“默认应用”（Debian 上是 xdg-mime）。")
    if "--register" in flags and n < len(assoc.EXTS) and "--quiet" not in flags:
        assoc.open_default_apps_settings()
    if "--quiet" in flags:  
        _write_report(body + tip, "tunekuo_cli.txt")
        return 0
    messagebox.showinfo(APP_NAME, body + tip)
    return 0

def _write_report(text: str, name: str) -> None:
    import tempfile

    out = os.path.join(tempfile.gettempdir(), name)
    try:
        with open(out, "w", encoding="utf-8") as fp:
            fp.write(text + "\n")
    except OSError:
        pass
    print(text)

def run_selftest(paths) -> int:
    import time
    import traceback

    import vlcenv

    report = [f"frozen={getattr(sys, 'frozen', False)}",
              f"python={sys.version.split()[0]}",
              f"libvlc={vlcenv.LIB}",
              f"输入文件={paths}"]
    code = 1
    player = None
    try:
        import vlc

        report.append("libvlc 版本=" + vlc.libvlc_get_version().decode("ascii", "replace"))

        from library import scan_paths
        from player import Player, Track

        files = scan_paths(paths) if paths else []
        report.append(f"可播放文件={len(files)}")
        player = Player(on_event=lambda kind, payload: None, volume=80)
        report.append("播放器实例=OK")

        if files:
            from library import PARSE_FLAG, _wait_parsed

            report.append("时长自检（列表 --:-- 的回归检查）:")
            _inst = vlc.Instance("--no-video", "--quiet")
            for _f in files[:3]:
                _m = _inst.media_new(_f)
                try:
                    _wait_parsed(_m)
                    report.append(f"  {os.path.basename(_f)} → {_m.get_duration() or 0}ms")
                finally:
                    try:
                        _m.release()
                    except Exception:
                        pass
            player.set_playlist([Track(path=f) for f in files], 0, autoplay=True)
            deadline = time.time() + 8
            while time.time() < deadline:
                if player.is_playing() and player.get_time() > 300:
                    break
                time.sleep(0.2)
            report.append(f"is_playing={player.is_playing()} 已播放={player.get_time()}ms "
                          f"总长={player.get_length()}ms")
            if not player.is_playing():
                raise RuntimeError("文件已加载但没有开始播放")
        code = 0
        report.append("结果=通过")
    except Exception:
        report.append("结果=失败\n" + traceback.format_exc())
    finally:
        if player is not None:
            try:
                player.release()
            except Exception:
                pass
        _write_report("\n".join(report), "tunekuo_selftest.txt")
    return code

def main() -> int:
    _ensure_sys_path()

    if any(a.lower() == "--selftest" for a in sys.argv[1:]):
        return run_selftest(collect_paths(sys.argv[1:]))

    cli = run_cli(sys.argv[1:])
    if cli is not None:
        return cli

    import vlcenv

    paths = collect_paths(sys.argv[1:])

    primary = None
    try:
        import instance

        if paths and instance.send_to_primary(paths):
            return 0
        primary = instance.SingleInstance(on_paths=None)
        if not primary.acquire():
            primary = None
    except Exception:
        primary = None

    root = tk.Tk()
    root.withdraw()

    if os.name == "nt":
        if vlcenv.LIB is None:
            messagebox.showerror(
                APP_NAME,
                "没有找到 64 位 libvlc，播放引擎无法启动。\n\n"
                "解决办法（任选其一）：\n"
                "1. 把解压出来的 64 位 VLC 文件夹放到程序旁边并命名为 vlc\n"
                "2. 安装 64 位 VLC（videolan.org 下载 win64 版）\n\n"
                "注意：Program Files (x86) 里那个 32 位的 VLC 用不了。",
            )
            return 2
    else:
        try:
            import vlc

            vlc.libvlc_get_version()
        except Exception:
            messagebox.showerror(
                APP_NAME,
                "没有找到 libvlc，播放引擎无法启动。\n\n"
                "装一个 VLC 就行（只要 libvlc，不需要图形界面）：\n"
                "  Debian/Ubuntu:  sudo apt install vlc-plugin-base\n"
                "  Fedora:         sudo dnf install vlc\n"
                "  Arch:           sudo pacman -S vlc",
            )
            return 2

    try:
        from ui import TuneKuoUI

        app = TuneKuoUI(root, initial_paths=paths)
    except Exception as e:
        import traceback

        messagebox.showerror(APP_NAME, f"启动失败：\n{e}\n\n{traceback.format_exc()}")
        return 3

    if primary is not None:
        primary.on_paths = lambda ps: app.evq.put(("path", ps, None))

    root.deiconify()
    root.lift()
    root.mainloop()

    if primary is not None:
        primary.release()
    return 0

if __name__ == "__main__":
    sys.exit(main())
