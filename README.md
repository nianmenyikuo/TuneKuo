# TuneKuo 🎵

![界面语言](https://img.shields.io/badge/界面语言-中文%20%7C%20English%20%7C%20日本語-red) ![平台](https://img.shields.io/badge/平台-Android%207.0%2B%20%7C%20Windows%2010%2F11-green) ![架构](https://img.shields.io/badge/架构-armeabi--v7a%20%7C%20arm64--v8a%20%7C%20x64-blue)

完全自用的本地音乐播放器，手机（Android）和电脑（Windows）两端都有。基于 libVLC 解码，全格式通吃——DSD (DSF/DFF)、APE、FLAC、杜比 TrueHD 等都能播。

**界面语言：简体中文 / English / 日本語**，两端都能在设置页里随时切换。

## 功能

- **全格式播放**：libVLC 自带解码器，不依赖系统 MediaCodec，无损与杜比码流均可播放
- **四种播放模式**：顺序 / 列表循环 / 单曲循环 / 随机（洗牌队列，手动切歌与自然播完走不同逻辑）
- **锁屏与通知栏**：MediaSession 集成，锁屏显示歌名/封面/进度，支持上一首/播放暂停/下一首与蓝牙线控
- **专辑封面自动获取**：优先内嵌封面（ID3 APIC / FLAC PICTURE / M4A covr），其次同目录 cover.jpg 等常见命名
- **歌词显示**：内嵌歌词标签 + 同名 .lrc 文件双通道，全屏歌词页逐行高亮滚动
- **音乐搜索**：顶部搜索框实时过滤歌名/歌手/专辑，点击结果在完整曲库队列中播放
- **重新扫描**：右上角一键重扫本地音乐，新下载的歌不用重启 App
- **设置页**：主界面右滑进入（Windows 端在工具栏齿轮按钮），可切换界面语言（汉语 / English / 日本語）、查看版本号、跳转问题反馈
- **深色 UI**：卡片式列表、当前曲目高亮（♪）、矢量图标、64dp 渐变播放大按钮

## Windows 版

电脑端是独立的 Python + libVLC + tkinter 实现（源码在 [`windows/`](windows/) 目录），支持 Windows 10 / 11 64 位。

- **下载安装**：见 [最新发布页](https://github.com/nianmenyikuo/TuneKuo/releases)，下载 `TuneKuo-Setup-*.exe` 双击安装（中文向导，安装包内自带解码引擎，无需另装 VLC）
- **可设为默认播放器**：安装时勾选“注册为音频播放器”，装完在 系统设置 → 应用 → 默认应用 里把音频文件关联到 TuneKuo（Windows 不允许程序静默抢占，只能这样手动点一下）
- **设置页**：工具栏齿轮进入，与手机端一致（语言切换 / 版本号 / 问题反馈）
- 功能与手机端对齐：25 种格式、四种播放模式、歌词逐行高亮与内嵌封面、音乐搜索、重新扫描、深色界面、键盘媒体键、单实例

自行构建（需要 64 位 Python 3.10+）：

```powershell
cd windows
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File build.ps1
```

`build.ps1` 会自动下载 64 位 VLC 解码库，打包出免安装目录 `dist\TuneKuo\`。想做成安装程序再跑 `python scripts\make_installer.py`（需先安装 Inno Setup 6）。

## 构建（Android）

- Android Studio：打开项目直接 Run
- 命令行：`./gradlew assembleDebug`（首次先 `gradle wrapper` 生成 wrapper）
- 本机验证过的组合：Gradle 8.9 + JDK 17 + Android SDK 34（`local.properties` 里的 `sdk.dir` 指向本地 SDK）
- APK 输出：`app/build/outputs/apk/debug/app-debug.apk`

## 环境（Android）

- Kotlin / minSdk 24 / targetSdk 34
- 依赖：libVLC (org.videolan.android:libvlc)、AndroidX、MediaSessionCompat

## 说明

- 32 位与 64 位 ABI 均支持（armeabi-v7a + arm64-v8a）
- 开机自启动接收器已内置（可选）
- 杜比 TrueHD/AC-3 码流解码播放正常；完整 Atmos 空间渲染需杜比授权 SDK，立体声下混输出
- 遇到 bug 或有功能建议 → [提交 Issue](https://github.com/nianmenyikuo/TuneKuo/issues/new/choose)（App 内设置页也有直达链接）
