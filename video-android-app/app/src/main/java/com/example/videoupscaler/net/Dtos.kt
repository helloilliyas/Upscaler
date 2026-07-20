package com.example.videoupscaler.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class MeDto(
    val email: String,
    val authorized: Boolean,
)

@Serializable
data class SubmitJobResponseDto(
    @SerialName("job_id") val jobId: String,
    val status: String,
    val mode: String,
    val output: String,
    @SerialName("duration_seconds") val durationSeconds: Double,
    @SerialName("frames_total") val framesTotal: Int,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class JobStatusDto(
    @SerialName("job_id") val jobId: String,
    val status: String,
    val stage: String,
    val progress: Int = 0,
    val message: String? = null,
    @SerialName("result_available") val resultAvailable: Boolean = false,
    val width: Int? = null,
    val height: Int? = null,
    @SerialName("duration_seconds") val durationSeconds: Double? = null,
    val fps: Double? = null,
    @SerialName("frames_total") val framesTotal: Int? = null,
    @SerialName("frames_done") val framesDone: Int? = null,
    @SerialName("error_code") val errorCode: String? = null,
    @SerialName("error_message") val errorMessage: String? = null,
)

@Serializable
data class JobSummaryDto(
    @SerialName("job_id") val jobId: String,
    val status: String,
    val mode: String,
    val output: String,
    @SerialName("duration_seconds") val durationSeconds: Double? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class JobListDto(
    val jobs: List<JobSummaryDto> = emptyList(),
)

@Serializable
data class ErrorEnvelopeDto(
    val error: ErrorBodyDto,
)

@Serializable
data class ErrorBodyDto(
    val code: String,
    val message: String,
)
