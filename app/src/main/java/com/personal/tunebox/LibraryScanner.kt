package com.personal.tunebox

import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * 曲库扫描：
 * 1) MediaStore（系统音频库，快）；
 * 2) 补扫文件系统（MediaStore 认不出的扩展名，如 .ape/.dsf/.dff/.wv/.tak/.tta）。
 */
object LibraryScanner {

    // MediaStore 能覆盖的常见格式
    private val COMMON_EXT = setOf(
        "mp3", "flac", "m4a", "aac", "ogg", "oga", "opus", "wav", "wma", "aiff", "aif"
    )
    // libVLC 支持但 MediaStore 常忽略的无损/小众格式
    private val EXTRA_EXT = setOf(
        "ape", "dsf", "dff", "wv", "tak", "tta", "mka", "ac3", "dts", "shn", "caf", "alac"
    )

    suspend fun scan(context: Context): List<Song> = withContext(Dispatchers.IO) {
        val seen = HashSet<String>()
        val out = ArrayList<Song>()

        // ---- 1. MediaStore ----
        val proj = arrayOf(
            MediaStore.Audio.Media._ID,
            MediaStore.Audio.Media.TITLE,
            MediaStore.Audio.Media.ARTIST,
            MediaStore.Audio.Media.ALBUM,
            MediaStore.Audio.Media.DURATION,
            MediaStore.Audio.Media.SIZE,
            MediaStore.Audio.Media.DATA
        )
        try {
            context.contentResolver.query(
                MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, proj, null, null,
                MediaStore.Audio.Media.TITLE + " COLLATE NOCASE ASC"
            )?.use { c ->
                while (c.moveToNext()) {
                    val path = c.getString(6) ?: continue
                    if (seen.add(path)) {
                        out.add(
                            Song(
                                path = path,
                                title = c.getString(1) ?: File(path).nameWithoutExtension,
                                artist = c.getString(2) ?: "未知艺术家",
                                album = c.getString(3) ?: "未知专辑",
                                durationMs = c.getLong(4),
                                sizeBytes = c.getLong(5)
                            )
                        )
                    }
                }
            }
        } catch (_: Exception) { }

        // ---- 2. 文件系统补扫（Download/Music/Documents 根目录递归） ----
        val roots = listOf(
            android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_MUSIC),
            android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS),
            File(android.os.Environment.getExternalStorageDirectory(), "Netease"),
            File(android.os.Environment.getExternalStorageDirectory(), "Music")
        )
        for (root in roots) {
            if (root != null && root.exists()) walk(root, seen, out)
        }

        out.sortedBy { it.title.lowercase() }
    }

    private fun walk(dir: File, seen: MutableSet<String>, out: MutableList<Song>) {
        val files = dir.listFiles() ?: return
        for (f in files) {
            if (f.isDirectory) {
                walk(f, seen, out)
            } else {
                val ext = f.extension.lowercase()
                if ((COMMON_EXT.contains(ext) || EXTRA_EXT.contains(ext)) && seen.add(f.absolutePath)) {
                    out.add(
                        Song(
                            path = f.absolutePath,
                            title = f.nameWithoutExtension,
                            artist = "未知艺术家",
                            album = "本地文件",
                            durationMs = 0L,
                            sizeBytes = f.length()
                        )
                    )
                }
            }
        }
    }
}
