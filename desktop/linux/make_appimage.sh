#!/usr/bin/env bash
# 打 AppImage（只能在 Linux 上跑）：
#     desktop/linux/make_appimage.sh [输出目录，默认 desktop/dist-linux]
#
# 和 deb 的区别：AppImage 把 libvlc 与插件一起装进包里，对方不装 VLC 也能放。
# 步骤：linux/build.sh 出 onedir → 塞进系统 libvlc + 插件 → 摆 AppDir → appimagetool
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"     # desktop/
OUT="${1:-$ROOT/dist-linux}"
WORK="$ROOT/build-appimage"
TOOLS="$OUT/tools"
APP="TuneKuo"

die() { echo "失败：$*" >&2; exit 1; }

VER="$("${PYTHON:-python3}" -c "import sys; sys.path.insert(0, '$ROOT/app'); from version import VERSION; print(VERSION)")"
[ -n "$VER" ] || die "读不到版本号"

echo "== 1/4 PyInstaller onedir =="
bash "$ROOT/linux/build.sh"

echo "== 2/4 找系统 libvlc =="
LIBVLC=""
for d in /usr/lib/x86_64-linux-gnu /usr/lib /usr/lib64 /usr/local/lib; do
  if [ -e "$d/libvlc.so.5" ]; then LIBVLC="$d"; break; fi
done
[ -n "$LIBVLC" ] || die "找不到 libvlc.so.5，先装 vlc-plugin-base 或 vlc"

PLUGINS=""
for d in "$LIBVLC/vlc/plugins" /usr/lib/vlc/plugins /usr/lib64/vlc/plugins; do
  if [ -d "$d" ]; then PLUGINS="$d"; break; fi
done
[ -n "$PLUGINS" ] || die "找不到 VLC 插件目录"
echo "   libvlc: $LIBVLC    插件: $PLUGINS"

echo "== 3/4 摆 AppDir =="
rm -rf "$WORK"
mkdir -p "$WORK/$APP/usr/bin" "$WORK/$APP/usr/share/applications" \
         "$WORK/$APP/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT/dist/$APP/." "$WORK/$APP/usr/bin/"

VLCDIR="$WORK/$APP/usr/bin/_internal/vlc"          # vlcenv.posix_setup() 认这个位置
mkdir -p "$VLCDIR"
cp -a "$LIBVLC"/libvlc.so* "$LIBVLC"/libvlccore.so* "$VLCDIR"/ 2>/dev/null || true
cp -a "$PLUGINS" "$VLCDIR/plugins"

"${PYTHON:-python3}" "$ROOT/scripts/make_deb.py" --desktop > "$WORK/$APP/$APP.desktop"
sed -i "s|^Exec=.*|Exec=$APP|" "$WORK/$APP/$APP.desktop"
cp "$ROOT/app/assets/icon.png" "$WORK/$APP/tunekuo.png"
cp "$ROOT/app/assets/icon.png" "$WORK/$APP/usr/share/icons/hicolor/256x256/apps/tunekuo.png"

cat > "$WORK/$APP/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
VLC="$HERE/usr/bin/_internal/vlc"
if [ -d "$VLC" ]; then
  VLC_PLUGIN_PATH="$VLC/plugins"
  LD_LIBRARY_PATH="$VLC${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export VLC_PLUGIN_PATH LD_LIBRARY_PATH
fi
exec "$HERE/usr/bin/TuneKuo" "$@"
EOF
chmod +x "$WORK/$APP/AppRun"

echo "== 4/4 appimagetool =="
mkdir -p "$TOOLS"
TOOL="$TOOLS/appimagetool-x86_64.AppImage"
if [ ! -x "$TOOL" ]; then
  curl -fsSL -o "$TOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage \
    || die "下载 appimagetool 失败（需要联网）"
  chmod +x "$TOOL"
fi

mkdir -p "$OUT"
TARGET="$OUT/$APP-$VER-x86_64.AppImage"
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$WORK/$APP" "$TARGET"
echo
echo "打包完成：$TARGET"
