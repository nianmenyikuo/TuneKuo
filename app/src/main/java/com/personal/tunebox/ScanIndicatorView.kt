package com.personal.tunebox

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View
import android.view.animation.LinearInterpolator
import androidx.core.content.ContextCompat
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

class ScanIndicatorView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    private val ringPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        color = ContextCompat.getColor(context, R.color.tk_primary)
        strokeWidth = 3f * resources.displayMetrics.density
    }

    private val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.tk_primary)
    }

    private val bounds = RectF()
    private var phase = 0f
    private var animator: ValueAnimator? = null

    fun start() {
        if (animator != null) return
        animator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 1500L
            repeatCount = ValueAnimator.INFINITE
            interpolator = LinearInterpolator()
            addUpdateListener {
                phase = it.animatedValue as Float
                invalidate()
            }
            start()
        }
    }

    fun stop() {
        animator?.cancel()
        animator = null
        phase = 0f
        invalidate()
    }

    override fun onDetachedFromWindow() {
        stop()
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        val d = resources.displayMetrics.density
        val cx = width / 2f
        val cy = height / 2f
        val radius = min(width, height) / 2f - 3f * d
        if (radius <= 0f) return
        bounds.set(cx - radius, cy - radius, cx + radius, cy + radius)
        canvas.save()
        canvas.rotate(phase * 360f, cx, cy)
        canvas.drawArc(bounds, 0f, 245f, false, ringPaint)
        canvas.restore()
        val orbit = radius * 0.4f
        for (i in 0 until 3) {
            val angle = (phase * 360f + i * 120f) * Math.PI.toFloat() / 180f
            val pulse = 0.5f + 0.5f * sin(phase * 2f * Math.PI.toFloat() + i * 2.1f)
            dotPaint.alpha = (90 + 165 * pulse).toInt()
            canvas.drawCircle(
                cx + cos(angle) * orbit,
                cy + sin(angle) * orbit,
                (2.6f + 1.4f * pulse) * d,
                dotPaint
            )
        }
    }
}
