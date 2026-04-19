import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance
import io


class ELADetector:
    """Error Level Analysis — detects JPEG re-compression artifacts from editing."""

    def __init__(self, quality: int = 90):
        self.quality = quality

    def detect(self, image_path: str) -> dict:
        try:
            original = Image.open(image_path).convert('RGB')
            img_h, img_w = original.size[1], original.size[0]

            # Re-compress at target quality
            buf = io.BytesIO()
            original.save(buf, 'JPEG', quality=self.quality)
            buf.seek(0)
            recompressed = Image.open(buf).convert('RGB')

            # Pixel-level difference
            ela_img = ImageChops.difference(original, recompressed)

            extrema = ela_img.getextrema()
            max_diff = max(ex[1] for ex in extrema) or 1
            scale = 255.0 / max_diff
            ela_img = ImageEnhance.Brightness(ela_img).enhance(scale)

            ela_array = np.array(ela_img)
            gray = cv2.cvtColor(ela_array, cv2.COLOR_RGB2GRAY)

            mean_ela = float(np.mean(gray))
            std_ela = float(np.std(gray))

            # Adaptive threshold: flag regions significantly above mean
            threshold = mean_ela + std_ela
            _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

            # Morphological cleanup to reduce noise
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            suspicious_regions = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 200:          # skip tiny noise specks
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                # Clamp to image bounds
                x = max(0, min(x, img_w - 1))
                y = max(0, min(y, img_h - 1))
                w = min(w, img_w - x)
                h = min(h, img_h - y)
                if w < 5 or h < 5:
                    continue
                region_mean = float(np.mean(gray[y:y + h, x:x + w]))
                severity = min(1.0, region_mean / 180.0)
                suspicious_regions.append({
                    'bbox': [x, y, w, h],
                    'severity': round(severity, 3),
                    'type': 'image_editing_artifact',
                })

            # Decision: require meaningful std AND at least one real region
            is_forged = std_ela > 25 and len(suspicious_regions) > 0
            confidence = min(1.0, std_ela / 60.0)

            # Plain-English explanation
            if is_forged:
                plain = (
                    f"ELA detected {len(suspicious_regions)} region(s) with unusually high "
                    f"re-compression error (σ={std_ela:.1f}). These areas were likely edited "
                    "after the original document was created."
                )
            else:
                plain = (
                    f"Re-compression errors are uniform (σ={std_ela:.1f}), "
                    "consistent with an unmodified document."
                )

            return {
                'is_forged': is_forged,
                'confidence': round(confidence, 4),
                'plain_english': plain,
                'details': {
                    'mean_ela': round(mean_ela, 2),
                    'std_ela': round(std_ela, 2),
                    'suspicious_regions_count': len(suspicious_regions),
                },
                'suspicious_regions': suspicious_regions,
            }

        except Exception as e:
            return {
                'is_forged': False,
                'confidence': 0.0,
                'plain_english': f'ELA could not run: {e}',
                'details': {'error': str(e)},
                'suspicious_regions': [],
            }