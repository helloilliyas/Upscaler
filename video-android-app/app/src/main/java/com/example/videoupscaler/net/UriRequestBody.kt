package com.example.videoupscaler.net

import android.content.ContentResolver
import android.net.Uri
import java.io.FileNotFoundException
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody
import okio.BufferedSink
import okio.source

/**
 * A [RequestBody] that streams directly from a content [Uri] via the
 * [ContentResolver], so a large video is never fully loaded into memory.
 */
class UriRequestBody(
    private val resolver: ContentResolver,
    private val uri: Uri,
    private val contentType: String,
) : RequestBody() {

    override fun contentType(): MediaType? = contentType.toMediaTypeOrNull()

    override fun contentLength(): Long =
        resolver.openAssetFileDescriptor(uri, "r")?.use { it.length } ?: -1L

    override fun writeTo(sink: BufferedSink) {
        val input = resolver.openInputStream(uri)
            ?: throw FileNotFoundException("Cannot open $uri")
        input.source().use { source -> sink.writeAll(source) }
    }
}
