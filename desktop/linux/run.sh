#!/usr/bin/env bash
# 开发态直接运行（不打包）：先装好 VLC / python-vlc / Pillow，然后
#     desktop/linux/run.sh [音乐文件或目录...]
set -e
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$here/../app/main.py" "$@"
