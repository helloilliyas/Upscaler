package com.example.photorestorer.worker

import android.content.Context
import android.net.Uri
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.WorkerParameters
import com.example.photorestorer.data.model.OutputSize
import com.example.photorestorer.data.model.RestorationMode
import com.example.photorestorer.database.RestorationJobEntity
import com.example.photorestorer.repository.RemoteJobException
import com.example.photorestorer.repository.HistoryRepository
import com.example.photorestorer.repository.RestorationRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

/**
 * Uploads the photo (+ optional mask) and records the remote job id in history.
 * Output: [WorkKeys.JOB_ID] for the rest of the chain.
 */
@HiltWorker
class SubmitJobWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val repository: RestorationRepository,
    private val history: HistoryRepository,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val photoUri = inputData.getString(WorkKeys.PHOTO_URI)?.let(Uri::parse)
            ?: return Result.failure()
        val maskUri = inputData.getString(WorkKeys.MASK_URI)?.let(Uri::parse)
        val mode = RestorationMode.fromWire(inputData.getString(WorkKeys.MODE) ?: "natural")
        val output = OutputSize.fromWire(inputData.getString(WorkKeys.OUTPUT) ?: "2x")
        val strength = inputData.getFloat(WorkKeys.STRENGTH, 1f)
        val preserve = inputData.getBoolean(WorkKeys.PRESERVE_METADATA, false)
        val idempotencyKey = inputData.getString(WorkKeys.IDEMPOTENCY_KEY)
            ?: return Result.failure()

        return try {
            val result = repository.submitJob(
                photoUri = photoUri,
                repairMaskUri = maskUri,
                mode = mode,
                output = output,
                strength = strength,
                preserveMetadata = preserve,
                idempotencyKey = idempotencyKey,
            )
            history.upsert(
                RestorationJobEntity(
                    remoteJobId = result.jobId,
                    originalUri = photoUri.toString(),
                    mode = mode.wire,
                    output = output.wire,
                    status = "queued",
                    stage = "queued",
                    progress = 0,
                    createdAt = System.currentTimeMillis(),
                ),
            )
            Result.success(Data.Builder().putString(WorkKeys.JOB_ID, result.jobId).build())
        } catch (e: RemoteJobException) {
            if (e.retryable && runAttemptCount < MAX_ATTEMPTS) {
                Result.retry()
            } else {
                recordFailure(photoUri, mode, output, idempotencyKey, e.message, e.code)
                Result.failure(errorData(e.message, e.code))
            }
        } catch (e: Exception) {
            if (runAttemptCount < MAX_ATTEMPTS) {
                Result.retry()
            } else {
                recordFailure(photoUri, mode, output, idempotencyKey, e.message, null)
                Result.failure(errorData(e.message, null))
            }
        }
    }

    /** A rejected submit must be visible in History, not silently dropped. */
    private suspend fun recordFailure(
        photoUri: Uri,
        mode: RestorationMode,
        output: OutputSize,
        idempotencyKey: String,
        message: String?,
        code: String?,
    ) {
        history.upsert(
            RestorationJobEntity(
                remoteJobId = "failed_$idempotencyKey",
                originalUri = photoUri.toString(),
                mode = mode.wire,
                output = output.wire,
                status = "failed",
                stage = "failed",
                progress = 0,
                createdAt = System.currentTimeMillis(),
                errorCode = code,
                errorMessage = message ?: "Upload failed",
            ),
        )
    }

    private fun errorData(message: String?, code: String?): Data =
        Data.Builder()
            .putString("error_message", message ?: "Upload failed")
            .putString("error_code", code)
            .build()

    private companion object {
        const val MAX_ATTEMPTS = 4
    }
}
