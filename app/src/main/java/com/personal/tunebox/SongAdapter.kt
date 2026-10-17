package com.personal.tunebox

import android.graphics.Typeface
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView

class SongAdapter(
    private val songs: List<Song>,
    private val onClick: (Song) -> Unit,
    private val onLongClick: (Song, View) -> Unit
) : RecyclerView.Adapter<SongAdapter.VH>() {

    var playingPath: String? = null
        set(v) { field = v; notifyDataSetChanged() }

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val tvIndex: TextView = v.findViewById(R.id.tvIndex)
        val tvTitle: TextView = v.findViewById(R.id.tvTitle)
        val tvSub: TextView = v.findViewById(R.id.tvSub)
        val tvDuration: TextView = v.findViewById(R.id.tvDuration)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_song, parent, false)
        return VH(v)
    }

    override fun getItemCount() = songs.size

    override fun onBindViewHolder(h: VH, pos: Int) {
        val s = songs[pos]
        val playing = s.path == playingPath
        h.tvTitle.text = s.title
        h.tvSub.text = s.artist + " · " + s.album
        h.tvDuration.text = format(s.durationMs)
        if (playing) {
            h.tvIndex.text = "♪"
            h.tvIndex.setTextColor(0xFF7A7AFF.toInt())
            h.tvTitle.setTextColor(0xFF7A7AFF.toInt())
            h.tvTitle.typeface = Typeface.DEFAULT_BOLD
            h.itemView.setBackgroundResource(R.drawable.bg_playing)
        } else {
            h.tvIndex.text = (pos + 1).toString()
            h.tvIndex.setTextColor(0xFF5A5A78.toInt())
            h.tvTitle.setTextColor(0xFFFFFFFF.toInt())
            h.tvTitle.typeface = Typeface.DEFAULT
            h.itemView.setBackgroundResource(R.drawable.bg_item)
        }
        h.itemView.setOnClickListener { onClick(s) }
        h.itemView.setOnLongClickListener { onLongClick(s, h.itemView); true }
    }

    private fun format(ms: Long): String {
        val s = ms / 1000
        return "%d:%02d".format(s / 60, s % 60)
    }
}
