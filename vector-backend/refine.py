"""Compare-and-refine loop for vectorization results.

Level 1 (always): try several conversion parameter variants, render each SVG
back to pixels, score against the original image (Lab color error + edge
overlap), and keep the best.

Level 2 (when an Anthropic API key is supplied): show the original and the
best render to Claude as a designer-style critique and apply its suggested
color corrections to the SVG's fills.
"""
import base64
import io
import json
import re

import cv2
import numpy as np
from PIL import Image

import pipeline

SCORE_SIDE = 512     # comparison resolution
SEARCH_SIDE = 1024   # input resolution during the variant search (speed)
CLAUDE_SIDE = 768    # image size sent to Claude
CLAUDE_MODEL = "claude-opus-4-8"

CRITIQUE_SCHEMA = {
    "type": "object",
    "properties": {
        "color_edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from_hex": {"type": "string"},
                    "to_hex": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["from_hex", "to_hex", "reason"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["color_edits", "notes"],
    "additionalProperties": False,
}


def _svg_to_image(svg: str, side: int) -> Image.Image:
    import cairosvg

    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=side)
    return Image.open(io.BytesIO(png)).convert("RGB")


def _score(original: Image.Image, render: Image.Image) -> float:
    """Higher is better: negative Lab color error + weighted edge overlap."""
    a = np.asarray(original.resize((SCORE_SIDE, SCORE_SIDE), Image.LANCZOS))
    b = np.asarray(render.resize((SCORE_SIDE, SCORE_SIDE), Image.LANCZOS))
    lab_a = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab_b = cv2.cvtColor(b, cv2.COLOR_RGB2LAB).astype(np.float32)
    color_err = float(np.sqrt(((lab_a - lab_b) ** 2).sum(axis=2)).mean())
    ea = cv2.Canny(cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), 60, 120) > 0
    eb = cv2.Canny(cv2.cvtColor(b, cv2.COLOR_RGB2GRAY), 60, 120) > 0
    union = int((ea | eb).sum())
    edge_iou = (float((ea & eb).sum()) / union) if union else 1.0
    return -color_err + 40.0 * edge_iou


def _shrink(data: bytes, side: int) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((side, side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _variants(preset: str, colors: int, detail: int):
    base = {"preset": preset, "colors": colors, "detail": detail}
    seen, out = set(), []
    for tweak in (
        {},
        {"detail": min(100, detail + 20)},
        {"detail": max(0, detail - 20)},
        {"colors": 12},
        {"colors": 16},
        {"colors": 6},
    ):
        v = {**base, **tweak}
        key = (v["preset"], v["colors"], v["detail"])
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _claude_critique(anthropic_key: str, original: Image.Image,
                     render: Image.Image, fills: list[str]) -> dict:
    import anthropic

    def img_block(img: Image.Image) -> dict:
        small = img.copy()
        small.thumbnail((CLAUDE_SIDE, CLAUDE_SIDE), Image.LANCZOS)
        buf = io.BytesIO()
        small.save(buf, "JPEG", quality=88)
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(buf.getvalue()).decode(),
            },
        }

    client = anthropic.Anthropic(api_key=anthropic_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        output_config={"format": {"type": "json_schema", "schema": CRITIQUE_SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Original image:"},
                img_block(original),
                {"type": "text", "text": "Traced vector version of the same image:"},
                img_block(render),
                {"type": "text", "text": (
                    "You are refining an auto-traced vector graphic. Compare the vector "
                    "version to the original and identify colors that came out wrong — "
                    "e.g. white text that traced as greenish, a gold border that turned "
                    "brown, near-duplicate shades that should be one color. The vector "
                    "currently uses exactly these fill colors: "
                    + ", ".join(fills[:40]) +
                    ". Propose corrections ONLY as mappings from one of those exact "
                    "existing fill hexes (from_hex) to a better hex (to_hex), judging the "
                    "intended color from the original image (undo blur contamination: if "
                    "text reads as white in context, map its fill to pure white). Merge "
                    "near-duplicate shades by mapping them to one shared hex. Only propose "
                    "edits you are confident improve fidelity to the original's intent; "
                    "an empty list is a valid answer. Put a one-sentence overall assessment "
                    "in notes."
                )},
            ],
        }],
    )
    if response.stop_reason == "refusal":
        return {"color_edits": [], "notes": "AI critique unavailable (refused)."}
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def _apply_color_edits(svg: str, edits: list[dict]) -> tuple[str, int]:
    applied = 0
    for edit in edits:
        src, dst = edit.get("from_hex", ""), edit.get("to_hex", "")
        if not (_HEX_RE.match(src) and _HEX_RE.match(dst)):
            continue
        src = "#" + src.lstrip("#").upper()
        dst = "#" + dst.lstrip("#").upper()
        pat = re.compile(re.escape(f'fill="{src}"'), re.IGNORECASE)
        svg, n = pat.subn(f'fill="{dst}"', svg)
        applied += 1 if n else 0
    return svg, applied


def refine(data: bytes, preset: str = "photo", colors: int = 0,
           detail: int = 60, anthropic_key: str | None = None) -> dict:
    original = Image.open(io.BytesIO(data)).convert("RGB")
    small_data = _shrink(data, SEARCH_SIDE)

    # -------- Level 1: measured variant search (at reduced size for speed)
    best, best_score, best_cfg = None, None, None
    baseline_score = None
    for i, cfg in enumerate(_variants(preset, colors, detail)):
        try:
            r = pipeline.vectorize(small_data, cfg["preset"], cfg["colors"], cfg["detail"])
            s = _score(original, _svg_to_image(r["svg"], SCORE_SIDE))
        except Exception:  # noqa: BLE001 - a broken variant just drops out
            continue
        if i == 0:
            baseline_score = s
        if best_score is None or s > best_score:
            best, best_score, best_cfg = r, s, cfg
    if best is None:
        raise RuntimeError("all refinement variants failed")

    # re-run the winning configuration at full resolution
    result = pipeline.vectorize(data, best_cfg["preset"], best_cfg["colors"], best_cfg["detail"])
    svg = result["svg"]

    # -------- Level 2: Claude vision critique (optional)
    ai_notes = None
    edits_applied = 0
    if anthropic_key:
        try:
            fills = sorted(set(re.findall(r'fill="(#[0-9A-Fa-f]{6})"', svg)))
            critique = _claude_critique(
                anthropic_key, original, _svg_to_image(svg, CLAUDE_SIDE), fills)
            svg, edits_applied = _apply_color_edits(svg, critique.get("color_edits", []))
            ai_notes = critique.get("notes")
        except Exception as exc:  # noqa: BLE001 - degrade to level 1, keep the reason
            ai_notes = f"AI critique unavailable: {exc}"

    final_score = _score(original, _svg_to_image(svg, SCORE_SIDE))
    return {
        "svg": svg,
        "width": result["width"],
        "height": result["height"],
        "path_count": svg.count("<path"),
        "chosen": best_cfg,
        "score_baseline": round(baseline_score or 0, 2),
        "score_final": round(final_score, 2),
        "ai_notes": ai_notes,
        "ai_edits_applied": edits_applied,
    }
