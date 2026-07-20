package com.example.videoupscaler

import com.example.videoupscaler.net.JobStatusDto
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Test

class ModelsTest {

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun outputSizeApiValuesMatchBackend() {
        assertEquals("2x", OutputSize.X2.apiValue)
        assertEquals("4x", OutputSize.X4.apiValue)
        assertEquals("4k", OutputSize.K4.apiValue)
        assertEquals(OutputSize.K4, OutputSize.fromApiValue("4k"))
        assertEquals(OutputSize.X2, OutputSize.fromApiValue("unknown"))
    }

    @Test
    fun jobStatusParsesBackendPayload() {
        val payload = """
            {
              "job_id": "vjob_abc123",
              "status": "processing",
              "stage": "enhancing",
              "progress": 42,
              "message": "Upscaling frames",
              "result_available": false,
              "width": null,
              "height": null,
              "duration_seconds": 12.5,
              "fps": 30.0,
              "frames_total": 375,
              "frames_done": 150,
              "error_code": null,
              "error_message": null
            }
        """.trimIndent()
        val dto = json.decodeFromString<JobStatusDto>(payload)
        assertEquals("vjob_abc123", dto.jobId)
        assertEquals(42, dto.progress)
        assertEquals(150, dto.framesDone)
        assertEquals(375, dto.framesTotal)
        assertEquals(30.0, dto.fps!!, 1e-9)
    }

    @Test
    fun jobStatusToleratesMissingOptionalFields() {
        val payload = """{"job_id": "vjob_x", "status": "queued", "stage": "queued"}"""
        val dto = json.decodeFromString<JobStatusDto>(payload)
        assertEquals(0, dto.progress)
        assertEquals(null, dto.framesDone)
    }
}
