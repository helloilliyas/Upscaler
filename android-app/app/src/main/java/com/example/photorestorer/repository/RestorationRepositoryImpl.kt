package com.example.photorestorer.repository

import android.content.Context
import android.net.Uri
import com.example.photorestorer.data.model.Fidelity
import com.example.photorestorer.data.model.JobStatus
import com.example.photorestorer.data.model.OutputSize
import com.example.photorestorer.data.model.RestorationMode
import com.example.photorestorer.network.ErrorEnvelopeDto
import com.example.photorestorer.network.JobStatusDto
import com.example.photorestorer.network.RestorationApi
import com.example.photorestorer.network.UriRequestBody
import com.example.photorestorer.util.MediaStoreSaver
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import okhttp3.MultipartBody
import retrofit2.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RestorationRepositoryImpl @Inject constructor(
    @ApplicationContext private val context: Context,
    private val api: RestorationApi,
    private val mediaStoreSaver: MediaStoreSaver,
    private val json: Json,
) : RestorationRepository {

    override suspend fun submitJob(
        photoUri: Uri,
        repairMaskUri: Uri?,
        mode: RestorationMode,
        output: OutputSize,
        strength: Float,
        preserveMetadata: Boolean,
        idempotencyKey: String,
    ): SubmitJobResult {
        val resolver = context.contentResolver
        val photoType = resolver.getType(photoUri) ?: "image/jpeg"
        val photoPart = MultipartBody.Part.createFormData(
            "photo",
            "photo",
            UriRequestBody(resolver, photoUri, photoType),
        )
        val maskPart = repairMaskUri?.let {
            MultipartBody.Part.createFormData(
                "repair_mask",
                "mask.png",
                UriRequestBody(resolver, it, "image/png"),
            )
        }

        val response = api.submitJob(
            idempotencyKey = idempotencyKey,
            photo = photoPart,
            mode = MultipartBody.Part.createFormData("mode", mode.wire),
            output = MultipartBody.Part.createFormData("output", output.wire),
            strength = MultipartBody.Part.createFormData("strength", strength.toString()),
            preserveMetadata = MultipartBody.Part.createFormData(
                "preserve_metadata",
                preserveMetadata.toString(),
            ),
            repairMask = maskPart,
        )
        val body = response.bodyOrThrow()
        return SubmitJobResult(body.jobId)
    }

    override suspend fun getJob(jobId: String): RemoteJobStatus {
        val dto = api.getJob(jobId).bodyOrThrow()
        return dto.toStatus()
    }

    override suspend fun downloadResult(jobId: String): Uri {
        val response = api.downloadResult(jobId)
        if (!response.isSuccessful) throw response.toError()
        val responseBody = response.body() ?: throw RemoteJobException(
            "RESULT_EXPIRED", "Result body was empty",
        )
        return responseBody.use { rb ->
            mediaStoreSaver.saveJpeg("restored_$jobId", rb.source())
        }
    }

    override suspend fun deleteRemoteJob(jobId: String) {
        val response = api.deleteJob(jobId)
        // 404 means it is already gone; treat as success.
        if (!response.isSuccessful && response.code() != 404) {
            throw response.toError()
        }
    }

    // --- helpers ---------------------------------------------------------

    private fun <T> Response<T>.bodyOrThrow(): T {
        if (!isSuccessful) throw toError()
        return body() ?: throw RemoteJobException(
            "INTERNAL_ERROR", "Empty response body", code(),
        )
    }

    private fun Response<*>.toError(): RemoteJobException {
        val raw = errorBody()?.string()
        val parsed = raw?.let {
            runCatching { json.decodeFromString<ErrorEnvelopeDto>(it) }.getOrNull()
        }
        return RemoteJobException(
            code = parsed?.error?.code,
            message = parsed?.error?.message ?: "Request failed (${code()})",
            httpStatus = code(),
        )
    }

    private fun JobStatusDto.toStatus(): RemoteJobStatus = RemoteJobStatus(
        jobId = jobId,
        status = JobStatus.fromWire(status),
        stage = stage,
        progress = progress,
        message = message,
        resultAvailable = resultAvailable,
        width = width,
        height = height,
        fidelity = Fidelity.fromWire(fidelity),
        errorCode = errorCode,
        errorMessage = errorMessage,
    )
}
