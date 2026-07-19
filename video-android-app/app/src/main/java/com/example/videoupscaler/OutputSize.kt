package com.example.videoupscaler

/** Output choices offered by the backend (`2x`/`4x` are capped inside 4K). */
enum class OutputSize(val apiValue: String, val label: String) {
    X2("2x", "2×"),
    X4("4x", "4×"),
    K4("4k", "4K");

    companion object {
        fun fromApiValue(value: String): OutputSize =
            entries.firstOrNull { it.apiValue == value } ?: X2
    }
}
