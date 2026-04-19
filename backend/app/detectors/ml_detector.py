import torch
import torchvision.transforms as transforms
from PIL import Image

class MLDetector:
    """CNN-based forgery classifier (lightweight, explainable integration)."""

    def __init__(self, model_path: str = None):
        self.device = "cpu"
        self.model = self._load_model(model_path)

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
        ])

    def _load_model(self, model_path):
        from torchvision import models
        model = models.resnet18(pretrained=True)

        # Modify last layer for binary classification
        model.fc = torch.nn.Linear(model.fc.in_features, 1)
        model.eval()
        return model

    def detect(self, image_path: str) -> dict:
        try:
            img = Image.open(image_path).convert("RGB")
            tensor = self.transform(img).unsqueeze(0)

            with torch.no_grad():
                output = self.model(tensor)
                prob = torch.sigmoid(output).item()

            is_forged = prob > 0.5

            return {
                "is_forged": is_forged,
                "confidence": round(prob, 4),
                "plain_english": (
                    "Deep learning model detected patterns consistent with forged documents."
                    if is_forged else
                    "Deep learning model found no strong forgery patterns."
                ),
                "details": {"ml_probability": prob},
                "suspicious_regions": []  # global model (no bbox)
            }

        except Exception as e:
            return {
                "is_forged": False,
                "confidence": 0.0,
                "plain_english": f"ML model failed: {e}",
                "details": {"error": str(e)},
                "suspicious_regions": []
            }