package com.personal.tunebox

import android.Manifest
import android.app.AlertDialog
import android.app.RecoverableSecurityException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.ContentUris
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.media.MediaScannerConnection
import android.net.Uri
import android.provider.MediaStore
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
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.PopupMenu
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity : AppCompatActivity() {

    private lateinit var adapter: SongAdapter
    private val songs = ArrayList<Song>()
    private val display = ArrayList<Song>()
    private val handler = Handler(Looper.getMainLooper())
    private val ui = CoroutineScope(Dispatchers.Main)

    private var pendingDelete: Song? = null

    private val deleteLauncher =
        registerForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { res ->
            val s = pendingDelete
            pendingDelete = null
            when {
                s != null && res.resultCode == RESULT_OK -> finishDelete(s)
                res.resultCode == RESULT_CANCELED -> toast(R.string.delete_canceled)
                else -> toast(R.string.delete_failed)
            }
        }

    private lateinit var tvNowTitle: TextView
    private lateinit var tvNowInfo: TextView
    private lateinit var tvTime: TextView
    private lateinit var tvMode: TextView
    private lateinit var tvCount: TextView
    private lateinit var seekBar: SeekBar
    private lateinit var btnPlay: MaterialButton
    private lateinit var btnMode: TextView
    private lateinit var ivNowCover: ImageView
    private var loadedFor: String? = null

    private lateinit var pageNow: View
    private lateinit var waveform: WaveformView
    private lateinit var tvBigTitle: TextView
    private lateinit var tvBigArtist: TextView
    private lateinit var tvBigTime: TextView
    private lateinit var btnNowPlay: MaterialButton
    private lateinit var btnNowMode: MaterialButton
    private var showingNow = false
    private var peaksFor: String? = null

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
                tvBigTitle.text = e.current!!.title
                tvBigArtist.text = e.current!!.artist + " · " + e.current!!.album
                btnPlay.setIconResource(if (e.isPlaying) R.drawable.ic_pause else R.drawable.ic_play)
                btnNowPlay.setIconResource(if (e.isPlaying) R.drawable.ic_pause else R.drawable.ic_play)
                if (dur > 0) {
                    waveform.setProgress(e.position.toFloat() / dur.toFloat())
                    tvBigTime.text = format(e.position) + " / " + format(dur)
                }
                val modeText = when (e.mode) {
                    PlayMode.SEQUENTIAL -> getString(R.string.mode_sequential)
                    PlayMode.REPEAT_LIST -> getString(R.string.mode_repeat_list)
                    PlayMode.REPEAT_ONE -> getString(R.string.mode_repeat_one)
                    else -> getString(R.string.mode_shuffle)
                }
                btnMode.text = modeText
                tvMode.text = modeText
                btnNowMode.text = modeText
                if (adapter.playingPath != e.current!!.path)
                    adapter.playingPath = e.current!!.path
                val cur = e.current!!
                if (cur.path != loadedFor) {
                    loadedFor = cur.path
                    loadArt(cur)
                }
                if (peaksFor != cur.path && WaveformPeaks.cached(cur.path) == null) loadPeaks(cur)
            } else {
                if (adapter.playingPath != null) adapter.playingPath = null
                waveform.setProgress(0f)
            }
            handler.postDelayed(this, 500)
        }
    }

    private fun loadArt(song: Song) {
        ui.launch {
            val r = withContext(Dispatchers.IO) { MediaArt.load(this@MainActivity, song) }
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
        WindowCompat.setDecorFitsSystemWindows(window, false)
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.rootSwipe)) { v, insets ->
            val bars = insets.getInsets(
                WindowInsetsCompat.Type.systemBars()
                    or WindowInsetsCompat.Type.displayCutout()
                    or WindowInsetsCompat.Type.ime()
            )
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }

        tvNowTitle = findViewById(R.id.tvNowTitle)
        tvNowInfo = findViewById(R.id.tvNowInfo)
        tvTime = findViewById(R.id.tvTime)
        tvMode = findViewById(R.id.tvMode)
        tvCount = findViewById(R.id.tvCount)
        seekBar = findViewById(R.id.seekBar)
        btnPlay = findViewById(R.id.btnPlay)
        btnMode = findViewById(R.id.btnMode)
        ivNowCover = findViewById(R.id.ivNowCover)

        pageNow = findViewById(R.id.pageNow)
        waveform = findViewById(R.id.waveform)
        tvBigTitle = findViewById(R.id.tvBigTitle)
        tvBigArtist = findViewById(R.id.tvBigArtist)
        tvBigTime = findViewById(R.id.tvBigTime)
        btnNowPlay = findViewById(R.id.btnNowPlay)
        btnNowMode = findViewById(R.id.btnNowMode)

        findViewById<View>(R.id.btnNow).setOnClickListener { showNow() }
        findViewById<View>(R.id.btnNowBack).setOnClickListener { hideNow() }
        findViewById<View>(R.id.btnNowPrev).setOnClickListener { PlaybackService.engine?.prev() }
        findViewById<View>(R.id.btnNowNext).setOnClickListener { PlaybackService.engine?.next() }
        btnNowPlay.setOnClickListener { PlaybackService.engine?.playPause() }
        btnNowMode.setOnClickListener {
            val e = PlaybackService.engine ?: return@setOnClickListener
            e.cycleMode()
        }
        waveform.onSeek = { ratio ->
            val e = PlaybackService.engine
            if (e != null && e.duration > 0) e.seekTo((ratio * e.duration).toLong())
        }

        findViewById<View>(R.id.btnLyrics).setOnClickListener {
            val e = PlaybackService.engine
            if (e?.current != null) startActivity(Intent(this, LyricsActivity::class.java))
        }

        val rv = findViewById<RecyclerView>(R.id.rvSongs)
        rv.layoutManager = LinearLayoutManager(this)
        adapter = SongAdapter(display, { song ->
            val pos = songs.indexOfFirst { it.path == song.path }
            if (pos >= 0) playAt(pos)
        }, { song, anchor -> showSongMenu(song, anchor) })
        rv.adapter = adapter

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

    private fun setupPager() {
        rootSwipe = findViewById(R.id.rootSwipe)
        pageMain = findViewById(R.id.pageMain)
        pageSettings = findViewById(R.id.pageSettings)

        rootSwipe.exclude = seekBar
        rootSwipe.onSwipeRight = { slideToSettings(true) }
        rootSwipe.onSwipeLeft = { slideToMain(true) }

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
        fb.setOnClickListener {
            try {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(getString(R.string.feedback_url))))
            } catch (_: Exception) {
            }
        }
        val ver = try {
            packageManager.getPackageInfo(packageName, 0).versionName ?: ""
        } catch (_: Exception) {
            ""
        }
        findViewById<TextView>(R.id.tvVersion).text = getString(R.string.version_fmt, ver)
        refreshLanguageOptions()

        val prefs = LocaleHelper.pref(this)
        if (prefs.getBoolean(LocaleHelper.KEY_OPEN_SETTINGS, false)) {
            prefs.edit().putBoolean(LocaleHelper.KEY_OPEN_SETTINGS, false).apply()
            slideToSettings(false)
        }
    }

    private fun showNow() {
        if (showingSettings) slideToMain(false)
        showingNow = true
        pageNow.visibility = View.VISIBLE
        pageNow.alpha = 0f
        pageNow.animate().alpha(1f).setDuration(160).start()
        rootSwipe.exclude = waveform
        val e = PlaybackService.engine
        val cur = e?.current
        if (cur != null) {
            waveform.setAmplitudes(WaveformPeaks.cached(cur.path) ?: FloatArray(0))
            if (peaksFor != cur.path && WaveformPeaks.cached(cur.path) == null) loadPeaks(cur)
        } else {
            waveform.setAmplitudes(FloatArray(0))
        }
    }

    private fun hideNow() {
        showingNow = false
        pageNow.visibility = View.GONE
        rootSwipe.exclude = seekBar
    }

    private fun loadPeaks(song: Song) {
        peaksFor = song.path
        ui.launch {
            val amps = WaveformPeaks.load(song.path)
            val e = PlaybackService.engine ?: return@launch
            if (e.current?.path != song.path) return@launch
            waveform.setAmplitudes(amps)
        }
    }

    private fun slideToSettings(animated: Boolean) {
        if (showingSettings || showingNow) return
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
        if (showingNow) hideNow()
        else if (showingSettings) slideToMain(true)
        else super.onBackPressed()
    }

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
        val perms = ArrayList<String>(2)
        if (!hasRead()) perms.add(readPermission)
        // Android 10 及以下删文件要写权限（11 起走系统的删除请求，不需要权限）
        if (Build.VERSION.SDK_INT <= 29 && !hasWrite()) {
            perms.add(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        }
        if (perms.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, perms.toTypedArray(), 1)
            return
        }
        scan()
    }

    private val readPermission: String
        get() = if (Build.VERSION.SDK_INT >= 33)
            Manifest.permission.READ_MEDIA_AUDIO else Manifest.permission.READ_EXTERNAL_STORAGE

    private fun granted(perm: String) =
        ContextCompat.checkSelfPermission(this, perm) == PackageManager.PERMISSION_GRANTED

    private fun hasRead() = granted(readPermission)

    private fun hasWrite() = Build.VERSION.SDK_INT > 29 || granted(Manifest.permission.WRITE_EXTERNAL_STORAGE)

    override fun onRequestPermissionsResult(rc: Int, perms: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(rc, perms, results)
        if (rc == 1 && hasRead()) scan()
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

    private fun showSongMenu(song: Song, anchor: View) {
        val pop = PopupMenu(this, anchor)
        pop.menu.add(0, 1, 0, getString(R.string.menu_fetch_info))
        pop.menu.add(0, 2, 1, getString(R.string.menu_detail))
        pop.menu.add(0, 3, 2, getString(R.string.menu_copy_title))
        pop.menu.add(0, 4, 3, getString(R.string.menu_copy_path))
        pop.menu.add(0, 5, 4, getString(R.string.menu_delete))
        pop.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                1 -> fetchOnline(song)
                2 -> showDetail(song)
                3 -> copyText(song.title)
                4 -> copyText(song.path)
                else -> confirmDelete(song)
            }
            true
        }
        pop.show()
    }

    private fun toast(res: Int) = Toast.makeText(this, getString(res), Toast.LENGTH_SHORT).show()

    private fun confirmDelete(song: Song) {
        AlertDialog.Builder(this)
            .setTitle(R.string.menu_delete)
            .setMessage(getString(R.string.delete_confirm, song.title))
            .setNegativeButton(R.string.cancel, null)
            .setPositiveButton(R.string.delete_ok) { _, _ -> deleteSong(song) }
            .show()
    }

    private fun deleteSong(song: Song) {
        val f = File(song.path)
        if (!f.exists()) {
            finishDelete(song)
            return
        }
        if (Build.VERSION.SDK_INT >= 30) {
            val uri = mediaUri(f)
            if (uri != null) askSystemToDelete(song, uri) else scanThenDelete(song, f)
            return
        }
        if (hasWrite() && runCatching { f.delete() }.getOrDefault(false)) {
            finishDelete(song)
            return
        }
        if (Build.VERSION.SDK_INT == 29) {
            val uri = mediaUri(f)
            if (uri != null && deleteViaResolver(song, uri)) return
        }
        toast(if (hasWrite()) R.string.delete_not_in_library else R.string.delete_no_perm)
    }

    private fun mediaUri(f: File): Uri? = runCatching {
        MediaStore.getDocumentUri(this, Uri.fromFile(f))?.let { MediaStore.getMediaUri(this, it) }
    }.getOrNull()

    private fun askSystemToDelete(song: Song, uri: Uri) {
        pendingDelete = song
        val req = MediaStore.createDeleteRequest(contentResolver, listOf(uri))
        deleteLauncher.launch(IntentSenderRequest.Builder(req.intentSender).build())
    }

    private fun scanThenDelete(song: Song, f: File) {
        MediaScannerConnection.scanFile(this, arrayOf(f.absolutePath), null) { _, _ ->
            val uri = queryMediaUri(f) ?: mediaUri(f)
            runOnUiThread {
                if (uri == null) toast(R.string.delete_not_in_library) else askSystemToDelete(song, uri)
            }
        }
    }

    private fun queryMediaUri(f: File): Uri? = runCatching {
        contentResolver.query(
            MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,
            arrayOf(MediaStore.Audio.Media._ID),
            MediaStore.Audio.Media.DATA + "=?",
            arrayOf(f.absolutePath), null
        )?.use { c ->
            if (c.moveToFirst()) ContentUris.withAppendedId(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, c.getLong(0))
            else null
        }
    }.getOrNull()

    private fun deleteViaResolver(song: Song, uri: Uri): Boolean = try {
        contentResolver.delete(uri, null, null)
        finishDelete(song)
        true
    } catch (e: RecoverableSecurityException) {
        pendingDelete = song
        deleteLauncher.launch(IntentSenderRequest.Builder(e.userAction.actionIntent.intentSender).build())
        true
    } catch (_: Throwable) {
        false
    }

    private fun finishDelete(song: Song) {
        val wasCurrent = PlaybackService.engine?.current?.path == song.path
        if (wasCurrent) PlaybackService.engine?.forget(song.path)
        songs.removeAll { it.path == song.path }
        applyFilter()
        if (wasCurrent) {
            loadedFor = null
            tvNowTitle.text = getString(R.string.not_playing)
            tvNowInfo.text = ""
            seekBar.progress = 0
            btnPlay.setIconResource(R.drawable.ic_play)
            ivNowCover.setImageResource(R.drawable.ic_default_cover)
            MediaArtHolder.cover = null
            MediaArtHolder.lyrics = emptyList()
        }
        toast(R.string.deleted)
    }

    private fun copyText(text: String) {
        val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText("TuneKuo", text))
        Toast.makeText(this, getString(R.string.copied), Toast.LENGTH_SHORT).show()
    }

    private fun showDetail(song: Song) {
        val sb = StringBuilder()
        sb.append(kv(R.string.detail_title, song.title)).append('\n')
        sb.append(kv(R.string.detail_artist, song.artist)).append('\n')
        sb.append(kv(R.string.detail_album, song.album)).append('\n')
        sb.append(kv(R.string.detail_duration, format(song.durationMs))).append('\n')
        sb.append(kv(R.string.detail_format, File(song.path).extension.uppercase().ifBlank { "?" })).append('\n')
        sb.append(kv(R.string.detail_size, human(song.sizeBytes))).append('\n')
        sb.append(kv(R.string.detail_path, song.path))
        AlertDialog.Builder(this)
            .setTitle(R.string.menu_detail)
            .setMessage(sb.toString())
            .setPositiveButton(R.string.close, null)
            .show()
    }

    private fun fetchOnline(song: Song) {
        Toast.makeText(this, getString(R.string.fetching_online), Toast.LENGTH_SHORT).show()
        ui.launch {
            val info = OnlineMeta.fetch(this@MainActivity, song)
            if (info == null) {
                Toast.makeText(this@MainActivity, getString(R.string.fetch_failed), Toast.LENGTH_LONG).show()
                return@launch
            }
            val i = songs.indexOfFirst { it.path == song.path }
            if (i >= 0) {
                val old = songs[i]
                val updated = old.copy(
                    title = info.title.ifBlank { old.title },
                    artist = info.artist.ifBlank { old.artist },
                    album = info.album.ifBlank { old.album }
                )
                songs[i] = updated
                val d = display.indexOfFirst { it.path == song.path }
                if (d >= 0) display[d] = updated
                adapter.notifyDataSetChanged()
                PlaybackService.engine?.retitle(updated)
            }
            if (PlaybackService.engine?.current?.path == song.path) {
                info.cover?.let { f ->
                    BitmapFactory.decodeFile(f.absolutePath)?.let {
                        MediaArtHolder.cover = it
                        ivNowCover.setImageBitmap(it)
                    }
                }
                if (info.lyrics.isNotEmpty()) MediaArtHolder.lyrics = info.lyrics
            }
            showInfoDialog(song, info)
        }
    }

    private fun showInfoDialog(song: Song, info: OnlineMeta.Info) {
        val sb = StringBuilder()
        sb.append(kv(R.string.detail_title, info.title)).append('\n')
        sb.append(kv(R.string.detail_artist, info.artist)).append('\n')
        if (info.album.isNotBlank()) sb.append(kv(R.string.detail_album, info.album)).append('\n')
        if (info.year.isNotBlank()) sb.append(kv(R.string.detail_year, info.year)).append('\n')
        if (info.genre.isNotBlank()) sb.append(kv(R.string.detail_genre, info.genre)).append('\n')
        val src = listOf(info.metaSource, info.lyricSource).filter { it.isNotBlank() }.joinToString(" · ")
        if (src.isNotBlank()) sb.append(kv(R.string.detail_source, src)).append('\n')
        sb.append(kv(R.string.detail_cover,
            getString(if (info.cover != null) R.string.got else R.string.not_found))).append('\n')
        sb.append(if (info.lyrics.isEmpty()) getString(R.string.fetch_lyrics_none)
                  else getString(R.string.fetch_lyrics_ok, info.lyrics.size))

        val b = AlertDialog.Builder(this)
            .setTitle(R.string.menu_fetch_info)
            .setMessage(sb.toString())
            .setNegativeButton(R.string.close, null)
        if (info.lyrics.isNotEmpty() && PlaybackService.engine?.current?.path == song.path) {
            b.setPositiveButton(R.string.view_lyrics) { _, _ ->
                startActivity(Intent(this, LyricsActivity::class.java))
            }
        }
        b.show()
    }

    private fun kv(labelRes: Int, value: String) =
        getString(R.string.kv_fmt, getString(labelRes), value)

    private fun human(bytes: Long): String = when {
        bytes >= 1073741824L -> "%.2f GB".format(bytes / 1073741824.0)
        bytes >= 1048576L -> "%.1f MB".format(bytes / 1048576.0)
        bytes >= 1024L -> "%.0f KB".format(bytes / 1024.0)
        else -> "$bytes B"
    }
}
