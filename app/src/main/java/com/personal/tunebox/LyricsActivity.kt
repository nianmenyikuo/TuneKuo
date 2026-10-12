package com.personal.tunebox

import android.graphics.Bitmap
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * 全屏歌词页：封面大图 + 歌名 + 逐行歌词，当前行高亮并自动滚动到屏幕中央。
 * 从主界面底部小箭头进入。
 */
class LyricsActivity : AppCompatActivity() {

    private val handler = Handler(Looper.getMainLooper())
    private lateinit var tvLines: List<TextView>
    private lateinit var scroll: ScrollView
    private lateinit var ivCover: ImageView
    private var currentLine = -1

    private val tick = object : Runnable {
        override fun run() {
            val e = PlaybackService.engine ?: return
            val song = e.current ?: return
            val pos = e.position

            // 找当前行：最后一个 timeMs <= pos 的行
            val lines = MediaArtHolder.lyrics
            var idx = -1
            for (i in lines.indices) {
                if (lines[i].timeMs <= pos) idx = i else break
            }
            if (idx != currentLine) {
                currentLine = idx
                for (i in tvLines.indices) {
                    if (i == idx) {
                        tvLines[i].setTextColor(0xFFFFFFFF.toInt())
                        tvLines[i].textSize = 20f
                    } else {
                        tvLines[i].setTextColor(0xFF8888A0.toInt())
                        tvLines[i].textSize = 16f
                    }
                }
                if (idx >= 0 && idx < tvLines.size) {
                    scroll.post {
                        scroll.smoothScrollTo(0, tvLines[idx].top - height / 3)
                    }
                }
            }
            handler.postDelayed(this, 200)
        }
    }

    private var height = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val e = PlaybackService.engine
        val song = e?.current
        val cover: Bitmap? = MediaArtHolder.cover
        val lyrics = MediaArtHolder.lyrics

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(0xFF101018.toInt())
            setPadding(48, 64, 48, 48)
        }

        // 封面
        ivCover = ImageView(this).apply {
            adjustViewBounds = true
            maxHeight = 720
            setImageBitmap(cover)
        }
        root.addView(ivCover, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
            topMargin = 0; bottomMargin = 32
        })

        // 歌名
        root.addView(TextView(this).apply {
            text = song?.title ?: "未播放"
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 22f
        })
        root.addView(TextView(this).apply {
            text = (song?.artist ?: "") + " · " + (song?.album ?: "")
            setTextColor(0xFF8888A0.toInt())
            textSize = 13f
        })

        // 歌词滚动区
        scroll = ScrollView(this)
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val list = if (lyrics.isEmpty())
            listOf(LyricLine(0, "暂无歌词")) else lyrics
        tvLines = list.map { line ->
            TextView(this).apply {
                text = line.text
                setTextColor(0xFF8888A0.toInt())
                textSize = 16f
                setPadding(0, 24, 0, 24)
                setLineSpacing(0f, 1.2f)
            }.also { col.addView(it) }
        }
        scroll.addView(col)
        root.addView(scroll, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))

        setContentView(root)
        height = resources.displayMetrics.heightPixels

        // 点击封面/空白处关闭
        root.setOnClickListener { finish() }
        ivCover.setOnClickListener { finish() }
    }

    override fun onResume() { super.onResume(); handler.post(tick) }
    override fun onPause() { super.onPause(); handler.removeCallbacks(tick) }
    override fun onBackPressed() { finish() }
}

/** 进程级缓存：主界面加载完封面/歌词后传给歌词页。 */
object MediaArtHolder {
    var cover: Bitmap? = null
    var lyrics: List<LyricLine> = emptyList()
}
