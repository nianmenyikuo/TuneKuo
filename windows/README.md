# TuneKuo for Windows

全格式本地音乐播放器，可以设为 Windows 的默认音频播放器 —— 双击音乐文件就用它打开。

这是安卓版 **TuneKuo** 的 Windows 版本，界面与功能对齐：列表 / 搜索 / 封面 / 歌词 / 四种播放模式。

---

## 一、功能

| 分类 | 说明 |
| --- | --- |
| 播放格式 | MP3、FLAC、APE、WAV、M4A/AAC、OGG、Opus、WMA、AIFF、DSD(DSF/DFF)、WV、TTA、TAK、MKA、AC3、DTS、MPC… 能播的格式由 libVLC 决定，基本覆盖市面上所有音频格式 |
| 曲库 | 添加文件 / 添加文件夹 / 一键扫描「音乐」「下载」「桌面」以及各磁盘根目录 |
| 搜索 | 顶部搜索框，实时按歌名 / 歌手 / 专辑过滤，Esc 清空 |
| 播放模式 | 顺序播放、列表循环、单曲循环、随机播放（底栏左侧按钮循环切换） |
| 封面 / 歌词 | 读取内嵌封面 + 同名 `.lrc`（含时间轴，逐行高亮，点一行跳转到该句） |
| 媒体键 | 键盘 / 耳机上的 ▶⏸ ⏮ ⏭ ⏹ 直接控制，无需窗口在前台 |
| 记住状态 | 关掉再开：曲库、当前曲目、音量、播放模式都在 |
| 单实例 | 已经在播放时再双击别的歌，会直接加到当前窗口播放，不会开第二个播放器 |
| 默认播放器 | 一键注册到系统（HKCU，不需要管理员），双击 `.mp3` 等直接用它打开 |
| 快捷键 | `空格` 播放/暂停，`←/→` 快退/快进 5 秒，`Ctrl+O` 打开文件，`Ctrl+F` 搜索，`Esc` 清空搜索 |

## 二、安装使用

**方式一：安装程序（推荐）**

从 [发布页](https://github.com/nianmenyikuo/TuneKuo/releases) 下载 `TuneKuo-Setup-*.exe` 双击安装：

1. 向导里选「为所有用户安装」或「仅为我安装」
2. 附加任务默认勾选：创建桌面快捷方式、注册为音频播放器候选（可取消）
3. 装完可直接启动；卸载走「设置 → 应用」，注册表和快捷方式会一并清理（曲库配置保留在 `%APPDATA%\TuneKuo`）

**方式二：免安装解压包**

1. 把 `TuneKuo` 文件夹整个解压出来（**不要只复制 exe**，`vlc\` 和 `_internal\` 都要在）
2. 双击 `TuneKuo.exe`
3. 想设为默认播放器 → 点右上角 **设为默认播放器**：
   - 程序会写入注册表，把自己挂进系统的「默认应用」列表
   - 然后自动打开「设置 → 应用 → 默认应用」，在 **音乐播放器** 那一项选择 **TuneKuo** 即可全部生效
4. 之后双击任意音乐文件就是 TuneKuo 打开（也可以右键 →「打开方式」→ 选择 TuneKuo）

> 为什么不能像老软件那样"一键抢占"？Windows 8 以后，系统给用户的默认程序选择加了哈希保护（`UserChoice`），任何程序都**不能**静默修改，只能由用户在设置里确认一次。这是系统限制，不是软件的问题。

## 三、自己打包

```powershell
# 在项目目录打开 PowerShell，然后：

# 1) 下载 64 位 libvlc 到 vendor\vlc64（约 80MB，走清华镜像）
.\scripts\fetch_vlc.ps1

# 2) 打包（需要 Python 3.10+，会自动装依赖）
.\build.ps1
```

> 如果提示"禁止运行脚本"，先用一次：
> `powershell -ExecutionPolicy Bypass -File .\build.ps1`

**做成安装程序**（可选，需先装 [Inno Setup 6](https://jrsoftware.org/isdl.php)）：

```powershell
python scripts\make_installer.py     # 生成 installer\TuneKuo.iss，并编译出 dist-installer\TuneKuo-Setup-*.exe
```

产物在 `dist\TuneKuo\`，整个文件夹拷给别人就能用（实测 **189 MB / 477 个文件**，其中 121 MB 是解码库 `vlc\`）。
打包完成后 `dist\TuneKuo\` 里是：`TuneKuo.exe` + `_internal\` + `vlc\` + `使用说明.md`（就是本文档）。

**开发模式运行**（改代码后立刻看效果，不用打包）：

```powershell
.\run.ps1
.\run.ps1 "D:\Music\某首歌.flac"     # 带文件参数启动
python scripts\smoke_test.py          # 不弹窗口，自检解码链路（WAV/MP3/FLAC/OGG + 播放模式）
python scripts\ui_test.py             # 弹出窗口自动跑一遍：加载/搜索/播放/歌词/音量/暂停
```

**打包后自检**（没有控制台，结果写到 `%TEMP%\tunekuo_selftest.txt`）：

```powershell
dist\TuneKuo\TuneKuo.exe --selftest "D:\Music\某首歌.flac"
```

**命令行开关**：`--register` 注册默认播放器 ｜ `--unregister` 撤销 ｜ `--status` 看每种格式当前是谁 ｜
`--open-defaults` 打开系统默认应用页 ｜ 加 `--quiet` 不弹窗（结果写到 `%TEMP%\tunekuo_cli.txt`，方便脚本调用）。

## 四、目录结构

```
TuneKuo-Windows\（仓库里位于 windows\）
├─ app\                  程序本体
│  ├─ main.py            入口：命令行参数、单实例、启动界面
│  ├─ ui.py              tkinter 界面（深色主题、列表/搜索/封面/歌词/播放条）
│  ├─ player.py          libVLC 播放引擎（播放模式、切歌、进度、音量）
│  ├─ vlcenv.py          定位 64 位 libvlc（打包后 vlc\ 目录 / 系统安装的 VLC）
│  ├─ library.py         扫描音频文件 + 后台读取元数据（封面/歌词/时长）
│  ├─ metadata.py        手写标签解析：ID3v2、FLAC、OGG、APE、MP4、LRC
│  ├─ assoc.py           注册成 Windows 默认播放器（HKCU 注册表）
│  ├─ register.py        命令行版注册工具
│  ├─ mediakeys.py       系统媒体键（播放/暂停/上一首/下一首/停止）
│  ├─ instance.py        单实例：把文件转交给已运行的窗口
│  └─ assets\icon.ico    程序图标
├─ scripts\
│  ├─ fetch_vlc.ps1      下载并精简 64 位 VLC 运行库
│  ├─ make_icon.py       PNG -> 多尺寸 .ico
│  ├─ smoke_test.py      解码链路自检（不开界面）
│  ├─ ui_test.py         界面自检（真开窗口跑一遍各功能）
│  ├─ make_zip.py        把 dist\TuneKuo 打成可分发 zip（输出到桌面）
│  └─ make_installer.py  生成安装包（需 Inno Setup 6）
├─ installer\            安装包脚本与简体中文语言文件（TuneKuo.iss 由 make_installer.py 生成）
├─ assets\icon-source.png 图标原图（改图标用）
├─ vendor\vlc64\         64 位 libvlc（打包用，不进版本库）
├─ dist\TuneKuo\         打包产物（拷贝这个文件夹就能用）
├─ build.ps1             打包脚本
└─ run.ps1               开发运行脚本
```

## 五、常见问题

**打开提示"没有找到 64 位 libvlc"**
程序旁边缺少 `vlc\` 目录。把解压出来的 64 位 VLC 放到 exe 同级并改名 `vlc`，或安装 [64 位 VLC](https://www.videolan.org/vlc/)。
注意 `Program Files (x86)` 里的是 **32 位** VLC，64 位 Python 载入不了，用不上。

**某个文件播放失败**
该格式的解码插件缺失（精简 VLC 时删掉了极冷门的插件），或文件损坏。多数常见格式都自带。

**设为默认播放器后双击还是老程序打开**
系统里已经存在 `UserChoice` 记录。到「设置 → 应用 → 默认应用 → 按文件类型选择默认应用」，把 `.mp3` 等逐个改成 TuneKuo（或者在「音乐播放器」一项里改）。

**想彻底撤销**
`TuneKuo.exe --unregister`（或 `python app\register.py unregister`），只删除自己写入的 HKCU 项，不动别的软件。

## 六、说明

- 纯本地播放器：不联网、不上传、没有账号，全部数据只在你机器上（曲库记忆在 `%APPDATA%\TuneKuo\state.json`）。
- 只写 `HKCU`（当前用户）注册表，不请求管理员权限。
- 与安卓版 TuneKuo 共享同一套 UI 设计，代码各自独立。
