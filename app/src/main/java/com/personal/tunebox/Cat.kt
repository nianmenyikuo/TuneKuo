package com.personal.tunebox

import android.content.Context

object Cat {
    private const val PREFS = "tunekuo"
    private const val KEY = "cat_mode"

    fun on(c: Context): Boolean = c.getSharedPreferences(PREFS, 0).getBoolean(KEY, false)

    fun set(c: Context, value: Boolean) {
        c.getSharedPreferences(PREFS, 0).edit().putBoolean(KEY, value).apply()
    }

    fun toggle(c: Context): Boolean {
        val v = !on(c)
        set(c, v)
        return v
    }

    fun s(c: Context, id: Int, vararg args: Any?): String {
        val text = if (on(c)) catOf(c, id) else c.getString(id)
        return if (args.isEmpty()) text else String.format(text, *args)
    }

    private fun catOf(c: Context, id: Int): String {
        return try {
            val name = c.resources.getResourceEntryName(id)
            val catId = c.resources.getIdentifier("cat_$name", "string", c.packageName)
            if (catId != 0) c.getString(catId) else c.getString(id)
        } catch (e: Exception) {
            c.getString(id)
        }
    }
}
