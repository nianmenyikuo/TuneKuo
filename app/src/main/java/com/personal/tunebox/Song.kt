package com.personal.tunebox

/** 一首歌曲的元数据。 */
data class Song(
    val path: String,
    val title: String,
    val artist: String,
    val album: String,
    val durationMs: Long,
    val sizeBytes: Long
)
