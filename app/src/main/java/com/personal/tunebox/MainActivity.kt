package com.personal.tunebox

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Paint
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.EditText
import android.widget.ImageView
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private lateinit var adapter: SongAdapter
    private val songs = ArrayList<Song>()          // 完整曲库
    private val display = ArrayList<Song>()        // 搜索过滤后的展示列表
    private val handler = Handler(Looper.getMainLooper())
    private val ui = CoroutineScope(Dispatchers.Main)

    private lateinit var tvNowTitle: TextView
    private lateinit var tvNowInfo: TextView
    private lateinit var tvTime: TextView
    private lateinit var tvMode: TextView
    private lateinit var tvCount: TextView
    private lateinit var seekBar: SeekBar
    private lateinit var btnPlay: ImageView
    private lateinit var btnMode: TextView
    private lateinit var ivNowCover: ImageView
    private var loadedFor: String? = null   // 当前已加载封面/歌词的歌曲路径

    // 两页式界面：主界面 / 设置页
    private lateinit var rootSwipe: SwipeLayout
    private lateinit var pageMain: View
    private lateinit var pageSettings: View
    private lateinit var optZh: TextView
    private lateinit var optEn: TextView
    private lateinit var optJa: TextView
    private var showingSettings = false
    private var scanning = false

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(LocaleHelper.wrap(newBase))
    }

    private val tick = object : Runnable {
        override fun run() {
            val e = PlaybackService.engine
            if (e != null && e.current != null) {
                val dur = e.duration
                if (dur > 0) {
                    seekBar.max = dur.toInt()
                    seekBar.progress = e.position.toInt()
                    tvTime.text = format(e.position) + " / " + format(dur)
                }
                tvNowTitle.text = e.current!!.title
                tvNowInfo.text = e.current!!.artist + " · " + e.current!!.album
                btnPlay.setImageResource(if (e.isPlaying) R.drawable.ic_pause else R.drawable.ic_play)
                val modeText = when (e.mode) {
                    PlayMode.SEQUENTIAL -> getString(R.string.mode_sequential)
                    PlayMode.REPEAT_LIST -> getString(R.string.mode_repeat_list)
                    PlayMode.REPEAT_ONE -> getString(R.string.mode_repeat_one)
                    else -> getString(R.string.mode_shuffle)
                }
                btnMode.text = modeText
                tvMode.text = modeText
                // 列表高亮当前曲目
                if (adapter.playingPath != e.current!!.path)
                    adapter.playingPath = e.current!!.path
                // 切歌后加载封面+歌词
                val cur = e.current!!
                if (cur.path != loadedFor) {
                    loadedFor = cur.path
                    loadArt(cur)
                }
            } else {
                if (adapter.playingPath != null) adapter.playingPath = null
            }
            handler.postDelayed(this, 500)
        }
    }

    /** 后台提取封面与歌词，更新底部小图与歌词页缓存。 */
    private fun loadArt(song: Song) {
        ui.launch {
            val r = withContext(Dispatchers.IO) { MediaArt.load(this@MainActivity, song) }
            // 期间可能已切歌
            val e = PlaybackService.engine ?: return@launch
            if (e.current?.path != song.path) return@launch
            MediaArtHolder.cover = r.cover
            MediaArtHolder.lyrics = r.lyrics
            if (r.cover != null) ivNowCover.setImageBitmap(r.cover)
            else ivNowCover.setImageResource(R.drawable.ic_default_cover)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        tvNowTitle = findViewById(R.id.tvNowTitle)
        tvNowInfo = findViewById(R.id.tvNowInfo)
        tvTime = findViewById(R.id.tvTime)
        tvMode = findViewById(R.id.tvMode)
        tvCount = findViewById(R.id.tvCount)
        seekBar = findViewById(R.id.seekBar)
        btnPlay = findViewById(R.id.btnPlay)
        btnMode = findViewById(R.id.btnMode)
        ivNowCover = findViewById(R.id.ivNowCover)

        // 点击小箭头 → 全屏歌词页
        findViewById<View>(R.id.btnLyrics).setOnClickListener {
            val e = PlaybackService.engine
            if (e?.current != null) startActivity(Intent(this, LyricsActivity::class.java))
        }

        val rv = findViewById<RecyclerView>(R.id.rvSongs)
        rv.layoutManager = LinearLayoutManager(this)
        adapter = SongAdapter(display) { song ->
            val pos = songs.indexOfFirst { it.path == song.path }
            if (pos >= 0) playAt(pos)
        }
        rv.adapter = adapter

        // 搜索框：实时过滤 歌名/歌手/专辑
        val etSearch = findViewById<EditText>(R.id.etSearch)
        etSearch.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun afterTextChanged(s: Editable?) { applyFilter() }
        })

        findViewById<View>(R.id.btnPrev).setOnClickListener { PlaybackService.engine?.prev() }
        findViewById<View>(R.id.btnNext).setOnClickListener { PlaybackService.engine?.next() }
        btnPlay.setOnClickListener { PlaybackService.engine?.playPause() }
        btnMode.setOnClickListener {
            val e = PlaybackService.engine ?: return@setOnClickListener
            e.cycleMode()
        }

        var seeking = false
        seekBar.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(sb: SeekBar?, progress: Int, fromUser: Boolean) {
                if (fromUser) seeking = true
            }
            override fun onStartTrackingTouch(sb: SeekBar?) {}
            override fun onStopTrackingTouch(sb: SeekBar?) {
                PlaybackService.engine?.seekTo(sb!!.progress.toLong())
                seeking = false
            }
        })

        setupPager()
        requestPermissionAndScan()
    }

    // ---------------- 两页式界面：主界面 ⇄ 设置页 ----------------

    private fun setupPager() {
        rootSwipe = findViewById(R.id.rootSwipe)
        pageMain = findViewById(R.id.pageMain)
        pageSettings = findViewById(R.id.pageSettings)

        // 拖动进度条时不翻页
        rootSwipe.exclude = seekBar
        rootSwipe.onSwipeRight = { slideToSettings(true) }   // 主界面右滑 → 设置页
        rootSwipe.onSwipeLeft = { slideToMain(true) }        // 设置页左滑 → 主界面

        findViewById<View>(R.id.btnSettings).setOnClickListener { slideToSettings(true) }
        findViewById<View>(R.id.btnRescan).setOnClickListener { rescan() }
        findViewById<View>(R.id.btnBack).setOnClickListener { slideToMain(true) }

        optZh = findViewById(R.id.optZh)
        optEn = findViewById(R.id.optEn)
        optJa = findViewById(R.id.optJa)
        optZh.setOnClickListener { switchLanguage("zh") }
        optEn.setOnClickListener { switchLanguage("en") }
        optJa.setOnClickListener { switchLanguage("ja") }

        val fb = findViewById<TextView>(R.id.btnFeedback)
        fb.paintFlags = fb.paintFlags or Paint.UNDERLINE_TEXT_FLAG
        fb.setOnClickListener {
            try {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(getString(R.string.feedback_url))))
            } catch (_: Exception) {
                // 没有浏览器等情况下静默忽略
            }
        }
        val ver = try {
            packageManager.getPackageInfo(packageName, 0).versionName ?: ""
        } catch (_: Exception) {
            ""
        }
        findViewById<TextView>(R.id.tvVersion).text = getString(R.string.version_fmt, ver)
        refreshLanguageOptions()

        // 刚因为切换语言重建过 → 直接停在设置页
        val prefs = LocaleHelper.pref(this)
        if (prefs.getBoolean(LocaleHelper.KEY_OPEN_SETTINGS, false)) {
            prefs.edit().putBoolean(LocaleHelper.KEY_OPEN_SETTINGS, false).apply()
            slideToSettings(false)
        }
    }

    private fun slideToSettings(animated: Boolean) {
        if (showingSettings) return
        showingSettings = true
        val w = pageWidth()
        pageSettings.visibility = View.VISIBLE
        pageSettings.translationX = w.toFloat()
        if (!animated) {
            pageSettings.translationX = 0f
            pageMain.visibility = View.GONE
            return
        }
        pageSettings.animate().translationX(0f).setDuration(220).start()
        pageMain.animate().translationX(-w.toFloat()).setDuration(220).withEndAction {
            pageMain.visibility = View.GONE
            pageMain.translationX = 0f
        }.start()
    }

    private fun slideToMain(animated: Boolean) {
        if (!showingSettings) return
        showingSettings = false
        val w = pageWidth()
        pageMain.visibility = View.VISIBLE
        pageMain.translationX = -w.toFloat()
        if (!animated) {
            pageMain.translationX = 0f
            pageSettings.visibility = View.GONE
            return
        }
        pageMain.animate().translationX(0f).setDuration(220).start()
        pageSettings.animate().translationX(w.toFloat()).setDuration(220).withEndAction {
            pageSettings.visibility = View.GONE
            pageSettings.translationX = 0f
        }.start()
    }

    private fun pageWidth(): Int {
        val w = rootSwipe.width
        return if (w > 0) w else resources.displayMetrics.widthPixels
    }

    private fun refreshLanguageOptions() {
        val cur = LocaleHelper.current(this)
        for ((tag, v) in listOf("zh" to optZh, "en" to optEn, "ja" to optJa)) {
            val label = when (tag) {
                "en" -> getString(R.string.lang_en)
                "ja" -> getString(R.string.lang_ja)
                else -> getString(R.string.lang_zh)
            }
            if (tag == cur) {
                v.text = "✓  $label"
                v.setTextColor(0xFFFFFFFF.toInt())
                v.background = ContextCompat.getDrawable(this, R.drawable.bg_playing)
            } else {
                v.text = label
                v.setTextColor(0xFFB0B0C0.toInt())
                v.background = ContextCompat.getDrawable(this, R.drawable.bg_item)
            }
        }
    }

    private fun switchLanguage(tag: String) {
        if (LocaleHelper.saved(this) == tag) return
        LocaleHelper.set(this, tag)
        LocaleHelper.pref(this).edit().putBoolean(LocaleHelper.KEY_OPEN_SETTINGS, true).apply()
        recreate()
    }

    override fun onBackPressed() {
        if (showingSettings) slideToMain(true) else super.onBackPressed()
    }

    // ---------------- 曲库 ----------------

    /** 重新扫描曲库（右上角「重新扫描」，或首次进入时的权限通过后）。 */
    private fun rescan() {
        if (scanning) return
        scanning = true
        tvCount.text = getString(R.string.scanning)
        ui.launch {
            val list = withContext(Dispatchers.IO) { LibraryScanner.scan(this@MainActivity) }
            songs.clear()
            songs.addAll(list)
            scanning = false
            applyFilter()
            Toast.makeText(
                this@MainActivity,
                getString(R.string.rescan_done, list.size),
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    /** 按搜索词过滤展示列表（歌名/歌手/专辑，大小写不敏感）。 */
    private fun applyFilter() {
        val q = (findViewById<EditText>(R.id.etSearch).text ?: "").toString().trim()
        display.clear()
        if (q.isEmpty()) display.addAll(songs)
        else display.addAll(songs.filter {
            it.title.contains(q, true) || it.artist.contains(q, true) ||
            it.album.contains(q, true)
        })
        adapter.notifyDataSetChanged()
        tvCount.text = if (q.isEmpty()) getString(R.string.count_all, songs.size)
                       else getString(R.string.count_filtered, display.size, songs.size)
    }

    override fun onResume() {
        super.onResume()
        handler.post(tick)
    }

    override fun onPause() {
        super.onPause()
        handler.removeCallbacks(tick)
    }

    private fun requestPermissionAndScan() {
        val perm = if (Build.VERSION.SDK_INT >= 33)
            Manifest.permission.READ_MEDIA_AUDIO else Manifest.permission.READ_EXTERNAL_STORAGE
        if (ContextCompat.checkSelfPermission(this, perm) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(perm), 1)
            return
        }
        scan()
    }

    override fun onRequestPermissionsResult(rc: Int, perms: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(rc, perms, results)
        if (rc == 1 && results.firstOrNull() == PackageManager.PERMISSION_GRANTED) scan()
    }

    private fun scan() {
        if (scanning) return
        scanning = true
        tvCount.text = getString(R.string.scanning)
        ui.launch {
            val list = withContext(Dispatchers.IO) { LibraryScanner.scan(this@MainActivity) }
            songs.clear()
            songs.addAll(list)
            scanning = false
            applyFilter()
        }
    }

    private fun playAt(pos: Int) {
        PlaybackService.start(this)
        // 服务 onCreate 是同步的，startForegroundService 后 engine 可能尚未就绪，轮询一次
        fun go() {
            val e = PlaybackService.engine
            if (e != null) e.setQueue(songs, pos) else handler.postDelayed({ go() }, 100)
        }
        go()
    }

    private fun format(ms: Long): String {
        val s = ms / 1000
        return "%d:%02d".format(s / 60, s % 60)
    }
}
