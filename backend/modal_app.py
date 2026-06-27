"""Modal deployment entrypoint.

Wires the framework-agnostic FastAPI app to Modal-backed storage and GPU
workers. Run locally with ``modal serve backend/modal_app.py`` or deploy with
``modal deploy backend/modal_app.py``.

This module imports ``modal`` and is intentionally excluded from the unit-test,
lint, and type-check passes (it cannot run without the Modal runtime). The
testable logic lives in ``backend/app``.

Current status: the GPU workers run the placeholder resize processor so the end
to end async flow is deployable today. Replace ``LocalPlaceholderProcessor``
with the real Real-ESRGAN / CodeFormer / LaMa / SUPIR pipelines as each phase
lands.
"""

from __future__ import annotations

from collections.abc import Iterator

import modal
from app.config import get_settings
from app.jobs import JobService
from app.main import create_app
from app.storage import FileStore, MetadataStore
from app.workers.processor import LocalPlaceholderProcessor

DATA_MOUNT = "/data"

app = modal.App("ai-photo-restorer")

files_volume = modal.Volume.from_name("photo-restorer-files", create_if_missing=True)
jobs_dict = modal.Dict.from_name("photo-restorer-jobs", create_if_missing=True)

# Lightweight image for the web layer (no torch / CUDA).
web_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.111",
        "python-multipart>=0.0.9",
        "pydantic>=2.7",
        "pydantic-settings>=2.3",
        "Pillow>=10.3",
        "google-auth>=2.30",
    )
    .add_local_python_source("app")
)

# Standard GPU worker image (model libraries added as pipelines are implemented).
standard_image = web_image  # TODO: extend with Real-ESRGAN / CodeFormer / LaMa deps.


# --- Modal-backed storage implementations --------------------------------


class ModalVolumeFileStore(FileStore):
    """FileStore over a mounted Modal Volume; commit/reload bridge containers."""

    def __init__(self, mount: str, volume: modal.Volume) -> None:
        from app.storage import LocalFileStore

        self._local = LocalFileStore(mount)
        self._volume = volume

    def write(self, path: str, data: bytes) -> None:
        self._local.write(path, data)

    def read(self, path: str) -> bytes:
        return self._local.read(path)

    def exists(self, path: str) -> bool:
        return self._local.exists(path)

    def delete(self, path: str) -> None:
        self._local.delete(path)

    def delete_prefix(self, prefix: str) -> None:
        self._local.delete_prefix(prefix)

    def commit(self) -> None:
        self._volume.commit()

    def reload(self) -> None:
        self._volume.reload()


class ModalDictMetadataStore(MetadataStore):
    """MetadataStore over a Modal Dict."""

    def __init__(self, d: modal.Dict) -> None:
        self._d = d

    def get(self, key: str) -> dict | None:
        return self._d.get(key, None)

    def put(self, key: str, value: dict) -> None:
        self._d[key] = value

    def delete(self, key: str) -> None:
        self._d.pop(key, None)

    def contains(self, key: str) -> bool:
        return key in self._d

    def items(self) -> Iterator[tuple[str, dict]]:
        yield from self._d.items()


# --- GPU workers ---------------------------------------------------------


@app.cls(gpu="L4", timeout=20 * 60, volumes={DATA_MOUNT: files_volume})
class StandardRestorer:
    @modal.enter()
    def load_models(self) -> None:
        # TODO: load Real-ESRGAN / CodeFormer / LaMa once per container.
        self._files = ModalVolumeFileStore(DATA_MOUNT, files_volume)
        self._jobs = JobService(ModalDictMetadataStore(jobs_dict), self._files)
        self._processor = LocalPlaceholderProcessor(self._jobs, self._files)

    @modal.method()
    def process(self, job_id: str) -> None:
        self._processor.process(job_id)


@app.cls(gpu="L40S", timeout=30 * 60, volumes={DATA_MOUNT: files_volume})
class UltraRestorer:
    @modal.enter()
    def load_models(self) -> None:
        # TODO: load SUPIR + supporting diffusion components once per container.
        self._files = ModalVolumeFileStore(DATA_MOUNT, files_volume)
        self._jobs = JobService(ModalDictMetadataStore(jobs_dict), self._files)
        self._processor = LocalPlaceholderProcessor(self._jobs, self._files)

    @modal.method()
    def process(self, job_id: str) -> None:
        self._processor.process(job_id)


class SpawnProcessor:
    """Processor that dispatches a job to the appropriate GPU worker via spawn().

    The web container never blocks on GPU work; the worker reads inputs from the
    shared Volume and writes results back.
    """

    def process(self, job_id: str) -> None:
        from app.schemas import RestorationMode

        jobs = JobService(
            ModalDictMetadataStore(jobs_dict),
            ModalVolumeFileStore(DATA_MOUNT, files_volume),
        )
        record = jobs.get(job_id)
        if record.mode == RestorationMode.ULTRA.value:
            call = UltraRestorer().process.spawn(job_id)
        else:
            call = StandardRestorer().process.spawn(job_id)
        jobs.set_call_id(job_id, call.object_id)


# --- Web app -------------------------------------------------------------


@app.function(
    image=web_image,
    volumes={DATA_MOUNT: files_volume},
    secrets=[modal.Secret.from_name("photo-restorer-auth")],
    min_containers=0,
)
@modal.asgi_app()
def fastapi_app():
    settings = get_settings()
    files = ModalVolumeFileStore(DATA_MOUNT, files_volume)
    meta = ModalDictMetadataStore(jobs_dict)
    return create_app(
        settings=settings,
        files=files,
        meta=meta,
        processor=SpawnProcessor(),
    )
