package com.personal.tunebox

import android.content.Context
import android.content.res.Configuration
import java.util.Locale

object LocaleHelper {

    private const val PREF = "cfg"
    private const val KEY_LANG = "lang"

    const val KEY_OPEN_SETTINGS = "open_settings"

    val SUPPORTED = listOf("zh", "en", "ja")

    fun pref(context: Context) = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)

    fun saved(context: Context): String = pref(context).getString(KEY_LANG, "") ?: ""

    fun current(context: Context): String {
        val s = saved(context)
        if (SUPPORTED.contains(s)) return s
        val sys = Locale.getDefault().language
        return if (SUPPORTED.contains(sys)) sys else "zh"
    }

    fun set(context: Context, tag: String) {
        pref(context).edit().putString(KEY_LANG, tag).apply()
    }

    fun wrap(base: Context): Context {
        val locale = Locale.forLanguageTag(current(base))
        Locale.setDefault(locale)
        val config = Configuration(base.resources.configuration)
        config.setLocale(locale)
        config.setLayoutDirection(locale)
        return base.createConfigurationContext(config)
    }
}
