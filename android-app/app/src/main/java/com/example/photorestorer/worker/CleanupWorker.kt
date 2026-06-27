package com.example.photorestorer.worker

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.example.photorestorer.repository.HistoryRepository
import com.example.photorestorer.repository.RestorationRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

/**
 * Optional final step: when immediate deletion is enabled, ask the server to
 * delete the cloud copy. The Gallery result is always retained.
 */
@HiltWorker
class CleanupWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val repository: RestorationRepository,
    private val history: HistoryRepository,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val jobId = inputData.getString(WorkKeys.JOB_ID) ?: return Result.success()
        val deleteAfterDownload = inputData.getBoolean(WorkKeys.DELETE_AFTER_DOWNLOAD, false)
        if (!deleteAfterDownload) return Result.success()

        return try {
            repository.deleteRemoteJob(jobId)
            history.markCloudDeleted(jobId)
            Result.success()
        } catch (e: Exception) {
            // Cleanup is best-effort; scheduled server retention will catch the rest.
            Result.success()
        }
    }
}
