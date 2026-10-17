from __future__ import annotations

import io
import os
import sys
import tarfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.join(ROOT, "app")
sys.path.insert(0, APP)

import assoc
from version import APP_NAME, VERSION

PKG = "tunekuo"
ARCH = "all"                              
LIBDIR = "/usr/share/tunekuo"
ICONDIR = "/usr/share/icons/hicolor/256x256/apps"
MAINTAINER = "nianmenyikuo <nianmenyikuo@users.noreply.github.com>"
HOMEPAGE = "https://github.com/nianmenyikuo/TuneKuo"
DEPENDS = "python3 (>= 3.9), python3-tk, python3-vlc, vlc-plugin-base"
RECOMMENDS = "python3-pil"     

LAUNCHER = f"""#!/bin/sh
# TuneKuo 启动器：用系统的 python3 跑 {LIBDIR}/main.py
exec python3 {LIBDIR}/main.py "$@"
"""

COPYRIGHT = f"""TuneKuo {VERSION} —— 基于 libVLC 的本地音乐播放器。

本包安装的是 Python 源码（{LIBDIR}）与启动器，不含 Python 解释器、
不含 libvlc；运行时用系统装的 python3 / python3-vlc / vlc-plugin-base。

上游项目：{HOMEPAGE}
"""

def desktop_entry() -> str:
    mimes = ";".join(assoc.mimes()) + ";"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"GenericName=Music Player\n"
        f"Name[zh_CN]={APP_NAME} 音乐播放器\n"
        "Comment=本地音乐播放器（全格式）\n"
        "Comment[en]=Local music player (all formats)\n"
        "Exec=/usr/bin/tunekuo %F\n"
        f"Icon={PKG}\n"
        "Terminal=false\n"
        "Categories=AudioVideo;Audio;Player;\n"
        f"MimeType={mimes}\n"
    )

def payload() -> list[tuple[str, bytes, int]]:
    out: list[tuple[str, bytes, int]] = [
        ("./usr/bin/tunekuo", LAUNCHER.encode("utf-8"), 0o755),
        ("./usr/share/applications/tunekuo.desktop", desktop_entry().encode("utf-8"), 0o644),
        ("./usr/share/doc/tunekuo/copyright", COPYRIGHT.encode("utf-8"), 0o644),
    ]
    icon = os.path.join(APP, "assets", "icon.png")
    with open(icon, "rb") as fp:
        out.append((f"./usr/share/icons/hicolor/256x256/apps/{PKG}.png", fp.read(), 0o644))
        out.append((f".{LIBDIR}/assets/icon.png", out[-1][1], 0o644))
    for name in sorted(os.listdir(APP)):
        if name.endswith(".py"):
            with open(os.path.join(APP, name), "rb") as fp:
                out.append((f".{LIBDIR}/{name}", fp.read(), 0o644))
    return out

def tar_gz(entries: list[tuple[str, bytes, int]]) -> bytes:
    dirs: dict[str, int] = {}
    for name, _, _ in entries:
        parts = name.split("/")[1:-1]              
        for i in range(1, len(parts) + 1):
            dirs.setdefault("./" + "/".join(parts[:i]) + "/", 0o755)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.GNU_FORMAT) as tf:
        for name in sorted(dirs):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            info.mode = dirs[name]
            info.mtime = int(time.time())
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tf.addfile(info)
        for name, blob, mode in entries:
            info = tarfile.TarInfo(name)
            info.size = len(blob)
            info.mode = mode
            info.mtime = int(time.time())
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tf.addfile(info, io.BytesIO(blob))
    return buf.getvalue()

def ar_pack(members: list[tuple[str, bytes]]) -> bytes:
    out = bytearray(b"!<arch>\n")
    for name, blob in members:
        header = (
            name.ljust(16)
            + str(int(time.time())).ljust(12)
            + "0".ljust(6)          
            + "0".ljust(6)          
            + "100644".ljust(8)
            + str(len(blob)).ljust(10)
            + "`\n"
        )
        assert len(header) == 60, len(header)
        out += header.encode("ascii") + blob
        if len(blob) % 2:
            out += b"\n"            
    return bytes(out)

def control_text(installed_kb: int) -> str:
    return (
        f"Package: {PKG}\n"
        f"Version: {VERSION}\n"
        f"Architecture: {ARCH}\n"
        f"Maintainer: {MAINTAINER}\n"
        f"Installed-Size: {installed_kb}\n"
        f"Depends: {DEPENDS}\n"
        f"Recommends: {RECOMMENDS}\n"
        f"Section: sound\n"
        f"Priority: optional\n"
        f"Homepage: {HOMEPAGE}\n"
        "Description: local music player with all-format support\n"
        " TuneKuo is a local music player built on libVLC. It plays\n"
        " mp3/flac/ape/wav/m4a/dsf/dff and 18 more formats, can register\n"
        " itself as the system default player, and its interface speaks\n"
        " Chinese, English and Japanese.\n"
    )

def main() -> int:
    out_dir = os.path.join(ROOT, "dist-linux")
    argv = sys.argv[1:]
    if "--desktop" in argv:            
        print(desktop_entry(), end="")
        return 0
    if "-o" in argv:
        out_dir = argv[argv.index("-o") + 1]
    os.makedirs(out_dir, exist_ok=True)

    data = payload()
    installed_kb = (sum(len(b) for _, b, _ in data) + 1023) // 1024
    control = tar_gz([
        ("./control", control_text(installed_kb).encode("utf-8"), 0o644),
    ])
    data_tar = tar_gz(data)
    deb = ar_pack([
        ("debian-binary", b"2.0\n"),
        ("control.tar.gz", control),
        ("data.tar.gz", data_tar),
    ])

    name = f"{APP_NAME}-{VERSION}-{ARCH}.deb"
    path = os.path.join(out_dir, name)
    with open(path, "wb") as fp:
        fp.write(deb)

    assert deb[:8] == b"!<arch>\n"
    assert deb.count(b"debian-binary") == 1
    with tarfile.open(fileobj=io.BytesIO(data_tar), mode="r:gz") as tf:
        names = tf.getnames()
    assert f".{LIBDIR}/main.py" in names and f".{LIBDIR}/paths.py" in names
    assert "./usr/bin/tunekuo" in names
    assert f"./usr/share/icons/hicolor/256x256/apps/{PKG}.png" in names
    assert "./usr/share/doc/tunekuo" in names           
    assert "./usr/share/tunekuo/assets" in names        

    print(f"输出      : {path}")
    print(f"大小      : {len(deb):,} B")
    print(f"纯 Python : {installed_kb} KB 已安装（不含 python/libvlc）")
    print(f"文件数    : {len(data)}")
    print("顶层      : debian-binary + control.tar.gz + data.tar.gz")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
