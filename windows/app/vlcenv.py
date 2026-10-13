"""定位可用的 64 位 libvlc，并设置 python-vlc 认得的两个环境变量。

必须在 `import vlc` 之前被导入（player.py 顶部就 import 本模块）。
查找顺序：
    1. 随程序一起打包的 vlc\\            （PyInstaller onedir: exe 同级 或 _internal\\vlc）
    2. 开发目录 vendor\\vlc64\\          （scripts\\fetch_vlc.ps1 下载的 64 位 VLC）
    3. 系统安装的 64 位 VLC              （Program Files\\VideoLAN\\VLC）
注意：Program Files (x86) 里的 VLC 是 32 位，64 位 Python 载入不了，故意跳过。
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional

LIB_ENV = "PYTHON_VLC_LIB_PATH"
MOD_ENV = "PYTHON_VLC_MODULE_PATH"

_lib_path: Optional[str] = None


def base_dir() -> str:
    """打包后是 exe 所在目录，开发时是项目根目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def candidates() -> List[str]:
    base = base_dir()
    out = [
        os.path.join(base, "vlc"),
        os.path.join(base, "_internal", "vlc"),
        os.path.join(base, "vendor", "vlc64"),
        os.path.join(base, "libvlc"),
    ]
    for pf in (os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles")):
        if pf:
            out.append(os.path.join(pf, "VideoLAN", "VLC"))
    return out


def _is_64bit_dll(path: str) -> bool:
    try:
        with open(path, "rb") as fp:
            head = fp.read(0x100)
        if head[:2] != b"MZ":
            return False
        import struct

        off = struct.unpack_from("<I", head, 0x3C)[0]
        with open(path, "rb") as fp:
            fp.seek(off)
            sig = fp.read(6)
        if sig[:4] != b"PE\0\0":
            return False
        return struct.unpack_from("<H", sig, 4)[0] == 0x8664
    except Exception:
        return False


def setup() -> Optional[str]:
    """设置环境变量并返回 libvlc.dll 路径；找不到返回 None。"""
    global _lib_path
    if _lib_path:
        return _lib_path
    if os.name != "nt":
        return None
    for d in candidates():
        dll = os.path.join(d, "libvlc.dll")
        if not os.path.isfile(dll):
            continue
        if "Program Files (x86)" in d or not _is_64bit_dll(dll):
            continue
        plug = os.path.join(d, "plugins")
        os.environ[LIB_ENV] = dll
        if os.path.isdir(plug):
            os.environ[MOD_ENV] = plug
            os.environ.setdefault("VLC_PLUGIN_PATH", plug)
        try:
            os.add_dll_directory(d)
        except Exception:
            pass
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        _lib_path = dll
        return dll
    return None


LIB = setup()
