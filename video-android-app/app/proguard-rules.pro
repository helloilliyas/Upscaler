# Keep kotlinx.serialization generated serializers.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**

-keepclassmembers class **$$serializer { *; }
-keepclasseswithmembers, allowshrinking class * {
    @kotlinx.serialization.SerialName <fields>;
}
-keep,includedescriptorclasses class com.example.videoupscaler.**$$serializer { *; }
-keepclassmembers class com.example.videoupscaler.** {
    *** Companion;
}
-keepclasseswithmembers class com.example.videoupscaler.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Retrofit / OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn retrofit2.**
-keepattributes Signature, Exceptions

# Models used by serialization are kept via the serializer rules above.
