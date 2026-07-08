package com.example.photorestorer.util

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.graphics.Matrix
import android.net.Uri
import android.os.Build
import android.util.Log
import androidx.exifinterface.media.ExifInterface
import kotlin.math.max
import kotlin.math.roundToInt

/** Width/height of an image after EXIF orientation is applied. */
data class ImageSize(val width: Int, val height: Int)

/** A display bitmap plus the image's full-resolution oriented dimensions. */
data class OrientedPhoto(val bitmap: Bitmap, val fullSize: ImageSize)

/**
 * Loads images with EXIF orientation baked in, so the repair-mask coordinate
 * system matches what the backend sees (it applies `exif_transpose` to the
 * uploaded photo).
 *
 * Uses ImageDecoder on API 28+ — BitmapFactory over a plain InputStream can't
 * decode HEIC/AVIF on many devices (the codec needs a seekable source), which
 * made the editor fail on modern camera photos. Falls back to the legacy
 * BitmapFactory + ExifInterface path on older APIs or decoder failure. Never
 * throws: any failure returns null.
 */
object OrientedImage {

    private const val TAG = "OrientedImage"

    /** Display bitmap (longest edge <= [maxEdge]) + full oriented size, or null. */
    fun load(context: Context, uri: Uri, maxEdge: Int): OrientedPhoto? {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            try {
                var fullSize = ImageSize(0, 0)
                val source = ImageDecoder.createSource(context.contentResolver, uri)
                val bitmap = ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
                    // info.size is the post-orientation output size.
                    fullSize = ImageSize(info.size.width, info.size.height)
                    decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                    val longest = max(info.size.width, info.size.height)
                    if (longest > maxEdge) {
                        val scale = maxEdge.toFloat() / longest
                        decoder.setTargetSize(
                            (info.size.width * scale).roundToInt().coerceAtLeast(1),
                            (info.size.height * scale).roundToInt().coerceAtLeast(1),
                        )
                    }
                }
                if (fullSize.width > 0 && fullSize.height > 0) {
                    return OrientedPhoto(bitmap, fullSize)
                }
            } catch (e: Exception) {
                Log.w(TAG, "ImageDecoder failed for $uri, trying legacy path", e)
            }
        }
        return legacyLoad(context, uri, maxEdge)
    }

    // --- Legacy path (API 26/27, or ImageDecoder failure) -----------------

    private fun legacyLoad(context: Context, uri: Uri, maxEdge: Int): OrientedPhoto? {
        return try {
            val (rawW, rawH) = rawBounds(context, uri) ?: return null
            val orientation = orientation(context, uri)
            val fullSize = if (isSwapped(orientation)) {
                ImageSize(rawH, rawW)
            } else {
                ImageSize(rawW, rawH)
            }

            var sample = 1
            val longest = max(rawW, rawH)
            while (longest / sample > maxEdge) sample *= 2

            val options = BitmapFactory.Options().apply { inSampleSize = sample }
            val decoded = context.contentResolver.openInputStream(uri)?.use {
                BitmapFactory.decodeStream(it, null, options)
            } ?: return null

            OrientedPhoto(applyOrientation(decoded, orientation), fullSize)
        } catch (e: Exception) {
            Log.w(TAG, "Legacy decode failed for $uri", e)
            null
        }
    }

    private fun rawBounds(context: Context, uri: Uri): Pair<Int, Int>? {
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, options)
        } ?: return null
        if (options.outWidth <= 0 || options.outHeight <= 0) return null
        return options.outWidth to options.outHeight
    }

    private fun orientation(context: Context, uri: Uri): Int = try {
        context.contentResolver.openInputStream(uri)?.use {
            ExifInterface(it).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL,
            )
        } ?: ExifInterface.ORIENTATION_NORMAL
    } catch (e: Exception) {
        Log.w(TAG, "EXIF read failed for $uri", e)
        ExifInterface.ORIENTATION_NORMAL
    }

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
