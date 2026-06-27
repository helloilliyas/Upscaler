package com.example.photorestorer.util

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import dagger.hilt.android.qualifiers.ApplicationContext
import okio.BufferedSource
import okio.buffer
import okio.sink
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

/** Streams a result image into the device Gallery via MediaStore. */
@Singleton
class MediaStoreSaver @Inject constructor(
    @ApplicationContext private val context: Context,
) {

    /**
     * Save [source] bytes as a JPEG named [displayName] under Pictures/PhotoRestorer.
     * Returns the content Uri of the saved image.
     */
    @Throws(IOException::class)
    fun saveJpeg(displayName: String, source: BufferedSource): Uri {
        val resolver = context.contentResolver
        val collection = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        } else {
            MediaStore.Images.Media.EXTERNAL_CONTENT_URI
        }

        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, "$displayName.jpg")
            put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(
                    MediaStore.Images.Media.RELATIVE_PATH,
                    "${Environment.DIRECTORY_PICTURES}/PhotoRestorer",
                )
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
        }

        val uri = resolver.insert(collection, values)
            ?: throw IOException("Failed to create MediaStore entry")

        try {
            val out = resolver.openOutputStream(uri)
                ?: throw IOException("Failed to open output stream")
            out.sink().buffer().use { sink ->
                source.use { src -> sink.writeAll(src) }
            }
        } catch (e: IOException) {
            resolver.delete(uri, null, null)
            throw e
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
        }
        return uri
    }
}
