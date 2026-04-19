import os


class Config:
    UPLOAD_FOLDER  = "uploads"
    REPORTS_FOLDER = "reports"
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'bmp', 'tiff', 'webp'}
    MAX_FILE_SIZE  = 20 * 1024 * 1024   # 20 MB

    # ── Detection thresholds (unified) ───────────────────────────────────────
    ELA_STD_THRESHOLD        = 25
    ELA_QUALITY              = 90
    FONT_MIN_SUSPICIOUS      = 3
    LAYOUT_MIN_SUSPICIOUS    = 2
    OCR_CONFIDENCE_THRESHOLD = 0.45

    # ── PDF multi-page settings ───────────────────────────────────────────────
    PDF_MAX_PAGES = 10      # analyse up to 10 pages
    PDF_DPI       = 200     # higher DPI → better font/OCR accuracy

    # ── File cleanup ─────────────────────────────────────────────────────────
    FILE_TTL_SECONDS         = 3600   # delete files older than 1 hour
    CLEANUP_INTERVAL_SECONDS = 1800   # run cleanup every 30 minutes

    # ── Request timeout ───────────────────────────────────────────────────────
    ANALYSIS_TIMEOUT_SECONDS = 300    # 5-minute hard cap per request

    # ── Regional language support (EasyOCR codes) ────────────────────────────
    SUPPORTED_LANGUAGES = [
        'en', 'hi', 'ta', 'te', 'kn', 'bn', 'mr',
        'gu', 'ar', 'ch_sim', 'ja', 'ko',
    ]

    @staticmethod
    def ensure_dirs():
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)