from __future__ import annotations
from applog import swallow

import os
import sys
from typing import List, Optional

LIB_ENV = "PYTHON_VLC_LIB_PATH"
MOD_ENV = "PYTHON_VLC_MODULE_PATH"

_lib_path: Optional[str] = None

def base_dir() -> str:
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
        swallow("vlcenv._is_64bit_dll")
        return False

def posix_setup() -> Optional[str]:
    global _lib_path
    base = base_dir()
    for d in (os.path.join(base, "vlc"), os.path.join(base, "_internal", "vlc"),
              os.path.join(base, "vendor", "vlc"), os.path.join(base, "libvlc")):
        lib = None
        for name in ("libvlc.so.5", "libvlc.so", "libvlc.dylib"):
            cand = os.path.join(d, name)
            if os.path.isfile(cand):
                lib = cand
                break
        if not lib:
            continue
        plug = os.path.join(d, "plugins")
        os.environ[LIB_ENV] = lib
        if os.path.isdir(plug):
            os.environ[MOD_ENV] = plug
            os.environ.setdefault("VLC_PLUGIN_PATH", plug)
        _lib_path = lib
        return lib
    return None

def setup() -> Optional[str]:
    global _lib_path
    if _lib_path:
        return _lib_path
    if os.name != "nt":
        return posix_setup()
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
            swallow("vlcenv.setup")
            pass
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        _lib_path = dll
        return dll
    return None

LIB = setup()
