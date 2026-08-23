"""
save_models.py
────────────────────────────────────────────────────────────────────────────────
Task Assignment — Promote Best Models to Production
────────────────────────────────────────────────────────────────────────────────
Reads results_classification.csv / results_regression.csv (written by
train.py), picks the winning model for each task by test-set metric
(F1 for classification, R2 for regression), and re-saves that model's
.joblib file as a .pkl for inference.py to load.

Picking the winner from the results CSV (rather than hardcoding a model
name) means this keeps working correctly even if a re-run of train.py
changes which model comes out on top — which it did here: Random Forest
beat Gradient Boosting on this dataset once class_weight="balanced" was
added to address the known class-imbalance issue.

Run:  python save_models.py
Next: python inference.py
"""

import os
import shutil
import pandas as pd

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(BASE_DIR, "artifacts")


def promote(results_csv: str, metric: str, suffix: str, out_name: str):
    path = os.path.join(ARTIFACTS, results_csv)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{path} not found — run train.py first.")

    results = pd.read_csv(path)
    winner_row = results.loc[results[metric].idxmax()]
    winner_name = winner_row["model"]

    src = os.path.join(ARTIFACTS, f"{winner_name}_{suffix}.joblib")
    dst = os.path.join(ARTIFACTS, out_name)
    if not os.path.isfile(src):
        raise FileNotFoundError(f"{src} not found — did train.py finish successfully?")

    shutil.copyfile(src, dst)
    print(f"  Winner ({metric}={winner_row[metric]:.3f}): {winner_name}")
    print(f"  {src}  →  {dst}")
    return winner_name


if __name__ == "__main__":
    print("="*70)
    print("  PROMOTING BEST MODELS")
    print("="*70)

    print("\n[Classification: assignment_success]")
    clf_winner = promote(
        "results_classification.csv", metric="test_f1",
        suffix="clf", out_name="best_classifier.pkl",
    )

    print("\n[Regression: delay_risk_score]")
    reg_winner = promote(
        "results_regression.csv", metric="test_R2",
        suffix="reg", out_name="best_regressor.pkl",
    )

    print("\n" + "="*70)
    print(f"  Saved artifacts/best_classifier.pkl  ({clf_winner})")
    print(f"  Saved artifacts/best_regressor.pkl   ({reg_winner})")
    print("  Next: python inference.py")
    print("="*70)
