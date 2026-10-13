"""TuneKuo: 主界面（tkinter 深色主题）。"""
from __future__ import annotations

import io
import json
import os
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

import assoc
from library import MetaLoader, default_roots, scan_paths
from metadata import parse_lrc
from player import PlayMode, Player, Track, fmt_time

try:
    from PIL import Image, ImageTk

    HAS_PIL = True
except Exception:  # 没装 Pillow 时退化为只显示 PNG 封面
    HAS_PIL = False

# ------------------------------------------------------------------ 配色
BG = "#12121A"
PANEL = "#1B1B26"
CARD = "#23232F"
CARD_HI = "#2E2E52"
LINE = "#2A2A38"
FG = "#E8E8F0"
FG_DIM = "#9A9AB0"
ACCENT = "#8A8AFF"
ACCENT_D = "#5A5AE0"
GREEN = "#4ECB71"

UI_FONT = "Microsoft YaHei UI"
ICON_FONT = "Segoe MDL2 Assets"

GLYPH_PLAY = "\uE768"
GLYPH_PAUSE = "\uE769"
GLYPH_PREV = "\uE892"
GLYPH_NEXT = "\uE893"
GLYPH_VOL = "\uE767"
GLYPH_MUTE = "\uE74F"
GLYPH_MUSIC = "\uE8D6"


def state_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "TuneKuo")
    os.makedirs(d, exist_ok=True)
    return d


STATE_FILE = os.path.join(state_dir(), "state.json")
MAX_STATE_TRACKS = 3000


def assets_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "assets"),
                 os.path.join(os.path.dirname(here), "assets")):
        if os.path.isdir(cand):
            return cand
    return here


class TuneKuoUI:
    def __init__(self, root: tk.Tk, initial_paths: Optional[List[str]] = None):
        self.root = root
        self.evq: "queue.Queue" = queue.Queue()
        self.view: List[int] = []          # 当前显示的行 -> 曲库索引
        self.lrc_lines = []                # [(time_ms, text)]
        self.lrc_line_no: List[int] = []   # 文本行号 -> 歌词下标
        self.seeking = False
        self.current_lyric = -1
        self._cover_photo = None
        self._idx_by_id = {}
        self.gen = 0

        self.player = Player(on_event=self._vlc_event)
        self.loader = MetaLoader(on_loaded=self._meta_loaded)

        self._build_style()
        self._build_ui()

        self.mediakeys = None
        try:
            import mediakeys

            if mediakeys.available():
                self.mediakeys = mediakeys.MediaKeys(lambda a: self.evq.put(("key", a, None)))
                self.mediakeys.start()
        except Exception:
            self.mediakeys = None

        self.load_state()
        self._update_mode_button()
        self._refresh_default_status()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(120, self._tick)

        paths = [p for p in (initial_paths or []) if p]
        if paths:
            self.add_paths(paths, autoplay=True)

    # ------------------------------------------------------------ 样式
    def _build_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG,
                        rowheight=30, borderwidth=0, font=(UI_FONT, 10))
        style.configure("Treeview.Heading", background=CARD, foreground=FG_DIM,
                        relief="flat", borderwidth=0, font=(UI_FONT, 9))
        style.map("Treeview", background=[("selected", CARD_HI)], foreground=[("selected", "#FFFFFF")])
        style.map("Treeview.Heading", background=[("active", CARD)])
        style.configure("TScrollbar", background=CARD, troughcolor=PANEL, bordercolor=PANEL,
                        arrowcolor=FG_DIM, relief="flat")
        style.configure("TScale", background=PANEL, troughcolor=CARD, borderwidth=0,
                        lightcolor=ACCENT, darkcolor=ACCENT)
        style.configure("Search.TEntry", fieldbackground=CARD, foreground=FG, borderwidth=0,
                        insertcolor=FG)

    def _btn(self, parent, text, command, *, icon=False, width=None, bg=CARD, fg=FG,
             font_size=10, padx=12, pady=6):
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                      activebackground=CARD_HI, activeforeground="#FFFFFF",
                      relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                      padx=padx, pady=pady,
                      font=(ICON_FONT if icon else UI_FONT, font_size))
        if width:
            b.config(width=width)
        return b

    # ------------------------------------------------------------ 布局
    def _build_ui(self) -> None:
        r = self.root
        r.configure(bg=BG)
        r.title("TuneKuo")
        r.geometry("1100x720")
        r.minsize(880, 560)
        icon = os.path.join(assets_dir(), "icon.ico")
        if os.path.isfile(icon):
            try:
                r.iconbitmap(icon)
            except Exception:
                pass

        r.grid_rowconfigure(1, weight=1)
        r.grid_columnconfigure(0, weight=1)

        # ---- 顶部工具栏
        top = tk.Frame(r, bg=BG)
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        tk.Label(top, text="TuneKuo", bg=BG, fg=FG, font=(UI_FONT, 16, "bold")).pack(side="left")
        self.lb_count = tk.Label(top, text="0 首", bg=BG, fg=FG_DIM, font=(UI_FONT, 9))
        self.lb_count.pack(side="left", padx=(10, 16))

        self._btn(top, "添加文件", self.choose_files).pack(side="left", padx=3)
        self._btn(top, "添加文件夹", self.choose_folder).pack(side="left", padx=3)
        self._btn(top, "扫描音乐库", self.scan_library).pack(side="left", padx=3)

        right_box = tk.Frame(top, bg=BG)
        right_box.pack(side="right")
        self.btn_default = self._btn(right_box, "设为默认播放器",
                                     self.register_default, bg=ACCENT_D, fg="#FFFFFF")
        self.btn_default.pack(side="right", padx=(6, 0))
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *_: self.apply_filter())
        ent = tk.Entry(right_box, textvariable=self.var_search, bg=CARD, fg=FG, bd=0,
                       insertbackground=FG, font=(UI_FONT, 10), width=26)
        ent.pack(side="right", padx=(0, 6), ipady=6, ipadx=8)
        ent.insert(0, "")
        self.search_entry = ent
        tk.Label(right_box, text="\uE721", bg=BG, fg=FG_DIM, font=(ICON_FONT, 12)).pack(side="right", padx=(0, 6))

        # ---- 主体：左列表 + 右封面/歌词
        body = tk.Frame(r, bg=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=14)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2, minsize=340)

        left = tk.Frame(body, bg=PANEL)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        cols = ("title", "artist", "album", "time")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c, t, w, anchor in (("title", "标题", 300, "w"), ("artist", "歌手", 170, "w"),
                                ("album", "专辑", 170, "w"), ("time", "时长", 70, "e")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=anchor, stretch=(c == "title"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", self.on_row_play)
        self.tree.bind("<Return>", self.on_row_play)
        self.tree.bind("<Button-3>", self.on_row_menu)
        self.tree.tag_configure("playing", foreground=ACCENT)

        right = tk.Frame(body, bg=PANEL)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.cover = tk.Canvas(right, bg=PANEL, height=260, highlightthickness=0)
        self.cover.grid(row=0, column=0, sticky="ew", pady=(14, 8))
        self.cover.bind("<Configure>", lambda e: self._render_cover())

        self.lb_now = tk.Label(right, text="未在播放", bg=PANEL, fg=FG, font=(UI_FONT, 12, "bold"),
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
        self.lyric_text.tag_configure("plain", foreground="#C0C0D0", font=(UI_FONT, 10))
        self.lyric_text.bind("<Button-1>", self.on_lyric_click)
        self.lyric_text.configure(state="disabled")
        lsb = ttk.Scrollbar(right, orient="vertical", command=self.lyric_text.yview)
        lsb.grid(row=3, column=1, sticky="ns")
        self.lyric_text.configure(yscrollcommand=lsb.set)

        # ---- 底部播放条
        bottom = tk.Frame(r, bg=PANEL)
        bottom.grid(row=2, column=0, sticky="ew", padx=14, pady=(8, 12))
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
        self.btn_mode = self._btn(ctl, "列表循环", self.cycle_mode, width=10, pady=4)
        self.btn_mode.pack(side="left", padx=(12, 8))
        self.btn_prev = self._btn(ctl, GLYPH_PREV, self.player.prev_manual, icon=True, font_size=15, padx=10, pady=2)
        self.btn_prev.pack(side="left", padx=2)
        self.btn_play = self._btn(ctl, GLYPH_PLAY, self.toggle_play, icon=True, font_size=18,
                                  bg=ACCENT, fg="#FFFFFF", padx=16, pady=2)
        self.btn_play.pack(side="left", padx=2)
        self.btn_next = self._btn(ctl, GLYPH_NEXT, self.player.next_manual, icon=True, font_size=15, padx=10, pady=2)
        self.btn_next.pack(side="left", padx=2)

        self.lb_status = tk.Label(ctl, text="就绪", bg=PANEL, fg=FG_DIM, font=(UI_FONT, 9))
        self.lb_status.pack(side="left", padx=14)

        vol_box = tk.Frame(ctl, bg=PANEL)
        vol_box.pack(side="right", padx=12)
        self.btn_vol = self._btn(vol_box, GLYPH_VOL, self.toggle_mute, icon=True, font_size=12, padx=6, pady=2)
        self.btn_vol.pack(side="left")
        self.vol = ttk.Scale(vol_box, from_=0, to=100, orient="horizontal", length=120,
                             command=self.on_volume)
        self.vol.set(80)
        self.vol.pack(side="left", padx=(4, 0))

        # 快捷键
        r.bind("<space>", self._on_space)
        r.bind("<Control-o>", lambda e: self.choose_files())
        r.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        r.bind("<Escape>", self.on_escape)
        r.bind("<Left>", lambda e: self._on_arrow(-5000))
        r.bind("<Right>", lambda e: self._on_arrow(5000))
        r.bind("<Control-l>", lambda e: self.focus_lyrics())

    # 空格/方向键在输入框里要正常打字，不能被快捷键抢走
    def _typing(self) -> bool:
        try:
            w = self.root.focus_get()
        except Exception:
            return False
        return isinstance(w, (tk.Entry, tk.Text))

    def _on_space(self, event=None):
        if self._typing():
            return None
        self.toggle_play()
        return "break"

    def _on_arrow(self, delta: int):
        if self._typing():
            return None
        self.player.seek(self.player.get_time() + delta)
        return "break"

    # ------------------------------------------------------------ 事件桥
    def _vlc_event(self, kind: str, payload) -> None:
        self.evq.put(("vlc", kind, payload))

    def _meta_loaded(self, gen: int, track: Track) -> None:
        self.evq.put(("meta", gen, track))

    def set_status(self, text: str) -> None:
        try:
            self.lb_status.config(text=text)
        except Exception:
            pass

    # ------------------------------------------------------------ 列表
    def add_paths(self, paths: List[str], autoplay: bool = True) -> None:
        files = scan_paths(paths)
        if not files:
            self.set_status("没有找到音频文件")
            return
        existing = {os.path.normcase(t.path) for t in self.player.tracks}
        fresh = [f for f in files if os.path.normcase(f) not in existing]
        if not fresh:
            self.set_status("这些文件已经在列表里了")
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
        self.set_status(f"已添加 {len(tracks)} 首，正在读取信息…")
        if autoplay and self.player.index < 0:
            self.player.play_index(start, autoplay=True)
        self.save_state()

    def refresh_list(self) -> None:
        self.apply_filter()

    def apply_filter(self) -> None:
        q = self.var_search.get().strip().lower()
        tracks = self.player.tracks
        self.tree.delete(*self.tree.get_children())
        self.view = []
        for i, t in enumerate(tracks):
            if q and q not in f"{t.display_title} {t.artist} {t.album}".lower():
                continue
            self.view.append(i)
            tags = ("playing",) if i == self.player.index else ()
            self.tree.insert("", "end", iid=str(i), tags=tags,
                             values=(t.display_title, t.display_artist, t.album, fmt_time(t.duration)))
        self.lb_count.config(text=f"{len(self.view)} / {len(tracks)} 首" if q else f"{len(tracks)} 首")
        self._highlight_current()

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
        idx = int(row)
        m = tk.Menu(self.root, tearoff=0, bg=CARD, fg=FG, activebackground=ACCENT_D,
                    activeforeground="#FFFFFF", bd=0)
        m.add_command(label="播放", command=lambda: self.player.play_index(idx))
        m.add_command(label="在文件夹中显示", command=lambda: self.reveal(idx))
        m.add_separator()
        m.add_command(label="从列表移除", command=lambda: self.remove_track(idx))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def reveal(self, idx: int) -> None:
        t = self.player.tracks[idx] if 0 <= idx < len(self.player.tracks) else None
        if not t:
            return
        try:
            os.system(f'explorer /select,"{t.path}"')
        except Exception:
            pass

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

    # ------------------------------------------------------------ 顶部按钮
    def choose_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="选择音乐文件",
            filetypes=[("音频文件", "*.mp3 *.flac *.ape *.wav *.m4a *.aac *.ogg *.opus *.wma *.aiff *.dsf *.dff *.wv *.tta *.tak *.mka *.ac3 *.dts"),
                       ("所有文件", "*.*")])
        if files:
            self.add_paths(list(files))

    def choose_folder(self) -> None:
        d = filedialog.askdirectory(title="选择音乐文件夹")
        if d:
            self.add_paths([d])

    def scan_library(self) -> None:
        roots = default_roots()
        if not roots:
            self.set_status("没找到默认音乐目录，请用“添加文件夹”")
            return
        self.set_status("正在扫描音乐库…")
        self.root.update_idletasks()
        self.add_paths(roots)
        self.set_status(f"扫描完成：{len(self.player.tracks)} 首")

    def register_default(self) -> None:
        try:
            done = assoc.register()
        except Exception as e:
            messagebox.showerror("注册失败", f"写入注册表时出错：\n{e}")
            return
        n = assoc.default_count()
        self._refresh_default_status()
        msg = ("已注册为音频播放器：\n\n- " + "\n- ".join(done) +
               f"\n\n当前已有 {n} / {len(assoc.EXTS)} 种格式的默认程序是 TuneKuo。\n\n"
               "Windows 10/11 的默认程序由用户确认，接下来我会打开系统“默认应用”页面，"
               "在音乐播放器那一项选择 TuneKuo 即可全部生效。")
        messagebox.showinfo("注册完成", msg)
        assoc.open_default_apps_settings()

    def _refresh_default_status(self) -> None:
        try:
            n = assoc.default_count()
        except Exception:
            return
        total = len(assoc.EXTS)
        if n:
            self.btn_default.config(text=f"默认播放器 {n}/{total}", bg=GREEN, fg="#0B2B14")
        else:
            self.btn_default.config(text="设为默认播放器", bg=ACCENT_D, fg="#FFFFFF")

    # ------------------------------------------------------------ 播放控制
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
        self.btn_mode.config(text=PlayMode.LABELS[self.player.mode])

    def on_escape(self, event=None) -> None:
        if self.var_search.get():
            self.var_search.set("")

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

    # ------------------------------------------------------------ 界面刷新
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

        self._update_lyric_line()
        self.root.after(120, self._tick)

    def _handle_event(self, kind: str, a, b) -> None:
        if kind == "vlc":
            if a == "track":
                self._on_track_changed()
            elif a == "playing":
                self.btn_play.config(text=GLYPH_PAUSE)
                self.set_status("播放中")
                self._highlight_current()
            elif a in ("paused", "stopped"):
                self.btn_play.config(text=GLYPH_PLAY)
                self.set_status("已暂停" if a == "paused" else "已停止")
            elif a == "ended":
                self.btn_play.config(text=GLYPH_PLAY)
            elif a == "error":
                self.set_status("这个文件播放失败（可能格式不受支持）")
                cur = self.player.current()
                if cur:
                    messagebox.showwarning("播放失败", f"无法播放：\n{os.path.basename(cur.path)}")
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
            self.tree.item(str(idx), values=(track.display_title, track.display_artist,
                                             track.album, fmt_time(track.duration)))
            if idx == self.player.index:
                self._show_track(track)
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
            self.root.title(f"{t.display_title} - {t.display_artist} - TuneKuo")
        self.save_state()

    def _show_track(self, t: Track) -> None:
        self.lb_now.config(text=t.display_title)
        self.lb_now_sub.config(text=f"{t.display_artist} · {t.album}" if t.album else t.display_artist)
        self._set_cover(t.cover)
        self._set_lyrics(t)

    # ------------------------------------------------------------ 封面
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
                pass
        if data and not HAS_PIL and data[:8] == b"\x89PNG\r\n\x1a\n":
            try:
                self._cover_photo = tk.PhotoImage(data=data)
                c.create_image(w / 2, h / 2, image=self._cover_photo)
                return
            except Exception:
                pass
        # 占位：圆角方块 + 音符
        c.create_rectangle(x0, y0, x0 + size, y0 + size, fill=CARD, outline="")
        c.create_text(w / 2, h / 2 - 14, text=GLYPH_MUSIC, fill="#4A4A66", font=(ICON_FONT, int(size / 4)))
        c.create_text(w / 2, y0 + size - 26, text="无封面", fill="#4A4A66", font=(UI_FONT, 9))

    # ------------------------------------------------------------ 歌词
    def _set_lyrics(self, t: Track) -> None:
        self.lyric_text.configure(state="normal")
        self.lyric_text.delete("1.0", "end")
        self.lrc_lines = []
        self.lrc_line_no = []
        self.current_lyric = -1
        text = (t.lyrics or "").strip()
        if not text:
            self.lyric_text.insert("end", "暂无歌词\n\n把同名 .lrc 文件放在歌曲旁边即可显示", "other")
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

    # ------------------------------------------------------------ 状态存取
    def save_state(self) -> None:
        try:
            data = {
                "tracks": [t.path for t in self.player.tracks][:MAX_STATE_TRACKS],
                "index": self.player.index,
                "volume": self.player.get_volume(),
                "mode": self.player.mode,
                "position": self.player.get_time(),
            }
            with open(STATE_FILE, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False)
        except Exception:
            pass

    def load_state(self) -> None:
        if not os.path.isfile(STATE_FILE):
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception:
            return
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

    # ------------------------------------------------------------ 关闭
    def on_close(self) -> None:
        try:
            self.save_state()
        except Exception:
            pass
        try:
            if self.mediakeys:
                self.mediakeys.stop()
        except Exception:
            pass
        try:
            self.loader.stop()
        except Exception:
            pass
        try:
            self.player.release()
        except Exception:
            pass
        self.root.destroy()
