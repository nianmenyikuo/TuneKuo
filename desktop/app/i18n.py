from __future__ import annotations
from applog import swallow

import json
import os

import paths

LANGS = [("zh", "汉语"), ("en", "English"), ("ja", "日本語")]

_CODES = [c for c, _ in LANGS]
DEFAULT_LANG = "zh"
_INDEX = {c: i for i, c in enumerate(_CODES)}

_lang = None

TEXT = {
    "tool.add_files": ("添加文件", "Add Files", "ファイルを追加"),
    "tool.add_folder": ("添加文件夹", "Add Folder", "フォルダを追加"),
    "tool.scan_library": ("扫描音乐库", "Scan Library", "ライブラリをスキャン"),
    "tool.set_default": ("设为默认播放器", "Set as Default Player", "既定のプレーヤーに設定"),
    "tool.default_ok": ("默认播放器 {n}/{total}", "Default Player {n}/{total}",
                        "既定のプレーヤー {n}/{total}"),
    "tool.settings": ("设置", "Settings", "設定"),
    "tool.search_hint": ("搜索…", "Search…", "検索…"),
    "col.title": ("标题", "Title", "タイトル"),
    "col.artist": ("歌手", "Artist", "アーティスト"),
    "col.album": ("专辑", "Album", "アルバム"),
    "col.time": ("时长", "Time", "長さ"),
    "count.all": ("{n} 首", "{n} tracks", "{n} 曲"),
    "count.filtered": ("{n} / {total} 首", "{n} / {total} tracks", "{n} / {total} 曲"),
    "unknown_artist": ("未知艺术家", "Unknown Artist", "不明なアーティスト"),
    "not_playing": ("未在播放", "Not Playing", "再生していません"),
    "no_cover": ("无封面", "No Cover", "カバーなし"),
    "lyrics_empty": ("暂无歌词\n\n把同名 .lrc 文件放在歌曲旁边即可显示",
                     "No lyrics\n\nPut a .lrc file with the same name next to the song to show them.",
                     "歌詞がありません\n\n同じ名前の .lrc ファイルを曲の隣に置くと表示されます"),
    "mode.0": ("顺序播放", "Play in Order", "順番に再生"),
    "mode.1": ("列表循环", "Repeat All", "リストをリピート"),
    "mode.2": ("单曲循环", "Repeat One", "1曲リピート"),
    "mode.3": ("随机播放", "Shuffle", "シャッフル"),
    "tip.mode": ("播放模式", "Play Mode", "再生モード"),
    "tip.prev": ("上一首", "Previous", "前へ"),
    "tip.play": ("播放 / 暂停", "Play / Pause", "再生 / 一時停止"),
    "tip.next": ("下一首", "Next", "次へ"),
    "tip.volume": ("音量", "Volume", "音量"),
    "tip.settings": ("打开设置", "Open settings", "設定を開く"),
    "tip.back": ("返回主界面", "Back to the player", "プレーヤーに戻る"),
    "status.ready": ("就绪", "Ready", "準備完了"),
    "status.playing": ("播放中", "Playing", "再生中"),
    "status.paused": ("已暂停", "Paused", "一時停止中"),
    "status.stopped": ("已停止", "Stopped", "停止"),
    "status.no_audio": ("没有找到音频文件", "No audio files found", "音声ファイルが見つかりません"),
    "status.duplicates": ("这些文件已经在列表里了", "These files are already in the list",
                          "これらのファイルはすでにリストにあります"),
    "status.added": ("已添加 {n} 首，正在读取信息…", "Added {n} tracks, reading info…",
                     "{n} 曲を追加しました。情報を読み込み中…"),
    "status.no_music_dir": ("没找到默认音乐目录，请用“添加文件夹”",
                            "No default music folder found - use \"Add Folder\"",
                            "既定の音楽フォルダが見つかりません。「フォルダを追加」を使ってください"),
    "status.scanning": ("正在扫描音乐库…", "Scanning the library…", "ライブラリをスキャン中…"),
    "status.scanned": ("扫描完成：{n} 首", "Scan complete: {n} tracks", "スキャン完了：{n} 曲"),
    "status.play_failed": ("这个文件播放失败（可能格式不受支持）",
                           "This file failed to play (the format may be unsupported)",
                           "このファイルを再生できませんでした（対応していない形式の可能性があります）"),
    "menu.play": ("播放", "Play", "再生"),
    "menu.reveal": ("在文件夹中显示", "Show in Folder", "フォルダーで表示"),
    "menu.remove": ("从列表移除", "Remove from List", "リストから削除"),
    "menu.delete_file": ("删除文件", "Delete File", "ファイルを削除"),
    "delete_confirm": ("确定删除「{name}」？会从硬盘上真正删掉，无法撤销。",
                       'Delete "{name}" from disk? This cannot be undone.',
                       "「{name}」をディスクから削除しますか？元に戻せません。"),
    "delete_failed": ("删除失败：{err}", "Delete failed: {err}", "削除に失敗しました：{err}"),
    "deleted": ("已删除：{name}", "Deleted: {name}", "削除しました：{name}"),
    "menu.fetch_info": ("联网获取歌曲信息（含歌词）", "Fetch Info Online (incl. lyrics)",
                        "オンラインで曲情報を取得（歌詞付き）"),
    "menu.detail": ("歌曲详情", "Track Details", "曲の詳細"),
    "menu.copy_title": ("复制歌名", "Copy Title", "曲名をコピー"),
    "menu.copy_path": ("复制文件路径", "Copy File Path", "ファイルパスをコピー"),
    "copied": ("已复制到剪贴板", "Copied to clipboard", "クリップボードにコピーしました"),
    "fetching_online": ("正在联网获取…", "Fetching online…", "オンラインで取得中…"),
    "fetch_failed": ("联网获取失败：没找到这首歌的信息", "Nothing found online for this track",
                     "オンラインで情報が見つかりませんでした"),
    "fetch_ok": ("已获取：{src}，歌词 {n} 行", "Fetched from {src} - {n} lyric lines",
                 "{src} から取得 - 歌詞 {n} 行"),
    "fetch_lyrics_ok": ("歌词：已获取 {n} 行", "Lyrics: {n} lines", "歌詞：{n} 行"),
    "fetch_lyrics_none": ("歌词：未找到", "Lyrics: not found", "歌詞：見つかりません"),
    "got": ("已获取", "Got it", "取得済み"),
    "not_found": ("未找到", "Not found", "見つかりません"),
    "detail.title": ("歌名", "Title", "曲名"),
    "detail.artist": ("歌手", "Artist", "アーティスト"),
    "detail.album": ("专辑", "Album", "アルバム"),
    "detail.year": ("年份", "Year", "年"),
    "detail.genre": ("流派", "Genre", "ジャンル"),
    "detail.source": ("来源", "Source", "取得元"),
    "detail.cover": ("封面", "Cover", "カバー"),
    "detail.duration": ("时长", "Duration", "長さ"),
    "detail.format": ("格式", "Format", "形式"),
    "detail.size": ("大小", "Size", "サイズ"),
    "detail.path": ("路径", "Path", "パス"),
    "kv_fmt": ("{k}：{v}", "{k}: {v}", "{k}：{v}"),
    "dlg.choose_files": ("选择音乐文件", "Select Music Files", "音楽ファイルを選択"),
    "dlg.choose_folder": ("选择音乐文件夹", "Select Music Folder", "音楽フォルダを選択"),
    "dlg.ft_audio": ("音频文件", "Audio Files", "音声ファイル"),
    "dlg.ft_all": ("所有文件", "All Files", "すべてのファイル"),
    "dlg.register_failed_title": ("注册失败", "Registration Failed", "登録に失敗"),
    "dlg.register_failed_body": ("写入注册表时出错：\n{e}", "Error writing to the registry:\n{e}",
                                 "レジストリへの書き込み中にエラーが発生しました：\n{e}"),
    "dlg.register_done_title": ("注册完成", "Registration Complete", "登録完了"),
    "dlg.register_done": ("已注册为音频播放器：\n\n- {done}\n\n"
                          "当前已有 {n} / {total} 种格式的默认程序是 TuneKuo。\n\n"
                          "Windows 10/11 的默认程序由用户确认，接下来我会打开系统“默认应用”页面，"
                          "在音乐播放器那一项选择 TuneKuo 即可全部生效。",
                          "Registered as an audio player:\n\n- {done}\n\n"
                          "{n} / {total} formats now use TuneKuo by default.\n\n"
                          "Windows 10/11 asks the user to confirm default apps. I will open the system "
                          "\"Default apps\" page - pick TuneKuo for the music player entry to apply them all.",
                          "音声プレーヤーとして登録しました：\n\n- {done}\n\n"
                          "現在 {n} / {total} 形式の既定のアプリが TuneKuo です。\n\n"
                          "Windows 10/11 では既定のアプリをユーザーが確認する必要があります。"
                          "システムの「既定のアプリ」ページを開きますので、"
                          "音楽プレーヤーの項目で TuneKuo を選んでください。"),
    "dlg.play_failed_title": ("播放失败", "Playback Failed", "再生に失敗"),
    "dlg.play_failed_body": ("无法播放：\n{name}", "Cannot play:\n{name}", "再生できません：\n{name}"),
    "settings.title": ("设置", "Settings", "設定"),
    "settings.back": ("← 返回", "← Back", "← 戻る"),
    "settings.language": ("语言", "Language", "言語"),
    "settings.feedback": ("Bug 与更新意见反馈", "Bug reports & feedback", "バグ報告・ご意見"),
    "settings.log": ("打开日志文件", "Open log file", "ログを開く"),
    "settings.mark": ("●", "●", "●"),
}

def state_file() -> str:
    return os.path.join(paths.config_dir(), "state.json")

def _read_state() -> dict:
    try:
        with open(state_file(), "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except Exception:
        swallow("i18n._read_state")
        return {}

def _write_state(data: dict) -> None:
    path = state_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False)
    except Exception:
        swallow("i18n._write_state")
        pass

def _load() -> str:
    global _lang
    if _lang is None:
        saved = _read_state().get("lang")
        _lang = saved if saved in _INDEX else DEFAULT_LANG
    return _lang

def current_language() -> str:
    return _load()

def language_name(code: str = "") -> str:
    code = code or _load()
    for c, name in LANGS:
        if c == code:
            return name
    return code

def set_language(code: str, save: bool = True) -> bool:
    global _lang
    if code not in _INDEX:
        code = DEFAULT_LANG
    changed = code != _load()
    _lang = code
    if save:
        data = _read_state()
        data["lang"] = code
        _write_state(data)
    return changed

def t(key: str, **kw) -> str:
    row = TEXT.get(key)
    if not row:
        return key
    i = _INDEX.get(_load(), _INDEX[DEFAULT_LANG])
    text = row[i] if 0 <= i < len(row) and row[i] else row[_INDEX[DEFAULT_LANG]]
    if not text:
        return key
    if kw:
        try:
            text = text.format(**kw)
        except Exception:
            swallow("i18n.t")
            pass
    return text
