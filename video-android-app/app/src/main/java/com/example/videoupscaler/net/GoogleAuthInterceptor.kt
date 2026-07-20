package com.example.videoupscaler.net

import com.example.videoupscaler.auth.TokenStore
import okhttp3.Interceptor
import okhttp3.Response

/**
 * Attaches `Authorization: Bearer <google-id-token>` to every request when a
 * token is available. The token is acquired at sign-in (Credential Manager
 * needs an Activity), so this interceptor only reads the cached value; on a 401
 * the UI re-acquires a credential and retries.
 */
class GoogleAuthInterceptor(private val tokenStore: TokenStore) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokenStore.currentToken()
        val request = if (token.isNullOrBlank()) {
            chain.request()
        } else {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        }
        return chain.proceed(request)
    }
}
