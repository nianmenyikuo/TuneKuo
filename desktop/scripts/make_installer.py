"""生成 TuneKuo 的 Inno Setup 安装脚本并编译成单文件安装包。

    python scripts\\make_installer.py            # 生成 .iss 并编译
    python scripts\\make_installer.py --iss-only # 只生成 installer\\TuneKuo.iss

产物：dist-installer\\TuneKuo-Setup-<版本>.exe
注册表部分由 app\\assoc.py 的 EXTS / PROGID 生成，避免两处清单不一致。
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

import assoc  # noqa: E402
import version as app_version  # noqa: E402

APP_NAME = app_version.APP_NAME
APP_VERSION = app_version.VERSION
APP_EXE = "TuneKuo.exe"
PROGID = assoc.PROGID
BUILD_DIR = os.path.join(ROOT, "dist", "TuneKuo")
INSTALLER_DIR = os.path.join(ROOT, "installer")
ISS_PATH = os.path.join(INSTALLER_DIR, "TuneKuo.iss")
OUT_DIR = os.path.join(ROOT, "dist-installer")
ICON = os.path.join(ROOT, "app", "assets", "icon.ico")
LANG_FILE = os.path.join(INSTALLER_DIR, "ChineseSimplified.isl")

ISCC_CANDIDATES = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def find_iscc() -> str:
    for p in ISCC_CANDIDATES:
        if p and os.path.isfile(p):
            return p
    for p in os.environ.get("PATH", "").split(os.pathsep):
        cand = os.path.join(p, "ISCC.exe")
        if os.path.isfile(cand):
            return cand
    return ""


def build_iss() -> str:
    """拼出 .iss 文本（用绝对路径，避免编译时相对路径解析到别处）。"""
    # Inno 里字符串要用引号包起来、内部的引号再翻倍，
    # 所以最终的 ValueData 长这样： """{app}\TuneKuo.exe"" ""%1"""
    cmd = '"""' + os.path.join("{app}", APP_EXE) + '"" ""%1"""'
    L: list = []
    add = L.append

    add("; 本文件由 scripts\\make_installer.py 自动生成，不要手改；")
    add("; 要增删音频格式请改 app\\assoc.py 里的 EXTS，然后重新生成。")
    add("")
    add("[Setup]")
    add("AppId={{8E3F1C42-5B7A-4A9E-9E2C-1F0A6B7D4C31}")
    add("AppName=" + APP_NAME)
    add("AppVersion=" + APP_VERSION)
    add("AppVerName=" + APP_NAME + " " + APP_VERSION)
    add("AppPublisher=" + APP_NAME)
    add("DefaultDirName={autopf}\\" + APP_NAME)
    add("DisableProgramGroupPage=yes")
    add("AllowNoIcons=yes")
    add("OutputDir=" + OUT_DIR)
    add("OutputBaseFilename=TuneKuo-Setup-" + APP_VERSION)
    add("SetupIconFile=" + ICON)
    add("UninstallDisplayIcon={app}\\" + APP_EXE)
    add("UninstallDisplayName=" + APP_NAME + " 音乐播放器")
    add("Compression=lzma2/max")
    add("SolidCompression=yes")
    add("WizardStyle=modern")
    add("PrivilegesRequired=admin")
    add("PrivilegesRequiredOverridesAllowed=dialog")  # 向导里可选"所有用户 / 仅我"
    add("ArchitecturesAllowed=x64compatible")
    add("ArchitecturesInstallIn64BitMode=x64compatible")
    add("MinVersion=10.0")
    add("VersionInfoVersion=" + APP_VERSION + ".0")
    add("VersionInfoCompany=" + APP_NAME)
    add("VersionInfoDescription=" + APP_NAME + " 安装程序")
    add("VersionInfoProductName=" + APP_NAME)
    add("VersionInfoProductVersion=" + APP_VERSION)
    add("")
    add("[Languages]")
    if os.path.isfile(LANG_FILE):
        add('Name: "chinese"; MessagesFile: "' + LANG_FILE + '"')
    add('Name: "english"; MessagesFile: "compiler:Default.isl"')
    add("")
    add("[Tasks]")
    add('Name: "desktopicon"; Description: "创建桌面快捷方式"; '
        'GroupDescription: "附加任务："; Flags: checkedonce')
    add('Name: "assoc"; Description: "把 TuneKuo 注册为音频播放器'
        '（出现在右键“打开方式”和系统默认应用列表里）"; '
        'GroupDescription: "附加任务："; Flags: checkedonce')
    add("")
    add("[Files]")
    add('Source: "' + os.path.join(BUILD_DIR, "*") + '"; DestDir: "{app}"; '
        "Flags: ignoreversion recursesubdirs createallsubdirs")
    add("")
    add("[Icons]")
    add('Name: "{autodesktop}\\' + APP_NAME + '"; Filename: "{app}\\' + APP_EXE + '"; '
        'WorkingDir: "{app}"; IconFilename: "{app}\\' + APP_EXE + '"; '
        'Comment: "TuneKuo 全格式音乐播放器"; Tasks: desktopicon')
    add("")
    add("[Registry]")
    add("; ---- 1) ProgID：双击文件时靠它找到打开命令 ----")
    add('Root: HKA; Subkey: "Software\\Classes\\' + PROGID + '"; ValueType: string; '
        'ValueName: ""; ValueData: "音频文件"; Tasks: assoc; Flags: uninsdeletekey')
    add('Root: HKA; Subkey: "Software\\Classes\\' + PROGID + '"; ValueType: string; '
        'ValueName: "FriendlyTypeName"; ValueData: "TuneKuo 音频文件"; Tasks: assoc')
    add('Root: HKA; Subkey: "Software\\Classes\\' + PROGID + '\\DefaultIcon"; ValueType: string; '
        'ValueName: ""; ValueData: "{app}\\' + APP_EXE + ',0"; Tasks: assoc')
    add('Root: HKA; Subkey: "Software\\Classes\\' + PROGID + '\\shell\\open\\command"; '
        'ValueType: string; ValueName: ""; ValueData: ' + cmd + "; Tasks: assoc")
    add('Root: HKA; Subkey: "Software\\Classes\\' + PROGID + '\\shell\\play\\command"; '
        'ValueType: string; ValueName: ""; ValueData: ' + cmd + "; Tasks: assoc")
    add("")
    add("; ---- 2) 应用程序条目：右键“打开方式”里出现 TuneKuo ----")
    add('Root: HKA; Subkey: "Software\\Classes\\Applications\\' + APP_EXE + '"; ValueType: string; '
        'ValueName: "FriendlyAppName"; ValueData: "TuneKuo 音乐播放器"; Tasks: assoc; '
        "Flags: uninsdeletekey")
    add('Root: HKA; Subkey: "Software\\Classes\\Applications\\' + APP_EXE + '\\DefaultIcon"; '
        'ValueType: string; ValueName: ""; ValueData: "{app}\\' + APP_EXE + ',0"; Tasks: assoc')
    add('Root: HKA; Subkey: "Software\\Classes\\Applications\\' + APP_EXE + '\\shell\\open\\command"; '
        'ValueType: string; ValueName: ""; ValueData: ' + cmd + "; Tasks: assoc")
    add("")
    add("; ---- 3) 各扩展名登记为可打开（OpenWithProgids），并列入 SupportedTypes ----")
    for ext in assoc.EXTS:
        add('Root: HKA; Subkey: "Software\\Classes\\Applications\\' + APP_EXE
            + '\\SupportedTypes"; ValueType: string; ValueName: "' + ext
            + '"; ValueData: ""; Tasks: assoc; Flags: uninsdeletevalue')
    for ext in assoc.EXTS:
        # 注意：不能用 ValueType: none —— Inno 6.7 会静默跳过，值根本不会写进去
        # （已用 probe 验证：none 两种写法都不生成，binary 正常生成）。
        # OpenWithProgids 只看值名，数据无所谓，这里写一个字节的 0。
        add('Root: HKA; Subkey: "Software\\Classes\\' + ext + '\\OpenWithProgids"; '
            'ValueType: binary; ValueName: "' + PROGID + '"; ValueData: "00"; Tasks: assoc; '
            "Flags: uninsdeletevalue")
    add("")
    add("; ---- 4) 系统“默认应用”里可选中（Windows 不允许程序静默抢默认，只能让用户点一下）----")
    # 这一行只为了让卸载时能把空的 Software\TuneKuo 一起删掉（uninsdeletekeyifempty）
    add('Root: HKA; Subkey: "Software\\' + APP_NAME + '"; Flags: uninsdeletekeyifempty; '
        "Tasks: assoc")
    add('Root: HKA; Subkey: "Software\\' + APP_NAME + '\\Capabilities"; ValueType: string; '
        'ValueName: "ApplicationName"; ValueData: "' + APP_NAME + '"; Tasks: assoc; '
        "Flags: uninsdeletekey")
    add('Root: HKA; Subkey: "Software\\' + APP_NAME + '\\Capabilities"; ValueType: string; '
        'ValueName: "ApplicationDescription"; '
        'ValueData: "TuneKuo 全格式本地音乐播放器"; Tasks: assoc')
    add('Root: HKA; Subkey: "Software\\' + APP_NAME + '\\Capabilities"; ValueType: string; '
        'ValueName: "ApplicationIcon"; ValueData: "{app}\\' + APP_EXE + ',0"; Tasks: assoc')
    for ext in assoc.EXTS:
        add('Root: HKA; Subkey: "Software\\' + APP_NAME + '\\Capabilities\\FileAssociations"; '
            'ValueType: string; ValueName: "' + ext + '"; ValueData: "' + PROGID
            + '"; Tasks: assoc')
    add('Root: HKA; Subkey: "Software\\RegisteredApplications"; ValueType: string; '
        'ValueName: "' + APP_NAME + '"; ValueData: "Software\\' + APP_NAME
        + '\\Capabilities"; Tasks: assoc; Flags: uninsdeletevalue')
    add("")
    add("[Run]")
    add('Filename: "{app}\\' + APP_EXE + '"; Description: "立即启动 TuneKuo"; '
        "Flags: nowait postinstall skipifsilent")
    add("")
    return "\n".join(L) + "\n"


def main() -> int:
    if not os.path.isfile(os.path.join(BUILD_DIR, APP_EXE)):
        print("没有找到 " + os.path.join(BUILD_DIR, APP_EXE) + "，先运行 build.ps1 打包")
        return 1
    if not os.path.isfile(ICON):
        print("缺少图标 " + ICON + "（先运行 scripts\\make_icon.py）")
        return 1
    os.makedirs(INSTALLER_DIR, exist_ok=True)
    text = build_iss()
    with open(ISS_PATH, "w", encoding="utf-8-sig", newline="\r\n") as fp:
        fp.write(text)
    print("已生成 " + ISS_PATH + f"（{len(text.splitlines())} 行，"
          f"{len(assoc.EXTS)} 种音频格式）")
    if "--iss-only" in sys.argv:
        return 0

    iscc = find_iscc()
    if not iscc:
        print("找不到 ISCC.exe（Inno Setup 6）。装一个：winget install JRSoftware.InnoSetup")
        return 1
    print("编译安装包:", iscc)
    proc = subprocess.run([iscc, "/Qp", ISS_PATH], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr.strip())
        print("编译失败，返回码", proc.returncode)
        return proc.returncode
    out = os.path.join(OUT_DIR, f"TuneKuo-Setup-{APP_VERSION}.exe")
    if os.path.isfile(out):
        print(f"安装包完成：{out}（{os.path.getsize(out) / 1024 / 1024:.1f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
