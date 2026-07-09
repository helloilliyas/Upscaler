"""Vector Converter backend — FastAPI served by Modal, scales to zero.

Deploy:
    modal secret create vector-converter-secret API_KEY=<your-long-random-key>
    modal deploy backend/modal_app.py

The printed URL + your API key go into the Flutter app's lib/config.dart.
"""
import modal

app = modal.App("vector-converter")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "fastapi[standard]==0.115.*",
        "python-multipart",
        "vtracer==0.6.*",
        "pillow",
        "pillow-heif",
        "opencv-python-headless",
        "numpy",
        "cairosvg",
    )
    .add_local_python_source("pipeline")
)

MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("vector-converter-secret")],
    timeout=180,
    max_containers=3,
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app()
def api():
    import base64
    import os

    from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

    import pipeline

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

        try:
            result = pipeline.vectorize(data, preset, colors, detail)
        except Exception as exc:  # noqa: BLE001 - surface a clean message to the app
            raise HTTPException(422, f"Could not process image: {exc}") from exc

        body = {
            "format": format,
            "width": result["width"],
            "height": result["height"],
            "path_count": result["path_count"],
            "duration_ms": result["duration_ms"],
        }
        if format == "svg":
            body["svg"] = result["svg"]
        elif format == "pdf":
            body["data_base64"] = base64.b64encode(pipeline.to_pdf(result["svg"])).decode()
        else:
            body["data_base64"] = base64.b64encode(pipeline.to_png(result["svg"])).decode()
        return body

    return web
