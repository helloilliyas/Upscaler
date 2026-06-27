package com.example.photorestorer.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** User-facing restoration mode. Wire values match the backend `mode` field. */
@Serializable
enum class RestorationMode(val wire: String, val label: String) {
    @SerialName("natural")
    NATURAL("natural", "Natural Enhance"),

    @SerialName("restore")
    RESTORE("restore", "Restore"),

    @SerialName("ultra")
    ULTRA("ultra", "Ultra Detail");

    companion object {
        fun fromWire(value: String): RestorationMode =
            entries.firstOrNull { it.wire == value } ?: NATURAL
    }
}
