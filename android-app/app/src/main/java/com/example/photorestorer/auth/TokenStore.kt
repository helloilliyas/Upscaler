package com.example.photorestorer.auth

import javax.inject.Inject
import javax.inject.Singleton

/**
 * In-memory holder for the current Google ID token.
 *
 * The token is short-lived and is never persisted to disk. The OkHttp
 * interceptor reads it synchronously; [GoogleAuthManager] refreshes it (which
 * requires an Activity) and writes it here.
 */
@Singleton
class TokenStore @Inject constructor() {
    @Volatile
    private var token: String? = null

    fun current(): String? = token

    fun update(value: String?) {
        token = value
    }

    fun clear() {
        token = null
    }
}
