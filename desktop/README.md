# TuneKuo 电脑版（Windows / Linux）

全格式本地音乐播放器，可以设为系统的默认音频播放器 —— 双击音乐文件就用它打开。

Windows 与 Linux **共用同一份源码**，只有少数几处按平台分支（界面字体、窗口图标、默认程序注册方式）。
这是安卓版 **TuneKuo** 的电脑版，界面与功能对齐：列表 / 搜索 / 封面 / 歌词 / 四种播放模式 / 设置页（汉语 · English · 日本語）。

> 目录说明：1.0.4 起本目录由 `windows\` 改名为 `desktop\`，因为 Linux 版也用这份代码。

---

## 一、功能

| 分类 | 说明 |
| --- | --- |
| 播放格式 | MP3、FLAC、APE、WAV、M4A/AAC、OGG、Opus、WMA、AIFF、DSD(DSF/DFF)、WV、TTA、TAK、MKA、AC3、DTS、MPC… 能播的格式由 libVLC 决定，基本覆盖市面上所有音频格式 |
| 曲库 | 添加文件 / 添加文件夹 / 一键扫描「音乐」「下载」「桌面」以及各磁盘根目录；工具栏「扫描音乐库」可随时重扫 |
| 搜索 | 顶部搜索框，实时按歌名 / 歌手 / 专辑过滤，Esc 清空 |
| 设置页 | 工具栏「设置」按钮进入：界面语言（汉语 / English / 日本語）、版本号、问题反馈入口；与手机端右滑设置页一致 |
| 界面语言 | 三种语言随时切换、立即生效并记住；翻译集中在 `app\i18n.py`，加语言只改这一个文件 |
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

**方式三：Linux**

```bash
sudo apt install vlc-plugin-base        # 解码引擎（Fedora: sudo dnf install vlc，Arch: sudo pacman -S vlc）
pip install -r requirements.txt         # python-vlc + Pillow（打包时才需要 pyinstaller）
./linux/run.sh                          # 开发态直接运行

./linux/build.sh --install              # PyInstaller 打成 dist/TuneKuo/
./linux/install.sh                      # 装到 ~/.local，并注册成默认播放器
```

`install.sh` 写 `~/.local/share/applications/tunekuo.desktop`，再用 `xdg-mime` 把 25 种音频格式指向 TuneKuo（用户级，不需要 root）。
撤销：`./linux/install.sh --uninstall`。配置与语言记忆在 `~/.config/TuneKuo/state.json`。

> 已知差异：Linux 上系统媒体键（▶⏸ ⏮ ⏭）暂不支持（要额外的 MPRIS/D-Bus 支持）；窗口图标用 `app/assets/icon.png`（Linux 的 Tk 不认 `.ico`）；界面字体自动挑系统里有的那一个（Noto Sans CJK / 文泉驿 / DejaVu）。

**方式四：Linux 现成包（Release 附件）**

```bash
sudo dpkg -i TuneKuo-1.0.5-all.deb        # 源码包：依赖系统 python3-tk / python3-vlc / vlc-plugin-base
chmod +x TuneKuo-1.0.5-x86_64.AppImage    # 免安装：自带 libvlc 与插件，双击就跑
./TuneKuo-1.0.5-x86_64.AppImage
```

deb 里装的是 Python 源码（`/usr/share/tunekuo/*.py`）加上启动器 `/usr/bin/tunekuo`，只有 ~285 KB；
AppImage 把 libvlc 和插件一起塞进包里，对方不装 VLC 也能放，代价是体积大一些。
两个包都由 GitHub Actions 在 Ubuntu 22.04 上构建（`.github/workflows/linux-packages.yml`），
构建时会在 xvfb 里跑一遍界面自检、并真的 `dpkg -i` 装一次再启动验证。

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

**打 Linux 包**（`make_deb.py` 哪儿都能跑；AppImage 必须在 Linux 上跑）：

```bash
python3 scripts/make_deb.py        # -> dist-linux/TuneKuo-<版本>-all.deb（纯源码包，约 285 KB）
bash linux/make_appimage.sh        # -> dist-linux/TuneKuo-<版本>-x86_64.AppImage（自带 libvlc）
```

`make_appimage.sh` 先调 `linux/build.sh` 出 PyInstaller onedir，再把系统 libvlc 与插件复制到
`_internal/vlc`（`vlcenv.posix_setup()` 认这个位置，`AppRun` 会设好 `VLC_PLUGIN_PATH`），最后交给 appimagetool。
`make_deb.py` 只用标准库，所以 Windows 上也能跑，方便先把包结构验一遍。

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
desktop\（仓库里的 desktop\ 目录；Windows 与 Linux 同一份代码）
├─ app\                  程序本体
│  ├─ main.py            入口：命令行参数、单实例、启动界面
│  ├─ ui.py              tkinter 界面（深色主题、列表/搜索/封面/歌词/播放条/设置页）
│  ├─ i18n.py            多语言文本表（汉语 / English / 日本語）+ 语言记忆
│  ├─ version.py         版本号、程序名、反馈链接（只在这一处改）
│  ├─ paths.py           跨平台路径：配置目录（Windows %APPDATA%，Linux ~/.config）、资源目录
│  ├─ player.py          libVLC 播放引擎（播放模式、切歌、进度、音量）
│  ├─ vlcenv.py          定位 libvlc（Windows：随包 vlc\ / 系统 VLC；Linux：系统 VLC）
│  ├─ library.py         扫描音频文件 + 后台读取元数据（封面/歌词/时长）
│  ├─ metadata.py        手写标签解析：ID3v2、FLAC、OGG、APE、MP4、LRC
│  ├─ online.py          联网获取歌曲信息/歌词（iTunes + LRCLIB + 网易云兜底）
│  ├─ assoc.py           注册成系统默认播放器（Windows：HKCU 注册表；Linux：.desktop + xdg-mime）
│  ├─ register.py        命令行版注册工具
│  ├─ mediakeys.py       系统媒体键（仅 Windows）
│  ├─ instance.py        单实例：把文件转交给已运行的窗口
│  └─ assets\icon.ico    程序图标（Windows 用 .ico，Linux 用同目录的 icon.png）
├─ scripts\
│  ├─ fetch_vlc.ps1      下载并精简 64 位 VLC 运行库
│  ├─ make_icon.py       PNG -> 多尺寸 .ico / icon.png / 安卓 mipmap（--android）
│  ├─ smoke_test.py      解码链路自检（不开界面）
│  ├─ ui_test.py         界面自检（真开窗口跑一遍各功能）
│  ├─ make_zip.py        把 dist\TuneKuo 打成可分发 zip（输出到桌面）
│  ├─ make_installer.py  生成安装包（需 Inno Setup 6）
│  └─ make_deb.py        打 Linux .deb（纯标准库，Windows 上也能跑）
├─ linux\
│  ├─ run.sh             开发态运行（不打包）
│  ├─ build.sh           PyInstaller 打包 -> dist/TuneKuo/
│  ├─ make_appimage.sh   打 Linux AppImage（自带 libvlc，只能在 Linux 上跑）
│  └─ install.sh         装到 ~/.local + 注册默认播放器（--uninstall 卸载）
├─ installer\            安装包脚本与简体中文语言文件（TuneKuo.iss 由 make_installer.py 生成）
├─ assets\icon-source.png 图标原图（改图标用，跑 scripts\make_icon.py 生成各平台图标）
├─ vendor\vlc64\         64 位 libvlc（打包用，不进版本库）
├─ dist\TuneKuo\         打包产物（拷贝这个文件夹就能用）
├─ build.ps1             打包脚本（Windows）
└─ run.ps1               开发运行脚本（Windows）
```

## 五、常见问题

**打开提示"没有找到 64 位 libvlc"**
程序旁边缺少 `vlc\` 目录。把解压出来的 64 位 VLC 放到 exe 同级并改名 `vlc`，或安装 [64 位 VLC](https://www.videolan.org/vlc/)。
注意 `Program Files (x86)` 里的是 **32 位** VLC，64 位 Python 载入不了，用不上。

**Linux 上提示"没有找到 libvlc"**
装一下 VLC 运行库：`sudo apt install vlc-plugin-base`（Fedora: `sudo dnf install vlc`，Arch: `sudo pacman -S vlc`）。

**某个文件播放失败**
该格式的解码插件缺失（精简 VLC 时删掉了极冷门的插件），或文件损坏。多数常见格式都自带。

**设为默认播放器后双击还是老程序打开**
系统里已经存在 `UserChoice` 记录。到「设置 → 应用 → 默认应用 → 按文件类型选择默认应用」，把 `.mp3` 等逐个改成 TuneKuo（或者在「音乐播放器」一项里改）。

**想彻底撤销**
`TuneKuo.exe --unregister`（或 `python app\register.py unregister`），只删除自己写入的 HKCU 项，不动别的软件。

## 六、说明

- 纯本地播放器：不联网、不上传、没有账号，全部数据只在你机器上（曲库记忆与语言选择在 `%APPDATA%\TuneKuo\state.json`，Linux 上是 `~/.config/TuneKuo/state.json`；联网获取歌曲信息只在你主动点了菜单那一项时才发请求）。
- Windows 上只写 `HKCU`（当前用户）注册表，不请求管理员权限；Linux 上只写 `~/.local`，不需要 root。
- Linux 的 `.deb` 与 AppImage 由 GitHub Actions 在 Ubuntu 上构建（本机没有 Linux 环境），
  构建日志与产物在 [Actions](https://github.com/nianmenyikuo/TuneKuo/actions) 里可查。
- 与安卓版 TuneKuo 共享同一套 UI 设计，代码各自独立。
- Bug 与建议 → [提交 Issue](https://github.com/nianmenyikuo/TuneKuo/issues/new/choose)（设置页里也有直达链接）。
