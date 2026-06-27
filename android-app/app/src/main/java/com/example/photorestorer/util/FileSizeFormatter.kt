package com.example.photorestorer.util

import java.util.Locale

/** Formats a byte count as a human-readable size, e.g. "4.2 MB". */
object FileSizeFormatter {
    fun format(bytes: Long): String {
        if (bytes < 1024) return "$bytes B"
        val units = listOf("KB", "MB", "GB", "TB")
        var value = bytes.toDouble() / 1024
        var index = 0
        while (value >= 1024 && index < units.lastIndex) {
            value /= 1024
            index++
        }
        return String.format(Locale.US, "%.1f %s", value, units[index])
    }
}
