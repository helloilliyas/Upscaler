package com.example.photorestorer.data.model

import com.example.photorestorer.database.RestorationJobEntity

/** Domain representation of a job for the UI layer. */
data class RestorationJob(
    val remoteJobId: String,
    val mode: RestorationMode,
    val output: OutputSize,
    val status: JobStatus,
    val stage: String?,
    val progress: Int,
    val originalUri: String?,
    val resultUri: String?,
    val previewUri: String?,
    val fidelity: Fidelity?,
    val createdAt: Long,
    val completedAt: Long?,
    val errorMessage: String?,
    val cloudDeleted: Boolean,
)

fun RestorationJobEntity.toDomain(): RestorationJob = RestorationJob(
    remoteJobId = remoteJobId,
    mode = RestorationMode.fromWire(mode),
    output = OutputSize.fromWire(output),
    status = JobStatus.fromWire(status),
    stage = stage,
    progress = progress,
    originalUri = originalUri,
    resultUri = resultUri,
    previewUri = previewUri,
    fidelity = Fidelity.fromWire(fidelity),
    createdAt = createdAt,
    completedAt = completedAt,
    errorMessage = errorMessage,
    cloudDeleted = cloudDeleted,
)
