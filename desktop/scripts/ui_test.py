from __future__ import annotations

import json
import math
import os
import struct
import sys
import tempfile
import time
import wave
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_STATE_HOME = tempfile.mkdtemp(prefix="tunekuo_ui_state_")
os.environ["APPDATA"] = _STATE_HOME
os.environ["XDG_CONFIG_HOME"] = _STATE_HOME

sys.path.insert(0, os.path.join(ROOT, "app"))

import paths
import vlcenv

if os.name == "nt":
    if vlcenv.LIB is None:
        print("失败：找不到 64 位 libvlc")
        sys.exit(1)
else:
    try:
        import vlc
    except Exception as exc:
        print("失败：python-vlc / libvlc 不可用：", exc)
        sys.exit(1)

import tkinter as tk

from ui import TuneKuoUI
from version import VERSION

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

app.var_search.set("不存在")
pump(0.3)
print("搜索过滤后  :", len(app.tree.get_children()))
app.var_search.set("测试")
pump(0.3)
print("恢复过滤后  :", len(app.tree.get_children()))
app.var_search.set("")

m = app._row_menu(0)
labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1) if m.type(i) == "command"]
print("右键菜单    :", labels)
for want in ("放这首喵", "上网找这首歌的资料（连歌词）喵", "看看这首歌的底细喵", "复制歌名喵", "复制文件路径喵",
             "在文件夹里找出来喵", "从列表拿掉喵", "删掉文件喵"):
    if want not in labels:
        errors.append(f"右键菜单缺了「{want}」")
m.destroy()

app.copy_text(app.player.tracks[0].path)
pump(0.2)
try:
    clip = app.root.clipboard_get()
except Exception:
    clip = ""
print("剪贴板      :", repr(clip))
if os.path.normcase(clip) != os.path.normcase(app.player.tracks[0].path):
    errors.append(f"剪贴板内容不对: {clip!r}")
if app.lb_status.cget("text") != "复制好啦喵":
    errors.append("复制后状态栏不对: " + app.lb_status.cget("text"))

class _FakeBox:

    def __init__(self) -> None:
        self.calls = []
        self.answer = True

    def askyesno(self, title, msg, **kw) -> bool:
        self.calls.append(("ask", title, msg))
        return self.answer

    def showerror(self, title, msg, **kw) -> None:
        self.calls.append(("error", title, msg))

    def showinfo(self, title, msg, **kw) -> None:
        self.calls.append(("info", title, msg))

    def showwarning(self, title, msg, **kw) -> None:
        self.calls.append(("warn", title, msg))

import online as online_mod
import ui as ui_mod

fake = _FakeBox()
real_box = ui_mod.messagebox
ui_mod.messagebox = fake

app.show_song_detail(0)
print("详情弹窗    :", fake.calls[-1][1], "|", fake.calls[-1][2].replace("\n", " / ")[:90])
if fake.calls[-1][0] != "info" or "路径" not in fake.calls[-1][2]:
    errors.append("歌曲详情弹窗内容不对")

real_fetch = online_mod.fetch
online_mod.fetch = lambda t: online_mod.Info(
    "晴天", "周杰伦", "叶惠美", "2003", "Mandopop", "iTunes", "LRCLIB",
    b"\xff\xd8\xff" + b"0" * 64, "[00:01.00]第一句\n[00:02.00]第二句\n")
app.fetch_online(0)
deadline = time.time() + 5
while time.time() < deadline and len(fake.calls) < 2:
    pump(0.1)
online_mod.fetch = real_fetch
t0 = app.player.tracks[0]
print("联网后曲目  :", repr(t0.lyrics), "| 封面", len(t0.cover or b""), "字节")
print("联网后状态  :", app.lb_status.cget("text"))
if "第一句" not in (t0.lyrics or ""):
    errors.append("联网获取的歌词没写进曲目")
if not t0.cover:
    errors.append("联网获取的封面没写进曲目")
if len(fake.calls) < 2 or fake.calls[-1][0] != "info":
    errors.append(f"联网获取成功后没弹信息框: {fake.calls[-1:]}")
elif "从哪找的喵" not in fake.calls[-1][2]:
    errors.append("信息框里没有来源行")

row = app.tree.item("0", "values")            
print("列表已替换  :", row)
if row[0] != "晴天" or row[1] != "周杰伦":
    errors.append(f"联网获取后列表没替换: {row}")

online_mod.fetch = lambda t: None
app.fetch_online(0)
deadline = time.time() + 5
while time.time() < deadline and len(fake.calls) < 3:
    pump(0.1)
online_mod.fetch = real_fetch
if len(fake.calls) < 3 or fake.calls[-1][0] != "warn":
    errors.append(f"联网失败没提示: {fake.calls[-1:]}")

ui_mod.messagebox = real_box

app.player.play_index(0)
pump(3.0)
print("播放状态    :", "播放中" if app.player.is_playing() else "未播放",
      "| 进度", app.player.get_time(), "ms")
print("歌词行数    :", len(app.lrc_lines), "| 当前高亮行", app.current_lyric)
print("播放按钮    :", repr(app.btn_play.cget("text")), "| 模式", app.btn_mode.cget("text"))

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

app.toggle_play()
pump(0.6)
print("暂停后再切  :", "播放中" if app.player.is_playing() else "已暂停")
app.player.stop()
pump(0.4)

app.player.play_index(0)
pump(2.0)
print("\n重新播放    :", "播放中" if app.player.is_playing() else "未播放")

print("设置按钮    :", repr(app.btn_settings.cget("text")))
app.show_settings()
pump(1.0)
print("设置页标题  :", repr(app.lb_settings_title.cget("text")),
      "| 返回按钮", repr(app.btn_back.cget("text")))
print("版本号      :", repr(app.lb_version.cget("text")))
print("滑动位置    :", round(app.offset, 2), "(1=设置页)")
if app.lb_settings_title.cget("text") != "设置喵":
    errors.append("设置页标题不对: " + app.lb_settings_title.cget("text"))
if app.offset != 1.0:
    errors.append(f"没有滑到设置页: offset={app.offset}")
if app.lb_version.cget("text") != f"TuneKuo {VERSION}":
    errors.append("版本号不对: " + app.lb_version.cget("text"))

order = [("标题", app.lb_settings_title.winfo_rooty()),
         ("语言", app.lb_lang_group.winfo_rooty()),
         ("反馈", app.lb_feedback.winfo_rooty()),
         ("版本", app.lb_version.winfo_rooty())]
print("设置页顺序  :", order)
tops = [y for _, y in order]
if tops != sorted(tops) or len(set(tops)) != len(tops):
    errors.append(f"设置页内容顺序不对: {order}")
print("语言选项    :", sorted(app.lang_labels))
if sorted(app.lang_labels) != ["en", "ja", "zh"]:
    errors.append(f"语言选项不对: {sorted(app.lang_labels)}")
for code, lb in app.lang_labels.items():
    if not lb.bind("<Button-1>"):
        errors.append(f"{code} 选项没绑点击事件")

app.on_escape()
pump(1.0)
print("Esc 返回后  :", round(app.offset, 2), "(0=主界面)")
if app.offset != 0.0:
    errors.append(f"Esc 没有回到主界面: offset={app.offset}")

app.root.update()
width = max(app.root.winfo_width(), 600)
print("窗口宽度    :", width)

class _Ev:

    def __init__(self, x):
        self.x_root = x
        self.y_root = 100
        self.widget = app.tree

app._drag_press(_Ev(width - 40))
app._drag_motion(_Ev(width // 2))
mid = app.offset
print("拖动跟手    :", round(mid, 2), "(0<offset<1 说明页面跟着鼠标走)")
if not 0.0 < mid < 1.0:
    errors.append(f"拖动没跟手: offset={mid}")
app._drag_motion(_Ev(40))
app._drag_release(_Ev(40))
pump(1.2)
print("向左拖动后  :", round(app.offset, 2), "(1=设置页)")
if app.offset != 1.0:
    errors.append(f"向左拖动没有进入设置页: offset={app.offset}")

app._drag_press(_Ev(40))
app._drag_motion(_Ev(width - 40))
app._drag_release(_Ev(width - 40))
pump(1.2)
print("向右拖动后  :", round(app.offset, 2), "(0=主界面)")
if app.offset != 0.0:
    errors.append(f"向右拖动没有回到主界面: offset={app.offset}")

app.show_settings()
pump(0.5)
app.player.play_index(0)
pump(0.8)
print("\n切语言前    :", "播放中" if app.player.is_playing() else "未播放",
      "| 曲目", app.player.index, "| 模式", app.btn_mode.cget("text"))
if not app.player.is_playing():
    errors.append("切语言前就没在播放，后面的断言不成立")
lang_group = []
for code, want in (("en", ("Settings, nya", "Settings, nya", "Title, nya", "← Back, nya", "Language, nya",
                          "Found a bug or got an idea? Tell the kitty, nya")),
                   ("ja", ("設定にゃ", "設定にゃ", "タイトルにゃ", "← もどるにゃ", "言語にゃ",
                           "バグや要望があったら教えてにゃ"))):
    app.set_lang(code)
    pump(0.3)
    got = (app.lb_settings_title.cget("text"), app.btn_settings.cget("text"),
           app.tree.heading("title", "text"), app.btn_back.cget("text"),
           app.lb_lang_group.cget("text"), app.lb_feedback.cget("text"))
    print(f"切到 {code}     :", got)
    if got != want:
        errors.append(f"{code} 语言没生效: {got} != {want}")
    mark = app.lang_labels[code].cget("text")
    print("  选中样式  :", repr(mark), app.lang_labels[code].cget("bg"))
    if not mark.startswith("●"):
        errors.append(f"{code} 选项没有选中标记: {mark!r}")
    lang_group.append((app.btn_add_files.cget("text"), app.lb_status.cget("text")))

print("工具栏/状态  :", lang_group, "(en, ja)")

playing = app.player.is_playing()
print("切语言后    :", "播放中" if playing else "未播放", "| 曲目", app.player.index,
      "| 列表", len(app.tree.get_children()), "行")
if not playing:
    errors.append("切换语言后播放中断了")
if app.player.index != 0:
    errors.append(f"切换语言后曲目被换了: index={app.player.index}")

app.set_lang("zh")
pump(0.3)
back = (app.lb_settings_title.cget("text"), app.tree.heading("title", "text"),
        app.btn_settings.cget("text"), app.btn_back.cget("text"))
print("切回 zh     :", back)
if back != ("设置喵", "标题喵", "设置喵", "← 回去喵"):
    errors.append(f"切回中文失败: {back}")

app.show_main()
pump(0.3)
print("回主界面    :", round(app.offset, 2), "| 列表", len(app.tree.get_children()), "行")
if not app.tree.get_children():
    errors.append("切换语言后列表空了")
STATE_PATH = os.path.join(paths.config_dir(), "state.json")
try:
    with open(STATE_PATH, encoding="utf-8") as fp:
        saved = json.load(fp)
    print("state.json  :", sorted(saved))
    if saved.get("lang") != "zh":
        errors.append(f"state.json 没记住 lang: {saved.get('lang')!r}")
except Exception as exc:
    errors.append(f"读 state.json 失败: {exc}")

import version

if not app.lb_feedback.bind("<Button-1>"):
    errors.append("反馈链接没有绑定点击事件")
opened = []
_orig_open = webbrowser.open
webbrowser.open = lambda url, *a, **k: (opened.append(url), True)[1]
try:
    app.open_feedback()
finally:
    webbrowser.open = _orig_open
print("反馈链接    :", opened, "| version.FEEDBACK_URL =", version.FEEDBACK_URL)
if opened != [version.FEEDBACK_URL]:
    errors.append(f"反馈链接不对: {opened}")
if version.FEEDBACK_URL != "https://github.com/nianmenyikuo/TuneKuo/issues/new/choose":
    errors.append(f"反馈链接地址不对: {version.FEEDBACK_URL}")

with open(STATE_PATH, encoding="utf-8") as fp:
    st = json.load(fp)
st["lang"] = "ja"
st["zz_probe"] = 123          
with open(STATE_PATH, "w", encoding="utf-8") as fp:
    json.dump(st, fp, ensure_ascii=False)
app.load_state()
pump(0.4)
print("读回 ja     :", repr(app.lb_settings_title.cget("text")),
      repr(app.btn_settings.cget("text")))
if (app.lb_settings_title.cget("text"), app.btn_settings.cget("text")) != ("設定にゃ", "設定にゃ"):
    errors.append("没有按 state.json 记住的语言显示")
if app.lang_labels and app.lang_labels["ja"].cget("text").split()[-1] != "日本語":
    errors.append("日文选项没高亮")

app.save_state()
with open(STATE_PATH, encoding="utf-8") as fp:
    st2 = json.load(fp)
print("存回 state  :", sorted(st2))
if st2.get("zz_probe") != 123:
    errors.append("save_state 把别的键弄丢了")
if st2.get("lang") != "ja":
    errors.append(f"save_state 没写 lang: {st2.get('lang')!r}")

app.set_lang("zh")
pump(0.3)
print("最后切回 zh :", repr(app.btn_settings.cget("text")), "| 列表",
      len(app.tree.get_children()), "| 模型", len(app.player.tracks))
if app.btn_settings.cget("text") != "设置喵":
    errors.append("最后切回中文失败")
if len(app.tree.get_children()) != len(app.player.tracks):
    errors.append("切语言后列表被搜索框占位符过滤空了: 树 "
                  f"{len(app.tree.get_children())} / 模型 {len(app.player.tracks)}")

extra = os.path.join(tmp, "待删除.wav")
make_wav(extra, seconds=0.5)
app.add_paths([extra])
pump(0.8)
n_before = len(app.tree.get_children())
m_before = len(app.player.tracks)
print("删除前      : 树", n_before, "| 模型", m_before, "| 查询", repr(app._query()))
idx = next(i for i, tr in enumerate(app.player.tracks) if tr.path == extra)
box = _FakeBox()
ui_mod.messagebox = box
box.answer = False
app.delete_track(idx)
pump(0.2)
print("取消删除    :", "文件还在" if os.path.exists(extra) else "文件没了",
      "| 树", len(app.tree.get_children()), "| 模型", len(app.player.tracks))
if not os.path.exists(extra) or len(app.player.tracks) != m_before:
    errors.append("确认框选了“否”却还是删了")
box.answer = True
app.delete_track(idx)
pump(0.3)
print("确认删除    :", "文件还在" if os.path.exists(extra) else "文件没了",
      "| 树", len(app.tree.get_children()), "| 模型", len(app.player.tracks),
      "| 状态", repr(app.lb_status.cget("text")))
if os.path.exists(extra):
    errors.append("确认删除后文件还在")
if len(app.player.tracks) != m_before - 1 or len(app.tree.get_children()) != n_before - 1:
    errors.append(f"删除后列表没少一行: 树 {len(app.tree.get_children())}/{n_before - 1} "
                  f"模型 {len(app.player.tracks)}/{m_before - 1}")
if "删掉啦喵" not in app.lb_status.cget("text"):
    errors.append("删除后状态栏没提示: " + app.lb_status.cget("text"))
ui_mod.messagebox = real_box

real_os_name = ui_mod.os.name
probe = os.path.join(tmp, "a b.mp3")
ui_mod.os.name = "nt"
nt_cmd = ui_mod._reveal_cmd(probe)
ui_mod.os.name = "posix"
posix_cmd = ui_mod._reveal_cmd(probe)
ui_mod.os.name = real_os_name
print("在文件夹中显示 :", "nt", nt_cmd, "| posix", posix_cmd or "（这台机器上没有 xdg-open/open，正常）")
if not nt_cmd or os.path.basename(nt_cmd[0]) != "explorer" or not nt_cmd[1].startswith("/select,"):
    errors.append(f"Windows 分支的打开命令不对: {nt_cmd}")
if posix_cmd and (os.path.basename(posix_cmd[0]) not in ("xdg-open", "open")
                  or posix_cmd[-1] != os.path.dirname(probe)):
    errors.append(f"Linux 分支的打开命令不对: {posix_cmd}")

app.on_close()
print("\n界面自检通过" if not errors else f"\n发现问题: {errors}")
sys.exit(1 if errors else 0)
