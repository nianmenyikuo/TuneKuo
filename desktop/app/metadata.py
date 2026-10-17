from __future__ import annotations

import os
import re
import struct
from typing import Optional

AUDIO_EXTS = {
    ".mp3", ".flac", ".ape", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus",
    ".wma", ".aiff", ".aif", ".dsf", ".dff", ".wv", ".tta", ".tak", ".mka",
    ".ac3", ".dts", ".amr", ".mpc", ".spx", ".caf", ".m4b", ".mp2", ".ofr",
}
PLAYLIST_EXTS = {".m3u", ".m3u8", ".pls"}

_COVER_NAMES = ("cover", "folder", "album", "front", "albumart", "封面", "封面图")
_IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

def _decode_legacy(buf: bytes) -> str:
    raw = buf.split(b"\x00", 1)[0]
    for codec in ("utf-8", "gbk"):
        try:
            text = raw.decode(codec)
        except (UnicodeDecodeError, LookupError):
            continue
        if text.strip():
            return text.strip()
    return buf.decode("latin-1", "replace").strip("\x00").strip()

def _decode_text(buf: bytes, enc: int) -> str:
    if not buf:
        return ""
    if enc == 0:
        return _decode_legacy(buf)
    if enc == 1:
        if buf[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return buf.decode("utf-16", "replace").strip("\x00").strip()
        return buf.decode("utf-16-le", "replace").strip("\x00").strip()
    if enc == 2:
        return buf.decode("utf-16-be", "replace").strip("\x00").strip()
    return buf.decode("utf-8", "replace").strip("\x00").strip()

def _split_cstring(buf: bytes, enc: int):
    if enc in (1, 2):
        i = 0
        while i + 1 < len(buf):
            if buf[i] == 0 and buf[i + 1] == 0:
                return buf[:i], buf[i + 2:]
            i += 2
        return buf, b""
    j = buf.find(b"\x00")
    if j < 0:
        return buf, b""
    return buf[:j], buf[j + 1:]

def _synchsafe(b: bytes) -> int:
    v = 0
    for x in b:
        v = (v << 7) | (x & 0x7F)
    return v

_ID3_FRAMES = {
    b"TIT2": "title", b"TT2": "title",
    b"TPE1": "artist", b"TP1": "artist",
    b"TALB": "album", b"TAL": "album",
    b"TRCK": "track", b"TRK": "track",
    b"USLT": "lyrics", b"ULT": "lyrics",
    b"TXXX": "txxx",
}

def _parse_apic(payload: bytes, ver: int) -> Optional[bytes]:
    if not payload:
        return None
    enc = payload[0]
    rest = payload[1:]
    if ver == 2:
        if len(rest) < 4:
            return None
        rest = rest[3:]
    else:
        mime, rest = _split_cstring(rest, 0)
    if not rest:
        return None
    rest = rest[1:]
    _desc, rest = _split_cstring(rest, enc)
    data = rest.strip(b"\x00")
    if len(data) < 64:
        return None
    if data[:2] == b"\xff\xd8" or data[:8] == b"\x89PNG\r\n\x1a\n" or data[:4] == b"RIFF":
        return data
    for sig in (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n"):
        k = data.find(sig)
        if k >= 0:
            return data[k:]
    return data

def _parse_id3v2(f, out: dict) -> None:
    f.seek(0)
    head = f.read(10)
    if len(head) < 10 or head[:3] != b"ID3":
        return
    ver = head[3]
    size = _synchsafe(head[6:10])
    if size <= 0 or size > 40 * 1024 * 1024:
        return
    body = f.read(size)
    if ver == 2:
        idlen, szlen, flags_len = 3, 3, 0
    else:
        idlen, szlen, flags_len = 4, 4, 2
    i = 0
    while i + idlen + szlen + flags_len <= len(body):
        fid = body[i:i + idlen]
        if fid == b"\x00" * idlen:
            break
        raw = body[i + idlen:i + idlen + szlen]
        if len(raw) < szlen:
            break
        fsize = _synchsafe(raw) if ver == 4 else int.from_bytes(raw, "big")
        start = i + idlen + szlen + flags_len
        end = start + fsize
        if fsize <= 0 or end > len(body):
            break
        payload = body[start:end]
        i = end
        if fid in (b"APIC", b"PIC"):
            if out.get("cover") is None:
                img = _parse_apic(payload, ver)
                if img:
                    out["cover"] = img
            continue
        key = _ID3_FRAMES.get(fid)
        if key is None or not payload:
            continue
        if key == "txxx":
            desc, rest = _split_cstring(payload[1:], payload[0])
            if desc.strip().lower() in (b"lyrics", b"lyric", b"\xe6\xad\x8c\xe8\xaf\x8d"):
                out.setdefault("lyrics", _decode_text(rest, payload[0]))
            continue
        if key == "lyrics":
            if len(payload) > 4:
                _lang = payload[1:4]
                _desc, rest = _split_cstring(payload[4:], payload[0])
                out.setdefault("lyrics", _decode_text(rest, payload[0]))
            continue
        out.setdefault(key, _decode_text(payload[1:], payload[0]))

def _parse_vorbis_comment(buf: bytes) -> dict:
    d: dict = {}
    if len(buf) < 8:
        return d
    try:
        n = int.from_bytes(buf[0:4], "little")
        pos = 4
        vlen = int.from_bytes(buf[pos:pos + 4], "little")
        pos += 4 + vlen
        if n > 4096:
            return d
        for _ in range(n):
            if pos + 4 > len(buf):
                break
            ln = int.from_bytes(buf[pos:pos + 4], "little")
            pos += 4
            if ln <= 0 or pos + ln > len(buf):
                break
            kv = buf[pos:pos + ln].decode("utf-8", "replace")
            pos += ln
            if "=" in kv:
                k, v = kv.split("=", 1)
                d.setdefault(k.strip().upper(), v)
    except Exception:
        pass
    return d

_VORBIS_KEYS = {
    "TITLE": "title", "ARTIST": "artist", "ALBUM": "album",
    "TRACKNUMBER": "track", "LYRICS": "lyrics", "UNSYNCEDLYRICS": "lyrics",
}

def _apply_vorbis(d: dict, out: dict) -> None:
    for k, v in d.items():
        key = _VORBIS_KEYS.get(k)
        if key and key not in out and v:
            out[key] = v.strip()

def _parse_flac(f, out: dict) -> None:
    f.seek(0)
    if f.read(4) != b"fLaC":
        return
    while True:
        hdr = f.read(4)
        if len(hdr) < 4:
            break
        btype = hdr[0] & 0x7F
        last = bool(hdr[0] & 0x80)
        length = int.from_bytes(hdr[1:4], "big")
        if length < 0 or length > 32 * 1024 * 1024:
            break
        block = f.read(length)
        if btype == 0:
            try:
                val = int.from_bytes(block[10:18], "big")
                rate = val >> 44
                total = val & ((1 << 36) - 1)
                if rate > 0 and total > 0:
                    out["duration"] = total * 1000 // rate
            except Exception:
                pass
        elif btype == 4:
            _apply_vorbis(_parse_vorbis_comment(block), out)
        elif btype == 6:
            try:
                pos = 4
                mlen = int.from_bytes(block[pos:pos + 4], "big")
                pos += 4 + mlen
                dlen = int.from_bytes(block[pos:pos + 4], "big")
                pos += 4 + dlen
                pos += 16
                plen = int.from_bytes(block[pos:pos + 4], "big")
                pos += 4
                if out.get("cover") is None and plen > 0:
                    out["cover"] = block[pos:pos + plen]
            except Exception:
                pass
        if last:
            break

def _parse_ogg(f, out: dict) -> None:
    f.seek(0)
    data = f.read(256 * 1024)
    for magic, skip in ((b"OpusTags", 8), (b"\x03vorbis", 7)):
        k = data.find(magic)
        if k >= 0:
            _apply_vorbis(_parse_vorbis_comment(data[k + skip:]), out)
            break

def _parse_wav(f, out: dict) -> None:
    f.seek(12)
    rate = 0
    data = 0
    for _ in range(64):
        hdr = f.read(8)
        if len(hdr) < 8:
            break
        cid = hdr[:4]
        size = int.from_bytes(hdr[4:8], "little")
        pad = size & 1
        if cid == b"fmt ":
            body = f.read(min(size, 64))
            if len(body) >= 12:
                rate = int.from_bytes(body[8:12], "little")
            f.seek(max(0, size - len(body)) + pad, 1)
        elif cid == b"data":
            data = size
            f.seek(size + pad, 1)
        else:
            f.seek(size + pad, 1)
        if rate and data:
            break
    if rate > 0 and data > 0:
        out["duration"] = data * 1000 // rate

def _parse_ape(f, out: dict) -> None:
    try:
        f.seek(0, os.SEEK_END)
        total = f.tell()
        tail = 32 + 8192
        f.seek(max(0, total - tail))
        data = f.read(tail)
        k = data.rfind(b"APETAGEX")
        if k < 0:
            return
        if k + 32 > len(data):
            return
        raw_size = data[k + 12:k + 16]
        raw_n = data[k + 16:k + 20]
        if len(raw_size) < 4 or len(raw_n) < 4:
            return
        size = int.from_bytes(raw_size, "little")
        n = int.from_bytes(raw_n, "little")
        if size <= 0 or size > 32 * 1024 * 1024 or n > 4096:
            return
        start = k + 32 - size
        if start < 0:
            start = max(0, total - size)
            f.seek(start)
            items = f.read(size)
        else:
            f.seek(start)
            items = f.read(size)
        pos = 0
        for _ in range(n):
            if pos + 8 > len(items):
                break
            ln = int.from_bytes(items[pos:pos + 4], "little")
            pos += 8
            if ln <= 0 or pos + ln > len(items):
                break
            entry = items[pos:pos + ln]
            pos += ln
            j = entry.find(b"\x00")
            if j < 0:
                continue
            key = entry[:j].decode("utf-8", "replace").strip().lower()
            val = entry[j + 1:]
            if key == "title" and "title" not in out:
                out["title"] = val.decode("utf-8", "replace").strip()
            elif key == "artist" and "artist" not in out:
                out["artist"] = val.decode("utf-8", "replace").strip()
            elif key == "album" and "album" not in out:
                out["album"] = val.decode("utf-8", "replace").strip()
            elif key == "lyrics" and "lyrics" not in out:
                out["lyrics"] = val.decode("utf-8", "replace").strip()
            elif key.startswith("cover art") and out.get("cover") is None:
                z = val.find(b"\x00")
                if z >= 0:
                    out["cover"] = val[z + 1:]
    except Exception:
        pass

def _parse_mp4(f, out: dict) -> None:
    try:
        f.seek(0, os.SEEK_END)
        total = f.tell()
        _walk_atoms(f, 0, total, 0, out)
    except Exception:
        pass

def _walk_atoms(f, start: int, end: int, depth: int, out: dict) -> None:
    if depth > 6:
        return
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        hdr = f.read(8)
        if len(hdr) < 8:
            return
        size = int.from_bytes(hdr[0:4], "big")
        typ = hdr[4:8]
        body = pos + 8
        if size == 1:
            ext = f.read(8)
            if len(ext) < 8:
                return
            size = int.from_bytes(ext, "big")
            body = pos + 16
        if size < 8:
            return
        if typ in (b"moov", b"udta", b"trak", b"mdia", b"ilst"):
            _walk_atoms(f, body, min(pos + size, end), depth + 1, out)
        elif typ == b"meta":
            _walk_atoms(f, body + 4, min(pos + size, end), depth + 1, out)
        elif typ in (b"\xa9nam", b"\xa9ART", b"\xa9alb", b"\xa9lyr", b"covr"):
            _parse_ilst_item(f, body, min(pos + size, end), typ, out)
        pos += size

def _parse_ilst_item(f, start: int, end: int, typ: bytes, out: dict) -> None:
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        hdr = f.read(8)
        if len(hdr) < 8:
            return
        size = int.from_bytes(hdr[0:4], "big")
        name = hdr[4:8]
        if size < 8:
            return
        if name == b"data":
            payload = f.read(max(0, size - 16))
            if typ == b"covr":
                if out.get("cover") is None and len(payload) > 64:
                    out["cover"] = payload
            elif typ == b"\xa9lyr":
                if not out.get("lyrics"):
                    out["lyrics"] = payload.decode("utf-8", "replace").strip("\x00").strip()
            else:
                key = {b"\xa9nam": "title", b"\xa9ART": "artist", b"\xa9alb": "album"}[typ]
                if not out.get(key):
                    out[key] = payload.decode("utf-8", "replace").strip("\x00").strip()
            return
        pos += size

_LRC_TIME = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_LRC_META = re.compile(r"^\[(ar|ti|al|by|offset|length):(.*)\]$", re.I)

def parse_lrc(text: str, offset_ms: int = 0):
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _LRC_META.match(line) and not _LRC_TIME.search(line):
            continue
        stamps = list(_LRC_TIME.finditer(line))
        if not stamps:
            continue
        content = _LRC_TIME.sub("", line).strip()
        if not content:
            continue
        for m in stamps:
            mm = int(m.group(1))
            ss = int(m.group(2))
            frac = m.group(3) or "0"
            if len(frac) == 1:
                ms = int(frac) * 100
            elif len(frac) == 2:
                ms = int(frac) * 10
            else:
                ms = int(frac)
            out.append((mm * 60000 + ss * 1000 + ms + offset_ms, content))
    out.sort(key=lambda x: x[0])
    return out

def _folder_cover(path: str) -> Optional[bytes]:
    d = os.path.dirname(path)
    try:
        names = os.listdir(d)
    except Exception:
        return None
    low = {n.lower(): n for n in names}
    for base in _COVER_NAMES:
        for ext in _IMG_EXTS:
            n = low.get(base + ext)
            if n:
                try:
                    with open(os.path.join(d, n), "rb") as fp:
                        return fp.read()
                except Exception:
                    pass
    for n in names:
        if os.path.splitext(n)[1].lower() in _IMG_EXTS:
            try:
                with open(os.path.join(d, n), "rb") as fp:
                    return fp.read()
            except Exception:
                pass
    return None

def read_lyrics_file(path: str) -> str:
    base = os.path.splitext(path)[0]
    for ext in (".lrc", ".LRC", ".Lrc"):
        cand = base + ext
        if os.path.isfile(cand):
            for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
                try:
                    with open(cand, "r", encoding=enc) as fp:
                        return fp.read()
                except Exception:
                    continue
    return ""

def read_tags(path: str) -> dict:
    out: dict = {}
    ext = os.path.splitext(path)[1].lower()
    try:
        with open(path, "rb") as f:
            head = f.read(4)
            f.seek(0)
            if head[:3] == b"ID3":
                _parse_id3v2(f, out)
            elif head == b"fLaC":
                _parse_flac(f, out)
            elif head[:4] == b"OggS":
                _parse_ogg(f, out)
            elif head == b"RIFF":
                _parse_wav(f, out)
            elif head[4:8] in (b"ftyp", b"moov", b"mdat") or head[:4] == b"\x00\x00\x00\x20":
                _parse_mp4(f, out)
            elif ext in (".ape", ".wv", ".tta", ".mpc", ".ofr"):
                _parse_ape(f, out)
            if not out.get("title") and ext in (".mp3", ".wav", ".aiff", ".aif"):
                f.seek(0)
                _parse_id3v2(f, out)
    except Exception:
        pass
    if not out.get("lyrics"):
        txt = read_lyrics_file(path)
        if txt:
            out["lyrics"] = txt
            out["has_lrc"] = True
    if out.get("cover") is None:
        c = _folder_cover(path)
        if c:
            out["cover"] = c
    for k in ("title", "artist", "album", "lyrics"):
        if k in out and isinstance(out[k], str):
            out[k] = out[k].replace("\x00", "").strip()
    return out

def parse_playlist(path: str):
    ext = os.path.splitext(path)[1].lower()
    files = []
    if ext == ".pls":
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fp:
                for line in fp:
                    if line.lower().startswith("file"):
                        v = line.split("=", 1)
                        if len(v) == 2:
                            files.append(v[1].strip())
        except Exception:
            return []
    else:
        base = os.path.dirname(path)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as fp:
                for line in fp:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not os.path.isabs(line):
                        line = os.path.join(base, line)
                    files.append(line)
        except Exception:
            return []
    return [p for p in files if os.path.isfile(p)]
