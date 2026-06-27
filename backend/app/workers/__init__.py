"""Processing workers.

The ``Processor`` protocol decouples the API from how a job is actually run.
``LocalPlaceholderProcessor`` does a deterministic Pillow resize so the whole
system runs and is testable without a GPU (the Phase 2 placeholder operation).
The Modal GPU workers implement the same protocol in ``backend/modal_app.py``.
"""
