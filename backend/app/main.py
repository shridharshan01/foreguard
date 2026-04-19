from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

import asyncio
import os
import uuid
import time
import base64
import glob
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import cv2

from app.config import Config
from app.models.schemas import DetectionResult

from app.detectors.ela_detector      import ELADetector
from app.detectors.font_detector     import FontDetector
from app.detectors.layout_detector   import LayoutDetector
from app.detectors.metadata_detector import MetadataDetector
from app.detectors.ocr_detector      import OCRDetector
from app.detectors.ml_detector       import MLDetector
from app.utils.image_utils           import ImageUtils

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger("foreguard")

# ── Thread pool for CPU-bound detector work ───────────────────────────────────
_executor = ThreadPoolExecutor(max_workers=4)


# ── Lifespan: startup + background cleanup task ───────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    Config.ensure_dirs()
    # Start background file-cleanup loop
    task = asyncio.create_task(_cleanup_loop())
    log.info("ForeGuard v3 started. Cleanup task running.")
    yield
    task.cancel()


app = FastAPI(title="ForeGuard API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Detectors (singleton, initialized once) ───────────────────────────────────
ela_detector      = ELADetector()
font_detector     = FontDetector()
layout_detector   = LayoutDetector()
metadata_detector = MetadataDetector()
ml_detector       = MLDetector()

# OCR cache: lang_key → OCRDetector  (avoids 30s reload per request)
_ocr_cache: dict[str, OCRDetector] = {}


def get_ocr_detector(lang_list: list) -> OCRDetector:
    key = ','.join(sorted(lang_list))
    if key not in _ocr_cache:
        log.info(f"[OCR] Loading models for: {key}")
        _ocr_cache[key] = OCRDetector(lang_list)
    return _ocr_cache[key]


# ── Background file cleanup ───────────────────────────────────────────────────
async def _cleanup_loop():
    while True:
        await asyncio.sleep(Config.CLEANUP_INTERVAL_SECONDS)
        _purge_old_files()


def _purge_old_files():
    now = time.time()
    ttl = Config.FILE_TTL_SECONDS
    deleted = 0
    for folder in (Config.UPLOAD_FOLDER, Config.REPORTS_FOLDER):
        for fpath in glob.glob(os.path.join(folder, '*')):
            try:
                if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > ttl:
                    os.remove(fpath)
                    deleted += 1
            except Exception:
                pass
    if deleted:
        log.info(f"[Cleanup] Purged {deleted} expired file(s).")


# ── Helpers ───────────────────────────────────────────────────────────────────
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


def _run_detectors_on_page(image_path: str, lang_list: list) -> tuple[list, list]:
    """
    Run all image-based detectors on a single page image.
    Returns (detection_results_list, all_suspicious_regions).
    Called in a thread so it doesn't block the event loop.
    """
    results = []
    regions = []

    def add(name, result):
        results.append(DetectionResult(
            detector_name=name,
            is_forged=result['is_forged'],
            confidence=result['confidence'],
            details=result['details'],
            suspicious_regions=result['suspicious_regions'],
            plain_english=result.get('plain_english', ''),
        ))
        regions.extend(result['suspicious_regions'])

    add("Error Level Analysis", ela_detector.detect(image_path))
    add("Font Consistency",      font_detector.detect(image_path))
    add("Layout Analysis",       layout_detector.detect(image_path))
    add("OCR & Text Analysis",   get_ocr_detector(lang_list).detect(image_path))
    add("Deep Learning Model",   ml_detector.detect(image_path))
    return results, regions


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}


# ── Main detection endpoint ───────────────────────────────────────────────────
@app.post("/detect")
@app.post("/analyze")
async def detect_forgery(
    file: UploadFile = File(...),
    languages: str   = Form(default="en"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in {'.png', '.jpg', '.jpeg', '.pdf', '.bmp', '.tiff', '.webp'}:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    if len(content) > Config.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit")

    file_id   = str(uuid.uuid4())
    safe_name = "".join(c for c in file.filename if c.isalnum() or c in "._-")
    safe_name = safe_name[:80]   # cap filename length
    file_path = os.path.join(Config.UPLOAD_FOLDER, f"{file_id}_{safe_name}")

    with open(file_path, "wb") as f:
        f.write(content)

    start_time = time.time()

    try:
        lang_list = [l.strip() for l in languages.split(",") if l.strip()] or ["en"]

        # ── Wrap entire analysis in timeout ──────────────────────────────────
        try:
            result = await asyncio.wait_for(
                _analyse(file_id, file_path, ext, lang_list, file.filename, start_time),
                timeout=Config.ANALYSIS_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail=f"Analysis timed out after {Config.ANALYSIS_TIMEOUT_SECONDS}s. "
                       "Try a smaller file or fewer language packs."
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"[detect] Unhandled error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Core analysis (runs inside asyncio.wait_for) ─────────────────────────────
async def _analyse(file_id, file_path, ext, lang_list, filename, start_time):
    loop = asyncio.get_event_loop()

    # ── 1. Resolve page images ────────────────────────────────────────────────
    is_pdf      = (ext == ".pdf")
    page_images = []   # list of (page_idx, pil_image, saved_path)

    if is_pdf:
        pil_pages = await loop.run_in_executor(
            _executor,
            lambda: ImageUtils.pdf_to_images(
                file_path,
                dpi=Config.PDF_DPI,
                max_pages=Config.PDF_MAX_PAGES,
            )
        )
        if not pil_pages:
            raise HTTPException(status_code=422, detail="Failed to process PDF pages")
        for idx, pil in enumerate(pil_pages):
            saved = ImageUtils.save_page_image(pil, Config.UPLOAD_FOLDER, file_id, idx)
            page_images.append((idx, pil, saved))
        log.info(f"[PDF] {filename}: {len(page_images)} page(s) extracted at {Config.PDF_DPI} DPI")
    else:
        # Single image
        page_images.append((0, None, file_path))

    total_pages = len(page_images)

    # ── 2. Metadata (file-level, run once) ────────────────────────────────────
    meta_result = await loop.run_in_executor(
        _executor, lambda: metadata_detector.detect(file_path)
    )

    # ── 3. Per-page detector runs ─────────────────────────────────────────────
    # Weights: ELA=0.22, Font=0.13, Layout=0.13, OCR=0.15, ML=0.17, Meta=0.10
    # (must sum to 0.90; remaining 0.10 reserved for meta below)
    page_weights  = [0.22, 0.13, 0.13, 0.15, 0.17]
    per_page_data = []   # one entry per page

    for page_idx, _, image_path in page_images:
        label = f"Page {page_idx + 1}/{total_pages}"
        log.info(f"[Detect] Running detectors on {label}")

        det_results, page_regions = await loop.run_in_executor(
            _executor,
            lambda ip=image_path, ll=lang_list: _run_detectors_on_page(ip, ll)
        )

        # Annotate each region with page info
        for r in page_regions:
            r['page'] = page_idx + 1

        # Per-page confidence
        page_conf = sum(
            r.confidence * w
            for r, w in zip(det_results, page_weights)
        )

        per_page_data.append({
            'page':         page_idx + 1,
            'image_path':   image_path,
            'det_results':  det_results,
            'page_regions': page_regions,
            'page_conf':    page_conf,
        })

    # ── 4. Merge results across pages ─────────────────────────────────────────
    # Overall confidence = worst-page confidence * 0.90 + metadata * 0.10
    # (forgery on ANY single page makes the whole document suspicious)
    worst_page_conf = max(pd['page_conf'] for pd in per_page_data)
    meta_conf       = meta_result['confidence'] * 0.10
    weighted_conf   = worst_page_conf * 0.90 + meta_conf

    # Collect all regions and per-detector summaries
    all_regions: list = []
    for pd in per_page_data:
        all_regions.extend(pd['page_regions'])

    # Build merged detector list (max confidence per detector across all pages)
    detector_names = ["Error Level Analysis", "Font Consistency", "Layout Analysis",
                      "OCR & Text Analysis", "Deep Learning Model"]
    merged_detectors: list[DetectionResult] = []

    for name in detector_names:
        candidates = []
        for pd in per_page_data:
            for dr in pd['det_results']:
                if dr.detector_name == name:
                    candidates.append(dr)
        if not candidates:
            continue
        # Pick the most suspicious result for this detector across all pages
        worst = max(candidates, key=lambda r: r.confidence)
        # Merge suspicious regions from ALL pages for this detector
        merged_regions = []
        for c in candidates:
            merged_regions.extend(c.suspicious_regions)
        # Enrich plain_english with page info if multi-page
        plain = worst.plain_english
        if total_pages > 1:
            flagged_pages = [
                str(pd['page'])
                for pd in per_page_data
                for dr in pd['det_results']
                if dr.detector_name == name and dr.is_forged
            ]
            if flagged_pages:
                plain += f" (flagged on page{'s' if len(flagged_pages)>1 else ''}: {', '.join(flagged_pages)})"
        merged_detectors.append(DetectionResult(
            detector_name=name,
            is_forged=worst.is_forged,
            confidence=worst.confidence,
            details=worst.details,
            suspicious_regions=merged_regions,
            plain_english=plain,
        ))

    # Add metadata as final detector
    merged_detectors.append(DetectionResult(
        detector_name="Metadata Analysis",
        is_forged=meta_result['is_forged'],
        confidence=meta_result['confidence'],
        details=meta_result['details'],
        suspicious_regions=meta_result['suspicious_regions'],
        plain_english=meta_result.get('plain_english', ''),
    ))
    all_regions.extend(meta_result['suspicious_regions'])

    forged_count = sum(1 for r in merged_detectors if r.is_forged)
    is_forged    = forged_count >= 2 or weighted_conf >= 0.45

    reasons = [r.detector_name for r in merged_detectors if r.is_forged]
    confidence_reason = (
        "High confidence due to: " + ", ".join(reasons)
        if reasons else "No strong forgery indicators detected"
    )

    # ── 5. Risk label ─────────────────────────────────────────────────────────
    if weighted_conf >= 0.70:
        risk, verdict_text = "HIGH",   "🚨 Critical — Document almost certainly forged"
    elif weighted_conf >= 0.45:
        risk, verdict_text = "MEDIUM", "⚠️ Suspicious — Manual review recommended"
    elif weighted_conf >= 0.20:
        risk, verdict_text = "LOW",    "🔎 Minor anomalies detected"
    else:
        risk, verdict_text = "CLEAR",  "✅ Document appears genuine"

    # ── 6. Visual outputs ─────────────────────────────────────────────────────
    # Generate per-page annotated + heatmap images, then stack them
    ann_imgs  = []
    heat_imgs = []
    page_previews = []   # base64 per page for frontend page selector

    for pd in per_page_data:
        img = cv2.imread(pd['image_path'])
        if img is None:
            continue
        page_regions = pd['page_regions']
        label = f"Page {pd['page']}/{total_pages}"

        ann  = ImageUtils.draw_bounding_boxes(img, page_regions, page_label=label)
        heat = ImageUtils.draw_heatmap(img, page_regions)

        ann_imgs.append(ann)
        heat_imgs.append(heat)

        # Encode original page for per-page preview
        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        page_previews.append({
            'page':     pd['page'],
            'original': "data:image/jpeg;base64," + base64.b64encode(buf).decode(),
        })

    # Stack all pages into one tall composite image
    combined_ann  = ImageUtils.stack_images_vertically(ann_imgs)
    combined_heat = ImageUtils.stack_images_vertically(heat_imgs)

    ann_path  = os.path.join(Config.REPORTS_FOLDER, f"{file_id}_ann.jpg")
    heat_path = os.path.join(Config.REPORTS_FOLDER, f"{file_id}_heat.jpg")
    cv2.imwrite(ann_path,  combined_ann)
    cv2.imwrite(heat_path, combined_heat)

    # Original: use first page for the "original document" panel
    original_b64 = image_to_base64(per_page_data[0]['image_path'])

    # ── 7. OCR text (merge all pages) ────────────────────────────────────────
    all_text  = ""
    all_langs = []
    for pd in per_page_data:
        for dr in pd['det_results']:
            if dr.detector_name == "OCR & Text Analysis":
                all_text  += dr.details.get('extracted_text', '') + "\n"
                all_langs += dr.details.get('languages_detected', [])
    all_langs = list(dict.fromkeys(all_langs))   # deduplicate preserving order

    proc_time = round(time.time() - start_time, 2)

    # ── 8. Build per-page summary for frontend ────────────────────────────────
    page_summaries = [
        {
            'page':       pd['page'],
            'confidence': round(pd['page_conf'] * 100, 1),
            'is_forged':  pd['page_conf'] >= 0.45 or
                          sum(1 for r in pd['det_results'] if r.is_forged) >= 2,
            'region_count': len(pd['page_regions']),
        }
        for pd in per_page_data
    ]

    return {
        "document_name":      filename,
        "overall_confidence": round(weighted_conf * 100, 1),
        "overall_verdict":    "FORGED" if is_forged else "GENUINE",
        "overall_risk":       risk,
        "verdict":            verdict_text,
        "confidence_reason":  confidence_reason,
        "tampering_types":    classify_types(all_regions),

        # Multi-page info
        "total_pages":    total_pages,
        "page_summaries": page_summaries,
        "page_previews":  page_previews,

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
            for r in merged_detectors
        ],

        "original_image":  original_b64,
        "annotated_image": image_to_base64(ann_path),
        "heatmap_image":   image_to_base64(heat_path),

        "languages_detected":      all_langs,
        "extracted_text":          all_text[:3000],
        "processing_time_seconds": proc_time,
    }


# ── Static mounts ─────────────────────────────────────────────────────────────
app.mount("/reports", StaticFiles(directory=Config.REPORTS_FOLDER), name="reports")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")