package com.personal.tunebox

data class Song(
    val path: String,
    val title: String,
    val artist: String,
    val album: String,
    val durationMs: Long,
    val sizeBytes: Long
)
