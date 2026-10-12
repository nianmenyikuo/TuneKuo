package com.personal.tunebox

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import kotlin.random.Random

/** 播放模式。 */
enum class PlayMode { SEQUENTIAL, REPEAT_LIST, REPEAT_ONE, SHUFFLE }

/**
 * libVLC 播放引擎封装。
 * - 全格式：libVLC 自带解码器，不依赖系统 MediaCodec，DSD(DSF/DFF)/APE/杜比 TrueHD 等都能放。
 * - 音频输出走 audiotrack，gapless 由 VLC 内部处理。
 * - 播放模式：顺序 / 列表循环 / 单曲循环 / 随机。
 */
class PlayerEngine(private val context: Context) {

    val libVlc: LibVLC = LibVLC(
        context,
        arrayListOf(
            "--no-video",
            "--audio-time-stretch",
            "--avcodec-hw=none",
            "--audio-resampler=soxr",
            "-A", "audiotrack"
        )
    )
    val player: MediaPlayer = MediaPlayer(libVlc)

    /** 当前曲目（供界面查询时长/进度）。 */
    var current: Song? = null
        private set

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    private val queue = ArrayList<Song>()
    private var index = -1

    /** 当前播放模式（界面可切换）。 */
    var mode: PlayMode = PlayMode.REPEAT_LIST

    /** 随机模式下的洗牌顺序（queue 下标的排列）。 */
    private var shuffleOrder: MutableList<Int> = mutableListOf()
    private var shufflePos = -1

    /** 状态变化回调（界面/MediaSession 刷新用）。 */
    var onStateChanged: (() -> Unit)? = null

    init {
        player.setEventListener { event ->
            when (event.type) {
                MediaPlayer.Event.EndReached -> autoNext()
                MediaPlayer.Event.EncounteredError -> autoNext()
                MediaPlayer.Event.Playing, MediaPlayer.Event.Paused,
                MediaPlayer.Event.Stopped, MediaPlayer.Event.MediaChanged,
                MediaPlayer.Event.LengthChanged -> onStateChanged?.invoke()
                else -> {}
            }
        }
    }

    val isPlaying: Boolean get() = player.isPlaying

    fun setQueue(songs: List<Song>, startIndex: Int) {
        queue.clear()
        queue.addAll(songs)
        index = startIndex
        rebuildShuffle()
        if (mode == PlayMode.SHUFFLE) {
            shufflePos = shuffleOrder.indexOf(startIndex)
        }
        playCurrent()
    }

    private fun rebuildShuffle() {
        shuffleOrder = (queue.indices).shuffled(Random(System.currentTimeMillis())).toMutableList()
        shufflePos = -1
    }

    fun cycleMode(): PlayMode {
        mode = when (mode) {
            PlayMode.SEQUENTIAL -> PlayMode.REPEAT_LIST
            PlayMode.REPEAT_LIST -> PlayMode.REPEAT_ONE
            PlayMode.REPEAT_ONE -> PlayMode.SHUFFLE
            PlayMode.SHUFFLE -> PlayMode.SEQUENTIAL
        }
        if (mode == PlayMode.SHUFFLE) {
            rebuildShuffle()
            current?.let { cur ->
                val qi = queue.indexOfFirst { it.path == cur.path }
                if (qi >= 0) { shufflePos = shuffleOrder.indexOf(qi) }
            }
        }
        onStateChanged?.invoke()
        return mode
    }

    fun playCurrent() {
        if (index !in queue.indices) return
        val song = queue[index]
        current = song
        val media = Media(libVlc, Uri.parse("file://" + song.path))
        media.addOption(":no-video")
        player.media = media
        media.release()
        player.play()
        onStateChanged?.invoke()
    }

    fun playPause() {
        if (player.media == null) {
            playCurrent()
        } else if (player.isPlaying) {
            player.pause()
        } else {
            player.play()
        }
        onStateChanged?.invoke()
    }

    /** 用户手动点下一曲：任何模式都前进。 */
    fun next() {
        if (queue.isEmpty()) return
        when (mode) {
            PlayMode.SHUFFLE -> {
                if (shuffleOrder.isEmpty()) rebuildShuffle()
                shufflePos = if (shufflePos + 1 >= shuffleOrder.size) 0 else shufflePos + 1
                index = shuffleOrder[shufflePos]
            }
            else -> index = if (index + 1 >= queue.size) 0 else index + 1
        }
        playCurrent()
    }

    fun prev() {
        if (queue.isEmpty()) return
        when (mode) {
            PlayMode.SHUFFLE -> {
                if (shuffleOrder.isEmpty()) rebuildShuffle()
                shufflePos = if (shufflePos - 1 < 0) shuffleOrder.size - 1 else shufflePos - 1
                index = shuffleOrder[shufflePos]
            }
            else -> index = if (index - 1 < 0) queue.size - 1 else index - 1
        }
        playCurrent()
    }

    /** 播放自然结束时的推进逻辑（区别于手动切歌）。 */
    private fun autoNext() {
        if (queue.isEmpty()) return
        when (mode) {
            PlayMode.REPEAT_ONE -> { player.setTime(0); player.play() }
            PlayMode.SHUFFLE -> {
                shufflePos++
                if (shufflePos >= shuffleOrder.size) {
                    rebuildShuffle()
                    shufflePos = 0
                }
                index = shuffleOrder[shufflePos]
                playCurrent()
            }
            PlayMode.REPEAT_LIST -> {
                index = if (index + 1 >= queue.size) 0 else index + 1
                playCurrent()
            }
            PlayMode.SEQUENTIAL -> {
                if (index + 1 < queue.size) { index++; playCurrent() }
                // 列表末尾：停止，保持最后一曲
            }
        }
    }

    fun seekTo(ms: Long) = player.setTime(ms)

    val position: Long get() = player.time
    val duration: Long get() = player.length

    fun release() {
        player.release()
        libVlc.release()
        scope.cancel()
    }
}
