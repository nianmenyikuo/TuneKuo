package com.personal.tunebox

import android.graphics.Typeface
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.card.MaterialCardView

class SongAdapter(
    private val songs: List<Song>,
    private val onClick: (Song) -> Unit,
    private val onLongClick: (Song, View) -> Unit
) : RecyclerView.Adapter<SongAdapter.VH>() {

    var playingPath: String? = null
        set(v) { field = v; notifyDataSetChanged() }

    var selecting: Boolean = false
        private set

    val selected = LinkedHashSet<String>()

    fun startSelection(path: String) {
        selecting = true
        selected.clear()
        selected.add(path)
        notifyDataSetChanged()
    }

    fun toggle(path: String) {
        if (!selected.remove(path)) selected.add(path)
        if (selected.isEmpty()) selecting = false
        notifyDataSetChanged()
    }

    fun selectAll(paths: List<String>) {
        if (paths.isEmpty()) return
        selecting = true
        selected.clear()
        selected.addAll(paths)
        notifyDataSetChanged()
    }

    fun clearSelection() {
        selecting = false
        selected.clear()
        notifyDataSetChanged()
    }

    fun selectedSongs(): List<Song> = songs.filter { selected.contains(it.path) }

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val card: MaterialCardView = v as MaterialCardView
        val ivCheck: ImageView = v.findViewById(R.id.ivCheck)
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
        val picked = selecting && selected.contains(s.path)
        h.tvTitle.text = s.title
        h.tvSub.text = s.artist + " · " + s.album
        h.tvDuration.text = format(s.durationMs)
        h.ivCheck.visibility = if (picked) View.VISIBLE else View.GONE
        when {
            picked -> {
                h.tvIndex.text = (pos + 1).toString()
                h.tvIndex.setTextColor(0xFF6C7A8C.toInt())
                h.tvTitle.setTextColor(0xFF60CDFF.toInt())
                h.tvTitle.typeface = if (playing) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
                h.card.setCardBackgroundColor(0xFF12384C.toInt())
                h.card.strokeColor = 0xFF60CDFF.toInt()
            }
            playing -> {
                h.tvIndex.text = "♪"
                h.tvIndex.setTextColor(0xFF60CDFF.toInt())
                h.tvTitle.setTextColor(0xFF60CDFF.toInt())
                h.tvTitle.typeface = Typeface.DEFAULT_BOLD
                h.card.setCardBackgroundColor(0xFF12384C.toInt())
                h.card.strokeColor = 0xFF60CDFF.toInt()
            }
            else -> {
                h.tvIndex.text = (pos + 1).toString()
                h.tvIndex.setTextColor(0xFF6C7A8C.toInt())
                h.tvTitle.setTextColor(0xFFFFFFFF.toInt())
                h.tvTitle.typeface = Typeface.DEFAULT
                h.card.setCardBackgroundColor(0xFF1E1E2B.toInt())
                h.card.strokeColor = 0x00000000
            }
        }
        h.itemView.setOnClickListener { onClick(s) }
        h.itemView.setOnLongClickListener { onLongClick(s, h.itemView); true }
    }

    private fun format(ms: Long): String {
        val s = ms / 1000
        return "%d:%02d".format(s / 60, s % 60)
    }
}
