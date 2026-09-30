"""
save_surrogate_model.py
────────────────────────────────────────────────────────────────────────────────
Promotes the winning surrogate model (by test R²) to artifacts/best_surrogate.pkl.

Run:  python save_surrogate_model.py
"""

import os
import shutil
import pandas as pd

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(BASE_DIR, "artifacts")


if __name__ == "__main__":
    path = os.path.join(ARTIFACTS, "results_surrogate.csv")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{path} not found — run train_surrogate.py first.")

    results = pd.read_csv(path)
    winner_row = results.loc[results["test_R2"].idxmax()]
    winner_name = winner_row["model"]

    src = os.path.join(ARTIFACTS, f"{winner_name}_surrogate.joblib")
    dst = os.path.join(ARTIFACTS, "best_surrogate.pkl")
    shutil.copyfile(src, dst)

    print(f"Winner (test_R2={winner_row['test_R2']:.3f}): {winner_name}")
    print(f"{src} -> {dst}")
