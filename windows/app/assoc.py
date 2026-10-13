"""TuneKuo: 注册成 Windows 音频默认播放器（只写 HKCU，无需管理员）。

Windows 10/11 不允许程序静默抢占默认应用（UserChoice 有哈希保护），
这里做的是"完整注册 + 挂进系统默认应用列表"，用户随后在系统设置里点一下即可设为默认；
如果某格式还没有 UserChoice（从未手动指定过），注册后会直接生效。
"""
from __future__ import annotations

import os
import subprocess
import sys
import winreg

PROGID = "TuneKuo.Audio"
APP_NAME = "TuneKuo"

EXTS = [
    ".mp3", ".flac", ".ape", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus",
    ".wma", ".aiff", ".aif", ".dsf", ".dff", ".wv", ".tta", ".tak", ".mka",
    ".ac3", ".dts", ".mpc", ".spx", ".caf", ".mp2", ".m4b",
]


# ------------------------------------------------------------------ 路径
def exe_path() -> str:
    """返回注册用的可执行文件（打包后是 exe，开发态是 pythonw.exe）。"""
    if getattr(sys, "frozen", False):
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
    if getattr(sys, "frozen", False):
        return f'"{exe}" "%1"'
    return f'"{exe}" "{script_path()}" "%1"'


# ------------------------------------------------------------------ 注册表
def _set(hive, path: str, name: str, value, kind=winreg.REG_SZ) -> None:
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


def register() -> list:
    """写入全部注册项，返回已完成的动作说明列表。"""
    H = winreg.HKEY_CURRENT_USER
    exe = exe_path()
    cmd = open_command()
    icon = f"{exe},0"
    done = []

    # 1) ProgID：双击文件时用它找到打开命令
    base = f"Software\\Classes\\{PROGID}"
    _set(H, base, "", "音频文件")
    _set(H, base, "FriendlyTypeName", "TuneKuo 音频文件")
    _set(H, f"{base}\\DefaultIcon", "", icon)
    _set(H, f"{base}\\shell\\open\\command", "", cmd)
    _set(H, f"{base}\\shell\\play\\command", "", cmd)
    done.append(f"ProgID {PROGID}")

    # 2) 应用程序条目：右键"打开方式"里出现 TuneKuo
    app_key = f"Software\\Classes\\Applications\\{os.path.basename(exe)}"
    _set(H, app_key, "FriendlyAppName", "TuneKuo 音乐播放器")
    _set(H, f"{app_key}\\DefaultIcon", "", icon)
    _set(H, f"{app_key}\\shell\\open\\command", "", cmd)
    for ext in EXTS:
        _set(H, f"{app_key}\\SupportedTypes", ext, "")
    done.append(f"打开方式条目 {os.path.basename(exe)}")

    # 3) 扩展名：OpenWithProgids + 无 UserChoice 时直接设为默认
    for ext in EXTS:
        _set(H, f"Software\\Classes\\{ext}\\OpenWithProgids", PROGID, b"", winreg.REG_NONE)
        if not has_user_choice(ext):
            _set(H, f"Software\\Classes\\{ext}", "", PROGID)
    done.append(f"{len(EXTS)} 种音频格式")

    # 4) 系统"默认应用"里可选中
    cap = f"Software\\{APP_NAME}\\Capabilities"
    _set(H, cap, "ApplicationName", "TuneKuo")
    _set(H, cap, "ApplicationDescription", "TuneKuo 全格式本地音乐播放器")
    _set(H, cap, "ApplicationIcon", icon)
    for ext in EXTS:
        _set(H, f"{cap}\\FileAssociations", ext, PROGID)
    _set(H, "Software\\RegisteredApplications", APP_NAME, f"Software\\{APP_NAME}\\Capabilities")
    done.append("系统默认应用列表（RegisteredApplications）")
    return done


def unregister() -> list:
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


def has_user_choice(ext: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\{ext}\\UserChoice") as k:
            pid, _ = winreg.QueryValueEx(k, "ProgId")
            return bool(pid)
    except OSError:
        return False


def default_progid(ext: str) -> str:
    """返回该扩展名当前生效的 ProgID（用户选择优先）。"""
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
    return default_progid(ext) == PROGID


def default_count() -> int:
    return sum(1 for e in EXTS if is_default_for(e))


def open_default_apps_settings() -> None:
    """打开系统"默认应用"页，用户点一下 TuneKuo 即可设为默认。"""
    try:
        os.startfile("ms-settings:defaultapps")
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:defaultapps"])
        except Exception:
            pass
