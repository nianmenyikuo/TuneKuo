from __future__ import annotations
from applog import log_file, swallow

import io
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

import assoc
import online
import paths
from i18n import LANGS, TEXT as I18N_TEXT, current_language, set_language, t as tr
from library import MetaLoader, default_roots, scan_paths
from metadata import parse_lrc
from player import PlayMode, Player, Track, fmt_time
from version import APP_NAME, FEEDBACK_URL, VERSION
from waveform import WAVE_BG, Waveform
import peaks

HINTS = {s for s in I18N_TEXT["tool.search_hint"]}


def _reveal_cmd(path: str) -> list:
    if os.name == "nt":
        return ["explorer", f"/select,{path}"]
    opener = shutil.which("xdg-open") or shutil.which("open")
    return [opener, os.path.dirname(path)] if opener else []

try:
    from PIL import Image, ImageTk

    HAS_PIL = True
except Exception:
    swallow("ui")
    HAS_PIL = False

BG = "#14141E"
PANEL = "#191925"
CARD = "#1E1E2B"
CARD_HI = "#2C4A5F"
LINE = "#2A2A3A"
FG = "#FFFFFF"
FG_DIM = "#A9A9BE"
ACCENT = "#60CDFF"
ACCENT_D = "#1E6E96"
ON_ACCENT = "#002A3D"
GREEN = "#6CCB5F"

SCAN_MIN_S = 1.6
SCAN_TIP_MS = 2600
SCAN_TIP_COUNT = 10

UI_FONT = "Microsoft YaHei UI"
ICON_FONT = "Segoe MDL2 Assets"

if os.name == "nt":
    GLYPH_PLAY = "\uE768"
    GLYPH_PAUSE = "\uE769"
    GLYPH_PREV = "\uE892"
    GLYPH_NEXT = "\uE893"
    GLYPH_VOL = "\uE767"
    GLYPH_MUTE = "\uE74F"
    GLYPH_MUSIC = "\uE8D6"
    GLYPH_SEARCH = "\uE721"
else:
    GLYPH_PLAY = "▶"
    GLYPH_PAUSE = "▮▮"
    GLYPH_PREV = "◀◀"
    GLYPH_NEXT = "▶▶"
    GLYPH_VOL = "♪"
    GLYPH_MUTE = "✕"
    GLYPH_MUSIC = "♪"
    GLYPH_SEARCH = ""

def _shift(color: str, amount: int) -> str:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % (
        max(0, min(255, r + amount)),
        max(0, min(255, g + amount)),
        max(0, min(255, b + amount)),
    )

def _colorref(color: str) -> int:
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    return (b << 16) | (g << 8) | r

def apply_win_style(root: tk.Tk) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        for attr in (20, 19):
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value),
                                                       ctypes.sizeof(value))
        corner = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner),
                                                   ctypes.sizeof(corner))
        for attr, color in ((35, BG), (36, FG), (34, LINE)):
            value = ctypes.c_int(_colorref(color))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value),
                                                       ctypes.sizeof(value))
    except Exception:
        swallow("ui.apply_win_style")

def state_dir() -> str:
    return paths.config_dir()

STATE_FILE = os.path.join(state_dir(), "state.json")
MAX_STATE_TRACKS = 3000

def human_size(n: int) -> str:
    if not n or n <= 0:
        return "-"
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return "-"

def assets_dir() -> str:
    return paths.assets_dir()

def _pick_fonts() -> None:
    global UI_FONT, ICON_FONT
    try:
        from tkinter import font as tkfont

        families = set(tkfont.families())
    except Exception:
        swallow("ui._pick_fonts")
        return
    if os.name == "nt":
        for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if name in families:
                ICON_FONT = name
                break
        if UI_FONT not in families and "Microsoft YaHei" in families:
            UI_FONT = "Microsoft YaHei"
        return
    for name in ("Noto Sans CJK SC", "Source Han Sans SC", "Noto Sans SC",
                 "WenQuanYi Micro Hei", "Noto Sans", "DejaVu Sans"):
        if name in families:
            UI_FONT = name
            break
    for name in ("DejaVu Sans", "Noto Sans", "FreeSans", UI_FONT):
        if name in families:
            ICON_FONT = name
            break

class TuneKuoUI:
    def __init__(self, root: tk.Tk, initial_paths: Optional[List[str]] = None):
        self.root = root
        self.evq: "queue.Queue" = queue.Queue()
        self.view: List[int] = []
        self.lrc_lines = []
        self.lrc_line_no: List[int] = []
        self.seeking = False
        self.current_lyric = -1
        self._cover_photo = None
        self._idx_by_id = {}
        self.gen = 0

        self.player = Player(on_event=self._vlc_event)
        self.loader = MetaLoader(on_loaded=self._meta_loaded)

        _pick_fonts()
        self._build_style()
        self._build_ui()

        self.mediakeys = None
        try:
            import mediakeys

            if mediakeys.available():
                self.mediakeys = mediakeys.MediaKeys(lambda a: self.evq.put(("key", a, None)))
                self.mediakeys.start()
        except Exception:
            swallow("ui.TuneKuoUI.__init__")
            self.mediakeys = None

        self.load_state()
        self._update_mode_button()
        self._refresh_default_status()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(120, self._tick)

        paths = [p for p in (initial_paths or []) if p]
        if paths:
            self.add_paths(paths, autoplay=True)

    def _build_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            swallow("ui.TuneKuoUI._build_style")
            pass
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG,
                        rowheight=34, borderwidth=0, font=(UI_FONT, 10))
        style.configure("Treeview.Heading", background=BG, foreground=FG_DIM,
                        relief="flat", borderwidth=0, font=(UI_FONT, 9))
        style.map("Treeview", background=[("selected", CARD_HI)], foreground=[("selected", FG)])
        style.map("Treeview.Heading", background=[("active", BG)])
        style.configure("TScrollbar", background=LINE, troughcolor=PANEL, bordercolor=PANEL,
                        arrowcolor=FG_DIM, relief="flat", arrowsize=12, width=10)
        style.configure("TScale", background=PANEL, troughcolor=LINE, borderwidth=0,
                        lightcolor=ACCENT, darkcolor=ACCENT, gripcount=0)
        style.configure("Search.TEntry", fieldbackground=CARD, foreground=FG, borderwidth=0,
                        insertcolor=FG)

    def _btn(self, parent, text, command, *, icon=False, width=None, bg=CARD, fg=FG,
             font_size=10, padx=12, pady=6):
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                      activebackground=_shift(bg, -16), activeforeground=fg,
                      relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                      padx=padx, pady=pady,
                      font=(ICON_FONT if icon else UI_FONT, font_size))
        b.bind("<Enter>", lambda e: b.config(bg=_shift(bg, 14)))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
        if width:
            b.config(width=width)
        return b

    def _build_ui(self) -> None:
        r = self.root
        r.configure(bg=BG)
        r.title("TuneKuo")
        r.geometry("1100x720")
        r.minsize(880, 560)
        apply_win_style(r)
        icon = os.path.join(assets_dir(), "icon.ico" if os.name == "nt" else "icon.png")
        if os.path.isfile(icon):
            try:
                if os.name == "nt":
                    r.iconbitmap(icon)
                else:
                    r.iconphoto(True, tk.PhotoImage(file=icon))
            except Exception:
                swallow("ui.TuneKuoUI._build_ui")
                pass

        self.offset = 0.0
        self._anim = None
        self._dragging = False
        self._press_ok = False
        self._press_x = 0
        self._press_off = 0.0
        self._tip_win = None
        self.page_main = tk.Frame(r, bg=BG)
        self.page_settings = tk.Frame(r, bg=BG)
        for page in (self.page_main, self.page_settings):
            page.place(x=0, y=0, relwidth=1, relheight=1)
        main = self.page_main
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)

        top = tk.Frame(main, bg=BG)
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        tk.Label(top, text="TuneKuo", bg=BG, fg=FG, font=(UI_FONT, 18, "bold")).pack(side="left")
        self.lb_count = tk.Label(top, text="", bg=BG, fg=FG_DIM, font=(UI_FONT, 9))
        self.lb_count.pack(side="left", padx=(10, 16))

        self.btn_add_files = self._btn(top, tr("tool.add_files"), self.choose_files)
        self.btn_add_files.pack(side="left", padx=3)
        self.btn_add_folder = self._btn(top, tr("tool.add_folder"), self.choose_folder)
        self.btn_add_folder.pack(side="left", padx=3)
        self.btn_scan = self._btn(top, tr("tool.scan_library"), self.scan_library)
        self.btn_scan.pack(side="left", padx=3)

        right_box = tk.Frame(top, bg=BG)
        right_box.pack(side="right")
        self.btn_settings = self._btn(right_box, tr("tool.settings"), self.show_settings)
        self.btn_settings.pack(side="right", padx=(6, 0))
        self._tip(self.btn_settings, "tip.settings")
        self.btn_default = self._btn(right_box, tr("tool.set_default"),
                                     self.register_default, bg=ACCENT_D, fg="#FFFFFF")
        self.btn_default.pack(side="right", padx=(6, 0))
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *_: self.apply_filter())
        ent = tk.Entry(right_box, textvariable=self.var_search, bg=CARD, fg=FG, bd=0,
                       highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT,
                       insertbackground=FG, font=(UI_FONT, 10), width=26)
        ent.pack(side="right", padx=(0, 6), ipady=6, ipadx=8)
        self.search_entry = ent
        self._placeholder = False
        ent.bind("<FocusIn>", self._search_focus_in, add="+")
        ent.bind("<FocusOut>", self._search_focus_out, add="+")
        if GLYPH_SEARCH:
            tk.Label(right_box, text=GLYPH_SEARCH, bg=BG, fg=FG_DIM,
                     font=(ICON_FONT, 12)).pack(side="right", padx=(0, 6))

        tk.Frame(main, bg=LINE, height=1).grid(row=1, column=0, sticky="ew", padx=14)
        body = tk.Frame(main, bg=BG)
        body.grid(row=2, column=0, sticky="nsew", padx=14, pady=(10, 0))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2, minsize=340)

        left = tk.Frame(body, bg=PANEL)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        cols = ("title", "artist", "album", "time")
        self._tree_cols = (("title", "col.title", 300, "w"), ("artist", "col.artist", 170, "w"),
                           ("album", "col.album", 170, "w"), ("time", "col.time", 70, "e"))
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c, key, w, anchor in self._tree_cols:
            self.tree.heading(c, text=tr(key))
            self.tree.column(c, width=w, anchor=anchor, stretch=(c == "title"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", self.on_row_play)
        self.tree.bind("<Return>", self.on_row_play)
        self.tree.bind("<Button-3>", self.on_row_menu)
        self.tree.tag_configure("playing", foreground=ACCENT)

        self.scan_box = tk.Frame(left, bg=PANEL)
        self.scan_inner = tk.Frame(self.scan_box, bg=PANEL)
        self.scan_canvas = tk.Canvas(self.scan_inner, width=68, height=68, bg=PANEL,
                                     highlightthickness=0)
        self.scan_canvas.pack()
        self._scan_arc = self.scan_canvas.create_arc(7, 7, 61, 61, start=0, extent=245,
                                                     style="arc", outline=ACCENT, width=3)
        self.lb_scan_tip = tk.Label(self.scan_inner, bg=PANEL, fg=FG_DIM, font=(UI_FONT, 10),
                                    wraplength=320, justify="center")
        self.lb_scan_tip.pack(pady=(16, 0))

        right = tk.Frame(body, bg=PANEL)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.cover = tk.Canvas(right, bg=PANEL, height=260, highlightthickness=0)
        self.cover.grid(row=0, column=0, sticky="ew", pady=(14, 8))
        self.cover.bind("<Configure>", lambda e: self._render_cover())
        self.cover.bind("<Button-1>", lambda e: self.show_now())
        self.cover.configure(cursor="hand2")

        self.lb_now = tk.Label(right, text=tr("not_playing"), bg=PANEL, fg=FG, font=(UI_FONT, 12, "bold"),
                               wraplength=320, justify="center")
        self.lb_now.grid(row=1, column=0, sticky="ew", padx=14)
        self.lb_now_sub = tk.Label(right, text="", bg=PANEL, fg=FG_DIM, font=(UI_FONT, 9))
        self.lb_now_sub.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 8))

        self.lyric_text = tk.Text(right, bg=PANEL, fg=FG_DIM, bd=0, highlightthickness=0,
                                  wrap="word", font=(UI_FONT, 10), cursor="hand2",
                                  padx=14, pady=6, spacing1=2, spacing3=4)
        self.lyric_text.grid(row=3, column=0, sticky="nsew", padx=(6, 0))
        self.lyric_text.tag_configure("cur", foreground=ACCENT, font=(UI_FONT, 12, "bold"))
        self.lyric_text.tag_configure("other", foreground=FG_DIM, font=(UI_FONT, 10))
        self.lyric_text.tag_configure("plain", foreground="#E5E5E5", font=(UI_FONT, 10))
        self.lyric_text.bind("<Button-1>", self.on_lyric_click)
        self.lyric_text.configure(state="disabled")
        lsb = ttk.Scrollbar(right, orient="vertical", command=self.lyric_text.yview)
        lsb.grid(row=3, column=1, sticky="ns")
        self.lyric_text.configure(yscrollcommand=lsb.set)

        self.page_body = body
        self.now_open = False
        self._peaks_pending = set()
        self.page_now = tk.Frame(body, bg=WAVE_BG)
        now_head = tk.Frame(self.page_now, bg=WAVE_BG)
        now_head.pack(fill="x", padx=14, pady=(14, 6))
        self.btn_now_back = self._btn(now_head, tr("settings.back"), self.hide_now)
        self.btn_now_back.pack(side="left")
        self.lb_now_title = tk.Label(now_head, text=tr("now.title"), bg=WAVE_BG, fg=FG,
                                     font=(UI_FONT, 18, "bold"))
        self.lb_now_title.pack(side="left", padx=(12, 0))

        stage = tk.Frame(self.page_now, bg=WAVE_BG)
        stage.pack(expand=True, fill="both")
        inner = tk.Frame(stage, bg=WAVE_BG)
        inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=1)
        self.lb_big = tk.Label(inner, text=tr("not_playing"), bg=WAVE_BG, fg=FG,
                               font=(UI_FONT, 22, "bold"), wraplength=640, justify="center")
        self.lb_big.pack()
        self.lb_big_sub = tk.Label(inner, text="", bg=WAVE_BG, fg=FG_DIM, font=(UI_FONT, 11))
        self.lb_big_sub.pack(pady=(6, 0))
        self.wave = Waveform(inner, on_seek=self.seek_ratio, height=190)
        self.wave.pack(fill="x", padx=60, pady=(26, 12))
        self.lb_big_time = tk.Label(inner, text="0:00", bg=WAVE_BG, fg=FG_DIM, font=(UI_FONT, 10))
        self.lb_big_time.pack()

        bottom = tk.Frame(main, bg=PANEL)
        bottom.grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 12))
        tk.Frame(main, bg=LINE, height=1).grid(row=3, column=0, sticky="ew", padx=14, pady=(10, 10))
        bottom.grid_columnconfigure(1, weight=1)

        self.lb_time = tk.Label(bottom, text="0:00", bg=PANEL, fg=FG_DIM, font=(UI_FONT, 9), width=6, anchor="e")
        self.lb_time.grid(row=0, column=0, padx=(12, 8), pady=(10, 0))
        self.seek = ttk.Scale(bottom, from_=0, to=1000, orient="horizontal", command=self.on_seek_drag)
        self.seek.grid(row=0, column=1, columnspan=4, sticky="ew", pady=(10, 0))
        self.seek.bind("<ButtonPress-1>", lambda e: setattr(self, "seeking", True))
        self.seek.bind("<ButtonRelease-1>", self.on_seek_release)
        self.lb_len = tk.Label(bottom, text="--:--", bg=PANEL, fg=FG_DIM, font=(UI_FONT, 9), width=6, anchor="w")
        self.lb_len.grid(row=0, column=5, padx=(8, 12), pady=(10, 0))

        ctl = tk.Frame(bottom, bg=PANEL)
        ctl.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(6, 10))
        self.btn_mode = self._btn(ctl, tr(f"mode.{PlayMode.REPEAT_LIST}"), self.cycle_mode, width=10, pady=4)
        self.btn_mode.pack(side="left", padx=(12, 8))
        self.btn_prev = self._btn(ctl, GLYPH_PREV, self.player.prev_manual, icon=True, font_size=15, padx=10, pady=2)
        self.btn_prev.pack(side="left", padx=2)
        self.btn_play = self._btn(ctl, GLYPH_PLAY, self.toggle_play, icon=True, font_size=18,
                                  bg=ACCENT, fg=ON_ACCENT, padx=18, pady=4)
        self.btn_play.pack(side="left", padx=2)
        self.btn_next = self._btn(ctl, GLYPH_NEXT, self.player.next_manual, icon=True, font_size=15, padx=10, pady=2)
        self.btn_next.pack(side="left", padx=2)
        self.btn_wave = self._btn(ctl, GLYPH_MUSIC, self.show_now, icon=True, font_size=14,
                                  padx=10, pady=2)
        self.btn_wave.pack(side="left", padx=2)
        for widget, key in ((self.btn_mode, "tip.mode"), (self.btn_prev, "tip.prev"),
                            (self.btn_play, "tip.play"), (self.btn_next, "tip.next"),
                            (self.btn_wave, "tip.wave")):
            self._tip(widget, key)

        self.lb_status = tk.Label(ctl, text=tr("status.ready"), bg=PANEL, fg=FG_DIM, font=(UI_FONT, 9))
        self.lb_status.pack(side="left", padx=14)

        vol_box = tk.Frame(ctl, bg=PANEL)
        vol_box.pack(side="right", padx=12)
        self.btn_vol = self._btn(vol_box, GLYPH_VOL, self.toggle_mute, icon=True, font_size=12, padx=6, pady=2)
        self.btn_vol.pack(side="left")
        self._tip(self.btn_vol, "tip.volume")
        self.vol = ttk.Scale(vol_box, from_=0, to=100, orient="horizontal", length=120,
                             command=self.on_volume)
        self.vol.set(80)
        self.vol.pack(side="left", padx=(4, 0))

        r.bind("<space>", self._on_space)
        r.bind("<Control-o>", lambda e: self.choose_files())
        r.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        self._esc_orig = self.on_escape
        r.bind("<Escape>", self._on_escape_now)
        r.bind("<Left>", lambda e: self._on_arrow(-5000))
        r.bind("<Right>", lambda e: self._on_arrow(5000))
        r.bind("<Control-l>", lambda e: self.focus_lyrics())
        r.bind("<Configure>", self._on_configure, add="+")

        self._build_settings_page()
        self._apply_slide()
        self.root.after(50, self._apply_slide)
        self._retranslate()
        self.root.bind_all("<ButtonPress-1>", self._drag_press, add="+")
        self.root.bind_all("<B1-Motion>", self._drag_motion, add="+")
        self.root.bind_all("<ButtonRelease-1>", self._drag_release, add="+")

    def _build_settings_page(self) -> None:
        page = self.page_settings
        page.grid_rowconfigure(1, weight=1)
        page.grid_columnconfigure(0, weight=1)

        head = tk.Frame(page, bg=BG)
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
        self.btn_back = self._btn(head, tr("settings.back"), self.show_main)
        self.btn_back.pack(side="left")
        self._tip(self.btn_back, "tip.back")
        self.lb_settings_title = tk.Label(head, text=tr("settings.title"), bg=BG, fg=FG,
                                          font=(UI_FONT, 18, "bold"))
        self.lb_settings_title.pack(side="left", padx=(12, 0))

        box = tk.Frame(page, bg=PANEL)
        box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 10))
        self.lb_lang_group = tk.Label(box, text=tr("settings.language"), bg=PANEL, fg=FG_DIM,
                                      font=(UI_FONT, 10, "bold"))
        self.lb_lang_group.pack(anchor="w", padx=16, pady=(14, 4))

        self.lang_labels = {}
        for code, native in LANGS:
            lb = tk.Label(box, text=native, bg=PANEL, fg=FG, font=(UI_FONT, 12), anchor="w",
                          cursor="hand2", padx=12, pady=8)
            lb.pack(fill="x", padx=16, pady=2)
            lb.bind("<Button-1>", lambda e, c=code: self.set_lang(c), add="+")
            self.lang_labels[code] = lb

        self.lb_feedback = tk.Label(box, text=tr("settings.feedback"), bg=PANEL, fg=ACCENT,
                                    font=(UI_FONT, 10, "underline"), anchor="w", cursor="hand2")
        self.lb_feedback.pack(fill="x", padx=16, pady=(18, 6))
        self.lb_feedback.bind("<Button-1>", lambda e: self.open_feedback(), add="+")

        self.lb_log = tk.Label(box, text=tr("settings.log"), bg=PANEL, fg=FG_DIM,
                               font=(UI_FONT, 10, "underline"), anchor="w", cursor="hand2")
        self.lb_log.pack(fill="x", padx=16, pady=(0, 14))
        self.lb_log.bind("<Button-1>", lambda e: self.open_log(), add="+")

        self.lb_version = tk.Label(page, text=f"{APP_NAME} {VERSION}", bg=BG, fg=FG_DIM,
                                   font=(UI_FONT, 9), anchor="w")
        self.lb_version.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 14))
        self._apply_lang_highlight()

    def _apply_lang_highlight(self) -> None:
        cur = current_language()
        mark = tr("settings.mark")
        names = dict(LANGS)
        for code, lb in getattr(self, "lang_labels", {}).items():
            if code == cur:
                lb.config(text=f"{mark} {names[code]}", bg=CARD_HI, fg=FG,
                          font=(UI_FONT, 12, "bold"))
            else:
                lb.config(text=names[code], bg=PANEL, fg=FG, font=(UI_FONT, 12))

    def set_lang(self, code: str) -> None:
        set_language(code)
        self._retranslate()

    def open_feedback(self) -> None:
        try:
            webbrowser.open(FEEDBACK_URL)
        except Exception:
            swallow("ui.TuneKuoUI.open_feedback")
            pass

    def open_log(self) -> None:
        cmd = _reveal_cmd(log_file())
        if not cmd:
            return
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def _retranslate(self) -> None:
        self.btn_add_files.config(text=tr("tool.add_files"))
        self.btn_add_folder.config(text=tr("tool.add_folder"))
        self.btn_scan.config(text=tr("tool.scan_library"))
        self.btn_settings.config(text=tr("tool.settings"))
        for col, key, _w, _a in self._tree_cols:
            self.tree.heading(col, text=tr(key))
        self.btn_back.config(text=tr("settings.back"))
        self.lb_settings_title.config(text=tr("settings.title"))
        self.lb_lang_group.config(text=tr("settings.language"))
        self.lb_feedback.config(text=tr("settings.feedback"))
        self.lb_log.config(text=tr("settings.log"))
        self.btn_now_back.config(text=tr("settings.back"))
        self.lb_now_title.config(text=tr("now.title"))
        self.btn_wave.config(text=GLYPH_MUSIC)
        self._apply_lang_highlight()
        self._update_placeholder()
        self._update_count()
        self._update_mode_button()
        self._apply_default_button()
        self._refresh_status()
        cur = self.player.current()
        if cur:
            self._show_track(cur)
        else:
            self.lb_now.config(text=tr("not_playing"))
            self.lb_now_sub.config(text="")
            self._set_lyrics_text(tr("lyrics_empty"), "other")
        self.root.title(f"{cur.display_title} - {self._artist(cur)} - TuneKuo" if cur else APP_NAME)

    def _artist(self, track: Track) -> str:
        return track.artist or tr("unknown_artist")

    def _set_lyrics_text(self, text: str, tag: str = "other") -> None:
        self.lyric_text.configure(state="normal")
        self.lyric_text.delete("1.0", "end")
        self.lrc_lines = []
        self.lrc_line_no = []
        self.current_lyric = -1
        self.lyric_text.insert("end", text, tag)
        self.lyric_text.configure(state="disabled")

    def is_settings(self) -> bool:
        return self.offset > 0.5

    def show_settings(self) -> None:
        self._slide_to(1.0)

    def show_main(self) -> None:
        self._slide_to(0.0)

    def _slide_to(self, target: float) -> None:
        if self._anim is not None:
            try:
                self.root.after_cancel(self._anim)
            except Exception:
                swallow("ui.TuneKuoUI._slide_to")
                pass
            self._anim = None
        self._animate(target)

    def _animate(self, target: float) -> None:
        self.offset += (target - self.offset) * 0.35
        if abs(target - self.offset) < 0.012:
            self.offset = target
            self._apply_slide()
            self._anim = None
            return
        self._apply_slide()
        self._anim = self.root.after(12, lambda: self._animate(target))

    def show_now(self) -> None:
        if self.is_settings():
            self.show_main()
        cur = self.player.current()
        self.now_open = True
        self.page_now.place(in_=self.page_body, x=0, y=0, relwidth=1, relheight=1)
        self.page_now.lift()
        if cur:
            self.wave.set_peaks(peaks.cached(cur.path) or [])
            self._load_peaks(cur.path)
        else:
            self.wave.set_peaks([])
        self._sync_now()

    def hide_now(self) -> None:
        self.now_open = False
        self.page_now.place_forget()

    def seek_ratio(self, ratio) -> None:
        try:
            r = max(0.0, min(1.0, float(ratio)))
        except (TypeError, ValueError):
            return
        length = self.player.get_length()
        if length > 0:
            self.player.seek(int(r * length))
            self.wave.set_progress(r)

    def _load_peaks(self, path) -> None:
        if not path or path in self._peaks_pending:
            return
        self._peaks_pending.add(path)
        peaks.load_async(path, self._peaks_done)

    def _peaks_done(self, path, values) -> None:
        self.evq.put(("peaks", path, values))

    def _sync_now(self) -> None:
        cur = self.player.current()
        if cur:
            self.lb_big.config(text=cur.display_title)
            sub = f"{self._artist(cur)} · {cur.album}" if cur.album else self._artist(cur)
            self.lb_big_sub.config(text=sub)
        else:
            self.lb_big.config(text=tr("not_playing"))
            self.lb_big_sub.config(text="")
        length = self.player.get_length()
        pos = self.player.get_time()
        if length > 0:
            if not self.seeking:
                self.wave.set_progress(pos / float(length))
            self.lb_big_time.config(text=f"{fmt_time(pos)} / {fmt_time(length)}")
        else:
            self.lb_big_time.config(text=fmt_time(pos))

    def _on_escape_now(self, event=None):
        if self.now_open:
            self.hide_now()
            return "break"
        return self._esc_orig(event)

    def _apply_slide(self) -> None:
        w = max(1, self.root.winfo_width())
        off = int(round(self.offset * w))
        self.page_main.place_configure(x=-off)
        self.page_settings.place_configure(x=w - off)

    def _on_configure(self, event=None) -> None:
        if event is not None and getattr(event, "widget", self.root) is not self.root:
            return
        if self._dragging or self._anim is not None:
            return
        self._apply_slide()

    _NO_DRAG = ("Entry", "Text", "Scale", "Scrollbar", "TScrollbar",
                "TScale", "Button", "TButton", "Canvas")

    def _drag_ok(self, widget) -> bool:
        try:
            return widget.winfo_class() not in self._NO_DRAG
        except Exception:
            swallow("ui.TuneKuoUI._drag_ok")
            return False

    def _drag_press(self, event) -> None:
        self._dragging = False
        self._press_ok = False
        if self._anim is not None or not self._drag_ok(getattr(event, "widget", None)):
            return
        self._press_x = event.x_root
        self._press_off = self.offset
        self._press_ok = True

    def _drag_motion(self, event) -> None:
        if not self._press_ok or self._anim is not None:
            return
        dx = event.x_root - self._press_x
        if not self._dragging:
            if abs(dx) < 8:
                return
            self._dragging = True
        w = max(1, self.root.winfo_width())
        self.offset = max(0.0, min(1.0, self._press_off - dx / w))
        self._apply_slide()

    def _drag_release(self, event=None) -> None:
        self._press_ok = False
        if not self._dragging:
            return
        self._dragging = False
        self._animate(1.0 if self.offset > 0.5 else 0.0)

    def _tip(self, widget, key: str) -> None:
        def show(_e=None):
            self._tip_hide()
            try:
                win = tk.Toplevel(widget)
                win.wm_overrideredirect(True)
                win.attributes("-topmost", True)
                tk.Label(win, text=tr(key), bg=CARD, fg=FG, font=(UI_FONT, 9),
                         padx=8, pady=4, bd=0).pack()
                win.wm_geometry("+%d+%d" % (widget.winfo_rootx() + 10,
                                            widget.winfo_rooty() + widget.winfo_height() + 6))
                self._tip_win = win
            except Exception:
                swallow("ui.TuneKuoUI._tip.show")
                self._tip_win = None

        def hide(_e=None):
            self._tip_hide()

        widget.bind("<Enter>", show, add="+")
        widget.bind("<Leave>", hide, add="+")
        widget.bind("<ButtonPress>", hide, add="+")

    def _tip_hide(self) -> None:
        win = getattr(self, "_tip_win", None)
        self._tip_win = None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                swallow("ui.TuneKuoUI._tip_hide")
                pass

    def _query(self) -> str:
        raw = self.var_search.get().strip()
        if raw in HINTS:
            return ""
        return raw.lower()

    def _update_placeholder(self) -> None:
        hint = tr("tool.search_hint")
        if self._placeholder or self.var_search.get() in HINTS:
            self.var_search.set("")
            self._placeholder = True
        if not self.var_search.get():
            self._placeholder = True
            self.var_search.set(hint)
            self.search_entry.config(fg=FG_DIM)
        else:
            self._placeholder = False
            self.search_entry.config(fg=FG)

    def _search_focus_in(self, event=None) -> None:
        if self._placeholder:
            self._placeholder = False
            self.var_search.set("")
        self.search_entry.config(fg=FG)

    def _search_focus_out(self, event=None) -> None:
        if not self.var_search.get():
            self._placeholder = True
            self.var_search.set(tr("tool.search_hint"))
            self.search_entry.config(fg=FG_DIM)

    def _typing(self) -> bool:
        try:
            w = self.root.focus_get()
        except Exception:
            swallow("ui.TuneKuoUI._typing")
            return False
        return isinstance(w, (tk.Entry, tk.Text))

    def _on_space(self, event=None):
        if self._typing() or self.is_settings():
            return None
        self.toggle_play()
        return "break"

    def _on_arrow(self, delta: int):
        if self._typing() or self.is_settings():
            return None
        self.player.seek(self.player.get_time() + delta)
        return "break"

    def _vlc_event(self, kind: str, payload) -> None:
        self.evq.put(("vlc", kind, payload))

    def _meta_loaded(self, gen: int, track: Track) -> None:
        self.evq.put(("meta", gen, track))

    def set_status(self, text: str = "", key: Optional[str] = None, **kw) -> None:
        if key is not None:
            self._status_key = (key, dict(kw))
            text = tr(key, **kw)
        try:
            self.lb_status.config(text=text)
        except Exception:
            swallow("ui.TuneKuoUI.set_status")
            pass

    def _refresh_status(self) -> None:
        key, kw = getattr(self, "_status_key", ("status.ready", {}))
        try:
            self.lb_status.config(text=tr(key, **kw))
        except Exception:
            swallow("ui.TuneKuoUI._refresh_status")
            pass

    def add_paths(self, paths: List[str], autoplay: bool = True,
                  files: Optional[List[str]] = None) -> None:
        if files is None:
            files = scan_paths(paths)
        if not files:
            self.set_status(key="status.no_audio")
            return
        existing = {os.path.normcase(t.path) for t in self.player.tracks}
        fresh = [f for f in files if os.path.normcase(f) not in existing]
        if not fresh:
            self.set_status(key="status.duplicates")
            return
        start = len(self.player.tracks)
        tracks = [Track(path=f) for f in fresh]
        self.player.add_tracks(tracks)
        for i, t in enumerate(tracks):
            self._idx_by_id[id(t)] = start + i
        self.gen = self.loader.new_generation()
        for i, t in enumerate(tracks):
            self.loader.submit(self.gen, start + i, t)
        self.refresh_list()
        self.set_status(key="status.added", n=len(tracks))
        if autoplay and self.player.index < 0:
            self.player.play_index(start, autoplay=True)
        self.save_state()

    def refresh_list(self) -> None:
        self.apply_filter()

    def apply_filter(self) -> None:
        q = self._query()
        tracks = self.player.tracks
        self.tree.delete(*self.tree.get_children())
        self.view = []
        for i, t in enumerate(tracks):
            if q and q not in f"{t.display_title} {t.artist} {t.album}".lower():
                continue
            self.view.append(i)
            tags = ("playing",) if i == self.player.index else ()
            self.tree.insert("", "end", iid=str(i), tags=tags,
                             values=(t.display_title, self._artist(t), t.album, fmt_time(t.duration)))
        self._update_count()
        self._highlight_current()

    def _update_count(self) -> None:
        total = len(self.player.tracks)
        if self._query():
            self.lb_count.config(text=tr("count.filtered", n=len(getattr(self, "view", [])), total=total))
        else:
            self.lb_count.config(text=tr("count.all", n=total))

    def _highlight_current(self) -> None:
        for iid in self.tree.get_children():
            self.tree.item(iid, tags=("playing",) if iid == str(self.player.index) else ())
        iid = str(self.player.index)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.see(iid)

    def on_row_play(self, event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except ValueError:
            return
        self.player.play_index(idx)

    def on_row_menu(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.selection_set(row)
        m = self._row_menu(int(row))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _row_menu(self, idx: int) -> tk.Menu:
        m = tk.Menu(self.root, tearoff=0, bg=CARD, fg=FG, activebackground=ACCENT_D,
                    activeforeground="#FFFFFF", bd=0)
        m.add_command(label=tr("menu.play"), command=lambda: self.player.play_index(idx))
        m.add_separator()
        m.add_command(label=tr("menu.fetch_info"), command=lambda: self.fetch_online(idx))
        m.add_command(label=tr("menu.detail"), command=lambda: self.show_song_detail(idx))
        m.add_command(label=tr("menu.copy_title"),
                      command=lambda: self.copy_text(self._display_title(idx)))
        m.add_command(label=tr("menu.copy_path"),
                      command=lambda: self.copy_text(self._track_path(idx)))
        m.add_separator()
        m.add_command(label=tr("menu.reveal"), command=lambda: self.reveal(idx))
        m.add_command(label=tr("menu.remove"), command=lambda: self.remove_track(idx))
        m.add_command(label=tr("menu.delete_file"), command=lambda: self.delete_track(idx))
        return m

    def _track_at(self, idx: int) -> Optional[Track]:
        return self.player.tracks[idx] if 0 <= idx < len(self.player.tracks) else None

    def _display_title(self, idx: int) -> str:
        t = self._track_at(idx)
        return (t.title or t.display_title) if t else ""

    def _track_path(self, idx: int) -> str:
        t = self._track_at(idx)
        return t.path if t else ""

    def copy_text(self, text: str) -> None:
        if not text:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.set_status(key="copied")
        except Exception:
            swallow("ui.TuneKuoUI.copy_text")
            pass

    def _kv(self, key: str, value) -> str:
        return tr("kv_fmt", k=tr(key), v=value)

    def show_song_detail(self, idx: int) -> None:
        t = self._track_at(idx)
        if not t:
            return
        try:
            size = os.path.getsize(t.path)
        except Exception:
            swallow("ui.TuneKuoUI.show_song_detail")
            size = 0
        ext = os.path.splitext(t.path)[1].lstrip(".").upper() or "?"
        body = "\n".join((
            self._kv("detail.title", t.display_title),
            self._kv("detail.artist", self._artist(t)),
            self._kv("detail.album", t.album or "-"),
            self._kv("detail.duration", fmt_time(t.duration)),
            self._kv("detail.format", ext),
            self._kv("detail.size", human_size(size)),
            self._kv("detail.path", t.path),
        ))
        messagebox.showinfo(tr("menu.detail"), body)

    def fetch_online(self, idx: int) -> None:
        t = self._track_at(idx)
        if not t:
            return
        self.set_status(key="fetching_online")

        def work() -> None:
            try:
                info = online.fetch(t)
            except Exception:
                swallow("ui.TuneKuoUI.fetch_online.work")
                info = None
            self.evq.put(("online", idx, info))     

        threading.Thread(target=work, daemon=True).start()

    def _apply_online(self, idx: int, info) -> None:
        t = self._track_at(idx)
        if not t:
            return
        if info is None:
            self.set_status(key="fetch_failed")
            messagebox.showwarning(tr("menu.fetch_info"), tr("fetch_failed"))
            return
        t.title = info.title or t.title
        t.artist = info.artist or t.artist
        t.album = info.album or t.album
        if info.lyrics:
            t.lyrics = info.lyrics
        if info.cover:
            t.cover = info.cover
        if self.tree.exists(str(idx)):
            self.tree.item(str(idx), values=(t.display_title, self._artist(t), t.album,
                                             fmt_time(t.duration)))
        if idx == self.player.index:
            self._show_track(t)
        n = len(parse_lrc(info.lyrics)) or len([l for l in info.lyrics.splitlines() if l.strip()])
        src = " · ".join(x for x in (info.meta_source, info.lyric_source) if x)
        self.set_status(key="fetch_ok", src=src, n=n)
        body = [self._kv("detail.title", info.title),
                self._kv("detail.artist", info.artist or "-")]
        if info.album:
            body.append(self._kv("detail.album", info.album))
        if info.year:
            body.append(self._kv("detail.year", info.year))
        if info.genre:
            body.append(self._kv("detail.genre", info.genre))
        if src:
            body.append(self._kv("detail.source", src))
        body.append(self._kv("detail.cover", tr("got") if info.cover else tr("not_found")))
        body.append(tr("fetch_lyrics_ok", n=n) if n else tr("fetch_lyrics_none"))
        messagebox.showinfo(tr("menu.fetch_info"), "\n".join(body))

    def reveal(self, idx: int) -> None:
        t = self.player.tracks[idx] if 0 <= idx < len(self.player.tracks) else None
        if not t:
            return
        cmd = _reveal_cmd(t.path)
        if not cmd:
            return
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def delete_track(self, idx: int) -> None:
        t = self._track_at(idx)
        if t is None:
            return
        if not messagebox.askyesno(tr("menu.delete_file"), tr("delete_confirm", name=t.display_title)):
            return
        try:
            os.remove(t.path)
        except OSError as exc:
            messagebox.showerror(tr("menu.delete_file"), tr("delete_failed", err=exc))
            return
        self.remove_track(idx)
        self.set_status(tr("deleted", name=t.display_title))

    def remove_track(self, idx: int) -> None:
        if not (0 <= idx < len(self.player.tracks)):
            return
        was_current = idx == self.player.index
        del self.player.tracks[idx]
        self._reindex()
        if was_current:
            self.player.stop()
            self.player.index = min(idx, len(self.player.tracks) - 1)
        elif idx < self.player.index:
            self.player.index -= 1
        self.refresh_list()
        self.save_state()

    def _reindex(self) -> None:
        self._idx_by_id = {id(t): i for i, t in enumerate(self.player.tracks)}
        self.player._rebuild_shuffle(self.player.index if self.player.index >= 0 else None)

    def clear_list(self) -> None:
        self.player.stop()
        self.player.tracks = []
        self.player.index = -1
        self._reindex()
        self.refresh_list()
        self.save_state()

    def choose_files(self) -> None:
        files = filedialog.askopenfilenames(
            title=tr("dlg.choose_files"),
            filetypes=[(tr("dlg.ft_audio"), "*.mp3 *.flac *.ape *.wav *.m4a *.aac *.ogg *.opus *.wma *.aiff *.dsf *.dff *.wv *.tta *.tak *.mka *.ac3 *.dts"),
                       (tr("dlg.ft_all"), "*.*")])
        if files:
            self.add_paths(list(files))

    def choose_folder(self) -> None:
        d = filedialog.askdirectory(title=tr("dlg.choose_folder"))
        if d:
            self.add_paths([d])

    def scan_library(self) -> None:
        roots = default_roots()
        if not roots:
            self.set_status(key="status.no_music_dir")
            return
        self.set_status(key="status.scanning")
        self.show_scan_ui()

        def work() -> None:
            try:
                found = scan_paths(roots)
            except Exception:
                swallow("ui.TuneKuoUI.scan_library")
                found = []
            self.evq.put(("scan", roots, found))

        threading.Thread(target=work, daemon=True).start()

    def show_scan_ui(self) -> None:
        self._scan_t0 = time.time()
        self._scan_visible = True
        self._scan_angle = 0
        self._scan_tip = 0
        self.lb_scan_tip.config(text=tr("scan.tip1"))
        self.scan_box.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.scan_inner.place(relx=0.5, rely=0.5, anchor="center")
        self.scan_box.lift()
        self._scan_spin()
        self._scan_tip_after()

    def hide_scan_ui(self) -> None:
        self._scan_visible = False
        try:
            self.scan_box.place_forget()
        except Exception:
            swallow("ui.TuneKuoUI.hide_scan_ui")

    def _scan_spin(self) -> None:
        if not getattr(self, "_scan_visible", False):
            return
        self._scan_angle = (self._scan_angle + 18) % 360
        try:
            self.scan_canvas.itemconfigure(self._scan_arc, start=self._scan_angle)
        except Exception:
            swallow("ui.TuneKuoUI._scan_spin")
            return
        self.root.after(40, self._scan_spin)

    def _scan_tip_after(self) -> None:
        if not getattr(self, "_scan_visible", False):
            return
        self.root.after(SCAN_TIP_MS, self._scan_tip_next)

    def _scan_tip_next(self) -> None:
        if not getattr(self, "_scan_visible", False):
            return
        self._scan_tip = (self._scan_tip + 1) % SCAN_TIP_COUNT
        try:
            self.lb_scan_tip.config(text=tr("scan.tip%d" % (self._scan_tip + 1)))
        except Exception:
            swallow("ui.TuneKuoUI._scan_tip_next")
        self._scan_tip_after()

    def _scan_done(self, roots, found) -> None:
        wait = SCAN_MIN_S - (time.time() - getattr(self, "_scan_t0", 0.0))
        if wait > 0:
            self.root.after(int(wait * 1000), lambda: self._scan_apply(roots, found))
        else:
            self._scan_apply(roots, found)

    def _scan_apply(self, roots, found) -> None:
        self.hide_scan_ui()
        if not found:
            self.set_status(key="status.no_audio")
            return
        self.add_paths(roots, files=found)
        self.set_status(key="status.scanned", n=len(self.player.tracks))

    def register_default(self) -> None:
        try:
            done = assoc.register()
        except Exception as e:
            swallow("ui.TuneKuoUI.register_default")
            messagebox.showerror(tr("dlg.register_failed_title"), tr("dlg.register_failed_body", e=e))
            return
        self._refresh_default_status()
        msg = tr("dlg.register_done", done="\n- ".join(done),
                 n=getattr(self, "_default_n", 0), total=len(assoc.EXTS))
        messagebox.showinfo(tr("dlg.register_done_title"), msg)
        assoc.open_default_apps_settings()

    def _refresh_default_status(self) -> None:
        try:
            self._default_n = assoc.default_count()
        except Exception:
            swallow("ui.TuneKuoUI._refresh_default_status")
            return
        self._apply_default_button()

    def _apply_default_button(self) -> None:
        n = getattr(self, "_default_n", 0)
        if n:
            self.btn_default.config(text=tr("tool.default_ok", n=n, total=len(assoc.EXTS)),
                                    bg=GREEN, fg="#0B2B14")
        else:
            self.btn_default.config(text=tr("tool.set_default"), bg=ACCENT_D, fg="#FFFFFF")

    def toggle_play(self) -> None:
        if not self.player.tracks:
            self.choose_files()
            return
        self.player.toggle()

    def cycle_mode(self) -> None:
        self.player.cycle_mode()
        self._update_mode_button()
        self.save_state()

    def _update_mode_button(self) -> None:
        self.btn_mode.config(text=tr(f"mode.{self.player.mode}"))

    def on_escape(self, event=None) -> None:
        if self.is_settings():
            self.show_main()
            return "break"
        if self.var_search.get() and not self._placeholder:
            self.var_search.set("")
            self._search_focus_out()
            return "break"

    def focus_lyrics(self) -> None:
        self.lyric_text.focus_set()

    def toggle_mute(self) -> None:
        if self.player.get_volume() > 0:
            self._last_vol = self.player.get_volume()
            self.vol.set(0)
        else:
            self.vol.set(getattr(self, "_last_vol", 80))

    def on_volume(self, value) -> None:
        v = int(float(value))
        self.player.set_volume(v)
        self.btn_vol.config(text=GLYPH_MUTE if v == 0 else GLYPH_VOL)

    def on_seek_drag(self, value) -> None:
        if self.seeking:
            length = self.player.get_length()
            if length > 0:
                self.lb_time.config(text=fmt_time(int(length * float(value) / 1000)))

    def on_seek_release(self, event=None) -> None:
        self.player.seek_ratio(float(self.seek.get()) / 1000.0)
        self.seeking = False

    def on_lyric_click(self, event) -> None:
        line = int(self.lyric_text.index(f"@{event.x},{event.y}").split(".")[0])
        for i, ln in enumerate(self.lrc_line_no):
            if ln == line and i < len(self.lrc_lines):
                self.player.seek(self.lrc_lines[i][0])
                return

    def _tick(self) -> None:
        try:
            while True:
                kind, a, b = self.evq.get_nowait()
                self._handle_event(kind, a, b)
        except queue.Empty:
            pass

        if self.player.consume_end_pending():
            self.player.handle_end()

        if not self.seeking:
            length = self.player.get_length()
            cur = self.player.get_time()
            if length > 0:
                self.seek.set(min(1000.0, cur * 1000.0 / length))
            self.lb_time.config(text=fmt_time(cur))

        if self.now_open:
            self._sync_now()

        self._update_lyric_line()
        self.root.after(120, self._tick)

    def _handle_event(self, kind: str, a, b) -> None:
        if kind == "vlc":
            if a == "track":
                self._on_track_changed()
            elif a == "playing":
                self.btn_play.config(text=GLYPH_PAUSE)
                self.set_status(key="status.playing")
                self._highlight_current()
            elif a in ("paused", "stopped"):
                self.btn_play.config(text=GLYPH_PLAY)
                self.set_status(key="status.paused" if a == "paused" else "status.stopped")
            elif a == "ended":
                self.btn_play.config(text=GLYPH_PLAY)
            elif a == "error":
                self.set_status(key="status.play_failed")
                cur = self.player.current()
                if cur:
                    messagebox.showwarning(tr("dlg.play_failed_title"),
                                           tr("dlg.play_failed_body", name=os.path.basename(cur.path)))
            elif a == "length":
                self.lb_len.config(text=fmt_time(int(b or 0)))
                idx = self.player.index
                if 0 <= idx < len(self.player.tracks) and self.tree.exists(str(idx)):
                    self.tree.set(str(idx), "time", fmt_time(int(b or 0)))
        elif kind == "meta":
            gen, track = a, b
            if gen != self.gen:
                return
            idx = self._idx_by_id.get(id(track))
            if idx is None or not self.tree.exists(str(idx)):
                return
            self.tree.item(str(idx), values=(track.display_title, self._artist(track),
                                             track.album, fmt_time(track.duration)))
            if idx == self.player.index:
                self._show_track(track)
        elif kind == "online":
            self._apply_online(a, b)
        elif kind == "peaks":
            self._peaks_pending.discard(a)
            cur = self.player.current()
            if cur and cur.path == a:
                self.wave.set_peaks(b)
        elif kind == "scan":
            self._scan_done(a, b)
        elif kind == "path":
            self.root.deiconify()
            self.root.lift()
            self.add_paths(a, autoplay=True)
        elif kind == "key":
            if a == "play_pause":
                self.toggle_play()
            elif a == "next":
                self.player.next_manual()
            elif a == "prev":
                self.player.prev_manual()
            elif a == "stop":
                self.player.stop()

    def _on_track_changed(self) -> None:
        t = self.player.current()
        self._highlight_current()
        self.lb_len.config(text=fmt_time(self.player.get_length() or (t.duration if t else 0)))
        if t:
            self._show_track(t)
            self.root.title(f"{t.display_title} - {self._artist(t)} - TuneKuo")
        self.save_state()

    def _show_track(self, t: Track) -> None:
        self.lb_now.config(text=t.display_title)
        self.lb_now_sub.config(text=f"{self._artist(t)} · {t.album}" if t.album else self._artist(t))
        self._set_cover(t.cover)
        self._set_lyrics(t)
        if self.now_open:
            self._sync_now()
        self._load_peaks(t.path)

    def _set_cover(self, data: Optional[bytes]) -> None:
        self._cover_data = data
        self._render_cover()

    def _render_cover(self) -> None:
        c = self.cover
        c.delete("all")
        w = max(120, c.winfo_width())
        h = max(120, c.winfo_height())
        data = getattr(self, "_cover_data", None)
        size = min(w, h) - 24
        x0, y0 = (w - size) / 2, (h - size) / 2
        if data and HAS_PIL:
            try:
                img = Image.open(io.BytesIO(data))
                img = img.convert("RGB")
                img.thumbnail((int(size), int(size)))
                self._cover_photo = ImageTk.PhotoImage(img)
                c.create_image(w / 2, h / 2, image=self._cover_photo)
                return
            except Exception:
                swallow("ui.TuneKuoUI._render_cover")
                pass
        if data and not HAS_PIL and data[:8] == b"\x89PNG\r\n\x1a\n":
            try:
                self._cover_photo = tk.PhotoImage(data=data)
                c.create_image(w / 2, h / 2, image=self._cover_photo)
                return
            except Exception:
                swallow("ui.TuneKuoUI._render_cover")
                pass
        c.create_rectangle(x0, y0, x0 + size, y0 + size, fill=CARD, outline="")
        c.create_text(w / 2, h / 2 - 14, text=GLYPH_MUSIC, fill="#3E4A5C", font=(ICON_FONT, int(size / 4)))
        c.create_text(w / 2, y0 + size - 26, text=tr("no_cover"), fill="#3E4A5C", font=(UI_FONT, 9))

    def _set_lyrics(self, t: Track) -> None:
        self.lyric_text.configure(state="normal")
        self.lyric_text.delete("1.0", "end")
        self.lrc_lines = []
        self.lrc_line_no = []
        self.current_lyric = -1
        text = (t.lyrics or "").strip()
        if not text:
            self.lyric_text.insert("end", tr("lyrics_empty"), "other")
            self.lyric_text.configure(state="disabled")
            return
        parsed = parse_lrc(text)
        if parsed:
            for time_ms, line in parsed:
                self.lrc_lines.append((time_ms, line))
                self.lrc_line_no.append(int(self.lyric_text.index("end-1c").split(".")[0]))
                self.lyric_text.insert("end", line + "\n", "other")
        else:
            for line in text.splitlines():
                self.lyric_text.insert("end", (line or " ") + "\n", "plain")
        self.lyric_text.configure(state="disabled")
        self.lyric_text.yview_moveto(0)

    def _update_lyric_line(self) -> None:
        if not self.lrc_lines:
            return
        cur = self.player.get_time()
        idx = -1
        for i, (time_ms, _) in enumerate(self.lrc_lines):
            if time_ms <= cur + 120:
                idx = i
            else:
                break
        if idx == self.current_lyric:
            return
        self.current_lyric = idx
        self.lyric_text.configure(state="normal")
        self.lyric_text.tag_remove("cur", "1.0", "end")
        if idx >= 0:
            line_no = self.lrc_line_no[idx]
            self.lyric_text.tag_add("cur", f"{line_no}.0", f"{line_no}.end")
            total = max(1, int(self.lyric_text.index("end-1c").split(".")[0]))
            frac = max(0.0, min(0.92, (line_no - 3) / total))
            self.lyric_text.yview_moveto(frac)
        self.lyric_text.configure(state="disabled")

    def save_state(self) -> None:
        try:
            data = {}
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as fp:
                    old = json.load(fp)
                if isinstance(old, dict):
                    data.update(old)
            except Exception:
                swallow("ui.TuneKuoUI.save_state")
                pass
            data.update({
                "tracks": [t.path for t in self.player.tracks][:MAX_STATE_TRACKS],
                "index": self.player.index,
                "volume": self.player.get_volume(),
                "mode": self.player.mode,
                "position": self.player.get_time(),
                "lang": current_language(),
            })
            with open(STATE_FILE, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False)
        except Exception:
            swallow("ui.TuneKuoUI.save_state")
            pass

    def load_state(self) -> None:
        if not os.path.isfile(STATE_FILE):
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception:
            swallow("ui.TuneKuoUI.load_state")
            return
        lang = data.get("lang")
        if isinstance(lang, str) and lang != current_language() and lang in {c for c, _ in LANGS}:
            set_language(lang, save=False)
            self._retranslate()
        paths = [p for p in data.get("tracks", []) if isinstance(p, str) and os.path.isfile(p)]
        if paths:
            tracks = [Track(path=p) for p in paths]
            self.player.tracks = tracks
            self.player.index = max(-1, min(int(data.get("index", 0)), len(tracks) - 1))
            self._reindex()
            self.gen = self.loader.new_generation()
            for i, t in enumerate(tracks):
                self.loader.submit(self.gen, i, t)
            self.refresh_list()
        mode = int(data.get("mode", PlayMode.REPEAT_LIST))
        if mode in PlayMode.ORDER:
            self.player.set_mode(mode)
        vol = int(data.get("volume", 80))
        self.vol.set(vol)
        self.player.set_volume(vol)
        self._update_mode_button()

    def on_close(self) -> None:
        try:
            self._tip_hide()
        except Exception:
            swallow("ui.TuneKuoUI.on_close")
            pass
        try:
            self.save_state()
        except Exception:
            swallow("ui.TuneKuoUI.on_close")
            pass
        try:
            if self.mediakeys:
                self.mediakeys.stop()
        except Exception:
            swallow("ui.TuneKuoUI.on_close")
            pass
        try:
            self.loader.stop()
        except Exception:
            swallow("ui.TuneKuoUI.on_close")
            pass
        try:
            self.player.release()
        except Exception:
            swallow("ui.TuneKuoUI.on_close")
            pass
        self.root.destroy()
