"""界面自检（开发者用）：真的把窗口建起来，加载一个临时音频，跑几秒事件循环。

    python scripts/ui_test.py
"""
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

import vlcenv  # noqa: E402

if vlcenv.LIB is None:
    print("失败：找不到 64 位 libvlc")
    sys.exit(1)

import tkinter as tk  # noqa: E402

from ui import TuneKuoUI  # noqa: E402


def make_wav(path: str, seconds: float = 6.0, rate: int = 44100) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(
            struct.pack("<hh", (v := int(9000 * math.sin(2 * math.pi * 330 * i / rate))), v)
            for i in range(int(rate * seconds))))


tmp = tempfile.mkdtemp(prefix="tunekuo_ui_")
wav = os.path.join(tmp, "测试歌曲.wav")
make_wav(wav)
with open(os.path.join(tmp, "测试歌曲.lrc"), "w", encoding="utf-8") as fp:
    fp.write("[00:00.00]第一句歌词\n[00:02.00]第二句歌词\n[00:04.00]第三句歌词\n")

root = tk.Tk()
app = TuneKuoUI(root, initial_paths=[wav])
errors = []


def pump(seconds: float) -> None:
    t0 = time.time()
    while time.time() - t0 < seconds:
        root.update()
        time.sleep(0.03)


pump(1.5)
rows = app.tree.get_children()
print("列表行数    :", len(rows))

# 回归检查：列表里的时长必须真的显示出来（曾经全是 --:--）
dur_text = ""
deadline = time.time() + 5
while time.time() < deadline:
    root.update()
    rows = app.tree.get_children()
    if rows:
        vals = app.tree.item(rows[0], "values")
        dur_text = str(vals[-1]) if vals else ""
        if dur_text not in ("", "--:--"):
            break
    time.sleep(0.05)
print("时长列      :", repr(dur_text), "(期望 0:06)")
if dur_text in ("", "--:--"):
    errors.append(f"列表时长列没有显示出来: {dur_text!r}")

print("标题列      :", app.tree.item(rows[0], "values") if rows else None)
print("状态栏      :", app.lb_status.cget("text"))
print("正在播放    :", app.lb_now.cget("text"), "|", app.lb_now_sub.cget("text"))

# 搜索过滤
app.var_search.set("不存在")
pump(0.3)
print("搜索过滤后  :", len(app.tree.get_children()))
app.var_search.set("测试")
pump(0.3)
print("恢复过滤后  :", len(app.tree.get_children()))
app.var_search.set("")

# 播放 + 歌词跟随
app.player.play_index(0)
pump(3.0)
print("播放状态    :", "播放中" if app.player.is_playing() else "未播放",
      "| 进度", app.player.get_time(), "ms")
print("歌词行数    :", len(app.lrc_lines), "| 当前高亮行", app.current_lyric)
print("播放按钮    :", repr(app.btn_play.cget("text")), "| 模式", app.btn_mode.cget("text"))

# 模式切换 / 音量 / 静音
for _ in range(3):
    app.cycle_mode()
print("三连切模式  :", app.btn_mode.cget("text"))
app.vol.set(35)
pump(0.2)
print("音量        :", app.player.get_volume())
app.toggle_mute()
pump(0.2)
print("静音后音量  :", app.player.get_volume())
app.toggle_mute()
pump(0.2)

# 暂停 / 继续
app.toggle_play()
pump(0.6)
print("暂停后再切  :", "播放中" if app.player.is_playing() else "已暂停")
app.player.stop()
pump(0.4)

app.on_close()
print("\n界面自检通过" if not errors else f"\n发现问题: {errors}")
