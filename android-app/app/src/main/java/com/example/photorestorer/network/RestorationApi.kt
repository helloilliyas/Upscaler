package com.example.photorestorer.network

import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

/**
 * Retrofit interface for the backend `/v1` API. The Google ID token is attached
 * by [GoogleAuthInterceptor]; the idempotency key is passed per-submit.
 */
interface RestorationApi {

    @GET("v1/me")
    suspend fun me(): Response<MeDto>

    @Multipart
    @POST("v1/jobs")
    suspend fun submitJob(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Part photo: MultipartBody.Part,
        @Part mode: MultipartBody.Part,
        @Part output: MultipartBody.Part,
        @Part preserveMetadata: MultipartBody.Part,
        @Part repairMask: MultipartBody.Part? = null,
    ): Response<SubmitJobResponseDto>

    @GET("v1/jobs/{jobId}")
    suspend fun getJob(@Path("jobId") jobId: String): Response<JobStatusDto>

    @GET("v1/jobs")
    suspend fun listJobs(@Query("limit") limit: Int = 20): Response<JobListDto>

    @Streaming
    @GET("v1/jobs/{jobId}/result")
    suspend fun downloadResult(@Path("jobId") jobId: String): Response<ResponseBody>

    @Streaming
    @GET("v1/jobs/{jobId}/preview")
    suspend fun downloadPreview(@Path("jobId") jobId: String): Response<ResponseBody>

    @DELETE("v1/jobs/{jobId}")
    suspend fun deleteJob(@Path("jobId") jobId: String): Response<Unit>
}
