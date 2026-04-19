from PIL import Image
from PIL.ExifTags import TAGS
import os
from datetime import datetime

EDITING_SOFTWARE = ['photoshop', 'gimp', 'canva', 'snapseed', 'illustrator',
                    'lightroom', 'paint', 'affinity', 'pixlr']

# Tag 0x0131 = Software (decimal 305) — hardcoded for robustness across Pillow versions
SOFTWARE_TAG_ID = 305


class MetadataDetector:

    def detect(self, path: str) -> dict:
        issues = []
        regions = []

        try:
            img = Image.open(path)
            exif = img.getexif()

            if not exif:
                issues.append("No EXIF metadata found — possibly stripped after editing")
            else:
                # Robust software tag lookup using hardcoded tag ID
                sw = str(exif.get(SOFTWARE_TAG_ID, '')).lower().strip()
                if sw and any(s in sw for s in EDITING_SOFTWARE):
                    issues.append(f"Document was processed by editing software: '{sw}'")

                # Check for DateTime vs DateTimeOriginal mismatch
                DATETIME_ORIGINAL = 36867   # 0x9003
                DATETIME_MODIFIED = 306     # 0x0132
                dt_orig = exif.get(DATETIME_ORIGINAL)
                dt_mod  = exif.get(DATETIME_MODIFIED)
                if dt_orig and dt_mod and dt_orig != dt_mod:
                    issues.append(
                        f"Modification timestamp differs from original: "
                        f"orig={dt_orig}, modified={dt_mod}"
                    )

            # Filesystem mtime vs ctime gap
            stat = os.stat(path)
            mtime = datetime.fromtimestamp(stat.st_mtime)
            ctime = datetime.fromtimestamp(stat.st_ctime)
            gap_hours = abs((mtime - ctime).total_seconds()) / 3600
            if gap_hours > 1:
                issues.append(
                    f"File modified {gap_hours:.1f}h after creation "
                    "(normal for scanned/converted docs, suspicious if original)"
                )

            if issues:
                regions.append({
                    'bbox': [0, 0, 120, 40],
                    'severity': min(1.0, 0.3 * len(issues)),
                    'type': 'metadata_anomaly',
                    'details': ' | '.join(issues),
                })

            return {
                'is_forged': len(issues) > 0,
                'confidence': min(1.0, len(issues) * 0.3),
                'plain_english': '; '.join(issues) if issues else 'No metadata anomalies detected.',
                'details': {'issues': issues},
                'suspicious_regions': regions,
            }

        except Exception as e:
            return {
                'is_forged': False,
                'confidence': 0.0,
                'plain_english': f'Metadata analysis failed: {e}',
                'details': {'error': str(e)},
                'suspicious_regions': [],
            }