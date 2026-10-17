package com.personal.tunebox

import android.content.Context
import android.graphics.BitmapFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

object OnlineMeta {

    data class Info(
        val title: String,
        val artist: String,
        val album: String,
        val year: String,
        val genre: String,
        val metaSource: String,
        val lyricSource: String,
        val cover: File?,
        val lyrics: List<LyricLine>
    )

    private fun key(song: Song) = Integer.toHexString(song.path.hashCode())

    private fun cacheDir(context: Context, sub: String): File =
        File(context.getExternalFilesDir(null), "online/$sub").apply { mkdirs() }

    fun cachedLyrics(context: Context, song: Song) = File(cacheDir(context, "lyrics"), key(song) + ".lrc")

    fun cachedCover(context: Context, song: Song) = File(cacheDir(context, "covers"), key(song) + ".img")

    data class Meta(val title: String, val artist: String, val album: String)

    private fun metaFile(context: Context, song: Song) = File(cacheDir(context, "meta"), key(song) + ".json")

    fun cachedMeta(context: Context, song: Song): Meta? = try {
        val f = metaFile(context, song)
        if (!f.isFile) null else JSONObject(f.readText()).let {
            Meta(it.optString("title"), it.optString("artist"), it.optString("album"))
        }
    } catch (_: Exception) {
        null
    }

    private fun saveMeta(context: Context, song: Song, title: String, artist: String, album: String) = try {
        metaFile(context, song).writeText(
            JSONObject().put("title", title).put("artist", artist).put("album", album).toString()
        )
        Unit
    } catch (_: Exception) {
        Unit
    }

    suspend fun fetch(context: Context, song: Song): Info? = withContext(Dispatchers.IO) {
        val unknownArtist = context.getString(R.string.unknown_artist)
        val artistTag = song.artist.trim().let { if (it == unknownArtist) "" else it }
        val query = listOf(artistTag, song.title).filter { it.isNotBlank() }.joinToString(" ")
        if (query.isBlank()) return@withContext null

        var title = song.title
        var artist = artistTag
        var album = ""
        var year = ""
        var genre = ""
        var metaSource = ""
        var coverUrl = ""

        json("https://itunes.apple.com/search?media=music&entity=song&limit=5&term=" + enc(query))
            ?.optJSONArray("results")?.let { pickITunes(it, song, artistTag) }?.let { it ->
                title = it.optString("trackName").ifBlank { title }
                artist = it.optString("artistName").ifBlank { artist }
                album = it.optString("collectionName")
                year = it.optString("releaseDate").take(4)
                genre = it.optString("primaryGenreName")
                coverUrl = it.optString("artworkUrl100").replace("100x100", "600x600")
                metaSource = "iTunes"
            }

        var lyrText = lrcLib(title, artist, album, song.durationMs)
        var lyricSource = if (lyrText.isNotBlank()) "LRCLIB" else ""
        if (lyrText.isBlank() || metaSource.isEmpty()) {
            val ne = neteaseSearch(query, song.title, artistTag, song.durationMs)
            if (ne != null) {
                if (lyrText.isBlank()) {
                    lyrText = neteaseLyrics(ne.optLong("id"))
                    if (lyrText.isNotBlank()) lyricSource = "NetEase"
                }
                if (metaSource.isEmpty()) {
                    title = ne.optString("name").ifBlank { title }
                    ne.optJSONArray("artists")?.optJSONObject(0)?.optString("name")
                        ?.takeIf { it.isNotBlank() }?.let { artist = it }
                    ne.optJSONObject("album")?.let {
                        album = it.optString("name")
                        if (coverUrl.isBlank()) coverUrl = it.optString("picUrl")
                    }
                    metaSource = "NetEase"
                }
            }
        }

        if (metaSource.isEmpty() && lyricSource.isEmpty()) return@withContext null

        val parsed = MediaArt.parseLrc(lyrText)
        val lyrics: List<LyricLine>
        val cacheText: String
        if (parsed.isNotEmpty()) {
            lyrics = parsed
            cacheText = lyrText
        } else {
            lyrics = lyrText.lines().map { it.trim() }.filter { it.isNotEmpty() }.map { LyricLine(0, it) }
            cacheText = lyrics.joinToString("\n") { "[00:00.00]" + it.text }
        }
        if (cacheText.isNotBlank()) cachedLyrics(context, song).writeText(cacheText)

        val cover = if (coverUrl.isNotBlank()) downloadCover(context, song, coverUrl) else null

        if (metaSource.isNotEmpty()) saveMeta(context, song, title, artist, album)

        Info(title, artist, album, year, genre, metaSource, lyricSource, cover, lyrics)
    }

    private fun pickITunes(arr: JSONArray, song: Song, artist: String): JSONObject? {
        val wantTitle = norm(song.title)
        val wantArtist = norm(artist)
        var best: JSONObject? = null
        var bestScore = 0
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            if (!titleLike(norm(o.optString("trackName")), wantTitle)) continue
            val nameArtist = norm(o.optString("artistName"))
            if (wantArtist.isNotEmpty() && wantArtist != nameArtist) continue
            var score = 2
            val ms = o.optLong("trackTimeMillis")
            if (song.durationMs > 0 && ms > 0 && Math.abs(ms - song.durationMs) < 5000) score += 1
            if (score > bestScore) { bestScore = score; best = o }
        }
        return best
    }

    private fun titleLike(a: String, b: String) =
        a.isNotEmpty() && b.isNotEmpty() && (a.contains(b) || b.contains(a))

    private fun norm(s: String) = s.lowercase().replace(Regex("[^\\p{L}\\p{N}]"), "")

    private fun lrcLib(title: String, artist: String, album: String, durationMs: Long): String {
        if (title.isBlank()) return ""
        val u = StringBuilder("https://lrclib.net/api/search?track_name=").append(enc(title))
        if (artist.isNotBlank()) u.append("&artist_name=").append(enc(artist))
        if (album.isNotBlank()) u.append("&album_name=").append(enc(album))
        val arr = jsonArr(u.toString()) ?: return ""
        val wantTitle = norm(title)
        val secs = durationMs / 1000
        var synced = ""
        var plain = ""
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            if (!titleLike(norm(o.optString("trackName")), wantTitle)) continue
            val d = o.optLong("duration")
            if (secs > 0 && d > 0 && Math.abs(d - secs) > 5) continue
            if (synced.isBlank()) synced = o.optString("syncedLyrics")
            if (plain.isBlank()) plain = o.optString("plainLyrics")
            if (synced.isNotBlank() && plain.isNotBlank()) break
        }
        return synced.ifBlank { plain }
    }

    private fun neteaseSearch(query: String, title: String, artist: String, durationMs: Long): JSONObject? {
        val j = json("https://music.163.com/api/search/get/web?type=1&offset=0&limit=10&s=" + enc(query))
        val arr = j?.optJSONObject("result")?.optJSONArray("songs") ?: return null
        val wantTitle = norm(title)
        val wantArtist = norm(artist)
        var best: JSONObject? = null
        var bestRank = -1
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            if (!titleLike(norm(o.optString("name")), wantTitle)) continue
            var rank = 0
            val arts = o.optJSONArray("artists")
            if (wantArtist.isNotEmpty() && arts != null) {
                for (k in 0 until arts.length()) {
                    if (norm(arts.optJSONObject(k)?.optString("name").orEmpty()) == wantArtist) rank += 2
                }
            }
            val d = o.optLong("duration")
            if (durationMs > 0 && d > 0 && Math.abs(d - durationMs) < 5000) rank += 1
            if (rank > bestRank) { bestRank = rank; best = o }
        }
        return best
    }

    private fun neteaseLyrics(id: Long): String {
        if (id <= 0) return ""
        val j = json("https://music.163.com/api/song/lyric?id=$id&lv=1&kv=1&tv=-1") ?: return ""
        return j.optJSONObject("lrc")?.optString("lyric").orEmpty()
    }

    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8")

    private fun open(url: String): HttpURLConnection? = try {
        (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8000
            readTimeout = 10000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 13) TuneKuo/1.0")
            setRequestProperty("Accept", "application/json,text/plain,*/*")
            if (url.contains("163.com")) setRequestProperty("Referer", "https://music.163.com/")
        }
    } catch (_: Exception) {
        null
    }

    private fun text(url: String): String? {
        val c = open(url) ?: return null
        return try {
            if (c.responseCode !in 200..299) null
            else c.inputStream.bufferedReader().use { it.readText() }
        } catch (_: Exception) {
            null
        } finally {
            c.disconnect()
        }
    }

    private fun json(url: String): JSONObject? = try {
        text(url)?.let { JSONObject(it) }
    } catch (_: Exception) {
        null
    }

    private fun jsonArr(url: String): JSONArray? = try {
        text(url)?.let { JSONArray(it) }
    } catch (_: Exception) {
        null
    }

    private fun downloadCover(context: Context, song: Song, url: String): File? {
        val c = open(url) ?: return null
        val f = cachedCover(context, song)
        return try {
            if (c.responseCode !in 200..299) {
                null
            } else {
                c.inputStream.use { input -> f.outputStream().use { input.copyTo(it) } }
                if (BitmapFactory.decodeFile(f.absolutePath) == null) { f.delete(); null } else f
            }
        } catch (_: Exception) {
            f.delete()
            null
        } finally {
            c.disconnect()
        }
    }
}
