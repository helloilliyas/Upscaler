package com.example.photorestorer.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Coarse job status mirrored from the backend. */
@Serializable
enum class JobStatus(val wire: String) {
    @SerialName("queued")
    QUEUED("queued"),

    @SerialName("processing")
    PROCESSING("processing"),

    @SerialName("completed")
    COMPLETED("completed"),

    @SerialName("failed")
    FAILED("failed"),

    @SerialName("cancelled")
    CANCELLED("cancelled"),

    @SerialName("expired")
    EXPIRED("expired");

    val isTerminal: Boolean
        get() = this == COMPLETED || this == FAILED || this == CANCELLED || this == EXPIRED

    /** User-facing label (never show the raw wire value in the UI). */
    val label: String
        get() = when (this) {
            QUEUED -> "Queued"
            PROCESSING -> "Processing"
            COMPLETED -> "Completed"
            FAILED -> "Failed"
            CANCELLED -> "Cancelled"
            EXPIRED -> "Expired"
        }

    companion object {
        fun fromWire(value: String?): JobStatus =
            entries.firstOrNull { it.wire == value } ?: QUEUED
    }
}

/** User-facing fidelity label attached to a completed result. */
@Serializable
enum class Fidelity(val wire: String, val label: String) {
    @SerialName("high")
    HIGH("high", "High fidelity"),

    @SerialName("moderate")
    MODERATE("moderate", "Moderate fidelity"),

    @SerialName("generative")
    GENERATIVE("generative", "Generative");

    companion object {
        fun fromWire(value: String?): Fidelity? =
            entries.firstOrNull { it.wire == value }
    }
}
