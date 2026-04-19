import cv2
import numpy as np
from app.config import Config


class OCRDetector:
    """OCR-based text analysis with regional language support."""

    def __init__(self, langs: list):
        import easyocr
        self.langs = langs
        self.reader = easyocr.Reader(langs, gpu=False)

    def detect(self, path: str) -> dict:
        try:
            results = self.reader.readtext(path)
            regions = []
            texts = []
            conf_threshold = Config.OCR_CONFIDENCE_THRESHOLD  # unified from config

            for bbox, text, conf in results:
                texts.append(text)

                if conf < conf_threshold:
                    x_min = int(min(p[0] for p in bbox))
                    y_min = int(min(p[1] for p in bbox))
                    x_max = int(max(p[0] for p in bbox))
                    y_max = int(max(p[1] for p in bbox))

                    regions.append({
                        'bbox': [x_min, y_min, x_max - x_min, y_max - y_min],
                        'severity': round(1 - conf, 3),
                        'type': 'low_ocr_confidence',
                        'details': f"Low OCR confidence ({conf:.2f}) — text may be pasted or blurred",
                    })

            full_text = ' '.join(texts)

            # Detect numeric inconsistency (e.g. grade vs percentage mismatch)
            nums = [int(s) for s in full_text.split() if s.isdigit() and len(s) <= 4]
            if len(nums) >= 2 and max(nums) - min(nums) > 50:
                regions.append({
                    'bbox': [0, 0, 100, 40],
                    'severity': 0.6,
                    'type': 'numeric_inconsistency',
                    'details': f"Large numeric spread detected: {min(nums)}–{max(nums)}",
                })

            # Detect abrupt language switches (mixed-script heuristic)
            detected_langs = self._detect_script_mix(full_text)

            return {
                'is_forged': len(regions) >= 2,
                'confidence': min(1.0, len(regions) / 6),
                'plain_english': (
                    f"{len(regions)} OCR anomaly/anomalies detected "
                    f"across {len(results)} text blocks."
                    if regions else
                    "All text regions read with high OCR confidence."
                ),
                'details': {
                    'text': full_text[:500],
                    'languages_detected': detected_langs,
                    'extracted_text': full_text[:2000],
                    'total_text_blocks': len(results),
                    'low_confidence_blocks': len([r for r in regions if r['type'] == 'low_ocr_confidence']),
                },
                'suspicious_regions': regions,
            }

        except Exception as e:
            return {
                'is_forged': False,
                'confidence': 0.0,
                'plain_english': f'OCR analysis failed: {e}',
                'details': {'error': str(e)},
                'suspicious_regions': [],
            }

    @staticmethod
    def _detect_script_mix(text: str) -> list:
        """Heuristic: identify which scripts appear in extracted text."""
        scripts = []
        if any('\u0900' <= c <= '\u097f' for c in text):
            scripts.append('Devanagari (Hindi/Marathi)')
        if any('\u0b80' <= c <= '\u0bff' for c in text):
            scripts.append('Tamil')
        if any('\u0c00' <= c <= '\u0c7f' for c in text):
            scripts.append('Telugu')
        if any('\u0c80' <= c <= '\u0cff' for c in text):
            scripts.append('Kannada')
        if any('\u0980' <= c <= '\u09ff' for c in text):
            scripts.append('Bengali')
        if any('\u0600' <= c <= '\u06ff' for c in text):
            scripts.append('Arabic')
        if any('\u4e00' <= c <= '\u9fff' for c in text):
            scripts.append('Chinese')
        if any('a' <= c.lower() <= 'z' for c in text):
            scripts.append('Latin')
        return scripts if scripts else ['Unknown']