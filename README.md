# TuneKuo 🎵

![界面语言](https://img.shields.io/badge/界面语言-简体中文-red) ![平台](https://img.shields.io/badge/平台-Android%207.0%2B-green) ![架构](https://img.shields.io/badge/架构-armeabi--v7a%20%7C%20arm64--v8a-blue)

完全自用的安卓本地音乐播放器。基于 libVLC 解码，全格式通吃——DSD (DSF/DFF)、APE、FLAC、杜比 TrueHD 等都能播。

**界面语言：简体中文**

## 功能

- **全格式播放**：libVLC 自带解码器，不依赖系统 MediaCodec，无损与杜比码流均可播放
- **四种播放模式**：顺序 / 列表循环 / 单曲循环 / 随机（洗牌队列，手动切歌与自然播完走不同逻辑）
- **锁屏与通知栏**：MediaSession 集成，锁屏显示歌名/封面/进度，支持上一首/播放暂停/下一首与蓝牙线控
- **专辑封面自动获取**：优先内嵌封面（ID3 APIC / FLAC PICTURE / M4A covr），其次同目录 cover.jpg 等常见命名
- **歌词显示**：内嵌歌词标签 + 同名 .lrc 文件双通道，全屏歌词页逐行高亮滚动
- **音乐搜索**：顶部搜索框实时过滤歌名/歌手/专辑，点击结果在完整曲库队列中播放
- **深色 UI**：卡片式列表、当前曲目高亮（♪）、矢量图标、64dp 渐变播放大按钮

## 构建

- Android Studio：打开项目直接 Run
- 命令行：`./gradlew assembleDebug`（首次先 `gradle wrapper` 生成 wrapper）
- APK 输出：`app/build/outputs/apk/debug/app-debug.apk`

## 环境

- Kotlin / minSdk 24 / targetSdk 34
- 依赖：libVLC (org.videolan.android:libvlc)、AndroidX、MediaSessionCompat

## 说明

- 32 位与 64 位 ABI 均支持（armeabi-v7a + arm64-v8a）
- 开机自启动接收器已内置（可选）
- 杜比 TrueHD/AC-3 码流解码播放正常；完整 Atmos 空间渲染需杜比授权 SDK，立体声下混输出
