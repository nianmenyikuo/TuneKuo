from __future__ import annotations

import os
import sys

APP_NAME = "TuneKuo"

def config_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d

def assets_dir() -> str:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(base, "assets"), os.path.join(os.path.dirname(base), "assets")):
        if os.path.isdir(cand):
            return cand
    return base
