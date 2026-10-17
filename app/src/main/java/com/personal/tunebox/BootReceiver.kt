package com.personal.tunebox

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.view.KeyEvent

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_MEDIA_BUTTON) return
        val e = PlaybackService.engine ?: return
        when (intent.getParcelableExtra<KeyEvent>(Intent.EXTRA_KEY_EVENT)?.action) {
            KeyEvent.ACTION_DOWN -> when (intent.getParcelableExtra<KeyEvent>(Intent.EXTRA_KEY_EVENT)?.keyCode) {
                KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, KeyEvent.KEYCODE_MEDIA_PLAY -> e.playPause()
                KeyEvent.KEYCODE_MEDIA_NEXT -> e.next()
                KeyEvent.KEYCODE_MEDIA_PREVIOUS -> e.prev()
            }
        }
    }
}
