package com.example.photorestorer.worker

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.example.photorestorer.data.model.OutputSize
import com.example.photorestorer.data.model.RestorationMode
import dagger.hilt.android.qualifiers.ApplicationContext
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/** Parameters for one photo's restoration chain. */
data class RestorationRequest(
    val photoUri: String,
    val maskUri: String?,
    val mode: RestorationMode,
    val output: OutputSize,
    val preserveMetadata: Boolean,
    val idempotencyKey: String,
    val wifiOnly: Boolean,
    val deleteAfterDownload: Boolean,
)

/**
 * Enqueues the persistent Submit → Poll → Download → Cleanup chain. Keyed by the
 * idempotency key with KEEP policy so a retried enqueue never double-submits.
 */
@Singleton
class RestorationScheduler @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val workManager = WorkManager.getInstance(context)

    fun enqueue(request: RestorationRequest) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(
                if (request.wifiOnly) NetworkType.UNMETERED else NetworkType.CONNECTED,
            )
            .build()

        val inputData = Data.Builder()
            .putString(WorkKeys.PHOTO_URI, request.photoUri)
            .putString(WorkKeys.MASK_URI, request.maskUri)
            .putString(WorkKeys.MODE, request.mode.wire)
            .putString(WorkKeys.OUTPUT, request.output.wire)
            .putBoolean(WorkKeys.PRESERVE_METADATA, request.preserveMetadata)
            .putString(WorkKeys.IDEMPOTENCY_KEY, request.idempotencyKey)
            .putBoolean(WorkKeys.DELETE_AFTER_DOWNLOAD, request.deleteAfterDownload)
            .build()

        val submit = OneTimeWorkRequestBuilder<SubmitJobWorker>()
            .setConstraints(constraints)
            .setInputData(inputData)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
            .addTag(WorkKeys.TAG_RESTORATION)
            .build()

        val poll = OneTimeWorkRequestBuilder<PollJobWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.SECONDS)
            .addTag(WorkKeys.TAG_RESTORATION)
            .build()

        val download = OneTimeWorkRequestBuilder<DownloadResultWorker>()
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 10, TimeUnit.SECONDS)
            .addTag(WorkKeys.TAG_RESTORATION)
            .build()

        val cleanup = OneTimeWorkRequestBuilder<CleanupWorker>()
            .setInputData(
                Data.Builder()
                    .putBoolean(WorkKeys.DELETE_AFTER_DOWNLOAD, request.deleteAfterDownload)
                    .build(),
            )
            .addTag(WorkKeys.TAG_RESTORATION)
            .build()

        workManager.beginUniqueWork(
            WorkKeys.uniqueName(request.idempotencyKey),
            ExistingWorkPolicy.KEEP,
            submit,
        ).then(poll).then(download).then(cleanup).enqueue()
    }
}
