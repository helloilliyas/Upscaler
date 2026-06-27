package com.example.photorestorer.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Requested output size. Wire values match the backend `output` field. */
@Serializable
enum class OutputSize(val wire: String, val label: String) {
    @SerialName("2x")
    X2("2x", "2×"),

    @SerialName("4x")
    X4("4x", "4×"),

    @SerialName("4k")
    K4("4k", "4K"),

    @SerialName("8k")
    K8("8k", "8K");

    companion object {
        fun fromWire(value: String): OutputSize =
            entries.firstOrNull { it.wire == value } ?: X2
    }
}
