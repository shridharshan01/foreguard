import os


class Config:
    UPLOAD_FOLDER = "uploads"
    REPORTS_FOLDER = "reports"
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'bmp', 'tiff', 'webp'}
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

    # Detection thresholds
    ELA_STD_THRESHOLD = 25          # lower = more sensitive
    ELA_QUALITY = 90
    FONT_MIN_SUSPICIOUS = 3
    LAYOUT_MIN_SUSPICIOUS = 2
    OCR_CONFIDENCE_THRESHOLD = 0.45

    # Regional language support (EasyOCR codes)
    SUPPORTED_LANGUAGES = [
        'en',   # English
        'hi',   # Hindi
        'ta',   # Tamil
        'te',   # Telugu
        'kn',   # Kannada
        'bn',   # Bengali
        'mr',   # Marathi  (uses Devanagari model)
        'gu',   # Gujarati
        'ar',   # Arabic
        'ch_sim',  # Chinese Simplified
        'ja',   # Japanese
        'ko',   # Korean
    ]

    @staticmethod
    def ensure_dirs():
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)