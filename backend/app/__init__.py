"""AI Photo Restorer backend package.

The FastAPI application is intentionally decoupled from Modal so it can be run
and unit-tested locally without a GPU. Modal Volume/Dict-backed storage and the
GPU workers are wired in ``backend/modal_app.py`` for deployment.
"""

__version__ = "1.0.0"
