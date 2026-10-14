package com.personal.tunebox

import android.content.Context
import android.content.res.Configuration
import java.util.Locale

/**
 * 应用内语言（汉语 / English / 日本語）。
 * 选择保存在 SharedPreferences("cfg") 的 lang 键里；没选过就跟随系统（不支持的语言回落中文）。
 */
object LocaleHelper {

    private const val PREF = "cfg"
    private const val KEY_LANG = "lang"

    /** 语言变更后需要自动重新打开设置页的标记 */
    const val KEY_OPEN_SETTINGS = "open_settings"

    val SUPPORTED = listOf("zh", "en", "ja")

    fun pref(context: Context) = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)

    /** 用户显式选择过的语言，空串表示没选过。 */
    fun saved(context: Context): String = pref(context).getString(KEY_LANG, "") ?: ""

    /** 当前生效的语言 tag。 */
    fun current(context: Context): String {
        val s = saved(context)
        if (SUPPORTED.contains(s)) return s
        val sys = Locale.getDefault().language
        return if (SUPPORTED.contains(sys)) sys else "zh"
    }

    fun set(context: Context, tag: String) {
        pref(context).edit().putString(KEY_LANG, tag).apply()
    }

    /** 用选定语言包一层 Context，在 Activity.attachBaseContext 里调用。 */
    fun wrap(base: Context): Context {
        val locale = Locale.forLanguageTag(current(base))
        Locale.setDefault(locale)
        val config = Configuration(base.resources.configuration)
        config.setLocale(locale)
        config.setLayoutDirection(locale)
        return base.createConfigurationContext(config)
    }
}
