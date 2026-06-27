package com.example.photorestorer.util

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.net.Uri
import androidx.core.net.toUri
import java.io.File
import java.util.UUID

/** A point in normalized image coordinates (0..1 on each axis). */
data class NormPoint(val x: Float, val y: Float)

/**
 * One repair-brush stroke. [widthFraction] is the brush diameter as a fraction
 * of the image width; [erase] strokes paint back to "preserve".
 */
data class MaskStroke(
    val points: List<NormPoint>,
    val widthFraction: Float,
    val erase: Boolean,
)

/**
 * Rasterizes repair strokes into a grayscale mask PNG (black = preserve,
 * white = repair) at the image's oriented pixel dimensions, so it aligns with
 * the photo the backend validates. Returns a cache-file Uri.
 */
object MaskWriter {

    fun write(
        context: Context,
        strokes: List<MaskStroke>,
        size: ImageSize,
    ): Uri {
        val bitmap = Bitmap.createBitmap(size.width, size.height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        canvas.drawColor(Color.BLACK)

        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeCap = Paint.Cap.ROUND
            strokeJoin = Paint.Join.ROUND
        }

        for (stroke in strokes) {
            paint.color = if (stroke.erase) Color.BLACK else Color.WHITE
            paint.strokeWidth = stroke.widthFraction * size.width
            drawStroke(canvas, paint, stroke, size)
        }

        val dir = File(context.cacheDir, "masks").apply { mkdirs() }
        val file = File(dir, "mask_${UUID.randomUUID()}.png")
        file.outputStream().use { out ->
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
        }
        bitmap.recycle()
        return file.toUri()
    }

    private fun drawStroke(canvas: Canvas, paint: Paint, stroke: MaskStroke, size: ImageSize) {
        val pts = stroke.points
        if (pts.isEmpty()) return
        if (pts.size == 1) {
            val p = pts.first()
            canvas.drawPoint(p.x * size.width, p.y * size.height, paint)
            return
        }
        val path = Path()
        path.moveTo(pts.first().x * size.width, pts.first().y * size.height)
        for (i in 1 until pts.size) {
            path.lineTo(pts[i].x * size.width, pts[i].y * size.height)
        }
        canvas.drawPath(path, paint)
    }
}
