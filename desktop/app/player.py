from __future__ import annotations
from applog import swallow

import random
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import vlcenv
import vlc

class PlayMode:
    SEQUENCE = 0
    REPEAT_LIST = 1
    REPEAT_ONE = 2
    SHUFFLE = 3

    ORDER = (SEQUENCE, REPEAT_LIST, REPEAT_ONE, SHUFFLE)
    LABELS = {
        SEQUENCE: "顺序播放",
        REPEAT_LIST: "列表循环",
        REPEAT_ONE: "单曲循环",
        SHUFFLE: "随机播放",
    }
    ICONS = {SEQUENCE: "\uE8FD", REPEAT_LIST: "\uE8EE", REPEAT_ONE: "\uE8ED", SHUFFLE: "\uE8B1"}

@dataclass
class Track:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: int = 0
    cover: Optional[bytes] = None
    lyrics: str = ""
    has_lrc: bool = False
    loaded: bool = False

    @property
    def display_title(self) -> str:
        if self.title:
            return self.title
        import os
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def display_artist(self) -> str:
        return self.artist or "未知艺术家"

def fmt_time(ms: int) -> str:
    if not ms or ms < 0:
        return "--:--"
    s = ms // 1000
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"

class Player:

    def __init__(self, on_event: Callable[[str, object], None], volume: int = 80):
        self.on_event = on_event
        self.instance = vlc.Instance("--no-video", "--quiet", "--no-video-title-show")
        if self.instance is None:
            raise RuntimeError("libvlc 初始化失败")
        self.player = self.instance.media_player_new()
        self.tracks: List[Track] = []
        self.index = -1
        self.mode = PlayMode.REPEAT_LIST
        self.shuffle_order: List[int] = []
        self.shuffle_pos = 0
        self._end_pending = False
        self._lock = threading.Lock()
        self.set_volume(volume)
        em = self.player.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end)
        em.event_attach(vlc.EventType.MediaPlayerPlaying, lambda e: self._fire("playing"))
        em.event_attach(vlc.EventType.MediaPlayerPaused, lambda e: self._fire("paused"))
        em.event_attach(vlc.EventType.MediaPlayerStopped, lambda e: self._fire("stopped"))
        em.event_attach(vlc.EventType.MediaPlayerEncounteredError, lambda e: self._fire("error"))
        em.event_attach(vlc.EventType.MediaPlayerLengthChanged, self._on_length)

    def _fire(self, kind: str, payload=None) -> None:
        try:
            self.on_event(kind, payload)
        except Exception:
            swallow("player.Player._fire")
            pass

    def _on_end(self, event):
        self._end_pending = True
        self._fire("ended")

    def _on_length(self, event):
        try:
            ms = int(event.u.new_length)
        except Exception:
            swallow("player.Player._on_length")
            ms = 0
        if ms <= 0:
            ms = self.get_length()
        if self.index >= 0 and 0 <= self.index < len(self.tracks) and ms > 0:
            self.tracks[self.index].duration = ms
        self._fire("length", ms)

    def set_playlist(self, tracks: List[Track], start: int = 0, autoplay: bool = True) -> None:
        self.tracks = list(tracks)
        self._rebuild_shuffle()
        if not self.tracks:
            self.index = -1
            return
        start = max(0, min(start, len(self.tracks) - 1))
        if self.mode == PlayMode.SHUFFLE:
            self.shuffle_order = [start] + [i for i in self.shuffle_order if i != start]
            self.shuffle_pos = 0
        self.index = start
        if autoplay:
            self._load(self.index, True)
        else:
            self._fire("track", self.index)

    def add_tracks(self, tracks: List[Track]) -> None:
        self.tracks.extend(tracks)
        self._rebuild_shuffle()

    def _rebuild_shuffle(self, keep_first: Optional[int] = None) -> None:
        order = list(range(len(self.tracks)))
        random.shuffle(order)
        if keep_first is not None and keep_first in order:
            order.remove(keep_first)
            order.insert(0, keep_first)
        self.shuffle_order = order
        self.shuffle_pos = 0

    def current(self) -> Optional[Track]:
        if 0 <= self.index < len(self.tracks):
            return self.tracks[self.index]
        return None

    def _load(self, index: int, play: bool) -> None:
        if not (0 <= index < len(self.tracks)):
            return
        t = self.tracks[index]
        media = self.instance.media_new(t.path)
        try:
            media.add_option(":no-video")
        except Exception:
            swallow("player.Player._load")
            pass
        self.player.set_media(media)
        self._end_pending = False
        self._fire("track", index)
        if play:
            self.player.play()

    def play_index(self, index: int, autoplay: bool = True) -> None:
        with self._lock:
            if not (0 <= index < len(self.tracks)):
                return
            self.index = index
            if self.mode == PlayMode.SHUFFLE:
                try:
                    self.shuffle_pos = self.shuffle_order.index(index)
                except ValueError:
                    self._rebuild_shuffle(index)
            self._load(index, autoplay)

    def toggle(self) -> None:
        if self.index < 0 and self.tracks:
            self.play_index(0)
            return
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def play(self) -> None:
        if self.index < 0 and self.tracks:
            self.play_index(0)
        else:
            self.player.play()

    def pause(self) -> None:
        self.player.pause()

    def stop(self) -> None:
        self.player.stop()

    def next_manual(self) -> None:
        n = len(self.tracks)
        if n == 0:
            return
        if self.mode == PlayMode.SHUFFLE:
            self.shuffle_pos += 1
            if self.shuffle_pos >= len(self.shuffle_order):
                cur = self.index
                self._rebuild_shuffle(cur)
                self.shuffle_pos = 1 if len(self.shuffle_order) > 1 else 0
            self.play_index(self.shuffle_order[self.shuffle_pos])
            return
        self.play_index((self.index + 1) % n)

    def prev_manual(self) -> None:
        if self.player.get_time() > 3000:
            self.seek(0)
            return
        n = len(self.tracks)
        if n == 0:
            return
        if self.mode == PlayMode.SHUFFLE:
            self.shuffle_pos -= 1
            if self.shuffle_pos < 0:
                self.shuffle_pos = len(self.shuffle_order) - 1
            self.play_index(self.shuffle_order[self.shuffle_pos])
            return
        self.play_index((self.index - 1) % n)

    def handle_end(self) -> None:
        self._end_pending = False
        n = len(self.tracks)
        if n == 0:
            return
        if self.mode == PlayMode.REPEAT_ONE:
            self.player.set_time(0)
            self.player.play()
            return
        if self.mode == PlayMode.SHUFFLE:
            self.shuffle_pos += 1
            if self.shuffle_pos >= len(self.shuffle_order):
                cur = self.index
                self._rebuild_shuffle(cur)
                self.shuffle_pos = 1 if len(self.shuffle_order) > 1 else 0
            self.play_index(self.shuffle_order[self.shuffle_pos])
            return
        if self.mode == PlayMode.REPEAT_LIST:
            self.play_index((self.index + 1) % n)
            return
        if self.index + 1 < n:
            self.play_index(self.index + 1)
        else:
            self.player.stop()
            self._fire("stopped")
            self._fire("track", self.index)

    def consume_end_pending(self) -> bool:
        if self._end_pending:
            self._end_pending = False
            return True
        return False

    def set_mode(self, mode: int) -> int:
        if mode not in PlayMode.ORDER:
            return self.mode
        if mode == PlayMode.SHUFFLE:
            self._rebuild_shuffle(self.index if self.index >= 0 else None)
        self.mode = mode
        return self.mode

    def cycle_mode(self) -> int:
        i = PlayMode.ORDER.index(self.mode)
        return self.set_mode(PlayMode.ORDER[(i + 1) % len(PlayMode.ORDER)])

    def get_time(self) -> int:
        try:
            return max(0, self.player.get_time())
        except Exception:
            swallow("player.Player.get_time")
            return 0

    def get_length(self) -> int:
        try:
            return max(0, self.player.get_length())
        except Exception:
            swallow("player.Player.get_length")
            return 0

    def seek(self, ms: int) -> None:
        try:
            self.player.set_time(max(0, int(ms)))
        except Exception:
            swallow("player.Player.seek")
            pass

    def seek_ratio(self, r: float) -> None:
        length = self.get_length()
        if length > 0:
            self.seek(int(length * max(0.0, min(1.0, r))))

    def set_volume(self, v: int) -> None:
        try:
            self.player.audio_set_volume(max(0, min(100, int(v))))
        except Exception:
            swallow("player.Player.set_volume")
            pass

    def get_volume(self) -> int:
        try:
            return max(0, self.player.audio_get_volume())
        except Exception:
            swallow("player.Player.get_volume")
            return 0

    def is_playing(self) -> bool:
        try:
            return bool(self.player.is_playing())
        except Exception:
            swallow("player.Player.is_playing")
            return False

    def set_rate(self, rate: float) -> None:
        try:
            self.player.set_rate(rate)
        except Exception:
            swallow("player.Player.set_rate")
            pass

    def release(self) -> None:
        try:
            self.player.stop()
        except Exception:
            swallow("player.Player.release")
            pass
        try:
            self.player.release()
            self.instance.release()
        except Exception:
            swallow("player.Player.release")
            pass
