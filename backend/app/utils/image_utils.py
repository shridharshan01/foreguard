import cv2
import numpy as np
from PIL import Image
from typing import List, Dict
import os


class ImageUtils:

    @staticmethod
    def preprocess_image(image_path: str) -> np.ndarray:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot load image: {image_path}")
        return img

    @staticmethod
    def resize_image(img: np.ndarray, max_dim: int = 1024) -> np.ndarray:
        h, w = img.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            return cv2.resize(img, (int(w * scale), int(h * scale)),
                              interpolation=cv2.INTER_AREA)
        return img

    @staticmethod
    def draw_heatmap(img: np.ndarray, suspicious_regions: List[Dict]) -> np.ndarray:
        if img is None:
            raise ValueError("Image is None")
        h, w = img.shape[:2]
        heatmap = np.zeros((h, w), dtype=np.float32)

        for region in suspicious_regions:
            bbox = region.get('bbox', [])
            if len(bbox) < 4:
                continue
            x, y, rw, rh = bbox
            x1 = max(0, min(int(x), w - 1))
            y1 = max(0, min(int(y), h - 1))
            x2 = max(x1 + 1, min(int(x + rw), w))
            y2 = max(y1 + 1, min(int(y + rh), h))
            severity = float(region.get('severity', 0.5))
            heatmap[y1:y2, x1:x2] += severity

        if np.max(heatmap) > 0:
            heatmap = heatmap / np.max(heatmap)

        heatmap_u8 = (heatmap * 255).astype(np.uint8)
        heatmap_colored = cv2.applyColorMap(heatmap_u8, cv2.COLORMAP_JET)
        return cv2.addWeighted(img, 0.55, heatmap_colored, 0.45, 0)

    @staticmethod
    def draw_bounding_boxes(img: np.ndarray, suspicious_regions: List[Dict],
                             page_label: str = "") -> np.ndarray:
        if img is None:
            raise ValueError("Image is None")
        out = img.copy()
        h, w = out.shape[:2]

        for region in suspicious_regions:
            bbox = region.get('bbox', [])
            if len(bbox) < 4:
                continue
            x, y, rw, rh = bbox
            x1 = max(0, min(int(x), w - 1))
            y1 = max(0, min(int(y), h - 1))
            x2 = max(x1 + 1, min(int(x + rw), w))
            y2 = max(y1 + 1, min(int(y + rh), h))

            severity = float(region.get('severity', 0.5))
            if severity >= 0.70:
                colour = (0, 0, 220)
                label = "HIGH"
            elif severity >= 0.40:
                colour = (0, 140, 255)
                label = "MED"
            else:
                colour = (200, 200, 0)
                label = "LOW"

            cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)
            region_type = region.get('type', '')[:18]
            tag = f"{label}:{region_type}"
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            ty = max(y1 - 4, th + 2)
            cv2.rectangle(out, (x1, ty - th - 2), (x1 + tw + 4, ty + 2), colour, -1)
            cv2.putText(out, tag, (x1 + 2, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

        # Stamp page label in top-left corner if provided
        if page_label:
            cv2.rectangle(out, (0, 0), (180, 28), (20, 20, 20), -1)
            cv2.putText(out, page_label, (6, 19),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 229, 255), 1, cv2.LINE_AA)

        return out

    @staticmethod
    def pdf_to_images(pdf_path: str, dpi: int = 200, max_pages: int = 10) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images using PyMuPDF.

        Args:
            pdf_path:  Path to the PDF file.
            dpi:       Render resolution. 200 DPI gives good font detail.
            max_pages: Maximum number of pages to extract.

        Returns:
            List of PIL Image objects, one per page.
        """
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            total = len(doc)
            pages_to_read = min(total, max_pages)
            images = []
            for i in range(pages_to_read):
                page = doc.load_page(i)
                pix  = page.get_pixmap(dpi=dpi)
                img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
            doc.close()
            return images
        except Exception as e:
            print(f"[ImageUtils] PDF conversion error: {e}")
            return []

    @staticmethod
    def save_page_image(pil_img: Image.Image, folder: str, file_id: str, page_idx: int) -> str:
        """Save a PIL image as JPEG and return its path."""
        path = os.path.join(folder, f"{file_id}_page{page_idx}.jpg")
        pil_img.save(path, "JPEG", quality=92)
        return path

    @staticmethod
    def stack_images_vertically(images: List[np.ndarray], gap: int = 8) -> np.ndarray:
        """
        Stack multiple annotated page images into a single tall image
        separated by a dark gap, for the combined multi-page preview.
        """
        if not images:
            return np.zeros((400, 600, 3), dtype=np.uint8)
        max_w = max(img.shape[1] for img in images)
        strips = []
        for img in images:
            h, w = img.shape[:2]
            if w < max_w:
                pad = np.zeros((h, max_w - w, 3), dtype=np.uint8)
                img = np.hstack([img, pad])
            strips.append(img)
            # Dark separator between pages
            strips.append(np.full((gap, max_w, 3), 20, dtype=np.uint8))
        return np.vstack(strips[:-1])   # drop last separator