package com.personal.tunebox

import android.content.Context
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import android.widget.FrameLayout
import kotlin.math.abs

class SwipeLayout @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyle: Int = 0
) : FrameLayout(context, attrs, defStyle) {

    var onSwipeRight: (() -> Unit)? = null
    var onSwipeLeft: (() -> Unit)? = null

    var exclude: View? = null

    private var downX = 0f
    private var downY = 0f
    private var ignore = false

    override fun dispatchTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downX = ev.x
                downY = ev.y
                ignore = isOnExclude(ev)
            }
            MotionEvent.ACTION_UP -> {
                if (!ignore) {
                    val dx = ev.x - downX
                    val dy = ev.y - downY
                    val min = 64f * resources.displayMetrics.density
                    if (abs(dx) > min && abs(dx) > abs(dy) * 1.3f) {
                        if (dx > 0) onSwipeRight?.invoke() else onSwipeLeft?.invoke()
                    }
                }
                ignore = false
            }
            MotionEvent.ACTION_CANCEL -> ignore = false
        }
        return super.dispatchTouchEvent(ev)
    }

    private fun isOnExclude(ev: MotionEvent): Boolean {
        val v = exclude ?: return false
        if (v.visibility != View.VISIBLE) return false
        val vLoc = IntArray(2)
        val myLoc = IntArray(2)
        v.getLocationInWindow(vLoc)
        getLocationInWindow(myLoc)
        val left = (vLoc[0] - myLoc[0]).toFloat()
        val top = (vLoc[1] - myLoc[1]).toFloat()
        return ev.x >= left && ev.x <= left + v.width && ev.y >= top && ev.y <= top + v.height
    }
}
