package com.example.photorestorer.worker

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.WorkerParameters
import com.example.photorestorer.repository.HistoryRepository
import com.example.photorestorer.repository.RestorationRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

/** Streams the full-resolution result into the Gallery and records its Uri. */
@HiltWorker
class DownloadResultWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val repository: RestorationRepository,
    private val history: HistoryRepository,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val jobId = inputData.getString(WorkKeys.JOB_ID) ?: return Result.failure()
        return try {
            val savedUri = repository.downloadResult(jobId)
            history.get(jobId)?.let { entity ->
                history.update(
                    entity.copy(
                        resultUri = savedUri.toString(),
                        status = "completed",
                        stage = "ready",
                        progress = 100,
                        completedAt = System.currentTimeMillis(),
                    ),
                )
            }
            Result.success(Data.Builder().putString(WorkKeys.JOB_ID, jobId).build())
        } catch (e: Exception) {
            if (runAttemptCount < MAX_ATTEMPTS) Result.retry()
            else Result.failure(
                Data.Builder().putString("error_message", e.message ?: "Download failed").build(),
            )
        }
    }

    private companion object {
        const val MAX_ATTEMPTS = 4
    }
}
