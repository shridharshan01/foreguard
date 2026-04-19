from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from enum import Enum


class RiskLevel(str, Enum):
    CLEAR = "CLEAR"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DetectionResult(BaseModel):
    detector_name: str
    is_forged: bool
    confidence: float           # 0.0 – 1.0
    details: Dict[str, Any]
    suspicious_regions: List[Dict[str, Any]]
    plain_english: str = ""


class ForgeryReport(BaseModel):
    document_name: str
    overall_verdict: str
    overall_confidence: float
    overall_risk: RiskLevel = RiskLevel.CLEAR
    verdict: str = ""
    detection_results: List[DetectionResult]
    summary: Dict[str, float]
    heatmap_path: Optional[str] = None
    annotated_path: Optional[str] = None
    report_path: Optional[str] = None
    extracted_text: str = ""
    languages_detected: List[str] = []
    processing_time_seconds: float = 0.0