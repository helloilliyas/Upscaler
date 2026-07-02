"""Modal deployment entrypoint.

Wires the framework-agnostic FastAPI app to Modal-backed storage and GPU
workers. Run locally with ``modal serve backend/modal_app.py`` or deploy with
``modal deploy backend/modal_app.py``.

This module imports ``modal`` and is intentionally excluded from the unit-test,
lint, and type-check passes (it cannot run without the Modal runtime). The
testable logic lives in ``backend/app``.

Current status: all three modes run real pipelines. Standard worker: Real-ESRGAN
(Natural) and GFPGAN faces + LaMa inpainting (Restore). Ultra worker: Stability
x4 latent-diffusion upscaler (Ultra Detail, generative).
"""

from __future__ import annotations

from collections.abc import Iterator

import modal
from app.config import get_settings
from app.jobs import JobService
from app.storage import FileStore, MetadataStore

# NOTE: app.main is imported lazily inside fastapi_app() (not here) because it
# pulls in FastAPI, which is only installed in the web image. The GPU worker
# containers also import this module, so a top-level FastAPI import would crash
# them on startup.

DATA_MOUNT = "/data"
# Weights are baked into the standard image at build time (see below).
MODELS_DIR = "/models"

# Real-ESRGAN checkpoints with pinned SHA-256 hashes (kept in sync with
# scripts/models.json). Verified before use; never committed to the repo.
STANDARD_WEIGHTS = [
    {
        "name": "realesr-general-x4v3",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
        "sha256": "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292",
    },
    {
        "name": "RealESRGAN_x4plus",
        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "sha256": "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1",
    },
    {
        "name": "GFPGANv1.4",
        "url": "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
        "sha256": "e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad",
    },
    {
        # LaMa inpainting (Restore-mode repair brush). Torchscript model; located
        # at runtime via the LAMA_MODEL env var set on the standard image below.
        "name": "big-lama",
        "file": "big-lama.pt",
        "url": "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt",
        "sha256": "7ba7aa7ac37a4d41fdbbeba3a2af7ead18058552997e3a3cd1a3b2210c9e6b4c",
    },
]

app = modal.App("ai-photo-restorer")

files_volume = modal.Volume.from_name("photo-restorer-files", create_if_missing=True)
jobs_dict = modal.Dict.from_name("photo-restorer-jobs", create_if_missing=True)


def _weight_download_commands() -> list[str]:
    """Shell commands that fetch + verify each weight into MODELS_DIR at build.

    Run via ``Image.run_commands`` (stdlib-only ``python -c``) rather than
    ``run_function`` so the build step never imports this module / the ``app``
    package (which isn't in the GPU image until a later layer).
    """
    cmds = [f"mkdir -p {MODELS_DIR}"]
    for model in STANDARD_WEIGHTS:
        path = f"{MODELS_DIR}/{model.get('file', model['name'] + '.pth')}"
        script = (
            "import urllib.request, hashlib; "
            f"p = {path!r}; "
            f"urllib.request.urlretrieve({model['url']!r}, p); "
            "h = hashlib.sha256(open(p, 'rb').read()).hexdigest(); "
            f"assert h == {model['sha256']!r}, h"
        )
        cmds.append(f'python -c "{script}"')
    return cmds


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
        # google.auth.transport.requests needs the `requests` library; google-auth
        # does not pull it in automatically. Without it, token verification 500s.
        "requests>=2.31",
    )
    .add_local_python_source("app")
)

# Shared GPU base image: Real-ESRGAN/GFPGAN/LaMa stack + weights baked at build.
# torch 2.1.2 / torchvision 0.16.2 are pinned because basicsr imports
# torchvision.transforms.functional_tensor, which was removed in torchvision 0.17.
#
# basicsr/realesrgan are installed in a SECOND step with --no-build-isolation so
# their setup.py sees the already-installed torch/numpy/cython instead of trying
# to resolve build-time deps in isolation (which pulls conflicting CUDA eggs).
# setuptools is pinned <70 because basicsr's legacy setup.py relies on
# setuptools.installer APIs removed in newer versions.
_gpu_base = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "torch==2.1.2",
        "torchvision==0.16.2",
        "numpy<2",
        "cython",
        "setuptools<70",
        "wheel",
        "opencv-python-headless==4.9.0.80",
        "Pillow>=10.3",
        "pydantic>=2.7",
        "pydantic-settings>=2.3",
        "google-auth>=2.30",
    )
    .pip_install(
        # Re-pin numpy<2 here: basicsr/realesrgan's transitive deps (scikit-image,
        # scipy, numba, ...) otherwise pull NumPy 2.x, which torch 2.1.2 (built
        # against NumPy 1.x) can't initialize -> "Numpy is not available" at load.
        "numpy<2",
        "basicsr==1.4.2",
        "realesrgan==0.3.0",
        extra_options="--no-build-isolation",
    )
    # LaMa wrapper, deps-free: it only needs torch / numpy / cv2 / Pillow, all
    # already present, so --no-deps avoids pulling non-headless opencv-python.
    .pip_install("simple-lama-inpainting==0.1.2", extra_options="--no-deps")
    .run_commands(*_weight_download_commands())
    # SimpleLama reads LAMA_MODEL for a pre-baked checkpoint instead of fetching
    # big-lama.pt from GitHub on first use.
    .env({"LAMA_MODEL": f"{MODELS_DIR}/big-lama.pt"})
)

standard_image = _gpu_base.add_local_python_source("app")

# Ultra worker image: the shared base + the diffusers stack, with the Stability
# x4 upscaler snapshot baked into the image (HF_HOME) so runtime never touches
# the network. Versions chosen for torch 2.1.2 / numpy<2 compatibility.
ULTRA_MODEL_ID = "stabilityai/stable-diffusion-x4-upscaler"
HF_CACHE_DIR = f"{MODELS_DIR}/hf"

_ULTRA_SNAPSHOT_CMD = (
    'python -c "'
    "from huggingface_hub import snapshot_download; "
    f"p = snapshot_download({ULTRA_MODEL_ID!r}, "
    "ignore_patterns=['*.ckpt', 'x4-upscaler-ema.safetensors']); "
    # The path ends in .../snapshots/<revision>; printed so the resolved
    # revision is recorded in the deploy log (pin it in models.json from there).
    "print('ULTRA_SNAPSHOT', p)"
    '"'
)

ultra_image = (
    _gpu_base.pip_install(
        "numpy<2",
        "diffusers==0.27.2",
        "transformers==4.38.2",
        "accelerate==0.27.2",
        # Pinned so resolver drift can't hand diffusers an incompatible hub.
        "huggingface_hub==0.25.2",
    )
    .env({"HF_HOME": HF_CACHE_DIR})
    .run_commands(_ULTRA_SNAPSHOT_CMD)
    .add_local_python_source("app")
)


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


@app.cls(
    gpu="L4",
    timeout=20 * 60,
    image=standard_image,
    volumes={DATA_MOUNT: files_volume},
)
class StandardRestorer:
    @modal.enter()
    def load_models(self) -> None:
        from app.workers.standard_processor import StandardModelProcessor

        self._files = ModalVolumeFileStore(DATA_MOUNT, files_volume)
        self._jobs = JobService(ModalDictMetadataStore(jobs_dict), self._files)
        # Real-ESRGAN (Natural), GFPGAN faces + LaMa inpainting (Restore).
        # half=True is safe on the L4 GPU.
        self._processor = StandardModelProcessor(
            self._jobs, self._files, weights_dir=MODELS_DIR, tile=512, half=True
        )
        self._processor.warmup()

    @modal.method()
    def process(self, job_id: str) -> None:
        self._processor.process(job_id)


@app.cls(
    gpu="L40S",
    timeout=30 * 60,
    image=ultra_image,
    volumes={DATA_MOUNT: files_volume},
)
class UltraRestorer:
    @modal.enter()
    def load_models(self) -> None:
        from app.workers.ultra_processor import UltraModelProcessor

        self._files = ModalVolumeFileStore(DATA_MOUNT, files_volume)
        self._jobs = JobService(ModalDictMetadataStore(jobs_dict), self._files)
        # Generative diffusion upscaling (Ultra Detail). fp16 on the L40S.
        self._processor = UltraModelProcessor(self._jobs, self._files)
        self._processor.warmup()

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
    from app.main import create_app  # lazy: FastAPI only exists in the web image

    settings = get_settings()
    files = ModalVolumeFileStore(DATA_MOUNT, files_volume)
    meta = ModalDictMetadataStore(jobs_dict)
    return create_app(
        settings=settings,
        files=files,
        meta=meta,
        processor=SpawnProcessor(),
    )
