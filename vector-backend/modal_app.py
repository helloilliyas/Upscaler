"""Vector Converter backend — FastAPI served by Modal, scales to zero.

Deploy:
    modal secret create vector-converter-secret API_KEY=<your-long-random-key>
    modal deploy backend/modal_app.py

The printed URL + your API key go into the Flutter app's lib/config.dart.
"""
import modal

app = modal.App("vector-converter")

MODELS_DIR = "/models"
_X4PLUS_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
_X4PLUS_SHA = "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1"

# GPU image for the optional Real-ESRGAN pre-enhance step. Pins mirror the
# proven Upscaler stack: torchvision 0.16 (basicsr needs functional_tensor),
# numpy<2 (torch 2.1.2 ABI), basicsr/realesrgan without build isolation.
gpu_image = (
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
        "pillow-heif",
    )
    .pip_install(
        "numpy<2",
        "basicsr==1.4.2",
        "realesrgan==0.3.0",
        extra_options="--no-build-isolation",
    )
    .run_commands(
        f"mkdir -p {MODELS_DIR}",
        'python -c "import urllib.request, hashlib; '
        f"p = '{MODELS_DIR}/RealESRGAN_x4plus.pth'; "
        f"urllib.request.urlretrieve('{_X4PLUS_URL}', p); "
        "h = hashlib.sha256(open(p, 'rb').read()).hexdigest(); "
        f"assert h == '{_X4PLUS_SHA}', h\"",
    )
)

_upsampler = None


@app.function(image=gpu_image, gpu="T4", timeout=300)
def enhance_image(data: bytes) -> bytes:
    """Real-ESRGAN 4x upscale, used as an optional pre-trace cleanup for
    small/blurry sources. Input is capped at 1024px so output stays <=4096."""
    import io

    import cv2
    import numpy as np
    import pillow_heif
    from PIL import Image, ImageOps

    pillow_heif.register_heif_opener()

    global _upsampler
    if _upsampler is None:
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer

        net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                      num_block=23, num_grow_ch=32, scale=4)
        _upsampler = RealESRGANer(
            scale=4,
            model_path=f"{MODELS_DIR}/RealESRGAN_x4plus.pth",
            model=net,
            tile=512,
            tile_pad=32,
            pre_pad=0,
            half=True,
        )

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    if max(img.size) > 1024:
        img.thumbnail((1024, 1024), Image.LANCZOS)
    arr = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    out, _ = _upsampler.enhance(arr, outscale=4)
    buf = io.BytesIO()
    Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB)).save(buf, "PNG")
    return buf.getvalue()


image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libcairo2")
    .pip_install(
        "fastapi[standard]==0.115.*",
        "python-multipart",
        "vtracer==0.6.*",
        "pillow",
        "pillow-heif",
        "opencv-python-headless",
        "numpy",
        "cairosvg",
        "anthropic",
    )
    .add_local_python_source("pipeline")
    .add_local_python_source("refine")
)

MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("vector-converter-secret")],
    timeout=300,
    max_containers=3,
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app()
def api():
    import base64
    import os

    from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

    import pipeline
    import refine as refine_mod

    web = FastAPI(title="Vector Converter", docs_url=None, redoc_url=None)
    api_key = os.environ["API_KEY"]

    def check(key: str | None):
        if key != api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    @web.get("/health")
    def health():
        return {"status": "ok", "presets": list(pipeline.PRESETS)}

    @web.post("/vectorize")
    async def vectorize(
        file: UploadFile = File(...),
        preset: str = Form("photo"),
        colors: int = Form(0),
        detail: int = Form(60),
        format: str = Form("svg"),
        enhance: int = Form(0),
        x_api_key: str | None = Header(None),
    ):
        check(x_api_key)
        if preset not in pipeline.PRESETS:
            raise HTTPException(422, f"Unknown preset '{preset}'")
        if format not in ("svg", "pdf", "png"):
            raise HTTPException(422, f"Unknown format '{format}'")

        data = await file.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "File larger than 10 MB")
        if not data:
            raise HTTPException(422, "Empty file")

        if enhance:
            try:
                data = enhance_image.remote(data)
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(500, f"AI enhance failed: {exc}") from exc

        try:
            result = pipeline.vectorize(data, preset, colors, detail)
        except Exception as exc:  # noqa: BLE001 - surface a clean message to the app
            raise HTTPException(422, f"Could not process image: {exc}") from exc

        body = {
            "format": format,
            "enhanced": bool(enhance),
            "width": result["width"],
            "height": result["height"],
            "path_count": result["path_count"],
            "duration_ms": result["duration_ms"],
        }
        try:
            if format == "svg":
                body["svg"] = result["svg"]
            elif format == "pdf":
                body["data_base64"] = base64.b64encode(pipeline.to_pdf(result["svg"])).decode()
            else:
                body["data_base64"] = base64.b64encode(pipeline.to_png(result["svg"])).decode()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, f"Export to {format} failed: {exc}") from exc
        return body

    @web.post("/refine")
    async def refine(
        file: UploadFile = File(...),
        preset: str = Form("photo"),
        colors: int = Form(0),
        detail: int = Form(60),
        anthropic_key: str = Form(""),
        x_api_key: str | None = Header(None),
    ):
        check(x_api_key)
        if preset not in pipeline.PRESETS:
            raise HTTPException(422, f"Unknown preset '{preset}'")
        data = await file.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "File larger than 10 MB")
        if not data:
            raise HTTPException(422, "Empty file")
        try:
            return refine_mod.refine(data, preset, colors, detail,
                                     anthropic_key or None)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, f"Refine failed: {exc}") from exc

    return web
