package com.personal.tunebox

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

object MediaArt {

    data class Result(val cover: Bitmap?, val lyrics: List<LyricLine>)

    private val COVER_NAMES = listOf("cover", "folder", "album", "front", "albumart")

    suspend fun load(context: Context, song: Song): Result = withContext(Dispatchers.IO) {
        var cover: Bitmap? = null
        val lyrics = ArrayList<LyricLine>()

        try {
            val mmr = MediaMetadataRetriever()
            mmr.setDataSource(song.path)

            val art = mmr.embeddedPicture
            if (art != null) cover = BitmapFactory.decodeByteArray(art, 0, art.size)

            for (key in intArrayOf(92, 93, 94, 95)) {
                try {
                    val t = mmr.extractMetadata(key)
                    if (!t.isNullOrBlank()) { lyrics.addAll(parseLrc(t)); break }
                } catch (_: Exception) { }
            }
            mmr.release()
        } catch (_: Exception) { }

        if (cover == null) {
            val dir = File(song.path).parentFile
            if (dir != null && dir.exists()) {
                for (f in dir.listFiles() ?: emptyArray()) {
                    val n = f.nameWithoutExtension.lowercase()
                    val e = f.extension.lowercase()
                    if ((e == "jpg" || e == "jpeg" || e == "png" || e == "webp") &&
                        (COVER_NAMES.any { n.contains(it) })) {
                        cover = BitmapFactory.decodeFile(f.absolutePath)
                        if (cover != null) break
                    }
                }
                if (cover == null) {
                    for (f in dir.listFiles() ?: emptyArray()) {
                        val e = f.extension.lowercase()
                        if (e == "jpg" || e == "jpeg" || e == "png" || e == "webp") {
                            cover = BitmapFactory.decodeFile(f.absolutePath)
                            if (cover != null) break
                        }
                    }
                }
            }
        }

        if (lyrics.isEmpty()) {
            val base = File(song.path).absolutePath
            for (cand in listOf(base.substringBeforeLast('.') + ".lrc",
                                base + ".lrc")) {
                val f = File(cand)
                if (f.exists()) {
                    lyrics.addAll(parseLrc(f.readText(Charsets.UTF_8)))
                    if (lyrics.isNotEmpty()) break
                }
            }
        }

        if (cover == null) {
            val f = OnlineMeta.cachedCover(context, song)
            if (f.exists()) cover = BitmapFactory.decodeFile(f.absolutePath)
        }
        if (lyrics.isEmpty()) {
            val f = OnlineMeta.cachedLyrics(context, song)
            if (f.exists()) lyrics.addAll(parseLrc(f.readText(Charsets.UTF_8)))
        }

        lyrics.sortBy { it.timeMs }
        Result(cover, lyrics)
    }

    fun parseLrc(text: String): List<LyricLine> {
        val out = ArrayList<LyricLine>()
        val re = Regex("""\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?]""")
        for (raw in text.lines()) {
            val stamps = re.findAll(raw).toList()
            if (stamps.isEmpty()) continue
            val content = raw.replace(re, "").trim()
            if (content.isEmpty()) continue
            for (m in stamps) {
                val min = m.groupValues[1].toLong()
                val sec = m.groupValues[2].toLong()
                val fracStr = m.groupValues[3]
                val frac = when (fracStr.length) {
                    0 -> 0L
                    1 -> fracStr.toLong() * 100
                    2 -> fracStr.toLong() * 10
                    else -> fracStr.take(3).toLong()
                }
                out.add(LyricLine(min * 60000 + sec * 1000 + frac, content))
            }
        }
        return out
    }
}

data class LyricLine(val timeMs: Long, val text: String)
