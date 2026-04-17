# =============================================================
# MODEL 4 — TEAM FORMATION
# model4_config.py  |  Paths, mappings, and shared constants
# =============================================================

import os

# ── Paths ─────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(SCRIPT_DIR, "../../dataset")
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "output")

FEATURES_FILE = os.path.join(OUTPUT_DIR, "model4_features.csv")
MODEL_FILE    = os.path.join(OUTPUT_DIR, "model4.pkl")
METADATA_FILE = os.path.join(OUTPUT_DIR, "model4_metadata.json")

# ── Ordinal encoding maps ──────────────────────────────────────
SENIORITY_MAP = {"Junior": 1, "Mid": 2, "Senior": 3, "Lead": 4, "Principal": 5}
STRESS_MAP    = {"Low": 1, "Medium": 2, "High": 3}
TREND_MAP     = {"Decreasing": -1, "Stable": 0, "Increasing": 1}
COMPLEXITY_MAP = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}
PRIORITY_MAP   = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
FORMATION_MAP  = {"Manual": 0, "Hybrid": 1, "AI-Recommended": 2}

# ── Feature extraction settings ───────────────────────────────
WORKLOAD_LOOKBACK_WEEKS = 8     # how far back to look in workload_history

# ── Training settings ─────────────────────────────────────────
TRAIN_SIZE_RATIO = 0.8          # fraction of (time-sorted) teams used for train
RANDOM_STATE     = 42

# ── Target column and columns to drop before modelling ────────
TARGET_COL = "actual_performance_score"

# These are identifiers / leakage columns — never used as features
DROP_COLS = ["team_id", "formation_date"]
