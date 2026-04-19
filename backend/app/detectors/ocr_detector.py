import cv2
import numpy as np

class OCRDetector:

    def __init__(self, langs):
        import easyocr
        self.reader = easyocr.Reader(langs, gpu=False)

    def detect(self, path):
        try:
            results = self.reader.readtext(path)
            regions = []
            texts = []

            for bbox, text, conf in results:
                texts.append(text)

                if conf < 0.4:
                    x_min = int(min(p[0] for p in bbox))
                    y_min = int(min(p[1] for p in bbox))
                    x_max = int(max(p[0] for p in bbox))
                    y_max = int(max(p[1] for p in bbox))

                    regions.append({
                        "bbox":[x_min,y_min,x_max-x_min,y_max-y_min],
                        "severity":1-conf,
                        "type":"low_ocr_confidence",
                        "details":f"Low OCR confidence: {conf:.2f}"
                    })

            full_text = " ".join(texts)

            # Numeric inconsistency detection
            nums = [int(s) for s in full_text.split() if s.isdigit()]
            if len(nums)>=2 and max(nums)-min(nums)>50:
                regions.append({
                    "bbox":[0,0,100,40],
                    "severity":0.6,
                    "type":"numeric_inconsistency",
                    "details":"Large numeric mismatch detected"
                })

            return {
                "is_forged": len(regions)>=2,
                "confidence": min(1.0, len(regions)/6),
                "plain_english": f"{len(regions)} OCR anomalies detected",
                "details":{"text":full_text[:500]},
                "suspicious_regions":regions
            }

        except Exception as e:
            return {
                "is_forged":False,
                "confidence":0,
                "plain_english":str(e),
                "details":{},
                "suspicious_regions":[]
            }