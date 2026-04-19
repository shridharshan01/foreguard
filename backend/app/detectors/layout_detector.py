import cv2
import numpy as np


class LayoutDetector:
    """Layout anomaly detection — broken lines, white patches, noise islands."""

    def detect(self, image_path: str) -> dict:
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Cannot read image")

            img_h, img_w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            suspicious_regions = []
            details: dict = {}

            # ── 1. White/light patch detection (white-out / cover-up) ────────
            # Stricter: require that surrounding context is meaningfully darker
            _, bright_mask = cv2.threshold(gray, 248, 255, cv2.THRESH_BINARY)
            kernel_wp = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 12))
            bright_closed = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel_wp)
            wp_contours, _ = cv2.findContours(bright_closed, cv2.RETR_EXTERNAL,
                                               cv2.CHAIN_APPROX_SIMPLE)
            white_patch_count = 0
            for cnt in wp_contours:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                # Skip full-page white, tiny noise, and very tall blobs
                if area < 800 or area > img_h * img_w * 0.10:
                    continue
                aspect = w / h if h > 0 else 0
                if not (2.0 < aspect < 40):   # only wide, flat patches
                    continue
                # Surrounding region must be DARK (≤160) — strict test
                pad = 15
                sy = max(0, y - pad); ey = min(img_h, y + h + pad)
                sx = max(0, x - pad); ex = min(img_w, x + w + pad)
                surround = gray[sy:ey, sx:ex].copy().astype(float)
                # Mask the patch itself out before measuring surroundings
                inner_y1 = pad; inner_y2 = pad + h
                inner_x1 = pad; inner_x2 = pad + w
                surround[inner_y1:inner_y2, inner_x1:inner_x2] = np.nan
                surrounding_mean = np.nanmean(surround)
                if surrounding_mean < 160:  # context is genuinely dark
                    white_patch_count += 1
                    suspicious_regions.append({
                        'bbox': [int(x), int(y), int(w), int(h)],
                        'severity': 0.75,
                        'type': 'white_patch_coverup',
                    })

            details['white_patches_found'] = white_patch_count

            # ── 2. Broken / interrupted horizontal ruling lines ───────────────
            binary_otsu = cv2.threshold(gray, 0, 255,
                                        cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
            h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT,
                                                 (max(20, img_w // 15), 1))
            h_lines = cv2.morphologyEx(binary_otsu, cv2.MORPH_OPEN, h_kernel)
            line_contours, _ = cv2.findContours(h_lines, cv2.RETR_EXTERNAL,
                                                cv2.CHAIN_APPROX_SIMPLE)
            broken_line_count = 0
            for cnt in line_contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w < img_w * 0.25:   # line must span ≥25% of page width
                    continue
                line_roi = binary_otsu[y:y + max(h, 3), x:x + w]
                if line_roi.size == 0:
                    continue
                coverage = np.sum(line_roi > 0) / line_roi.size
                # 30–65% coverage = broken line (genuine lines are >70% filled)
                if 0.30 < coverage < 0.65:
                    broken_line_count += 1
                    suspicious_regions.append({
                        'bbox': [int(x), int(y), int(w), max(int(h), 4)],
                        'severity': 0.80,
                        'type': 'broken_ruling_line',
                    })

            details['broken_lines_found'] = broken_line_count

            # ── 3. Noise / texture discontinuity islands ─────────────────────
            blur = cv2.GaussianBlur(gray, (21, 21), 0)
            noise_map = cv2.absdiff(gray, blur)
            mean_noise = float(np.mean(noise_map))
            std_noise = float(np.std(noise_map))
            noise_threshold = mean_noise + 3.0 * std_noise  # raised from 2.5→3.0
            _, noise_mask = cv2.threshold(noise_map, noise_threshold, 255, cv2.THRESH_BINARY)
            noise_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            noise_mask = cv2.morphologyEx(noise_mask, cv2.MORPH_CLOSE, noise_kernel)
            noise_contours, _ = cv2.findContours(noise_mask, cv2.RETR_EXTERNAL,
                                                  cv2.CHAIN_APPROX_SIMPLE)
            noise_island_count = 0
            for cnt in noise_contours:
                area = cv2.contourArea(cnt)
                if 600 < area < img_h * img_w * 0.06:   # raised minimum area
                    x, y, w, h = cv2.boundingRect(cnt)
                    noise_island_count += 1
                    suspicious_regions.append({
                        'bbox': [int(x), int(y), int(w), int(h)],
                        'severity': 0.60,
                        'type': 'noise_texture_anomaly',
                    })

            details['noise_islands_found'] = noise_island_count
            details['suspicious_regions_count'] = len(suspicious_regions)

            # Require ≥2 findings to reduce false positives
            is_forged = len(suspicious_regions) >= 2
            confidence = min(1.0, len(suspicious_regions) / 5.0)

            if is_forged:
                types = list({r['type'] for r in suspicious_regions})
                plain = (
                    f"Layout analysis found {len(suspicious_regions)} anomalies "
                    f"({', '.join(types)}), suggesting the document structure was altered."
                )
            else:
                plain = "Document layout appears structurally consistent with no tampering."

            return {
                'is_forged': is_forged,
                'confidence': round(confidence, 4),
                'plain_english': plain,
                'details': details,
                'suspicious_regions': suspicious_regions,
            }

        except Exception as e:
            return {
                'is_forged': False,
                'confidence': 0.0,
                'plain_english': f'Layout analysis failed: {e}',
                'details': {'error': str(e)},
                'suspicious_regions': [],
            }