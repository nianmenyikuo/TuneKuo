from __future__ import annotations
from applog import swallow

import hashlib
import json
import os
import paths
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from player import Track

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TuneKuo/1.0"
TIMEOUT = 10
_IMG_MAGIC = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"RIFF", b"BM")

@dataclass
class Info:
    title: str
    artist: str
    album: str
    year: str
    genre: str
    meta_source: str
    lyric_source: str
    cover: Optional[bytes]
    lyrics: str

def _state_base() -> str:
    return paths.config_dir()

def cache_dir(sub: str) -> str:
    d = os.path.join(_state_base(), "TuneKuo", "online", sub)
    os.makedirs(d, exist_ok=True)
    return d

def _key(path: str) -> str:
    return hashlib.sha1(os.path.normcase(os.path.abspath(path)).encode("utf-8")).hexdigest()[:16]

def lyrics_file(path: str) -> str:
    return os.path.join(cache_dir("lyrics"), _key(path) + ".lrc")

def cover_file(path: str) -> str:
    return os.path.join(cache_dir("covers"), _key(path) + ".img")

def cached_lyrics(path: str) -> str:
    try:
        with open(lyrics_file(path), "r", encoding="utf-8") as fp:
            return fp.read().strip()
    except Exception:
        swallow("online.cached_lyrics")
        return ""

def cached_cover(path: str) -> Optional[bytes]:
    try:
        with open(cover_file(path), "rb") as fp:
            data = fp.read()
        return data if _looks_like_image(data) else None
    except Exception:
        swallow("online.cached_cover")
        return None

def _looks_like_image(data: bytes) -> bool:
    return bool(data) and any(data.startswith(m) for m in _IMG_MAGIC)

META_KEYS = ("title", "artist", "album", "year", "genre")

def meta_file(path: str) -> str:
    return os.path.join(cache_dir("meta"), _key(path) + ".json")

def cached_meta(path: str) -> dict:
    try:
        with open(meta_file(path), "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception:
        swallow("online.cached_meta")
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(data.get(k) or "").strip() for k in META_KEYS}

def save_meta(path: str, info: Info) -> None:
    try:
        with open(meta_file(path), "w", encoding="utf-8") as fp:
            json.dump({k: getattr(info, k, "") for k in META_KEYS}, fp, ensure_ascii=False, indent=1)
    except Exception:
        swallow("online.save_meta")
        pass

def fetch(track: Track) -> Optional[Info]:
    title = (track.title or "").strip() or track.display_title
    artist = (track.artist or "").strip()
    query = " ".join(x for x in (artist, title) if x).strip()
    if not query:
        return None
    duration_ms = int(track.duration or 0)

    m_title, m_artist, m_album = title, artist, ""
    year = genre = meta_source = cover_url = ""

    res = _json("https://itunes.apple.com/search?media=music&entity=song&limit=5&term="
                + urllib.parse.quote(query))
    hit = _pick_itunes((res or {}).get("results") or [], title, artist, duration_ms)
    if hit:
        m_title = str(hit.get("trackName") or "").strip() or m_title
        m_artist = str(hit.get("artistName") or "").strip() or m_artist
        m_album = str(hit.get("collectionName") or "").strip()
        year = str(hit.get("releaseDate") or "")[:4]
        genre = str(hit.get("primaryGenreName") or "").strip()
        cover_url = str(hit.get("artworkUrl100") or "").replace("100x100", "600x600")
        meta_source = "iTunes"

    lyrics = _lrclib(m_title, m_artist, m_album, duration_ms)
    lyric_source = "LRCLIB" if lyrics else ""
    if not lyrics or not meta_source:
        ne = _netease_search(query, title, artist, duration_ms)
        if ne:
            if not lyrics:
                lyrics = _netease_lyrics(ne.get("id"))
                if lyrics:
                    lyric_source = "NetEase"
            if not meta_source:
                m_title = str(ne.get("name") or "").strip() or m_title
                artists = ne.get("artists") or []
                if artists and str(artists[0].get("name") or "").strip():
                    m_artist = str(artists[0]["name"]).strip()
                album = ne.get("album") or {}
                m_album = str(album.get("name") or "").strip()
                if not cover_url:
                    cover_url = str(album.get("picUrl") or "").strip()
                meta_source = "NetEase"

    if not meta_source and not lyric_source:
        return None

    if lyrics:
        try:
            with open(lyrics_file(track.path), "w", encoding="utf-8") as fp:
                fp.write(lyrics.strip() + "\n")
        except Exception:
            swallow("online.fetch")
            pass

    cover = None
    if cover_url:
        data = _get(cover_url)
        if data and _looks_like_image(data):
            cover = data
            try:
                with open(cover_file(track.path), "wb") as fp:
                    fp.write(data)
            except Exception:
                swallow("online.fetch")
                pass

    info = Info(m_title, m_artist, m_album, year, genre, meta_source, lyric_source, cover, lyrics)
    if info.meta_source:
        save_meta(track.path, info)
    return info

def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", (s or "").lower())

def _title_like(a: str, b: str) -> bool:
    return bool(a) and bool(b) and (a in b or b in a)

def _pick_itunes(results, title: str, artist: str, duration_ms: int):
    want_t, want_a = _norm(title), _norm(artist)
    best, best_score = None, 0
    for o in results:
        if not isinstance(o, dict):
            continue
        if not _title_like(_norm(str(o.get("trackName") or "")), want_t):
            continue
        name_a = _norm(str(o.get("artistName") or ""))
        if want_a and want_a != name_a:
            continue
        score = 2
        try:
            ms = int(o.get("trackTimeMillis") or 0)
        except Exception:
            swallow("online._pick_itunes")
            ms = 0
        if duration_ms > 0 and ms > 0 and abs(ms - duration_ms) < 5000:
            score += 1
        if score > best_score:
            best, best_score = o, score
    return best

def _lrclib(title: str, artist: str, album: str, duration_ms: int) -> str:
    if not title:
        return ""
    url = "https://lrclib.net/api/search?track_name=" + urllib.parse.quote(title)
    if artist:
        url += "&artist_name=" + urllib.parse.quote(artist)
    if album:
        url += "&album_name=" + urllib.parse.quote(album)
    arr = _json(url)
    if not isinstance(arr, list):
        return ""
    want_t = _norm(title)
    secs = duration_ms // 1000
    synced = plain = ""
    for o in arr:
        if not isinstance(o, dict):
            continue
        if not _title_like(_norm(str(o.get("trackName") or "")), want_t):
            continue
        try:
            d = int(o.get("duration") or 0)
        except Exception:
            swallow("online._lrclib")
            d = 0
        if secs > 0 and d > 0 and abs(d - secs) > 5:
            continue
        synced = synced or str(o.get("syncedLyrics") or "").strip()
        plain = plain or str(o.get("plainLyrics") or "").strip()
        if synced and plain:
            break
    return synced or plain

def _netease_search(query: str, title: str, artist: str, duration_ms: int):
    j = _json("https://music.163.com/api/search/get/web?type=1&offset=0&limit=10&s="
              + urllib.parse.quote(query))
    songs = ((j or {}).get("result") or {}).get("songs") or []
    want_t, want_a = _norm(title), _norm(artist)
    best, best_rank = None, -1
    for s in songs:
        if not isinstance(s, dict):
            continue
        if not _title_like(_norm(str(s.get("name") or "")), want_t):
            continue
        rank = 0
        if want_a:
            names = [_norm(str((a or {}).get("name") or "")) for a in (s.get("artists") or [])]
            if want_a in names:
                rank += 2
        try:
            d = int(s.get("duration") or 0)
        except Exception:
            swallow("online._netease_search")
            d = 0
        if duration_ms > 0 and d > 0 and abs(d - duration_ms) < 5000:
            rank += 1
        if rank > best_rank:
            best, best_rank = s, rank
    return best

def _netease_lyrics(song_id) -> str:
    try:
        sid = int(song_id or 0)
    except Exception:
        swallow("online._netease_lyrics")
        return ""
    if sid <= 0:
        return ""
    j = _json(f"https://music.163.com/api/song/lyric?id={sid}&lv=1&kv=1&tv=-1")
    try:
        return str(((j or {}).get("lrc") or {}).get("lyric") or "").strip()
    except Exception:
        swallow("online._netease_lyrics")
        return ""

def _get(url: str) -> Optional[bytes]:
    headers = {"User-Agent": UA, "Accept": "application/json,text/plain,*/*"}
    if "163.com" in url:
        headers["Referer"] = "https://music.163.com/"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if not 200 <= r.status < 300:
                return None
            return r.read()
    except Exception:
        swallow("online._get")
        return None

def _json(url: str):
    data = _get(url)
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8", "replace"))
    except Exception:
        swallow("online._json")
        return None
