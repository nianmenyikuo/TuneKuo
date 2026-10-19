#!/usr/bin/env bash
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

"$PY" -m PyInstaller --noconfirm --clean --windowed --onedir \
  --name TuneKuo \
  --icon "$ROOT/app/assets/icon.png" \
  --add-data "$ROOT/app/assets:assets" \
  --hidden-import vlc --hidden-import vlcenv --hidden-import mediakeys \
  --hidden-import instance --hidden-import paths --hidden-import applog \
  --hidden-import PIL.Image --hidden-import PIL.ImageTk \
  --distpath dist --workpath build --specpath build \
  app/main.py

cp "$ROOT/../VERSION" dist/TuneKuo/VERSION

echo
echo "打包完成：$ROOT/dist/TuneKuo/TuneKuo"
echo "装到用户目录（含默认播放器注册）：desktop/linux/install.sh"
