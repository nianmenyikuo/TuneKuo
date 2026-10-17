#!/usr/bin/env bash
# 打包 TuneKuo for Linux -> dist/TuneKuo/（PyInstaller onedir，和 Windows 端同一个 app/）
#     desktop/linux/build.sh           # 打包（要求已装依赖）
#     desktop/linux/build.sh --install # 顺便 pip install -r requirements.txt
#
# 播放引擎用系统装的 VLC，不随包携带（Linux 上 libvlc 的插件体系不适合塞进 onedir）。
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"

if [ "${1:-}" = "--install" ]; then
  "$PY" -m pip install --disable-pip-version-check -r requirements.txt pyinstaller
fi

if [ ! -f app/assets/icon.png ]; then
  "$PY" scripts/make_icon.py
fi

# 注意：--add-data / --icon 的源路径要写绝对路径 —— spec 文件落在 build/ 里，
# 相对路径会以 spec 所在目录为基准，PyInstaller 会报 "Unable to find .../build/app/assets"。
"$PY" -m PyInstaller --noconfirm --clean --windowed --onedir \
  --name TuneKuo \
  --icon "$ROOT/app/assets/icon.png" \
  --add-data "$ROOT/app/assets:assets" \
  --hidden-import vlc --hidden-import vlcenv --hidden-import mediakeys \
  --hidden-import instance --hidden-import paths \
  --hidden-import PIL.Image --hidden-import PIL.ImageTk \
  --distpath dist --workpath build --specpath build \
  app/main.py

echo
echo "打包完成：$ROOT/dist/TuneKuo/TuneKuo"
echo "装到用户目录（含默认播放器注册）：desktop/linux/install.sh"
