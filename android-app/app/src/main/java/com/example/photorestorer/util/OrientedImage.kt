package com.example.photorestorer.util

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import androidx.exifinterface.media.ExifInterface

/** Width/height of an image after EXIF orientation is applied. */
data class ImageSize(val width: Int, val height: Int)

/**
 * Loads images with EXIF orientation baked in, so the repair-mask coordinate
 * system matches what the backend sees (it applies `exif_transpose` to the
 * uploaded photo). minSdk 26 friendly — uses ExifInterface + BitmapFactory
 * rather than ImageDecoder (API 28+).
 */
object OrientedImage {

    /** Full-resolution oriented dimensions, or null if the image can't be read. */
    fun size(context: Context, uri: Uri): ImageSize? {
        val (rawW, rawH) = rawBounds(context, uri) ?: return null
        return if (isSwapped(orientation(context, uri))) {
            ImageSize(rawH, rawW)
        } else {
            ImageSize(rawW, rawH)
        }
    }

    /** A display bitmap, downsampled so its longest edge is at most [maxEdge]. */
    fun loadDownsampled(context: Context, uri: Uri, maxEdge: Int): Bitmap? {
        val (rawW, rawH) = rawBounds(context, uri) ?: return null

        var sample = 1
        val longest = maxOf(rawW, rawH)
        while (longest / sample > maxEdge) sample *= 2

        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        val decoded = context.contentResolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, options)
        } ?: return null

        return applyOrientation(decoded, orientation(context, uri))
    }

    private fun rawBounds(context: Context, uri: Uri): Pair<Int, Int>? {
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, options)
        } ?: return null
        if (options.outWidth <= 0 || options.outHeight <= 0) return null
        return options.outWidth to options.outHeight
    }

    private fun orientation(context: Context, uri: Uri): Int =
        context.contentResolver.openInputStream(uri)?.use {
            ExifInterface(it).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL,
            )
        } ?: ExifInterface.ORIENTATION_NORMAL

    private fun isSwapped(orientation: Int): Boolean = orientation in setOf(
        ExifInterface.ORIENTATION_ROTATE_90,
        ExifInterface.ORIENTATION_ROTATE_270,
        ExifInterface.ORIENTATION_TRANSPOSE,
        ExifInterface.ORIENTATION_TRANSVERSE,
    )

    private fun applyOrientation(bitmap: Bitmap, orientation: Int): Bitmap {
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.postScale(-1f, 1f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.postScale(1f, -1f)
            ExifInterface.ORIENTATION_TRANSPOSE -> {
                matrix.postRotate(90f); matrix.postScale(-1f, 1f)
            }
            ExifInterface.ORIENTATION_TRANSVERSE -> {
                matrix.postRotate(270f); matrix.postScale(-1f, 1f)
            }
            else -> return bitmap
        }
        val rotated = Bitmap.createBitmap(
            bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true,
        )
        if (rotated != bitmap) bitmap.recycle()
        return rotated
    }
}
