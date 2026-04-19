from PIL import Image
from PIL.ExifTags import TAGS
import os
from datetime import datetime

EDITING_SOFTWARE = ['photoshop','gimp','canva','snapseed','illustrator']

class MetadataDetector:

    def detect(self, path):
        issues = []
        regions = []

        try:
            img = Image.open(path)
            exif = img.getexif()

            if not exif:
                issues.append("No EXIF metadata found (possibly stripped after editing)")

            tag_map = {v:k for k,v in TAGS.items()}
            software_tag = tag_map.get("Software")

            if software_tag and software_tag in exif:
                sw = str(exif.get(software_tag)).lower()
                if any(s in sw for s in EDITING_SOFTWARE):
                    issues.append(f"Edited with software: {sw}")

            stat = os.stat(path)
            mtime = datetime.fromtimestamp(stat.st_mtime)
            ctime = datetime.fromtimestamp(stat.st_ctime)

            if abs((mtime-ctime).total_seconds()) > 3600:
                issues.append("File modified long after creation")

            if issues:
                regions.append({
                    "bbox":[0,0,120,40],
                    "severity":0.6,
                    "type":"metadata_anomaly",
                    "details":" | ".join(issues)
                })

            return {
                "is_forged": len(issues)>0,
                "confidence": min(1.0, len(issues)*0.3),
                "plain_english": "; ".join(issues) if issues else "No metadata issues",
                "details":{"issues":issues},
                "suspicious_regions":regions
            }

        except Exception as e:
            return {
                "is_forged": False,
                "confidence":0,
                "plain_english":str(e),
                "details":{},
                "suspicious_regions":[]
            }