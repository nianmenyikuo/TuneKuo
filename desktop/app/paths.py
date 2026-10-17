"""跨平台路径：配置目录、界面资源目录。

- 配置目录：Windows 用 %APPDATA%\\TuneKuo；Linux/macOS 用 XDG 配置目录（~/.config/TuneKuo）。
  自检脚本 ui_test.py 会把 APPDATA 指到临时目录，所以 Windows 上 APPDATA 优先。
- 资源目录：开发态是 app/assets，PyInstaller 打包后在解包目录旁边。
"""
from __future__ import annotations

import os
import sys

APP_NAME = "TuneKuo"


def config_dir() -> str:
    """配置目录（不存在就建）。"""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def assets_dir() -> str:
    """图标等资源所在目录。"""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(base, "assets"), os.path.join(os.path.dirname(base), "assets")):
        if os.path.isdir(cand):
            return cand
    return base
