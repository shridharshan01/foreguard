import os


class Config:
    UPLOAD_FOLDER = "uploads"
    REPORTS_FOLDER = "reports"
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'bmp', 'tiff', 'webp'}
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

    # Detection thresholds (unified — used by detectors directly)
    ELA_STD_THRESHOLD = 25
    ELA_QUALITY = 90
    FONT_MIN_SUSPICIOUS = 3
    LAYOUT_MIN_SUSPICIOUS = 2
    OCR_CONFIDENCE_THRESHOLD = 0.45   # unified (was split between config & detector)

    # Regional language support (EasyOCR codes)
    SUPPORTED_LANGUAGES = [
        'en', 'hi', 'ta', 'te', 'kn', 'bn', 'mr',
        'gu', 'ar', 'ch_sim', 'ja', 'ko',
    ]

    @staticmethod
    def ensure_dirs():
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)