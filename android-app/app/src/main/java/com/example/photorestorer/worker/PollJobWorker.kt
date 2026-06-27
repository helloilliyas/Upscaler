package com.example.photorestorer.worker

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.WorkerParameters
import com.example.photorestorer.data.model.JobStatus
import com.example.photorestorer.repository.HistoryRepository
import com.example.photorestorer.repository.RestorationRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.delay

/**
 * Polls job status until it reaches a terminal state, updating local history on
 * each tick. Poll interval widens over time (long SUPIR jobs). Succeeds when the
 * job completes so the chain proceeds to download; fails on failure/cancellation.
 */
@HiltWorker
class PollJobWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val repository: RestorationRepository,
    private val history: HistoryRepository,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val jobId = inputData.getString(WorkKeys.JOB_ID) ?: return Result.failure()
        val startedAt = System.currentTimeMillis()

        while (!isStopped) {
            val status = try {
                repository.getJob(jobId)
            } catch (e: Exception) {
                // Transient: back off via retry rather than failing the chain.
                return Result.retry()
            }

            history.get(jobId)?.let { entity ->
                history.update(
                    entity.copy(
                        status = status.status.wire,
                        stage = status.stage,
                        progress = status.progress,
                        fidelity = status.fidelity?.wire ?: entity.fidelity,
                        errorCode = status.errorCode,
                        errorMessage = status.errorMessage,
                    ),
                )
            }

            when (status.status) {
                JobStatus.COMPLETED ->
                    return Result.success(
                        Data.Builder().putString(WorkKeys.JOB_ID, jobId).build(),
                    )
                JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED ->
                    return Result.failure(
                        Data.Builder()
                            .putString("error_message", status.errorMessage ?: "Job ${status.status.wire}")
                            .putString("error_code", status.errorCode)
                            .build(),
                    )
                else -> Unit
            }

            delay(pollIntervalMillis(System.currentTimeMillis() - startedAt))
        }
        return Result.retry()
    }

    private fun pollIntervalMillis(elapsedMillis: Long): Long = when {
        elapsedMillis < 60_000 -> 3_000
        elapsedMillis < 300_000 -> 8_000
        else -> 15_000
    }
}
