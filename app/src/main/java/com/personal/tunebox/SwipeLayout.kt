package com.personal.tunebox

import android.content.Context
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import android.widget.FrameLayout
import kotlin.math.abs

/**
 * 只"观察"水平滑动、不消费触摸事件的容器：
 * - 右滑触发 onSwipeRight，左滑触发 onSwipeLeft；
 * - 子控件（列表滚动、按钮、进度条）照常工作；
 * - 触摸起点落在 [exclude] 上时忽略本次手势（避免拖动进度条被误判成翻页）。
 */
class SwipeLayout @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyle: Int = 0
) : FrameLayout(context, attrs, defStyle) {

    var onSwipeRight: (() -> Unit)? = null
    var onSwipeLeft: (() -> Unit)? = null

    /** 触摸起点在这个 View 上时不响应翻页手势。 */
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
