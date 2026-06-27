"""Image pipeline helpers.

Only the deterministic, GPU-free pieces (output sizing) live here in the
backend foundation. The model pipelines (natural/restore/ultra, faces,
inpainting, tiling, encoding) are added in later phases and run inside the
Modal GPU workers.
"""
