from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import os
import uuid
import time
import base64
from pathlib import Path
import cv2

from app.config import Config
from app.models.schemas import DetectionResult

# Detectors
from app.detectors.ela_detector import ELADetector
from app.detectors.font_detector import FontDetector
from app.detectors.layout_detector import LayoutDetector
from app.detectors.metadata_detector import MetadataDetector
from app.detectors.ocr_detector import OCRDetector
from app.detectors.ml_detector import MLDetector

from app.utils.image_utils import ImageUtils

# ─────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────
app = FastAPI(title="ForeGuard API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Config.ensure_dirs()

# ─────────────────────────────────────────────
# Initialize Detectors ONCE at startup
# (OCRDetector is lazy-initialized per request
#  because language selection is dynamic)
# ─────────────────────────────────────────────
ela_detector      = ELADetector()
font_detector     = FontDetector()
layout_detector   = LayoutDetector()
metadata_detector = MetadataDetector()
ml_detector       = MLDetector()

# OCR cache: lang_key → OCRDetector instance
# This avoids re-loading EasyOCR models (10-30s) on every request
_ocr_cache: dict = {}


def get_ocr_detector(lang_list: list) -> OCRDetector:
    key = ','.join(sorted(lang_list))
    if key not in _ocr_cache:
        print(f"[OCR] Loading models for languages: {key}")
        _ocr_cache[key] = OCRDetector(lang_list)
    return _ocr_cache[key]


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def image_to_base64(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def classify_types(regions: list) -> list:
    types = set()
    for r in regions:
        t = r.get("type", "").lower()
        if any(x in t for x in ["font", "text", "ocr", "numeric", "alignment"]):
            types.add("TEXT_MANIPULATION")
        elif any(x in t for x in ["image", "ela", "editing"]):
            types.add("IMAGE_EDITING")
        elif any(x in t for x in ["layout", "patch", "line", "noise"]):
            types.add("LAYOUT_TAMPERING")
        elif "metadata" in t:
            types.add("METADATA_TAMPERING")
    return list(types)


# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ─────────────────────────────────────────────
# Main Detection Endpoint
# ─────────────────────────────────────────────
@app.post("/detect")
@app.post("/analyze")
async def detect_forgery(
    file: UploadFile = File(...),
    languages: str = Form(default="en"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in {'.png', '.jpg', '.jpeg', '.pdf', '.bmp', '.tiff', '.webp'}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    if len(content) > Config.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit")

    file_id = str(uuid.uuid4())
    safe_name = "".join(c for c in file.filename if c.isalnum() or c in "._-")
    file_path = os.path.join(Config.UPLOAD_FOLDER, f"{file_id}_{safe_name}")

    with open(file_path, "wb") as f:
        f.write(content)

    start_time = time.time()

    try:
        image_path = file_path

        # PDF → Image conversion
        if ext == ".pdf":
            images = ImageUtils.pdf_to_images(file_path)
            if not images:
                raise HTTPException(status_code=422, detail="Failed to process PDF")
            image_path = os.path.join(Config.UPLOAD_FOLDER, f"{file_id}_page.jpg")
            images[0].save(image_path, "JPEG")

        lang_list = [l.strip() for l in languages.split(",") if l.strip()] or ["en"]

        # ─────────────────────────────
        # Run Detectors
        # ─────────────────────────────
        detection_results = []
        all_regions = []

        def add_result(name: str, result: dict):
            detection_results.append(DetectionResult(
                detector_name=name,
                is_forged=result['is_forged'],
                confidence=result['confidence'],
                details=result['details'],
                suspicious_regions=result['suspicious_regions'],
                plain_english=result.get('plain_english', ''),
            ))
            all_regions.extend(result['suspicious_regions'])

        add_result("Error Level Analysis",  ela_detector.detect(image_path))
        add_result("Font Consistency",       font_detector.detect(image_path))
        add_result("Layout Analysis",        layout_detector.detect(image_path))
        add_result("Metadata Analysis",      metadata_detector.detect(file_path))

        ocr_result = get_ocr_detector(lang_list).detect(image_path)
        add_result("OCR & Text Analysis", ocr_result)

        add_result("Deep Learning Model", ml_detector.detect(image_path))

        # ─────────────────────────────
        # Weighted Decision Logic
        # Weights: ELA=0.25, Font=0.15, Layout=0.15, Meta=0.10, OCR=0.15, ML=0.20
        # ─────────────────────────────
        weights = [0.25, 0.15, 0.15, 0.10, 0.15, 0.20]
        weighted_conf = sum(r.confidence * w for r, w in zip(detection_results, weights))
        forged_count  = sum(r.is_forged for r in detection_results)
        is_forged     = forged_count >= 2 or weighted_conf >= 0.45

        # ─────────────────────────────
        # Risk & Verdict Labels
        # ─────────────────────────────
        reasons = [r.detector_name for r in detection_results if r.is_forged]
        confidence_reason = (
            "High confidence due to: " + ", ".join(reasons)
            if reasons else "No strong forgery indicators detected"
        )

        if weighted_conf >= 0.70:
            risk = "HIGH"
            verdict_text = "🚨 Critical — Document almost certainly forged"
        elif weighted_conf >= 0.45:
            risk = "MEDIUM"
            verdict_text = "⚠️ Suspicious — Manual review recommended"
        elif weighted_conf >= 0.20:
            risk = "LOW"
            verdict_text = "🔎 Minor anomalies detected"
        else:
            risk = "CLEAR"
            verdict_text = "✅ Document appears genuine"

        # ─────────────────────────────
        # Visual Outputs
        # ─────────────────────────────
        img = cv2.imread(image_path)
        heatmap    = ImageUtils.draw_heatmap(img, all_regions)
        annotated  = ImageUtils.draw_bounding_boxes(img, all_regions)

        heatmap_path   = os.path.join(Config.REPORTS_FOLDER, f"{file_id}_heat.jpg")
        annotated_path = os.path.join(Config.REPORTS_FOLDER, f"{file_id}_ann.jpg")
        cv2.imwrite(heatmap_path, heatmap)
        cv2.imwrite(annotated_path, annotated)

        # Base64-encode original for frontend preview
        original_b64 = image_to_base64(image_path)

        # ─────────────────────────────
        # Response
        # ─────────────────────────────
        return JSONResponse(content={
            "document_name":      file.filename,
            "overall_confidence": round(weighted_conf * 100, 1),
            "overall_verdict":    "FORGED" if is_forged else "GENUINE",
            "overall_risk":       risk,
            "verdict":            verdict_text,
            "confidence_reason":  confidence_reason,
            "tampering_types":    classify_types(all_regions),

            "detectors": [
                {
                    "name":               r.detector_name,
                    "detector_name":      r.detector_name,
                    "is_forged":          r.is_forged,
                    "confidence":         round(r.confidence * 100, 1),
                    "details":            r.details,
                    "suspicious_regions": r.suspicious_regions,
                    "plain_english":      r.plain_english,
                }
                for r in detection_results
            ],

            "original_image":  original_b64,
            "annotated_image": image_to_base64(annotated_path),
            "heatmap_image":   image_to_base64(heatmap_path),

            "languages_detected": ocr_result.get("details", {}).get("languages_detected", lang_list),
            "extracted_text":     ocr_result.get("details", {}).get("extracted_text", ""),

            "processing_time_seconds": round(time.time() - start_time, 2),
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# Static File Mounts
# ─────────────────────────────────────────────
app.mount("/reports", StaticFiles(directory=Config.REPORTS_FOLDER), name="reports")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")