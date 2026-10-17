#!/usr/bin/env bash
# 把打包好的 TuneKuo 装到用户目录，并注册成音频默认播放器（全程不需要 root）
#     desktop/linux/install.sh              # 装到 ~/.local
#     PREFIX=~/.local desktop/linux/install.sh
#     desktop/linux/install.sh --uninstall
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
LIBDIR="$PREFIX/lib/tunekuo"
BINDIR="$PREFIX/bin"
APPDIR="$PREFIX/share/applications"

if [ "${1:-}" = "--uninstall" ]; then
  rm -rf "$LIBDIR"
  rm -f "$BINDIR/tunekuo" "$APPDIR/tunekuo.desktop"
  echo "已卸载（默认程序请到系统设置里改回别的播放器）"
  exit 0
fi

SRC="$ROOT/dist/TuneKuo"
if [ ! -x "$SRC/TuneKuo" ]; then
  echo "没找到 $SRC/TuneKuo，先跑 desktop/linux/build.sh"
  exit 1
fi

mkdir -p "$LIBDIR" "$BINDIR" "$APPDIR"
rm -rf "$LIBDIR/TuneKuo"
cp -r "$SRC" "$LIBDIR/TuneKuo"
ln -sf "$LIBDIR/TuneKuo/TuneKuo" "$BINDIR/tunekuo"

# .desktop 与 xdg-mime 关联交给程序自己（和 Windows 端同一份实现）
"$BINDIR/tunekuo" --register --quiet || true

echo "装好了：$BINDIR/tunekuo"
echo "如果 $BINDIR 不在 PATH 里，把它加进去，或直接用 $BINDIR/tunekuo 启动。"
echo "默认程序没生效时手动指定一个：xdg-mime default tunekuo.desktop audio/flac"
