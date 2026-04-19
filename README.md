# ForeGuard — Explainable AI for Document Forgery Detection

> AI-powered, multi-layer document forgery detection with explainable outputs and regional language support.

---

## 🚀 Quick Start (Windows)

```batch
start.bat
```

Then open **http://localhost:8000** in your browser.

---

## Manual Setup

### 1. Install dependencies

```powershell
cd backend
pip install -r requirements.txt
```

### 2. Start the server

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### 3. Open the app

Visit **http://localhost:8000** in your browser.

---

## Detection Pipeline

| Module | What it detects | Method |
|---|---|---|
| **ELA** | Image editing artifacts | JPEG re-compression → pixel difference heatmap |
| **Font Analysis** | Mixed fonts / replaced text | Connected-component character height distribution |
| **Layout Analysis** | Structural tampering, white-out patches | Hough lines + white-patch detection + noise profiling |
| **Metadata EXIF** | Editing software, timestamp gaps | Pillow EXIF extraction + software signature matching |
| **OCR + Regional** | Pasted text, language extraction | EasyOCR (12 languages) + background consistency check |

---

## Supported Languages

English · Hindi · Tamil · Telugu · Kannada · Bengali · Marathi · Gujarati · Arabic · Chinese · Japanese · Korean

> EasyOCR downloads language model weights (~100 MB) on first use. Requires internet access.

---

## API Reference

### `POST /analyze`

Upload a document and receive a full forgery report.

**Form fields:**
- `file` — document file (JPG, PNG, PDF, BMP, TIFF, WebP, max 20 MB)
- `languages` — comma-separated language codes (default: `en`)

**Response:**
```json
{
  "document_name": "certificate.jpg",
  "overall_confidence": 72.4,
  "overall_risk": "HIGH",
  "verdict": "🚨 Critical — Document almost certainly forged",
  "summary": "...",
  "detectors": [...],
  "annotated_image": "<base64>",
  "original_image": "<base64>",
  "languages_detected": ["en", "hi"],
  "extracted_text": "...",
  "processing_time_seconds": 3.2
}
```

### `GET /health`

Returns `{"status": "ok"}`.

---

## Project Structure

```
foreguard/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app
│   │   ├── config.py                # Global settings
│   │   ├── models/schemas.py        # Pydantic models
│   │   ├── detectors/
│   │   │   ├── ela_detector.py
│   │   │   ├── font_detector.py
│   │   │   ├── layout_detector.py
│   │   │   ├── metadata_detector.py
│   │   │   └── ocr_detector.py
│   │   └── utils/
│   │       ├── image_utils.py
│   │       └── report_generator.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/app.js
├── start.bat
└── README.md
```

---

## Explainability Report

Each analysis returns:
- **Overall forgery confidence** (0–100%)
- **Risk level**: CLEAR / LOW / MEDIUM / HIGH
- **Per-detector findings** in plain English
- **Annotated document image** with colour-coded bounding boxes:
  - 🔴 Red — High risk regions
  - 🟠 Orange — Medium risk
  - 🟡 Cyan-yellow — Low risk
- **Extracted OCR text** with language detection

---

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn
- **Computer Vision**: OpenCV, Pillow
- **ELA**: Custom JPEG re-compression pipeline
- **OCR**: EasyOCR (GPU optional, CPU default)
- **PDF Support**: PyMuPDF (no Poppler required)
- **Frontend**: Pure HTML + CSS + Vanilla JS
