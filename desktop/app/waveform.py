from __future__ import annotations

import tkinter as tk

WAVE_BG = "#222222"
WAVE_DIM = "#B0B0B0"
WAVE_ON = "#FFFFFF"
WAVE_POS = "#00A8FF"
STEP = 3
BAR_MIN = 0.06


class Waveform(tk.Canvas):
    def __init__(self, master, on_seek=None, height=140, **kw):
        super().__init__(master, bg=WAVE_BG, bd=0, highlightthickness=0, height=height, **kw)
        self.peaks = []
        self.progress = 0.0
        self.on_seek = on_seek
        self._bars = []
        self._pos = None
        self._last = -1
        self._dragging = False
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)

    def set_peaks(self, peaks) -> None:
        self.peaks = [float(p) for p in (peaks or [])]
        self.redraw()

    def set_progress(self, ratio) -> None:
        try:
            r = float(ratio)
        except (TypeError, ValueError):
            return
        r = 0.0 if r < 0.0 else (1.0 if r > 1.0 else r)
        if abs(r - self.progress) < 0.0008:
            return
        self.progress = r
        self._move_pos()

    def redraw(self) -> None:
        self.delete("all")
        self._bars = []
        self._pos = None
        self._last = -1
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 8 or h < 8:
            return
        n = max(1, w // STEP)
        bw = max(1, STEP - 1)
        half = h / 2.0
        vals = self.peaks
        for i in range(n):
            x = i * STEP + bw / 2.0
            a = vals[int(i * len(vals) / n)] if vals else BAR_MIN
            amp = max(BAR_MIN, min(1.0, a)) ** 0.9
            dy = half * amp * 0.92
            self._bars.append(self.create_line(x, half - dy, x, half + dy,
                                               width=bw, fill=WAVE_DIM, tags="bar"))
        self._pos = self.create_line(0, half, 0, half, fill=WAVE_POS, width=2, tags="pos")
        self._move_pos()

    def _move_pos(self) -> None:
        if not self._bars or self._pos is None:
            return
        idx = int(self.progress * len(self._bars))
        if idx != self._last:
            lo = min(self._last, idx) if self._last >= 0 else 0
            hi = max(self._last, idx)
            for i in range(max(0, lo), min(len(self._bars), hi)):
                self.itemconfigure(self._bars[i], fill=WAVE_ON if i < idx else WAVE_DIM)
            self._last = idx
        x = self.progress * self.winfo_width()
        self.coords(self._pos, x, 0, x, self.winfo_height())

    def _ratio(self, x) -> float:
        w = self.winfo_width()
        if w <= 0:
            return 0.0
        return max(0.0, min(1.0, float(x) / w))

    def _press(self, event) -> None:
        self._dragging = True
        self.set_progress(self._ratio(event.x))
        self._move_pos()

    def _motion(self, event) -> None:
        if not self._dragging:
            return
        self.set_progress(self._ratio(event.x))
        self._move_pos()

    def _release(self, event) -> None:
        if not self._dragging:
            return
        self._dragging = False
        ratio = self._ratio(event.x)
        self.set_progress(ratio)
        self._move_pos()
        if self.on_seek:
            self.on_seek(ratio)
