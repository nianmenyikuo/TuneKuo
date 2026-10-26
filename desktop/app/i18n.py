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
    "tool.add_files": ("加几个文件喵", "Add some files, nya", "ファイルを足すにゃ"),
    "tool.add_folder": ("加一个文件夹喵", "Add a folder, nya", "フォルダを足すにゃ"),
    "tool.scan_library": ("去扒拉音乐库喵", "Sniff the library, nya", "ライブラリをかき集めるにゃ"),
    "tool.set_default": ("让人家当默认播放器喵", "Make the kitty the default player, nya",
                         "ねこを既定のプレーヤーにするにゃ"),
    "tool.default_ok": ("默认播放器 {n}/{total} 喵", "Default player {n}/{total}, nya",
                        "既定のプレーヤー {n}/{total} にゃ"),
    "tool.settings": ("设置喵", "Settings, nya", "設定にゃ"),
    "tool.search_hint": ("找歌喵…", "Look for a song, nya…", "曲を探すにゃ…"),
    "col.title": ("标题喵", "Title, nya", "タイトルにゃ"),
    "col.artist": ("歌手喵", "Artist, nya", "アーティストにゃ"),
    "col.album": ("专辑喵", "Album, nya", "アルバムにゃ"),
    "col.time": ("时长喵", "Length, nya", "長さにゃ"),
    "count.all": ("{n} 首喵", "{n} songs, nya", "{n} 曲にゃ"),
    "count.filtered": ("{n} / {total} 首喵", "{n} / {total} songs, nya", "{n} / {total} 曲にゃ"),
    "unknown_artist": ("不知道是谁喵", "No idea who, meow", "誰かわからないにゃ"),
    "not_playing": ("还没开始放喵", "Nothing playing yet, meow", "まだ鳴ってないにゃ"),
    "no_cover": ("没有封面喵", "No cover, meow", "ジャケットなしにゃ"),
    "lyrics_empty": ("这首歌还没有歌词喵\n\n把同名的 .lrc 文件放在歌旁边，人家就能唱出来啦喵",
                     "No lyrics for this one, meow\n\nPut an .lrc file with the same name next to the song and the kitty will sing it.",
                     "この曲の歌詞はまだないにゃ\n\n同じ名前の .lrc を曲のとなりに置いてくれたら歌えるにゃ"),
    "mode.0": ("顺序放喵", "In order, nya", "順番に鳴らすにゃ"),
    "mode.1": ("列表循环喵", "Repeat the list, nya", "リストをくりかえすにゃ"),
    "mode.2": ("单曲循环喵", "Repeat one, nya", "この曲をくりかえすにゃ"),
    "mode.3": ("随机放喵", "Shuffle, nya", "シャッフルにゃ"),
    "tip.mode": ("播放模式喵", "Play mode, nya", "再生モードにゃ"),
    "tip.prev": ("上一首喵", "Previous one, nya", "まえの曲にゃ"),
    "tip.play": ("播放 / 暂停喵", "Play / Pause, nya", "再生 / 一時停止にゃ"),
    "tip.next": ("下一首喵", "Next one, nya", "つぎの曲にゃ"),
    "tip.volume": ("音量喵", "Volume, nya", "音量にゃ"),
    "tip.settings": ("打开设置喵", "Open settings, nya", "設定を開くにゃ"),
    "tip.back": ("回主界面喵", "Back to the player, nya", "プレーヤーに戻るにゃ"),
    "status.ready": ("待命中喵", "Ready, nya", "待機中にゃ"),
    "status.playing": ("放着呢喵", "Playing, nya", "鳴ってるにゃ"),
    "status.paused": ("停下来啦喵", "Paused, nya", "一時停止にゃ"),
    "status.stopped": ("停住了喵", "Stopped, nya", "止まったにゃ"),
    "status.no_audio": ("一个音频都没找到喵", "No audio files found, meow", "音声ファイルが一個もないにゃ"),
    "status.duplicates": ("这些歌已经在下边躺着啦喵", "These songs are already in the list, nya",
                          "この曲たちはもうリストにあるにゃ"),
    "status.added": ("加进来 {n} 首，人家正在看资料…喵", "Added {n} tracks, kitty is reading them… nya",
                     "{n} 曲足したにゃ、いま中身を見てる…にゃ"),
    "status.no_music_dir": ("找不到默认的音乐文件夹喵，用「加一个文件夹喵」指给人家吧",
                            "No default music folder, meow - point the kitty at one with Add a folder",
                            "既定の音楽フォルダが見つからないにゃ。「フォルダを足すにゃ」で教えてにゃ"),
    "status.scanning": ("人家在扒拉音乐库…喵", "Kitty is rummaging the library… nya",
                        "ねこがライブラリをごそごそしてる…にゃ"),
    "status.scanned": ("扒完啦：{n} 首喵", "All dug up: {n} tracks, nya", "かき集めたにゃ：{n} 曲"),
    "scan.tip1": ("喵～正用小爪子在每个角落扒拉你的歌哦",
                  "Nyaa~ little paws are pawing through every corner for your songs",
                  "にゃ〜、小さな肉球であちこち歌をかき集めてるよ"),
    "scan.tip2": ("主人稍等喵，猫猫在闻歌的味道～",
                  "Hold on, meowster~ kitty is sniffing out the tunes",
                  "ご主人様ちょっと待ってにゃ、今においで探してる〜"),
    "scan.tip3": ("一首一首数着喵，不许催人家啦",
                  "Counting one by one, nya~ no rushing the kitty",
                  "いち、に、さん…にゃ、急かしちゃだめだよ"),
    "scan.tip4": ("找到啦！猫猫叼进窝里放好了喵～",
                  "Found one! Carrying it home in my mouth, nyaa~",
                  "見つけた！お口にくわえておうちに運ぶにゃ〜"),
    "scan.tip5": ("耳朵竖起来听着呢，哪有声音就扑过去喵",
                  "Ears up and listening, meow~ I pounce at every sound",
                  "お耳を立てて聞いてるにゃ、音がしたら飛びつくよ"),
    "scan.tip6": ("在曲库的草丛里翻来翻去…喵呜",
                  "Rummaging through the song bushes… mrrp",
                  "曲の草むらをごそごそ…むにゃむにゃ"),
    "scan.tip7": ("很快就好啦，先摸摸猫猫的头嘛喵",
                  "Almost done~ pat the kitty on the head meanwhile, nya",
                  "もうすぐだよ、その間は頭をなでてにゃ"),
    "scan.tip8": ("这个文件夹乱得像毛线球喵…猫猫慢慢理",
                  "This folder is tangled like a yarn ball… kitty will sort it, meow",
                  "このフォルダ、毛糸みたいに絡まってるにゃ…少しずつほどくね"),
    "scan.tip9": ("数到一半被自己尾巴吸引走了…喵，继续！",
                  "Got distracted by my own tail… nya, continuing!",
                  "自分のしっぽに夢中になっちゃった…にゃ、続けるよ！"),
    "scan.tip10": ("全部叼回来啦喵！可以摸摸猫猫了",
                   "All fetched home! You may pet the kitty now, meow~",
                   "ぜんぶ運んだよ！ご主人様、なでなでしていいにゃ〜"),
    "status.play_failed": ("这首放不出来喵（可能格式不支持）",
                           "This one will not play, meow (the format may be unsupported)",
                           "この曲は鳴らせないにゃ（対応してない形式かも）"),
    "menu.play": ("放这首喵", "Play this one, nya", "この曲を鳴らすにゃ"),
    "menu.reveal": ("在文件夹里找出来喵", "Show it in the folder, nya", "フォルダで見つけるにゃ"),
    "menu.remove": ("从列表拿掉喵", "Take it off the list, nya", "リストから外すにゃ"),
    "menu.delete_file": ("删掉文件喵", "Delete the file, nya", "ファイルを消すにゃ"),
    "delete_confirm": ("真要删掉「{name}」吗喵？会从硬盘上真的消失，删了就找不回来啦喵。",
                       "Really delete {name} from the disk, meow? It is gone for good and cannot be undone.",
                       "「{name}」ほんとに消すにゃ？ディスクから本当に消えて、元には戻せないにゃ。"),
    "delete_failed": ("删不掉喵：{err}", "Could not delete it, meow: {err}", "消せなかったにゃ：{err}"),
    "deleted": ("删掉啦喵：{name}", "Gone, meow: {name}", "消したにゃ：{name}"),
    "menu.fetch_info": ("上网找这首歌的资料（连歌词）喵", "Look this song up online (with lyrics), nya",
                        "ネットでこの曲の情報を探す（歌詞つき）にゃ"),
    "menu.detail": ("看看这首歌的底细喵", "Peek at this song, nya", "この曲の中身をのぞくにゃ"),
    "menu.copy_title": ("复制歌名喵", "Copy the title, nya", "曲名をコピーするにゃ"),
    "menu.copy_path": ("复制文件路径喵", "Copy the file path, nya", "ファイルパスをコピーするにゃ"),
    "copied": ("复制好啦喵", "Copied, nya", "コピーしたにゃ"),
    "fetching_online": ("人家上网找找…喵", "Sniffing the internet, meow…", "ネットで探してるにゃ…"),
    "fetch_failed": ("网上没找到这首歌的资料喵", "Nothing found online for this song, meow",
                     "ネットにこの曲の情報がなかったにゃ"),
    "fetch_ok": ("拿到啦：{src}，歌词 {n} 行喵", "Got it from {src} - {n} lyric lines, nya",
                 "{src} からもらったにゃ - 歌詞 {n} 行"),
    "fetch_lyrics_ok": ("歌词找到啦：{n} 行喵", "Lyrics found: {n} lines, nya", "歌詞みつけたにゃ：{n} 行"),
    "fetch_lyrics_none": ("歌词没找到喵", "No lyrics found, meow", "歌詞は見つからなかったにゃ"),
    "got": ("拿到啦喵", "Got it, nya", "もらったにゃ"),
    "not_found": ("没找到喵", "Not found, meow", "見つからないにゃ"),
    "detail.title": ("歌名喵", "Title, nya", "曲名にゃ"),
    "detail.artist": ("歌手喵", "Artist, nya", "アーティストにゃ"),
    "detail.album": ("专辑喵", "Album, nya", "アルバムにゃ"),
    "detail.year": ("年份喵", "Year, nya", "年にゃ"),
    "detail.genre": ("流派喵", "Genre, nya", "ジャンルにゃ"),
    "detail.source": ("从哪找的喵", "Where it came from, nya", "どこから来たにゃ"),
    "detail.cover": ("封面喵", "Cover, nya", "ジャケットにゃ"),
    "detail.duration": ("多长喵", "How long, nya", "長さにゃ"),
    "detail.format": ("格式喵", "Format, nya", "形式にゃ"),
    "detail.size": ("多大喵", "How big, nya", "大きさにゃ"),
    "detail.path": ("路径喵", "Path, nya", "パスにゃ"),
    "kv_fmt": ("{k}：{v}", "{k}: {v}", "{k}：{v}"),
    "dlg.choose_files": ("挑几个音乐文件喵", "Pick some music files, nya", "音楽ファイルを選ぶにゃ"),
    "dlg.choose_folder": ("挑一个音乐文件夹喵", "Pick a music folder, nya", "音楽フォルダを選ぶにゃ"),
    "dlg.ft_audio": ("音频文件喵", "Audio files, nya", "音声ファイルにゃ"),
    "dlg.ft_all": ("所有文件喵", "All files, nya", "すべてのファイルにゃ"),
    "dlg.register_failed_title": ("注册不成喵", "Could not register, meow", "登録できなかったにゃ"),
    "dlg.register_failed_body": ("写注册表的时候出错了喵：\n{e}",
                                 "Writing to the registry failed, meow:\n{e}",
                                 "レジストリに書くときに失敗したにゃ：\n{e}"),
    "dlg.register_done_title": ("注册好啦喵", "Registered, nya", "登録したにゃ"),
    "dlg.register_done": ("人家已经登记成音频播放器啦喵：\n\n- {done}\n\n"
                          "现在 {n} / {total} 种格式的默认程序是 TuneKuo 喵。\n\n"
                          "Windows 10/11 的默认程序要主人自己点头，接下来人家打开系统「默认应用」页面，"
                          "在音乐播放器那项选 TuneKuo 就全生效啦喵。",
                          "The kitty is registered as an audio player, nya:\n\n- {done}\n\n"
                          "{n} / {total} formats now use TuneKuo by default, meow.\n\n"
                          "Windows 10/11 asks the owner to confirm default apps. The kitty will open the "
                          "system Default apps page - pick TuneKuo for the music player entry and all of them apply, nya.",
                          "ねこを音声プレーヤーとして登録したにゃ：\n\n- {done}\n\n"
                          "いま {n} / {total} 形式の既定が TuneKuo にゃ。\n\n"
                          "Windows 10/11 では既定のアプリをご主人様が決めるにゃ。"
                          "これからシステムの「既定のアプリ」を開くから、"
                          "音楽プレーヤーのところで TuneKuo を選べば全部効くにゃ。"),
    "dlg.play_failed_title": ("放不出来喵", "Could not play it, meow", "鳴らせなかったにゃ"),
    "dlg.play_failed_body": ("这首放不了喵：\n{name}", "The kitty cannot play this, meow:\n{name}",
                             "この曲は鳴らせないにゃ：\n{name}"),
    "settings.title": ("设置喵", "Settings, nya", "設定にゃ"),
    "settings.back": ("← 回去喵", "← Back, nya", "← もどるにゃ"),
    "settings.language": ("语言喵", "Language, nya", "言語にゃ"),
    "settings.feedback": ("有 bug 或想法？告诉人家喵", "Found a bug or got an idea? Tell the kitty, nya",
                          "バグや要望があったら教えてにゃ"),
    "settings.log": ("打开日志看看喵", "Open the log, nya", "ログを開くにゃ"),
    "settings.mark": ("●", "●", "●"),
    "now.title": ("正在放喵", "Now playing, nya", "いま鳴ってるにゃ"),
    "tip.wave": ("正在播放页喵", "Now playing page, nya", "再生中ページにゃ"),
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
