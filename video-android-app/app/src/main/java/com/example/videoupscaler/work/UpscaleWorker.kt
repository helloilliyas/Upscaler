package com.example.videoupscaler.work

import android.content.Context
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.example.videoupscaler.R
import com.example.videoupscaler.ServiceLocator
import com.example.videoupscaler.VideoUpscalerApp
import com.example.videoupscaler.net.ErrorEnvelopeDto
import com.example.videoupscaler.net.UriRequestBody
import com.example.videoupscaler.util.VideoSaver
import java.io.IOException
import kotlinx.coroutines.delay
import kotlinx.serialization.json.Json
import okhttp3.MultipartBody

/**
 * Runs one upscale end to end: submit (streaming upload) -> poll -> download
 * result into the Gallery. Runs as a dataSync foreground job so it survives
 * the app being backgrounded; the server does the heavy lifting, this worker
 * mostly waits and streams.
 */
class UpscaleWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    private val json = Json { ignoreUnknownKeys = true }

    override suspend fun doWork(): Result {
        val uriString = inputData.getString(KEY_URI)
            ?: return Result.failure(errorData("No video selected"))
        val output = inputData.getString(KEY_OUTPUT) ?: "2x"
        val idempotencyKey = inputData.getString(KEY_IDEMPOTENCY)
            ?: return Result.failure(errorData("Missing idempotency key"))

        setForeground(foregroundInfo(0))
        val api = ServiceLocator.api

        try {
            // --- submit (upload streams straight from the content Uri) ------
            val resolver = applicationContext.contentResolver
            val uri = Uri.parse(uriString)
            val mime = resolver.getType(uri) ?: "video/mp4"
            val videoPart = MultipartBody.Part.createFormData(
                "video", "video", UriRequestBody(resolver, uri, mime),
            )
            val submit = api.submitJob(
                idempotencyKey = idempotencyKey,
                video = videoPart,
                output = MultipartBody.Part.createFormData("output", output),
                mode = MultipartBody.Part.createFormData("mode", "natural"),
            )
            val submitted = submit.body()
            if (!submit.isSuccessful || submitted == null) {
                return httpFailure(submit.code(), submit.errorBody()?.string())
            }
            val jobId = submitted.jobId

            // --- poll -------------------------------------------------------
            val startedAt = SystemClock.elapsedRealtime()
            var transientErrors = 0
            while (true) {
                if (SystemClock.elapsedRealtime() - startedAt > MAX_JOB_MILLIS) {
                    return Result.failure(errorData("Timed out waiting for the server"))
                }
                val statusResponse = api.getJob(jobId)
                val status = statusResponse.body()
                if (!statusResponse.isSuccessful || status == null) {
                    if (statusResponse.code() in 400..499) {
                        return httpFailure(
                            statusResponse.code(), statusResponse.errorBody()?.string(),
                        )
                    }
                    if (++transientErrors > 10) {
                        return Result.failure(errorData("Server unavailable"))
                    }
                    delay(POLL_INTERVAL_MILLIS)
                    continue
                }
                transientErrors = 0

                when (status.status) {
                    "completed" -> break
                    "failed", "cancelled", "expired" -> return Result.failure(
                        errorData(status.errorMessage ?: "Processing failed"),
                    )
                    else -> {
                        setProgress(
                            workDataOf(
                                KEY_PROGRESS to status.progress,
                                KEY_STAGE to (status.message ?: status.stage),
                                KEY_FRAMES_DONE to (status.framesDone ?: 0),
                                KEY_FRAMES_TOTAL to (status.framesTotal ?: 0),
                            ),
                        )
                        setForeground(foregroundInfo(status.progress))
                    }
                }
                delay(POLL_INTERVAL_MILLIS)
            }

            // --- download straight into the Gallery -------------------------
            setForeground(foregroundInfo(95))
            val download = api.downloadResult(jobId)
            val body = download.body()
            if (!download.isSuccessful || body == null) {
                return httpFailure(download.code(), download.errorBody()?.string())
            }
            val savedUri = body.use {
                VideoSaver.saveMp4(
                    applicationContext,
                    "upscaled_${System.currentTimeMillis()}",
                    it.byteStream(),
                )
            }

            // Free the server-side copy right away (retention would anyway).
            runCatching { api.deleteJob(jobId) }

            val finalStatus = api.getJob(jobId).body()
            return Result.success(
                workDataOf(
                    KEY_SAVED_URI to savedUri.toString(),
                    KEY_WIDTH to (finalStatus?.width ?: 0),
                    KEY_HEIGHT to (finalStatus?.height ?: 0),
                ),
            )
        } catch (e: IOException) {
            // Same idempotency key on retry -> the server reuses the same job.
            return if (runAttemptCount < MAX_ATTEMPTS) {
                Result.retry()
            } else {
                Result.failure(errorData("Network error: ${e.message ?: "connection failed"}"))
            }
        } catch (e: SecurityException) {
            return Result.failure(errorData("Could not read the video — please re-select it"))
        } catch (e: Exception) {
            return Result.failure(errorData(e.message ?: "Unexpected error"))
        }
    }

    override suspend fun getForegroundInfo(): ForegroundInfo = foregroundInfo(0)

    private fun foregroundInfo(progress: Int): ForegroundInfo {
        val notification = NotificationCompat.Builder(
            applicationContext, VideoUpscalerApp.CHANNEL_ID,
        )
            .setContentTitle(applicationContext.getString(R.string.notification_title))
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setProgress(100, progress, progress == 0)
            .build()
        return ForegroundInfo(
            NOTIFICATION_ID,
            notification,
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
        )
    }

    private fun httpFailure(code: Int, errorBody: String?): Result {
        val message = when (code) {
            401 -> "Session expired — open the app and sign in again"
            403 -> "This Google account is not approved"
            else -> parseErrorMessage(errorBody) ?: "Server error ($code)"
        }
        return Result.failure(errorData(message))
    }

    private fun parseErrorMessage(body: String?): String? =
        try {
            body?.let { json.decodeFromString<ErrorEnvelopeDto>(it).error.message }
        } catch (_: Exception) {
            null
        }

    private fun errorData(message: String): Data = workDataOf(KEY_ERROR to message)

    companion object {
        const val UNIQUE_NAME = "video-upscale"

        const val KEY_URI = "uri"
        const val KEY_OUTPUT = "output"
        const val KEY_IDEMPOTENCY = "idempotency"

        const val KEY_PROGRESS = "progress"
        const val KEY_STAGE = "stage"
        const val KEY_FRAMES_DONE = "frames_done"
        const val KEY_FRAMES_TOTAL = "frames_total"

        const val KEY_ERROR = "error"
        const val KEY_SAVED_URI = "saved_uri"
        const val KEY_WIDTH = "width"
        const val KEY_HEIGHT = "height"

        private const val NOTIFICATION_ID = 42
        private const val POLL_INTERVAL_MILLIS = 3_000L
        private const val MAX_JOB_MILLIS = 45 * 60_000L
        private const val MAX_ATTEMPTS = 3
    }
}
