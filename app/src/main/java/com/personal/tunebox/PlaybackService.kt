package com.personal.tunebox

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.support.v4.media.MediaMetadataCompat
import android.support.v4.media.session.MediaSessionCompat
import android.support.v4.media.session.PlaybackStateCompat
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * 后台播放服务：持有 PlayerEngine 单例 + MediaSession。
 * MediaSession 让锁屏/通知栏/蓝牙线控显示歌曲信息、进度条和播放控制。
 */
class PlaybackService : Service() {

    companion object {
        const val CHANNEL = "playback"
        const val NOTIF_ID = 100

        @Volatile var engine: PlayerEngine? = null
            private set
        @Volatile var session: MediaSessionCompat? = null
            private set

        fun start(ctx: Context) {
            val i = Intent(ctx, PlaybackService::class.java)
            if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(i) else ctx.startService(i)
        }

        fun stop(ctx: Context) {
            engine?.playPause()
            ctx.stopService(Intent(ctx, PlaybackService::class.java))
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var myEngine: PlayerEngine
    private lateinit var mySession: MediaSessionCompat
    private var artLoadedFor: String? = null   // 已加载封面/歌词的歌曲路径

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIF_ID, buildNotification("就绪"))

        if (engine == null) {
            myEngine = PlayerEngine(applicationContext)
            engine = myEngine
        } else {
            myEngine = engine!!
        }

        mySession = MediaSessionCompat(this, "TuneBox")
        mySession.setFlags(
            MediaSessionCompat.FLAG_HANDLES_MEDIA_BUTTONS or
            MediaSessionCompat.FLAG_HANDLES_TRANSPORT_CONTROLS
        )
        mySession.setCallback(object : MediaSessionCompat.Callback() {
            override fun onPlay() { myEngine.playPause(); updateSession() }
            override fun onPause() { myEngine.playPause(); updateSession() }
            override fun onSkipToNext() { myEngine.next(); updateSession() }
            override fun onSkipToPrevious() { myEngine.prev(); updateSession() }
            override fun onSeekTo(pos: Long) { myEngine.seekTo(pos); updateSession() }
            override fun onMediaButtonEvent(mediaButtonEvent: Intent): Boolean {
                return super.onMediaButtonEvent(mediaButtonEvent)
            }
        })
        session = mySession

        // 引擎状态变化 → 更新 MediaSession 与通知
        myEngine.onStateChanged = { updateSession() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            "PREV" -> { myEngine.prev(); updateSession() }
            "PLAYPAUSE" -> { myEngine.playPause(); updateSession() }
            "NEXT" -> { myEngine.next(); updateSession() }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        mySession.release()
        session = null
        myEngine.release()
        engine = null
        scope.cancel()
        super.onDestroy()
    }

    /** 把当前曲目信息+播放状态写入 MediaSession（锁屏/通知栏读取这里）。 */
    fun updateSession() {
        val e = myEngine
        val s = e.current ?: return

        // 后台加载封面+歌词（服务侧，保证后台播放时锁屏也有封面）
        if (s.path != artLoadedFor) {
            artLoadedFor = s.path
            scope.launch {
                val r = MediaArt.load(applicationContext, s)
                if (myEngine.current?.path == s.path) {
                    MediaArtHolder.cover = r.cover
                    MediaArtHolder.lyrics = r.lyrics
                    updateSession()   // 封面就绪后刷新一次元数据
                }
            }
        }

        mySession.setMetadata(
            MediaMetadataCompat.Builder()
                .putString(MediaMetadataCompat.METADATA_KEY_TITLE, s.title)
                .putString(MediaMetadataCompat.METADATA_KEY_ARTIST, s.artist)
                .putString(MediaMetadataCompat.METADATA_KEY_ALBUM, s.album)
                .putLong(MediaMetadataCompat.METADATA_KEY_DURATION, e.duration)
                .apply {
                    // 锁屏/通知栏大封面
                    MediaArtHolder.cover?.let {
                        putBitmap(MediaMetadataCompat.METADATA_KEY_ALBUM_ART, it)
                    }
                }
                .build()
        )

        val state = if (e.isPlaying) PlaybackStateCompat.STATE_PLAYING else PlaybackStateCompat.STATE_PAUSED
        mySession.setPlaybackState(
            PlaybackStateCompat.Builder()
                .setActions(
                    PlaybackStateCompat.ACTION_PLAY or
                    PlaybackStateCompat.ACTION_PAUSE or
                    PlaybackStateCompat.ACTION_PLAY_PAUSE or
                    PlaybackStateCompat.ACTION_SKIP_TO_NEXT or
                    PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS or
                    PlaybackStateCompat.ACTION_SEEK_TO
                )
                .setState(state, e.position, 1.0f)
                .build()
        )
        mySession.isActive = true

        // 通知栏媒体样式（锁屏显示同源）
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "播放服务", NotificationManager.IMPORTANCE_LOW)
        )
        val pi = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val notif = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle(s.title)
            .setContentText(s.artist + " · " + s.album)
            .setContentIntent(pi)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .apply { MediaArtHolder.cover?.let { setLargeIcon(it) } }
            .addAction(android.R.drawable.ic_media_previous, "上一首",
                piAction(1, "PREV"))
            .addAction(if (e.isPlaying) android.R.drawable.ic_media_pause else android.R.drawable.ic_media_play,
                "播放暂停", piAction(2, "PLAYPAUSE"))
            .addAction(android.R.drawable.ic_media_next, "下一首",
                piAction(3, "NEXT"))
            .setStyle(androidx.media.app.NotificationCompat.MediaStyle()
                .setMediaSession(mySession.sessionToken)
                .setShowActionsInCompactView(0, 1, 2))
            .build()
        nm.notify(NOTIF_ID, notif)
    }

    private fun piAction(requestCode: Int, action: String): PendingIntent =
        PendingIntent.getService(
            this, requestCode,
            Intent(this, PlaybackService::class.java).setAction(action),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

    private fun buildNotification(text: String): Notification {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "播放服务", NotificationManager.IMPORTANCE_LOW)
        )
        val pi = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle("TuneBox")
            .setContentText(text)
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
    }
}
