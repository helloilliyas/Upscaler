package com.example.photorestorer.database

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/** Local history record for one restoration job. Survives app restarts. */
@Entity(
    tableName = "restoration_jobs",
    indices = [Index(value = ["remoteJobId"], unique = true)],
)
data class RestorationJobEntity(
    @PrimaryKey(autoGenerate = true) val localId: Long = 0,
    val remoteJobId: String,
    val originalUri: String? = null,
    val resultUri: String? = null,
    val previewUri: String? = null,
    val mode: String,
    val output: String,
    val status: String,
    val stage: String? = null,
    val progress: Int = 0,
    val createdAt: Long,
    val completedAt: Long? = null,
    val fidelity: String? = null,
    val errorCode: String? = null,
    val errorMessage: String? = null,
    val cloudDeleted: Boolean = false,
)
