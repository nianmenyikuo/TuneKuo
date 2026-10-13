"""TuneKuo: 音乐库扫描 + 后台元数据（标签/封面/歌词/时长）加载。"""
from __future__ import annotations

import os
import queue
import threading
import time
from typing import Callable, List, Optional

import vlcenv  # noqa: F401
import vlc

# python-vlc 3.x 的 MediaParseFlag 是 ctypes.c_uint 的子类，用 `|` 组合会抛
# TypeError: unsupported operand type(s) for |: 'MediaParseFlag' and 'MediaParseFlag'。
# 老代码把这个异常 except 掉了，于是 parse_with_options 从来没真正执行过 → 列表时长全 --:--。
# local(0x0) | fetch_local(0x2) = 0x2
PARSE_FLAG = vlc.MediaParseFlag(
    vlc.MediaParseFlag.local.value | vlc.MediaParseFlag.fetch_local.value)

from metadata import AUDIO_EXTS, PLAYLIST_EXTS, parse_playlist, read_tags
from player import Track

SKIP_DIRS = {"$recycle.bin", "system volume information", "windows", "program files",
             "program files (x86)", "programdata", "appdata", "node_modules", ".git",
             "temp", "tmp", "cache", "$windows.~bt", "$windows.~ws"}


def is_audio(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_EXTS


def scan_paths(paths, recursive: bool = True) -> List[str]:
    """把文件/文件夹/播放列表展开成音频文件路径（保序去重）。"""
    out: List[str] = []
    seen = set()

    def push(p: str) -> None:
        rp = os.path.normcase(os.path.abspath(p))
        if rp not in seen:
            seen.add(rp)
            out.append(os.path.abspath(p))

    def walk_dir(root: str) -> None:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for fn in sorted(filenames):
                full = os.path.join(dirpath, fn)
                if is_audio(full):
                    push(full)
                elif os.path.splitext(fn)[1].lower() in PLAYLIST_EXTS:
                    for f in parse_playlist(full):
                        if is_audio(f):
                            push(f)
            if not recursive:
                dirnames[:] = []

    for p in paths:
        if not p:
            continue
        p = os.path.expandvars(os.path.expanduser(p))
        if os.path.isfile(p):
            ext = os.path.splitext(p)[1].lower()
            if ext in PLAYLIST_EXTS:
                for f in parse_playlist(p):
                    push(f)
            else:
                push(p)
        elif os.path.isdir(p):
            walk_dir(p)
    return out


def default_roots() -> List[str]:
    home = os.path.expanduser("~")
    cands = [
        os.path.join(home, "Music"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "OneDrive", "Music"),
    ]
    out = []
    for c in cands:
        if os.path.isdir(c) and c not in out:
            out.append(c)
    return out


def _wait_parsed(media, timeout: float = 6.0) -> None:
    """等 libvlc 把媒体解析完。

    libvlc 的解析是异步的：调完 parse() 立刻 get_duration() 只会拿到 0。
    必须等 MediaParsedChanged 事件（或 is_parsed() 变真），否则列表里的时长全是 --:--。
    """
    try:
        if int(media.get_duration() or 0) > 0:
            return
    except Exception:
        pass
    done = threading.Event()
    try:
        media.event_manager().event_attach(vlc.EventType.MediaParsedChanged,
                                           lambda *_: done.set())
    except Exception:
        pass
    try:
        media.parse_with_options(PARSE_FLAG, 0)
    except Exception:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if done.is_set() or media.is_parsed():
                return
        except Exception:
            return
        time.sleep(0.02)


class MetaLoader:
    """单后台线程，按提交顺序读取元数据；结果通过回调送回（回调需自行转 UI 线程）。"""

    def __init__(self, on_loaded: Callable[[int, Track], None]):
        self.on_loaded = on_loaded
        self.q: "queue.Queue" = queue.Queue()
        self.gen = 0
        self.lock = threading.Lock()
        self._vlc_instance = None
        self.thread = threading.Thread(target=self._run, name="MetaLoader", daemon=True)
        self.thread.start()

    def new_generation(self) -> int:
        with self.lock:
            self.gen += 1
            return self.gen

    def submit(self, gen: int, index: int, track: Track) -> None:
        self.q.put((gen, index, track))

    def cancel_pending(self) -> None:
        """丢弃队列里尚未处理的任务。"""
        try:
            while True:
                self.q.get_nowait()
        except queue.Empty:
            pass

    def stop(self) -> None:
        self.q.put(None)

    def _current_gen(self) -> int:
        with self.lock:
            return self.gen

    def _run(self) -> None:
        inst = None
        while True:
            item = self.q.get()
            if item is None:
                break
            gen, index, track = item
            if gen != self._current_gen():
                continue
            try:
                self._load_one(track)
            except Exception:
                track.loaded = True
            try:
                self.on_loaded(gen, track)
            except Exception:
                pass

    def _load_one(self, track: Track) -> None:
        tags = read_tags(track.path)
        if tags.get("duration"):
            track.duration = int(tags["duration"])
        if tags.get("title"):
            track.title = tags["title"]
        if tags.get("artist"):
            track.artist = tags["artist"]
        if tags.get("album"):
            track.album = tags["album"]
        if tags.get("cover"):
            track.cover = tags["cover"]
        if tags.get("lyrics"):
            track.lyrics = tags["lyrics"]
            track.has_lrc = bool(tags.get("has_lrc"))
        # 只有标签里没拿到时长/标题/歌手时才花时间问 libvlc（DSD、TAK 等自研解析覆盖不到的格式也靠它）
        if track.duration <= 0 or not track.title or not track.artist:
            self._load_from_vlc(track)
        track.loaded = True

    def _instance(self):
        """整个 MetaLoader 共用一个 libvlc 实例。

        注意：不能在循环里 release() —— 实例被释放后 self._vlc_instance 还指着它，
        后续文件的解析会失败，表现就是"只有第一首有时长，其余全是 --:--"。
        """
        if self._vlc_instance is None:
            try:
                self._vlc_instance = vlc.Instance("--no-video", "--quiet")
            except Exception:
                self._vlc_instance = False  # 标记不可用，避免反复尝试
        return self._vlc_instance or None

    def _load_from_vlc(self, track: Track) -> None:
        inst = self._instance()
        if inst is None:
            return
        media = inst.media_new(track.path)
        try:
            _wait_parsed(media)
            dur = int(media.get_duration() or 0)
            if dur > 0:
                track.duration = dur
            if not track.title:
                track.title = (media.get_meta(vlc.Meta.Title) or "").strip()
            if not track.artist:
                track.artist = (media.get_meta(vlc.Meta.Artist) or "").strip()
            if not track.album:
                track.album = (media.get_meta(vlc.Meta.Album) or "").strip()
        except Exception:
            pass
        finally:
            try:
                media.release()
            except Exception:
                pass
        track.loaded = True
