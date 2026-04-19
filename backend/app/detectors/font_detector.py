import cv2
import numpy as np


class FontDetector:
    """Font consistency analysis using connected-component character heights."""

    def detect(self, image_path: str) -> dict:
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Cannot read image")

            img_h, img_w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            binary = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,
                blockSize=15, C=8
            )

            kernel_clean = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_clean)

            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
                binary, connectivity=8
            )

            char_heights = []
            char_boxes = []
            for i in range(1, num_labels):
                x = stats[i, cv2.CC_STAT_LEFT]
                y = stats[i, cv2.CC_STAT_TOP]
                w = stats[i, cv2.CC_STAT_WIDTH]
                h = stats[i, cv2.CC_STAT_HEIGHT]
                area = stats[i, cv2.CC_STAT_AREA]
                aspect = w / h if h > 0 else 0

                if (5 < h < img_h * 0.15 and
                        5 < w < img_w * 0.25 and
                        area > 20 and
                        0.05 < aspect < 15):
                    char_heights.append(h)
                    char_boxes.append((x, y, w, h))

            suspicious_regions = []
            details: dict = {'characters_found': len(char_heights)}

            if len(char_heights) < 5:
                details['note'] = 'Too few characters to analyse font consistency'
                return {
                    'is_forged': False,
                    'confidence': 0.0,
                    'plain_english': 'Not enough text found to assess font consistency.',
                    'details': details,
                    'suspicious_regions': [],
                }

            heights_arr = np.array(char_heights, dtype=float)
            mean_h = float(np.mean(heights_arr))
            std_h = float(np.std(heights_arr))
            details['mean_char_height_px'] = round(mean_h, 1)
            details['std_char_height_px'] = round(std_h, 1)

            seen_boxes = set()
            for (x, y, w, h) in char_boxes:
                if abs(h - mean_h) > 2.5 * std_h and std_h > 1:
                    key = (x // 4, y // 4)
                    if key in seen_boxes:
                        continue
                    seen_boxes.add(key)
                    severity = min(1.0, abs(h - mean_h) / (mean_h + 1e-6))
                    suspicious_regions.append({
                        'bbox': [int(x), int(y), int(w), int(h)],
                        'severity': round(severity, 3),
                        'type': 'font_size_anomaly',
                    })

            if mean_h > 0:
                bucket = max(1, int(mean_h * 0.8))
                row_x_starts: dict = {}
                for (x, y, w, h) in char_boxes:
                    row = y // bucket
                    row_x_starts.setdefault(row, []).append(x)

                left_margins = [min(xs) for xs in row_x_starts.values() if len(xs) > 2]
                if len(left_margins) > 2:
                    margin_std = float(np.std(left_margins))
                    details['left_margin_std_px'] = round(margin_std, 1)
                    if margin_std > img_w * 0.05:
                        median_margin = float(np.median(left_margins))
                        for row, xs in row_x_starts.items():
                            if len(xs) < 2:
                                continue
                            row_left = min(xs)
                            if abs(row_left - median_margin) > margin_std * 1.5:
                                ry = row * bucket
                                suspicious_regions.append({
                                    'bbox': [int(row_left), int(ry),
                                             int(img_w * 0.3), int(bucket)],
                                    'severity': 0.55,
                                    'type': 'text_alignment_break',
                                })

            details['suspicious_regions_count'] = len(suspicious_regions)
            is_forged = len(suspicious_regions) >= 3
            confidence = min(1.0, len(suspicious_regions) / 8.0)

            if is_forged:
                plain = (
                    f"Found {len(suspicious_regions)} font inconsistencies. "
                    f"Character heights vary significantly (mean={mean_h:.0f}px, σ={std_h:.1f}px), "
                    "suggesting text from different sources was pasted together."
                )
            else:
                plain = (
                    f"Font sizes are consistent throughout the document "
                    f"(mean height {mean_h:.0f}px, σ={std_h:.1f}px)."
                )

            return {
                'is_forged': is_forged,
                'confidence': round(confidence, 4),
                'plain_english': plain,
                'details': details,
                'suspicious_regions': suspicious_regions[:15],
            }

        except Exception as e:
            return {
                'is_forged': False,
                'confidence': 0.0,
                'plain_english': f'Font analysis failed: {e}',
                'details': {'error': str(e)},
                'suspicious_regions': [],
            }