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
    "scan.tip1": ("正在扫描音乐…",
                  "Scanning music...",
                  "音楽をスキャン中…"),
    "scan.tip2": ("正在查找音频文件",
                  "Finding audio files",
                  "音声ファイルを探しています"),
    "scan.tip3": ("正在读取音频信息",
                  "Reading audio info",
                  "音声情報を読み込み中"),
    "scan.tip4": ("找到一首新歌",
                  "Found a new track",
                  "新しい曲を見つけました"),
    "scan.tip5": ("正在整理曲库",
                  "Organizing the library",
                  "ライブラリを整理中"),
    "scan.tip6": ("正在遍历文件夹",
                  "Walking through folders",
                  "フォルダを巡回中"),
    "scan.tip7": ("马上就好",
                  "Almost there",
                  "もうすぐです"),
    "scan.tip8": ("正在建立索引",
                  "Building the index",
                  "インデックスを作成中"),
    "scan.tip9": ("还在扫描中…",
                  "Still scanning...",
                  "まだスキャン中です…"),
    "scan.tip10": ("扫描完成",
                  "Scan done",
                  "スキャン完了"),
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
    "now.title": ("正在播放", "Now Playing", "再生中"),
    "tip.wave": ("正在播放页", "Now playing page", "再生中ページ"),
}

CAT = {
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

_cat = None

def _load_cat() -> bool:
    global _cat
    if _cat is None:
        _cat = bool(_read_state().get("cat"))
    return _cat

def cat_mode() -> bool:
    return _load_cat()

def set_cat(value: bool, save: bool = True) -> None:
    global _cat
    _cat = bool(value)
    if save:
        data = _read_state()
        data["cat"] = _cat
        _write_state(data)

def toggle_cat(save: bool = True) -> bool:
    set_cat(not _load_cat(), save)
    return _load_cat()

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
    row = (CAT if _load_cat() else TEXT).get(key)
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
