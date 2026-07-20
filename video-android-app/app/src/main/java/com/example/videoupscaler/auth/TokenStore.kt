package com.example.videoupscaler.auth

import android.content.Context

/**
 * Holder for the current Google ID token and signed-in email.
 *
 * Persisted in app-private SharedPreferences so a WorkManager job that outlives
 * the UI process can still authenticate. ID tokens are short-lived (~1 h); a
 * 401 from the backend surfaces as "sign in again" in the UI.
 */
class TokenStore(context: Context) {

    private val prefs = context.getSharedPreferences("auth", Context.MODE_PRIVATE)

    @Volatile
    private var cachedToken: String? = prefs.getString(KEY_TOKEN, null)

    @Volatile
    private var cachedEmail: String? = prefs.getString(KEY_EMAIL, null)

    fun currentToken(): String? = cachedToken

    fun currentEmail(): String? = cachedEmail

    fun update(token: String, email: String) {
        cachedToken = token
        cachedEmail = email
        prefs.edit().putString(KEY_TOKEN, token).putString(KEY_EMAIL, email).apply()
    }

    fun clear() {
        cachedToken = null
        cachedEmail = null
        prefs.edit().clear().apply()
    }

    private companion object {
        const val KEY_TOKEN = "id_token"
        const val KEY_EMAIL = "email"
    }
}
