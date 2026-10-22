package com.personal.tunebox

import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.nio.ByteOrder
import kotlin.math.abs

object WaveformPeaks {

    private const val BARS = 320
    private const val TIMEOUT_MS = 25000L

    private val cache = HashMap<String, FloatArray>()

    fun cached(path: String): FloatArray? = cache[path]

    suspend fun load(path: String): FloatArray = withContext(Dispatchers.IO) {
        cache[path]?.let { return@withContext it }
        val data = try {
            val peaks = decode(path)
            if (peaks.size == BARS) peaks else synthetic(path)
        } catch (e: Exception) {
            synthetic(path)
        }
        cache[path] = data
        data
    }

    private fun decode(path: String): FloatArray {
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(path)
            var format: MediaFormat? = null
            var track = -1
            for (i in 0 until extractor.trackCount) {
                val f = extractor.getTrackFormat(i)
                val mime = f.getString(MediaFormat.KEY_MIME) ?: continue
                if (mime.startsWith("audio/")) {
                    format = f
                    track = i
                    break
                }
            }
            val fmt = format ?: return FloatArray(0)
            extractor.selectTrack(track)
            val mime = fmt.getString(MediaFormat.KEY_MIME) ?: return FloatArray(0)
            val codec = MediaCodec.createDecoderByType(mime)
            try {
                codec.configure(fmt, null, null, 0)
                codec.start()
                val peaks = ArrayList<Float>(8192)
                val info = MediaCodec.BufferInfo()
                val deadline = System.currentTimeMillis() + TIMEOUT_MS
                var inputDone = false
                var outputDone = false
                while (!outputDone && System.currentTimeMillis() < deadline) {
                    if (!inputDone) {
                        val inIndex = codec.dequeueInputBuffer(10000)
                        if (inIndex >= 0) {
                            val buf = codec.getInputBuffer(inIndex)
                            val size = if (buf == null) -1 else extractor.readSampleData(buf, 0)
                            if (size < 0) {
                                codec.queueInputBuffer(inIndex, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                                inputDone = true
                            } else {
                                codec.queueInputBuffer(inIndex, 0, size, extractor.sampleTime, 0)
                                extractor.advance()
                            }
                        }
                    }
                    val outIndex = codec.dequeueOutputBuffer(info, 10000)
                    if (outIndex >= 0) {
                        if (info.size > 0) {
                            val buf = codec.getOutputBuffer(outIndex)
                            if (buf != null) {
                                buf.order(ByteOrder.LITTLE_ENDIAN)
                                buf.position(info.offset)
                                buf.limit(info.offset + info.size)
                                var peak = 0
                                while (buf.remaining() >= 2) {
                                    val v = abs(buf.short.toInt())
                                    if (v > peak) peak = v
                                }
                                peaks.add(peak / 32768f)
                            }
                        }
                        codec.releaseOutputBuffer(outIndex, false)
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outputDone = true
                    }
                    if (inputDone && outIndex == MediaCodec.INFO_TRY_AGAIN_LATER) {
                        val at = extractor.sampleTime
                        if (at < 0) outputDone = true
                    }
                }
                return bucket(peaks)
            } finally {
                try {
                    codec.stop()
                } catch (e: Exception) {
                }
                codec.release()
            }
        } finally {
            extractor.release()
        }
    }

    private fun bucket(peaks: ArrayList<Float>): FloatArray {
        if (peaks.isEmpty()) return FloatArray(0)
        val out = FloatArray(BARS)
        var max = 0.0001f
        for (i in 0 until BARS) {
            val from = i * peaks.size / BARS
            val to = ((i + 1) * peaks.size / BARS).coerceAtLeast(from + 1)
            var v = 0f
            var j = from
            while (j < to && j < peaks.size) {
                if (peaks[j] > v) v = peaks[j]
                j++
            }
            out[i] = v
            if (v > max) max = v
        }
        for (i in out.indices) {
            val v = out[i] / max
            out[i] = if (v < 0.03f) 0.03f else if (v > 1f) 1f else v
        }
        return out
    }

    private fun synthetic(path: String): FloatArray {
        val out = FloatArray(BARS)
        var seed = path.hashCode()
        for (i in out.indices) {
            seed = seed * 1103515245 + 12345
            val r = ((seed ushr 16) and 0x7fff) / 32767f
            val shape = 0.35f + 0.45f * r
            val pulse = 0.6f + 0.4f * abs(kotlin.math.sin(i * 0.07f))
            val v = shape * pulse
            out[i] = if (v < 0.05f) 0.05f else if (v > 1f) 1f else v
        }
        return out
    }
}
