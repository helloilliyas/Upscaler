package com.example.photorestorer

import com.example.photorestorer.data.model.Fidelity
import com.example.photorestorer.data.model.JobStatus
import com.example.photorestorer.data.model.OutputSize
import com.example.photorestorer.data.model.RestorationMode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelMappingTest {

    @Test
    fun outputSizeFromWire() {
        assertEquals(OutputSize.X2, OutputSize.fromWire("2x"))
        assertEquals(OutputSize.K8, OutputSize.fromWire("8k"))
        // Unknown falls back to a safe default.
        assertEquals(OutputSize.X2, OutputSize.fromWire("16k"))
    }

    @Test
    fun restorationModeFromWire() {
        assertEquals(RestorationMode.ULTRA, RestorationMode.fromWire("ultra"))
        assertEquals(RestorationMode.NATURAL, RestorationMode.fromWire("unknown"))
    }

    @Test
    fun jobStatusTerminalFlag() {
        assertTrue(JobStatus.fromWire("completed").isTerminal)
        assertTrue(JobStatus.fromWire("failed").isTerminal)
        assertTrue(JobStatus.fromWire("cancelled").isTerminal)
        assertFalse(JobStatus.fromWire("processing").isTerminal)
        assertFalse(JobStatus.fromWire("queued").isTerminal)
        // Null/unknown defaults to queued (non-terminal).
        assertEquals(JobStatus.QUEUED, JobStatus.fromWire(null))
    }

    @Test
    fun fidelityFromWire() {
        assertEquals(Fidelity.GENERATIVE, Fidelity.fromWire("generative"))
        assertEquals(Fidelity.HIGH, Fidelity.fromWire("high"))
        assertNull(Fidelity.fromWire("nonsense"))
        assertNull(Fidelity.fromWire(null))
    }
}
