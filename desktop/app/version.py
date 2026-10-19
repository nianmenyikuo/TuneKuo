from __future__ import annotations

import os
import sys

APP_NAME = "TuneKuo"
FEEDBACK_URL = "https://github.com/nianmenyikuo/TuneKuo/issues/new/choose"


def _roots() -> list:
    out = []
    if getattr(sys, "frozen", False):
        out.append(os.path.dirname(os.path.abspath(sys.executable)))
    out.append(os.path.dirname(os.path.abspath(__file__)))
    return out


def _read_version() -> str:
    for base in _roots():
        cur = base
        for _ in range(5):
            path = os.path.join(cur, "VERSION")
            if os.path.isfile(path):
                try:
                    with open(path, encoding="utf-8") as fp:
                        text = fp.read().strip()
                except OSError:
                    text = ""
                if text:
                    return text
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    return "0.0.0"


VERSION = _read_version()
