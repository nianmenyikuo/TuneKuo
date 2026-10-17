from __future__ import annotations

import mimetypes
import os
import shutil
import subprocess
import sys

IS_WIN = os.name == "nt"
if IS_WIN:
    import winreg
else:
    winreg = None

PROGID = "TuneKuo.Audio"
APP_NAME = "TuneKuo"
DESKTOP_ID = "tunekuo.desktop"

EXTS = [
    ".mp3", ".flac", ".ape", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus",
    ".wma", ".aiff", ".aif", ".dsf", ".dff", ".wv", ".tta", ".tak", ".mka",
    ".ac3", ".dts", ".mpc", ".spx", ".caf", ".mp2", ".m4b",
]

def exe_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    if not IS_WIN:
        return sys.executable
    exe_dir = os.path.dirname(sys.executable)
    pyw = os.path.join(exe_dir, "pythonw.exe")
    if not os.path.isfile(pyw):
        pyw = sys.executable
    return pyw

def script_path() -> str:
    if getattr(sys, "frozen", False):
        return ""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

def open_command() -> str:
    exe = exe_path()
    arg = "%1" if IS_WIN else "%F"
    if getattr(sys, "frozen", False):
        return f'"{exe}" "{arg}"'
    return f'"{exe}" "{script_path()}" "{arg}"'

def _desktop_dir() -> str:
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    d = os.path.join(base, "applications")
    os.makedirs(d, exist_ok=True)
    return d

def desktop_file() -> str:
    return os.path.join(_desktop_dir(), DESKTOP_ID)

def mime_for(ext: str) -> str:
    mime, _ = mimetypes.guess_type("x" + ext)
    return mime or ("audio/x-" + ext.lstrip("."))

def mimes() -> list:
    return sorted({mime_for(e) for e in EXTS})

def desktop_entry() -> str:
    import paths

    icon = os.path.join(paths.assets_dir(), "icon.png")
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Name[zh_CN]={APP_NAME} 音乐播放器\n"
        "Comment=本地音乐播放器（全格式）\n"
        f"Exec={open_command()}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=AudioVideo;Audio;Player;\n"
        "MimeType=" + ";".join(mimes()) + ";\n"
    )

def _linux_register() -> list:
    path = desktop_file()
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(desktop_entry())
    done = [f"桌面项 {path}"]

    xdg = shutil.which("xdg-mime")
    if not xdg:
        done.append("没找到 xdg-mime，请在系统设置里手动指定默认程序")
        return done
    ok = 0
    for mime in mimes():
        try:
            r = subprocess.run([xdg, "default", DESKTOP_ID, mime],
                               capture_output=True, timeout=10)
            ok += 1 if r.returncode == 0 else 0
        except Exception:
            continue
    done.append(f"{ok}/{len(mimes())} 个音频类型已指向 TuneKuo")

    upd = shutil.which("update-desktop-database")
    if upd:
        try:
            subprocess.run([upd, _desktop_dir()], capture_output=True, timeout=15)
        except Exception:
            pass
    return done

def _linux_unregister() -> list:
    path = desktop_file()
    if os.path.isfile(path):
        try:
            os.remove(path)
            return [f"已删除 {path}（默认程序请到系统设置里改回）"]
        except OSError:
            pass
    return []

def _xdg_query(mime: str) -> str:
    xdg = shutil.which("xdg-mime")
    if not xdg:
        return ""
    try:
        r = subprocess.run([xdg, "query", "default", mime], capture_output=True, timeout=10)
    except Exception:
        return ""
    return r.stdout.decode("utf-8", "replace").strip()

def _set(hive, path: str, name: str, value, kind=None) -> None:
    kind = winreg.REG_SZ if kind is None else kind
    with winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, kind, value)

def _delete_tree(hive, path: str) -> bool:
    try:
        with winreg.OpenKey(hive, path) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(hive, path + "\\" + sub)
        winreg.DeleteKeyEx(hive, path, winreg.KEY_WOW64_64KEY, 0)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False

def _win_register() -> list:
    H = winreg.HKEY_CURRENT_USER
    exe = exe_path()
    cmd = open_command()
    icon = f"{exe},0"
    done = []

    base = f"Software\\Classes\\{PROGID}"
    _set(H, base, "", "音频文件")
    _set(H, base, "FriendlyTypeName", "TuneKuo 音频文件")
    _set(H, f"{base}\\DefaultIcon", "", icon)
    _set(H, f"{base}\\shell\\open\\command", "", cmd)
    _set(H, f"{base}\\shell\\play\\command", "", cmd)
    done.append(f"ProgID {PROGID}")

    app_key = f"Software\\Classes\\Applications\\{os.path.basename(exe)}"
    _set(H, app_key, "FriendlyAppName", "TuneKuo 音乐播放器")
    _set(H, f"{app_key}\\DefaultIcon", "", icon)
    _set(H, f"{app_key}\\shell\\open\\command", "", cmd)
    for ext in EXTS:
        _set(H, f"{app_key}\\SupportedTypes", ext, "")
    done.append(f"打开方式条目 {os.path.basename(exe)}")

    for ext in EXTS:
        _set(H, f"Software\\Classes\\{ext}\\OpenWithProgids", PROGID, b"", winreg.REG_NONE)
        if not has_user_choice(ext):
            _set(H, f"Software\\Classes\\{ext}", "", PROGID)
    done.append(f"{len(EXTS)} 种音频格式")

    cap = f"Software\\{APP_NAME}\\Capabilities"
    _set(H, cap, "ApplicationName", "TuneKuo")
    _set(H, cap, "ApplicationDescription", "TuneKuo 全格式本地音乐播放器")
    _set(H, cap, "ApplicationIcon", icon)
    for ext in EXTS:
        _set(H, f"{cap}\\FileAssociations", ext, PROGID)
    _set(H, "Software\\RegisteredApplications", APP_NAME, f"Software\\{APP_NAME}\\Capabilities")
    done.append("系统默认应用列表（RegisteredApplications）")
    return done

def _win_unregister() -> list:
    H = winreg.HKEY_CURRENT_USER
    removed = []
    if _delete_tree(H, f"Software\\Classes\\{PROGID}"):
        removed.append(f"ProgID {PROGID}")
    exe_name = os.path.basename(exe_path())
    if _delete_tree(H, f"Software\\Classes\\Applications\\{exe_name}"):
        removed.append(f"Applications\\{exe_name}")
    if _delete_tree(H, f"Software\\{APP_NAME}\\Capabilities"):
        removed.append("Capabilities")
    try:
        with winreg.OpenKey(H, "Software\\RegisteredApplications", 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
            removed.append("RegisteredApplications")
    except OSError:
        pass
    for ext in EXTS:
        try:
            with winreg.OpenKey(H, f"Software\\Classes\\{ext}\\OpenWithProgids", 0,
                                winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, PROGID)
        except OSError:
            pass
        try:
            with winreg.OpenKey(H, f"Software\\Classes\\{ext}", 0, winreg.KEY_QUERY_VALUE) as k:
                cur, _ = winreg.QueryValueEx(k, "")
            if cur == PROGID:
                with winreg.OpenKey(H, f"Software\\Classes\\{ext}", 0, winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, "")
        except OSError:
            pass
    return removed

def register() -> list:
    return _win_register() if IS_WIN else _linux_register()

def unregister() -> list:
    return _win_unregister() if IS_WIN else _linux_unregister()

def has_user_choice(ext: str) -> bool:
    if not IS_WIN:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{ext}\\UserChoice") as k:
            pid, _ = winreg.QueryValueEx(k, "ProgId")
            return bool(pid)
    except OSError:
        return False

def default_progid(ext: str) -> str:
    if not IS_WIN:
        return _xdg_query(mime_for(ext))
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{ext}\\UserChoice") as k:
            pid, _ = winreg.QueryValueEx(k, "ProgId")
            if pid:
                return str(pid)
    except OSError:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}") as k:
            return str(winreg.QueryValueEx(k, "")[0] or "")
    except OSError:
        return ""

def is_default_for(ext: str) -> bool:
    cur = default_progid(ext)
    return (cur == PROGID) if IS_WIN else (cur == DESKTOP_ID)

def default_count() -> int:
    return sum(1 for e in EXTS if is_default_for(e))

def open_default_apps_settings() -> None:
    if not IS_WIN:
        return
    try:
        os.startfile("ms-settings:defaultapps")
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:defaultapps"])
        except Exception:
            pass
