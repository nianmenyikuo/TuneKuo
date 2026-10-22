package com.personal.tunebox

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View

class WaveformView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyle: Int = 0
) : View(context, attrs, defStyle) {

    private val density = resources.displayMetrics.density
    private val step = 3f * density
    private val barWidth = 2f * density
    private val posWidth = 2f * density

    private val barPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        strokeWidth = barWidth
        strokeCap = Paint.Cap.ROUND
    }
    private val posPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#00A8FF")
        strokeWidth = posWidth
    }
    private val playedColor = Color.parseColor("#FFFFFF")
    private val restColor = Color.parseColor("#B0B0B0")

    private var amps = FloatArray(0)
    private var progress = 0f
    private var dragging = false

    var onSeek: ((Float) -> Unit)? = null

    fun setAmplitudes(data: FloatArray) {
        amps = data
        invalidate()
    }

    fun setProgress(ratio: Float) {
        val r = if (ratio < 0f) 0f else if (ratio > 1f) 1f else ratio
        if (r == progress) return
        progress = r
        if (!dragging) invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0f || h <= 0f) return
        val count = (w / step).toInt().coerceAtLeast(1)
        val cy = h / 2f
        val cut = (progress * count).toInt()
        for (i in 0 until count) {
            val x = i * step + step / 2f
            val raw = if (amps.isEmpty()) 0.08f else amps[i * amps.size / count]
            val amp = if (raw < 0.06f) 0.06f else if (raw > 1f) 1f else raw
            val dy = cy * amp * 0.92f
            barPaint.color = if (i < cut) playedColor else restColor
            canvas.drawLine(x, cy - dy, x, cy + dy, barPaint)
        }
        val px = progress * w
        canvas.drawLine(px, 0f, px, h, posPaint)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
                dragging = true
                progress = (event.x / width.toFloat()).coerceIn(0f, 1f)
                invalidate()
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                dragging = false
                val r = (event.x / width.toFloat()).coerceIn(0f, 1f)
                progress = r
                invalidate()
                onSeek?.invoke(r)
                return true
            }
        }
        return super.onTouchEvent(event)
    }
}
