package com.example.photorestorer

import com.example.photorestorer.util.FileSizeFormatter
import org.junit.Assert.assertEquals
import org.junit.Test

class FileSizeFormatterTest {

    @Test
    fun formatsBytes() {
        assertEquals("512 B", FileSizeFormatter.format(512))
    }

    @Test
    fun formatsKilobytes() {
        assertEquals("1.0 KB", FileSizeFormatter.format(1024))
        assertEquals("1.5 KB", FileSizeFormatter.format(1536))
    }

    @Test
    fun formatsMegabytes() {
        assertEquals("1.0 MB", FileSizeFormatter.format(1024L * 1024))
        assertEquals("4.2 MB", FileSizeFormatter.format((4.2 * 1024 * 1024).toLong()))
    }
}
