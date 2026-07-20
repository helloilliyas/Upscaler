package com.example.videoupscaler.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

// Brand: the icon's violet with a cyan accent — a deliberate "cinema" identity,
// distinct from the photo app's indigo/amber. Defined for both light and dark
// so the app keeps one identity everywhere (no wallpaper dynamic color).
private val Violet = Color(0xFF5B2EE5)
private val VioletBright = Color(0xFFC9BBFF)
private val Cyan = Color(0xFF00A5C4)
private val CyanBright = Color(0xFF4DE3FF)

private val LightColors = lightColorScheme(
    primary = Violet,
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFE7DEFF),
    onPrimaryContainer = Color(0xFF1C0263),
    secondary = Color(0xFF5F5A71),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFE5DFF9),
    onSecondaryContainer = Color(0xFF1B172B),
    tertiary = Cyan,
    onTertiary = Color(0xFFFFFFFF),
    background = Color(0xFFFBFCFF),
    onBackground = Color(0xFF1A1B22),
    surface = Color(0xFFFBFCFF),
    onSurface = Color(0xFF1A1B22),
    surfaceVariant = Color(0xFFE5E0EC),
    onSurfaceVariant = Color(0xFF47464F),
    outline = Color(0xFF787680),
    outlineVariant = Color(0xFFC8C5D0),
)

private val DarkColors = darkColorScheme(
    primary = VioletBright,
    onPrimary = Color(0xFF2C0A97),
    primaryContainer = Color(0xFF4318C9),
    onPrimaryContainer = Color(0xFFE7DEFF),
    secondary = Color(0xFFC8C2DC),
    onSecondary = Color(0xFF302D41),
    secondaryContainer = Color(0xFF474359),
    onSecondaryContainer = Color(0xFFE5DFF9),
    tertiary = CyanBright,
    onTertiary = Color(0xFF00363F),
    background = Color(0xFF10131C),
    onBackground = Color(0xFFE3E1EA),
    surface = Color(0xFF10131C),
    onSurface = Color(0xFFE3E1EA),
    surfaceVariant = Color(0xFF47464F),
    onSurfaceVariant = Color(0xFFC8C5D0),
    outline = Color(0xFF918F9A),
    outlineVariant = Color(0xFF47464F),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(32.dp),
)

@Composable
fun VideoUpscalerTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        shapes = AppShapes,
        content = content,
    )
}
