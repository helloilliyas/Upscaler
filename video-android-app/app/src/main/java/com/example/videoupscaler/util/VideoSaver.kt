package com.example.videoupscaler.util

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import java.io.IOException
import java.io.InputStream

/** Streams a result video into the device Gallery via MediaStore. */
object VideoSaver {

    /**
     * Save [input] as an MP4 named [displayName] under Movies/VideoUpscaler.
     * Returns the content Uri of the saved video.
     */
    @Throws(IOException::class)
    fun saveMp4(context: Context, displayName: String, input: InputStream): Uri {
        val resolver = context.contentResolver
        val collection = MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)

        val values = ContentValues().apply {
            put(MediaStore.Video.Media.DISPLAY_NAME, "$displayName.mp4")
            put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
            put(
                MediaStore.Video.Media.RELATIVE_PATH,
                "${Environment.DIRECTORY_MOVIES}/VideoUpscaler",
            )
            put(MediaStore.Video.Media.IS_PENDING, 1)
        }

        val uri = resolver.insert(collection, values)
            ?: throw IOException("Failed to create MediaStore entry")

        try {
            val out = resolver.openOutputStream(uri)
                ?: throw IOException("Failed to open output stream")
            out.use { sink -> input.use { it.copyTo(sink) } }
        } catch (e: IOException) {
            resolver.delete(uri, null, null)
            throw e
        }

        values.clear()
        values.put(MediaStore.Video.Media.IS_PENDING, 0)
        resolver.update(uri, values, null, null)
        return uri
    }
}
