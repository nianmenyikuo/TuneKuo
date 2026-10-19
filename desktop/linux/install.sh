#!/usr/bin/env bash
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

"$BINDIR/tunekuo" --register --quiet || true

echo "装好了：$BINDIR/tunekuo"
echo "如果 $BINDIR 不在 PATH 里，把它加进去，或直接用 $BINDIR/tunekuo 启动。"
echo "默认程序没生效时手动指定一个：xdg-mime default tunekuo.desktop audio/flac"
