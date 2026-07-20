package com.example.videoupscaler

import android.content.Context
import com.example.videoupscaler.auth.GoogleAuthManager
import com.example.videoupscaler.auth.TokenStore
import com.example.videoupscaler.net.GoogleAuthInterceptor
import com.example.videoupscaler.net.VideoApi
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit

/**
 * Hand-rolled singletons — this app is deliberately small enough that a DI
 * framework would outweigh the code it wires.
 */
object ServiceLocator {

    lateinit var tokenStore: TokenStore
        private set
    lateinit var authManager: GoogleAuthManager
        private set
    lateinit var api: VideoApi
        private set

    fun init(context: Context) {
        tokenStore = TokenStore(context.applicationContext)
        authManager = GoogleAuthManager(tokenStore)

        val json = Json { ignoreUnknownKeys = true }
        val client = OkHttpClient.Builder()
            .addInterceptor(GoogleAuthInterceptor(tokenStore))
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(2, TimeUnit.MINUTES)
            // Streaming a large clip upstream can legitimately take a while.
            .writeTimeout(15, TimeUnit.MINUTES)
            .build()

        api = Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(VideoApi::class.java)
    }
}
