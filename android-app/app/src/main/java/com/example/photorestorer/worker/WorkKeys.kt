package com.example.photorestorer.worker

/** Shared input/output keys for the restoration work chain. */
object WorkKeys {
    const val PHOTO_URI = "photo_uri"
    const val MASK_URI = "mask_uri"
    const val MODE = "mode"
    const val OUTPUT = "output"
    const val PRESERVE_METADATA = "preserve_metadata"
    const val IDEMPOTENCY_KEY = "idempotency_key"
    const val DELETE_AFTER_DOWNLOAD = "delete_after_download"

    const val JOB_ID = "job_id"

    const val TAG_RESTORATION = "restoration"

    fun uniqueName(idempotencyKey: String): String = "restoration_$idempotencyKey"
}
