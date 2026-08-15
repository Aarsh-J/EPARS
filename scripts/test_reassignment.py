"""
Throwaway harness: forces a high-confidence Critical prediction for one real
employee (since real data lands everyone in "low confidence" today) to
exercise assess_and_recommend's recommendation-generation path, which can't
be reached naturally yet. Run: python scripts/test_reassignment.py EMP_ID
"""
import sys
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR / "epars_agent" / "agent"))
sys.path.insert(0, str(SRC_DIR / "epars_policies"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.ml import reassignment

FAKE_PREDICTION = {
    "predicted_class": "Critical",
    "predicted_probabilities": {"Low": 0.01, "Moderate": 0.04, "High": 0.15, "Critical": 0.80},
    "confidence": "high",
    "real_feature_count": 120,
    "total_feature_count": 135,
    "imputed_features": [],
    "missing_top_features": [],
    "class_thresholds": {},
    "top_contributing_features": {},
}

if __name__ == "__main__":
    emp_id = sys.argv[1] if len(sys.argv) > 1 else "EMP001"
    with patch.object(reassignment, "predict_burnout", return_value=FAKE_PREDICTION):
        result = reassignment.assess_and_recommend(emp_id)
    import json
    print(json.dumps(result, indent=2, default=str))
