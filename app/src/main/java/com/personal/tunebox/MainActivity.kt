package com.personal.tunebox

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.text.Editable
import android.text.TextWatcher
import android.widget.EditText
import android.widget.ImageView
import android.widget.SeekBar
import android.widget.TextView
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
                    PlayMode.SEQUENTIAL -> "顺序"
                    PlayMode.REPEAT_LIST -> "列表循环"
                    PlayMode.REPEAT_ONE -> "单曲循环"
                    PlayMode.SHUFFLE -> "随机"
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

        requestPermissionAndScan()
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
        tvCount.text = if (q.isEmpty()) "共 ${songs.size} 首"
                       else "${display.size}/${songs.size} 首"
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
        ui.launch {
            val list = withContext(Dispatchers.IO) { LibraryScanner.scan(this@MainActivity) }
            songs.clear()
            songs.addAll(list)
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
