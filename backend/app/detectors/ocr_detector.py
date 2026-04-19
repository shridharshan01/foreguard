import re
from app.config import Config


# Document-type aware numeric ranges that should NOT be flagged
# e.g. years (1900-2099), percentages (0-100), grades (0-100)
_YEAR_PATTERN   = re.compile(r'\b(19|20)\d{2}\b')
_PERCENT_SUFFIX = re.compile(r'\d+\s*%')


class OCRDetector:
    """OCR-based text analysis with regional language support."""

    def __init__(self, langs: list):
        import easyocr
        self.langs  = langs
        self.reader = easyocr.Reader(langs, gpu=False)

    def detect(self, path: str) -> dict:
        try:
            results = self.reader.readtext(path)
            regions = []
            texts   = []
            conf_threshold = Config.OCR_CONFIDENCE_THRESHOLD

            for bbox, text, conf in results:
                texts.append(text)

                if conf < conf_threshold:
                    x_min = int(min(p[0] for p in bbox))
                    y_min = int(min(p[1] for p in bbox))
                    x_max = int(max(p[0] for p in bbox))
                    y_max = int(max(p[1] for p in bbox))
                    regions.append({
                        'bbox':     [x_min, y_min, x_max - x_min, y_max - y_min],
                        'severity': round(1 - conf, 3),
                        'type':     'low_ocr_confidence',
                        'details':  f"Low OCR confidence ({conf:.2f}) — text may be pasted or blurred",
                    })

            full_text = ' '.join(texts)

            # ── Smart numeric inconsistency check ────────────────────────────
            # Strip years and percentage values before comparing — they are
            # legitimately far apart (e.g. "2023" vs "87%") and should NOT fire.
            stripped = _YEAR_PATTERN.sub('', full_text)
            stripped = _PERCENT_SUFFIX.sub('', stripped)

            # Collect only short integers (1-3 digits) likely to be scores/grades
            nums = []
            for tok in stripped.split():
                tok = tok.strip('.,;:()[]')
                if tok.isdigit() and 1 <= len(tok) <= 3:
                    nums.append(int(tok))

            if len(nums) >= 3:
                nums_sorted = sorted(set(nums))
                spread = nums_sorted[-1] - nums_sorted[0]
                # Only flag if spread is suspicious AND there are very few distinct values
                # (a real doc with marks 45,72,88 has spread 43 but many values — not forged)
                if spread > 60 and len(nums_sorted) <= 4:
                    regions.append({
                        'bbox':     [0, 0, 100, 40],
                        'severity': 0.55,
                        'type':     'numeric_inconsistency',
                        'details':  f"Suspicious numeric spread ({nums_sorted[0]}–{nums_sorted[-1]}) "
                                    f"across only {len(nums_sorted)} distinct values",
                    })

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
                    'text':                  full_text[:500],
                    'languages_detected':    detected_langs,
                    'extracted_text':        full_text[:2000],
                    'total_text_blocks':     len(results),
                    'low_confidence_blocks': sum(1 for r in regions
                                                 if r['type'] == 'low_ocr_confidence'),
                },
                'suspicious_regions': regions,
            }

        except Exception as e:
            return {
                'is_forged':  False,
                'confidence': 0.0,
                'plain_english': f'OCR analysis failed: {e}',
                'details':    {'error': str(e)},
                'suspicious_regions': [],
            }

    @staticmethod
    def _detect_script_mix(text: str) -> list:
        scripts = []
        if any('\u0900' <= c <= '\u097f' for c in text): scripts.append('Devanagari (Hindi/Marathi)')
        if any('\u0b80' <= c <= '\u0bff' for c in text): scripts.append('Tamil')
        if any('\u0c00' <= c <= '\u0c7f' for c in text): scripts.append('Telugu')
        if any('\u0c80' <= c <= '\u0cff' for c in text): scripts.append('Kannada')
        if any('\u0980' <= c <= '\u09ff' for c in text): scripts.append('Bengali')
        if any('\u0600' <= c <= '\u06ff' for c in text): scripts.append('Arabic')
        if any('\u4e00' <= c <= '\u9fff' for c in text): scripts.append('Chinese')
        if any('a' <= c.lower() <= 'z' for c in text):  scripts.append('Latin')
        return scripts if scripts else ['Unknown']