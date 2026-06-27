package com.example.photorestorer

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

/**
 * Hilt application. Provides the WorkManager configuration so workers can be
 * constructed by [HiltWorkerFactory] (on-demand initialization is enabled via
 * the manifest provider removal).
 */
@HiltAndroidApp
class PhotoRestorerApp : Application(), Configuration.Provider {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()
}
