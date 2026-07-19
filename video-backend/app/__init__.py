"""AI Video Upscaler backend.

A standalone, personal-use video upscaling service. Mirrors the architecture of
the photo backend (FastAPI web layer + Modal GPU workers + Volume/Dict storage)
but shares no code with it and touches none of its files.
"""
