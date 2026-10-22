from __future__ import annotations
from applog import swallow

import hashlib
import json
import os
import struct
import tempfile
import threading
import time
import wave

import paths

BARS = 320
TIMEOUT_S = 120.0
CACHE_DIR = os.path.join(paths.config_dir(), "peaks")
TMP_DIR = os.path.join(tempfile.gettempdir(), "tunekuo-peaks")

_locks = {}


def _lock_for(key: str):
    with threading.Lock():
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
    return lock


def _cache_path(path: str) -> str:
    try:
        stamp = "%s:%s" % (int(os.path.getmtime(path)), os.path.getsize(path))
    except OSError:
        stamp = path
    key = hashlib.sha1((path + "|" + stamp).encode("utf-8", "replace")).hexdigest()[:20]
    return os.path.join(CACHE_DIR, key + ".json")


def cached(path: str):
    fp = _cache_path(path)
    if not os.path.isfile(fp):
        return None
    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        swallow("peaks.cached")
        return None
    if not isinstance(data, list) or len(data) != BARS:
        return None
    try:
        return [max(0.02, min(1.0, float(v))) for v in data]
    except Exception:
        swallow("peaks.cached")
        return None


def _store(path: str, values) -> None:
    fp = _cache_path(path)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            json.dump([round(float(v), 4) for v in values], f)
    except Exception:
        swallow("peaks._store")


def _synthetic(path: str):
    seed = int(hashlib.sha1(path.encode("utf-8", "replace")).hexdigest()[:8], 16) or 1
    out = []
    for i in range(BARS):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        r = ((seed >> 16) & 0x7FFF) / 32767.0
        shape = 0.35 + 0.45 * r
        pulse = 0.6 + 0.4 * abs(__import__("math").sin(i * 0.07))
        out.append(max(0.05, min(1.0, shape * pulse)))
    return out


def _to_wav(path: str) -> str:
    import vlc

    os.makedirs(TMP_DIR, exist_ok=True)
    dst = os.path.join(TMP_DIR, hashlib.sha1(path.encode("utf-8", "replace")).hexdigest()[:16] + ".wav")
    if os.path.exists(dst):
        try:
            os.remove(dst)
        except OSError:
            swallow("peaks._to_wav")
    inst = vlc.Instance("--intf=dummy", "--no-video")
    media = inst.media_new(path)
    media.add_option(
        "sout=#transcode{acodec=s16l,channels=1,samplerate=8000}:std{access=file,mux=wav,dst=%s}"
        % dst.replace("\\", "/")
    )
    media.add_option("sout-keep")
    player = inst.media_player_new()
    player.set_media(media)
    player.play()
    deadline = TIMEOUT_S
    step = 0.1
    waited = 0.0
    while waited < deadline:
        state = player.get_state()
        if state in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
            break
        if os.path.isfile(dst) and state == vlc.State.Playing:
            try:
                if os.path.getsize(dst) > 0 and player.get_time() >= player.get_length() > 0:
                    break
            except OSError:
                swallow("peaks._to_wav")
        time.sleep(step)
        waited += step
    try:
        player.stop()
    except Exception:
        swallow("peaks._to_wav")
    try:
        inst.release()
    except Exception:
        swallow("peaks._to_wav")
    return dst if os.path.isfile(dst) and os.path.getsize(dst) > 44 else ""


def _peaks_from_wav(wav_path: str):
    with wave.open(wav_path, "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        frames = w.getnframes()
        if frames <= 0 or width != 2:
            return []
        raw = w.readframes(frames)
    total = len(raw) // (2 * channels)
    if total <= 0:
        return []
    chunk = max(1, total // 4000)
    peaks = []
    fmt = "<%dh" % (chunk * channels)
    size = chunk * channels * 2
    for off in range(0, total - chunk + 1, chunk):
        block = raw[off * channels * 2:off * channels * 2 + size]
        if len(block) < size:
            break
        values = struct.unpack(fmt, block)
        peak = 0
        for v in values:
            if v < 0:
                v = -v
            if v > peak:
                peak = v
        peaks.append(peak / 32768.0)
    if not peaks:
        return []
    out = []
    top = 0.0001
    for i in range(BARS):
        a = i * len(peaks) // BARS
        b = max(a + 1, (i + 1) * len(peaks) // BARS)
        best = 0.0
        for j in range(a, min(b, len(peaks))):
            if peaks[j] > best:
                best = peaks[j]
        out.append(best)
        if best > top:
            top = best
    return [max(0.03, min(1.0, v / top)) for v in out]


def extract(path: str):
    if not path or not os.path.isfile(path):
        return _synthetic(path or "")
    hit = cached(path)
    if hit is not None:
        return hit
    with _lock_for(_cache_path(path)):
        hit = cached(path)
        if hit is not None:
            return hit
        values = []
        wav_path = ""
        try:
            wav_path = _to_wav(path)
            if wav_path:
                values = _peaks_from_wav(wav_path)
        except Exception:
            swallow("peaks.extract")
            values = []
        finally:
            if wav_path and os.path.isfile(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    swallow("peaks.extract")
        if len(values) != BARS:
            values = _synthetic(path)
        _store(path, values)
        return values


def load_async(path: str, on_done) -> None:
    def work():
        try:
            values = extract(path)
        except Exception:
            swallow("peaks.load_async")
            values = _synthetic(path or "")
        try:
            on_done(path, values)
        except Exception:
            swallow("peaks.load_async")

    threading.Thread(target=work, name="peaks", daemon=True).start()
