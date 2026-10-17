from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import vlcenv

print("libvlc  :", vlcenv.LIB)
if vlcenv.LIB is None:
    print("结果    : 失败——找不到 64 位 libvlc")
    sys.exit(1)

import vlc
from player import PlayMode, Player, Track

print("版本    :", vlc.libvlc_get_version().decode())

def make_wav(path: str, seconds: float = 3.0, rate: int = 44100) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * seconds)):
            v = int(12000 * math.sin(2 * math.pi * 440 * i / rate))
            frames += struct.pack("<hh", v, v)
        w.writeframes(bytes(frames))

def transcode(src: str, dst: str, acodec: str, mux: str = "raw") -> bool:
    inst = vlc.Instance("--no-video", "--quiet")
    media = inst.media_new(src, f":sout=#transcode{{acodec={acodec},ab=192,channels=2,samplerate=44100}}:standard{{access=file,mux={mux},dst={dst}}}")
    mp = inst.media_player_new()
    mp.set_media(media)
    if mp.play() != 0:
        return False
    for _ in range(200):
        time.sleep(0.1)
        if mp.get_state() in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
            break
    ok = os.path.isfile(dst) and os.path.getsize(dst) > 4096
    mp.release()
    inst.release()
    return ok

def play_check(label: str, path: str) -> bool:
    events = []
    p = Player(on_event=lambda k, v=None: events.append(k))
    p.set_playlist([Track(path=path)], start=0, autoplay=True)
    t0 = time.time()
    while time.time() - t0 < 4:
        time.sleep(0.2)
        if p.get_time() > 0:
            break
    played = p.is_playing() or p.get_time() > 0
    print(f"{label:<10} 时长 {p.get_length():>6}ms  已播 {p.get_time():>5}ms  "
          f"音量 {p.get_volume():>3}  事件 {sorted(set(events))}  -> {'OK' if played else '失败'}")
    p.release()
    return played

tmp = tempfile.mkdtemp(prefix="tunekuo_smoke_")
wav = os.path.join(tmp, "tone.wav")
make_wav(wav)
print()

results = {"WAV 播放": play_check("WAV", wav)}

mp3 = os.path.join(tmp, "tone.mp3")
flac = os.path.join(tmp, "tone.flac")
ogg = os.path.join(tmp, "tone.ogg")
if transcode(wav, mp3, "mp3"):
    results["MP3 解码"] = play_check("MP3", mp3)
if transcode(wav, flac, "flac"):
    results["FLAC 解码"] = play_check("FLAC", flac)
if transcode(wav, ogg, "vorb", "ogg"):
    results["OGG 解码"] = play_check("OGG", ogg)

p = Player(on_event=lambda k, v=None: None)
p.set_playlist([Track(path=wav) for _ in range(4)], start=0, autoplay=False)
modes = []
for _ in range(4):
    modes.append(PlayMode.LABELS[p.cycle_mode()])
p.release()
print("\n播放模式轮换:", " -> ".join(modes))

from metadata import parse_lrc, read_tags

tags = read_tags(wav)
print("read_tags :", tags)
print("parse_lrc :", parse_lrc("[00:01.50]第一句\n[00:03.00]第二句"))
print("临时文件  :", tmp)

failed = [k for k, v in results.items() if not v]
print("\n结果      :", "全部通过" if not failed else f"失败项 {failed}")
sys.exit(1 if failed else 0)
