package com.example.photorestorer.repository

import android.net.Uri
import com.example.photorestorer.data.model.Fidelity
import com.example.photorestorer.data.model.JobStatus
import com.example.photorestorer.data.model.OutputSize
import com.example.photorestorer.data.model.RestorationMode

/** Result of submitting a job. */
data class SubmitJobResult(val jobId: String)

/** Snapshot of a remote job's status. */
data class RemoteJobStatus(
    val jobId: String,
    val status: JobStatus,
    val stage: String,
    val progress: Int,
    val message: String?,
    val resultAvailable: Boolean,
    val width: Int?,
    val height: Int?,
    val fidelity: Fidelity?,
    val errorCode: String?,
    val errorMessage: String?,
)

/** A failure surfaced to the caller with a stable backend error code, if any. */
class RemoteJobException(
    val code: String?,
    message: String,
    val httpStatus: Int? = null,
) : Exception(message) {
    val retryable: Boolean
        get() = when (code) {
            "UNSUPPORTED_FORMAT", "INVALID_IMAGE", "FILE_TOO_LARGE",
            "PIXEL_LIMIT_EXCEEDED", "MASK_SIZE_MISMATCH", "ACCOUNT_NOT_ALLOWED",
            -> false
            else -> true
        }
}

interface RestorationRepository {
    suspend fun submitJob(
        photoUri: Uri,
        repairMaskUri: Uri?,
        mode: RestorationMode,
        output: OutputSize,
        strength: Float,
        preserveMetadata: Boolean,
        idempotencyKey: String,
    ): SubmitJobResult

    suspend fun getJob(jobId: String): RemoteJobStatus

    /** Stream the full-resolution result into the Gallery; returns the saved Uri. */
    suspend fun downloadResult(jobId: String): Uri

    suspend fun deleteRemoteJob(jobId: String)
}
