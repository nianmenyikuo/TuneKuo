from __future__ import annotations

import ctypes
import os
import threading
from typing import Callable, Optional

ON_WINDOWS = os.name == "nt"
if ON_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
else:
    wintypes = None
    user32 = None

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

_ACTIONS = {
    1: ("prev", VK_MEDIA_PREV_TRACK),
    2: ("play_pause", VK_MEDIA_PLAY_PAUSE),
    3: ("stop", VK_MEDIA_STOP),
    4: ("next", VK_MEDIA_NEXT_TRACK),
}

class MediaKeys(threading.Thread):

    def __init__(self, callback: Callable[[str], None]):
        super().__init__(name="MediaKeys", daemon=True)
        self.callback = callback
        self.registered: list = []
        self._stop = False

    def run(self) -> None:
        for hid, (action, vk) in _ACTIONS.items():
            try:
                if user32.RegisterHotKey(None, hid, MOD_NOREPEAT, vk):
                    self.registered.append(action)
            except Exception:
                pass
        if not self.registered:
            return
        msg = wintypes.MSG()
        while not self._stop:
            try:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            except Exception:
                break
            if ret in (0, -1):
                break
            if msg.message == WM_HOTKEY:
                act = _ACTIONS.get(int(msg.wParam))
                if act:
                    try:
                        self.callback(act[0])
                    except Exception:
                        pass
            try:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            except Exception:
                pass

    def stop(self) -> None:
        self._stop = True
        for hid in list(_ACTIONS):
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception:
                pass
        try:
            user32.PostThreadMessageW(self.ident, 0x0012, 0, 0)
        except Exception:
            pass

def available() -> bool:
    return ON_WINDOWS
