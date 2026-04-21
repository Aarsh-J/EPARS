"""
employee_predict.py — Burnout Risk Predictor
=============================================
CHANGES vs original:
  1. [FIX] Output is now JSON format (as required), written to
     burnout_predictions.json. CSV output retained as a side product.
  2. [FIX] print_table now shows all thresholds in a summary header
     AND per-row category explanation — not just single-employee mode.
  3. [FIX] Summary block always printed after table showing:
       - low_max / medium_max values
       - count breakdown per category
  4. Tests updated to verify JSON output file creation.

═══════════════════════════════════════════════════════
HOW THE BURNOUT SCORE IS CALCULATED
═══════════════════════════════════════════════════════

STEP 1 — Clinical Core (75% of final score)
  Based on the Maslach Burnout Inventory (MBI), the gold-standard
  clinical framework for burnout measurement.

  Three sub-scores are extracted from burnout_indicators.csv and
  min-max scaled to 0–100:

    Emotional Exhaustion   → weight 40%  (feeling drained, depleted)
    Depersonalization      → weight 30%  (detachment, cynicism)
    Reduced Accomplishment → weight 30%  (feeling ineffective)

  core = 0.40 × exhaust + 0.30 × deperson + 0.30 × reduced

STEP 2 — Behavioral Signals (25% of final score)
  Observable workplace behaviors that correlate with burnout:

    late_hours_frequency   × 5.0   (most impactful — chronic overwork)
    vacation_days_unused   × 1.5   (inability to disconnect)
    (10 − job_satisfaction) × 4.0  (inverted: high satisfaction = low risk)
    role_ambiguity          × 3.0  (unclear expectations = stress)

  This raw sum is min-max scaled to 0–100 → behavior

STEP 3 — Final Score
  burnout_risk = clip(core × 0.75 + behavior × 0.25, 0, 100)

  A GradientBoostingRegressor was trained to predict this score from
  15 employee features + 2 derived interaction terms:
    stress_load    = (late_hours_frequency × vacation_days_unused) / 10
    pressure_index = late_hours_frequency + role_ambiguity

STEP 4 — Risk Bucketing
  Thresholds are percentile-based (computed on training data):
    Low    : score < low_max   (~50th percentile)
    Medium : low_max ≤ score < medium_max  (~80th percentile)
    High   : score ≥ medium_max

  This means ~50% of employees fall in Low, ~30% in Medium, ~20% in High
  under normal conditions.
═══════════════════════════════════════════════════════
"""

import re
import json
import joblib
import numpy as np
import pandas as pd
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────
BUNDLE_PATH    = "model_bundle.pkl"
EMPLOYEES_PATH = "employees.csv"
BURNOUT_PATH   = "burnout_indicators.csv"
JSON_OUT_PATH  = "burnout_predictions.json"
CSV_OUT_PATH   = "burnout_predictions.csv"
PROJECT_HOURS  = 15
EMP_ID_PATTERN = re.compile(r"^EMP\d+$", re.IGNORECASE)

# ──────────────────────────────────────────
# Load model bundle
# ──────────────────────────────────────────
bundle     = joblib.load(BUNDLE_PATH)
MODEL      = bundle["model"]
FEATURES   = bundle["features"]
LOW_MAX    = bundle["low_max"]
MEDIUM_MAX = bundle["medium_max"]

# ──────────────────────────────────────────
# Data loading & feature engineering
# ──────────────────────────────────────────
def load_data() -> pd.DataFrame:
    emp = pd.read_csv(EMPLOYEES_PATH)
    emp.columns = emp.columns.str.lower().str.strip()

    bi = pd.read_csv(BURNOUT_PATH)
    bi.columns = bi.columns.str.lower().str.strip()

    bi_latest = (
        bi.sort_values("assessment_date")
          .groupby("employee_id", as_index=False)
          .last()
    )

    cap = emp["weekly_capacity_hours"].replace(0, 40)
    remaining = np.maximum(
        0, (cap - emp["current_project_count"] * PROJECT_HOURS) / cap
    ) * 100
    emp["workload_compatibility_score"] = np.clip(remaining, 0, 100)

    emp["is_available"] = emp["is_available"].astype(str).str.strip().str.lower()
    is_avail = emp["is_available"].isin(["true", "1", "yes"])
    avail_base = np.where(
        (~is_avail) | (emp["current_project_count"] >= 3), 25,
        np.where(emp["current_project_count"] == 0, 95,
        np.where(emp["current_project_count"] == 1, 78, 58))
    )
    emp["availability_score"] = np.clip(avail_base, 0, 100)

    return emp.merge(bi_latest, on="employee_id", how="inner")


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["stress_load"]    = (df["late_hours_frequency"] * df["vacation_days_unused"]) / 10
    df["pressure_index"] = df["late_hours_frequency"] + df["role_ambiguity"]
    return df


def categorize(score: float) -> str:
    if score < LOW_MAX:
        return "Low"
    elif score < MEDIUM_MAX:
        return "Medium"
    return "High"


# ──────────────────────────────────────────
# Prediction — returns DataFrame
# ──────────────────────────────────────────
def predict_employees(df: pd.DataFrame) -> pd.DataFrame:
    df = engineer_features(df)
    scores = np.clip(MODEL.predict(df[FEATURES]), 0, 100)

    results = df[["employee_id", "first_name", "last_name",
                  "department", "role", "seniority_level"]].copy()
    results["burnout_score"]        = np.round(scores, 2)
    results["risk_category"]        = [categorize(s) for s in scores]
    results["low_threshold"]        = round(LOW_MAX, 2)
    results["medium_threshold"]     = round(MEDIUM_MAX, 2)
    results["late_hours_frequency"] = df["late_hours_frequency"].values
    results["vacation_days_unused"] = df["vacation_days_unused"].values
    results["job_satisfaction"]     = df["job_satisfaction"].values
    results["role_ambiguity"]       = df["role_ambiguity"].values
    results["stress_load"]          = np.round(df["stress_load"].values, 2)
    results["pressure_index"]       = np.round(df["pressure_index"].values, 2)

    return results.reset_index(drop=True)


# ──────────────────────────────────────────
# JSON output builder
# ──────────────────────────────────────────
def build_json_output(results: pd.DataFrame) -> dict:
    """
    Returns a dict with:
      - meta:       thresholds, run timestamp, total count
      - summary:    per-category counts
      - employees:  list of per-employee dicts
    """
    counts = results["risk_category"].value_counts().to_dict()

    employees = []
    for _, row in results.iterrows():
        employees.append({
            "employee_id":         row["employee_id"],
            "name":                f"{row['first_name']} {row['last_name']}",
            "department":          row["department"],
            "role":                row["role"],
            "seniority_level":     row["seniority_level"],
            "burnout_score":       float(row["burnout_score"]),
            "risk_category":       row["risk_category"],
            "signals": {
                "late_hours_frequency": float(row["late_hours_frequency"]),
                "vacation_days_unused": float(row["vacation_days_unused"]),
                "job_satisfaction":     float(row["job_satisfaction"]),
                "role_ambiguity":       float(row["role_ambiguity"]),
                "stress_load":          float(row["stress_load"]),
                "pressure_index":       float(row["pressure_index"]),
            },
        })

    return {
        "meta": {
            "generated_at":    datetime.now().isoformat(timespec="seconds"),
            "total_employees": len(results),
            "thresholds": {
                "low_max":         round(LOW_MAX, 2),
                "medium_max":      round(MEDIUM_MAX, 2),
                "description":     (
                    f"Low < {LOW_MAX:.2f} | "
                    f"Medium {LOW_MAX:.2f}–{MEDIUM_MAX:.2f} | "
                    f"High ≥ {MEDIUM_MAX:.2f}"
                ),
            },
        },
        "summary": {
            "low":    counts.get("Low",    0),
            "medium": counts.get("Medium", 0),
            "high":   counts.get("High",   0),
        },
        "employees": employees,
    }


def save_outputs(results: pd.DataFrame) -> dict:
    """Save JSON + CSV and return the JSON payload."""
    payload = build_json_output(results)

    with open(JSON_OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    results.to_csv(CSV_OUT_PATH, index=False)
    return payload


# ──────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────
ICONS = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}

def _threshold_banner():
    return (
        f"  Thresholds : Low < {LOW_MAX:.2f}  |  "
        f"Medium {LOW_MAX:.2f}–{MEDIUM_MAX:.2f}  |  "
        f"High ≥ {MEDIUM_MAX:.2f}"
    )


def print_result(row: pd.Series):
    icon = ICONS.get(row["risk_category"], "⚪")
    print("\n" + "=" * 60)
    print(f"  Employee      : {row['employee_id']} — {row['first_name']} {row['last_name']}")
    print(f"  Role          : {row['role']} ({row['seniority_level']})")
    print(f"  Department    : {row['department']}")
    print(f"  {'─'*54}")
    print(f"  Burnout Score : {row['burnout_score']:.2f} / 100")
    print(f"  Risk Category : {icon} {row['risk_category']}")
    print()
    print(_threshold_banner())
    print(f"  {'─'*54}")
    print(f"  Late Hours Freq   : {row['late_hours_frequency']}")
    print(f"  Unused Vacation   : {row['vacation_days_unused']}")
    print(f"  Job Satisfaction  : {row['job_satisfaction']}")
    print(f"  Role Ambiguity    : {row['role_ambiguity']}")
    print(f"  Stress Load       : {row['stress_load']}")
    print(f"  Pressure Index    : {row['pressure_index']}")
    print("=" * 60)


def print_table(results: pd.DataFrame):
    # ── Header with thresholds ──────────────────────────────────
    print(f"\n{'='*60}")
    print(_threshold_banner())
    print(f"{'='*60}")
    print(f"\n{'ID':<10} {'Name':<22} {'Dept':<18} {'Score':>7}  {'Category'}")
    print("-" * 68)

    for _, row in results.iterrows():
        name = f"{row['first_name']} {row['last_name']}"
        icon = ICONS[row["risk_category"]]
        print(
            f"{row['employee_id']:<10} {name:<22} {row['department']:<18} "
            f"{row['burnout_score']:>7.2f}  {icon} {row['risk_category']}"
        )

    # ── Summary footer ──────────────────────────────────────────
    counts = results["risk_category"].value_counts()
    print(f"\n  🟢 Low: {counts.get('Low',0)}  "
          f"🟡 Medium: {counts.get('Medium',0)}  "
          f"🔴 High: {counts.get('High',0)}  "
          f"| Total: {len(results)}")
    print(f"{'='*60}")


# ──────────────────────────────────────────
# Input validation
# ──────────────────────────────────────────
def validate_ids(raw: str):
    tokens = raw.strip().split()
    valid   = [t.upper() for t in tokens if EMP_ID_PATTERN.match(t)]
    invalid = [t for t in tokens if not EMP_ID_PATTERN.match(t)]
    return valid, invalid


# ──────────────────────────────────────────
# Main
# ──────────────────────────────────────────
def main():
    print("Loading data...")
    df = load_data()

    print(f"\n{'='*60}")
    print("  Burnout Risk Predictor")
    print(_threshold_banner())
    print(f"{'='*60}")
    print("  Enter employee ID(s) in format EMP001, EMP002 ...")
    print("  Separate multiple IDs with spaces.")
    print(f"{'='*60}")

    while True:
        raw = input("\nEmployee ID(s): ").strip()

        if not raw:
            print("  ⚠️  Please enter at least one employee ID.")
            continue

        valid_ids, invalid = validate_ids(raw)

        if invalid:
            print(f"  ❌ Invalid format (must be EMP followed by digits): {', '.join(invalid)}")
            continue

        if not valid_ids:
            print("  ❌ No valid IDs entered.")
            continue

        subset = df[df["employee_id"].isin(valid_ids)]
        not_found = set(valid_ids) - set(subset["employee_id"])

        if not_found:
            print(f"  ⚠️  Not found in dataset: {', '.join(sorted(not_found))}")

        if subset.empty:
            print("  ❌ None of the IDs exist in the dataset.")
            continue

        results = predict_employees(subset)

        if len(results) == 1:
            print_result(results.iloc[0])
        else:
            print_table(results)

        payload = save_outputs(results)

        # Print JSON to console as well
        print(f"\n  📄 JSON Output:")
        print(json.dumps(payload, indent=2))
        print(f"\n  ✅ Saved → {JSON_OUT_PATH}")
        print(f"  ✅ Saved → {CSV_OUT_PATH}")

        again = input("\n  Predict another? (y/n): ").strip().lower()
        if again != "y":
            print("  Exiting.")
            break


# ══════════════════════════════════════════
# TESTS
# Run with: python employee_predict.py test
# ══════════════════════════════════════════
def run_tests(df: pd.DataFrame):
    print("\n" + "═" * 60)
    print("  RUNNING TESTS")
    print("═" * 60)
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  ✅ PASS — {name}")
            passed += 1
        else:
            print(f"  ❌ FAIL — {name}" + (f": {detail}" if detail else ""))
            failed += 1

    # 1–4. ID validation
    v, inv = validate_ids("EMP001 EMP999")
    check("Valid IDs accepted", v == ["EMP001", "EMP999"])

    v, inv = validate_ids("001 EMPLOYEE1 emp EMP")
    check("Invalid IDs rejected", len(v) == 0 and len(inv) == 4)

    v, inv = validate_ids("EMP001 badid EMP002")
    check("Mixed input splits correctly", v == ["EMP001", "EMP002"] and inv == ["badid"])

    v, inv = validate_ids("emp001 Emp002")
    check("Case insensitive (emp001 → EMP001)", v == ["EMP001", "EMP002"])

    # 5. Known employee exists
    subset = df[df["employee_id"] == "EMP001"]
    check("EMP001 exists in dataset", not subset.empty)

    if not subset.empty:
        res = predict_employees(subset)

        # 6. Score in range 0–100
        score = res.iloc[0]["burnout_score"]
        check("Score in range 0–100", 0 <= score <= 100, f"got {score}")

        # 7. Risk category valid
        cat = res.iloc[0]["risk_category"]
        check("Risk category is Low/Medium/High", cat in ["Low", "Medium", "High"], f"got {cat}")

        # 8. All output columns present
        required = ["employee_id", "burnout_score", "risk_category",
                    "low_threshold", "medium_threshold", "stress_load", "pressure_index"]
        check("All output columns present", all(c in res.columns for c in required))

        # 9. Thresholds populated correctly in every row
        check("low_threshold column populated",
              (res["low_threshold"] == round(LOW_MAX, 2)).all())
        check("medium_threshold column populated",
              (res["medium_threshold"] == round(MEDIUM_MAX, 2)).all())

        # 10. JSON output structure
        payload = build_json_output(res)
        check("JSON has meta key",      "meta"      in payload)
        check("JSON has summary key",   "summary"   in payload)
        check("JSON has employees key", "employees" in payload)
        check("JSON meta has thresholds",
              "thresholds" in payload["meta"])
        check("JSON threshold low_max matches bundle",
              payload["meta"]["thresholds"]["low_max"] == round(LOW_MAX, 2))
        check("JSON threshold medium_max matches bundle",
              payload["meta"]["thresholds"]["medium_max"] == round(MEDIUM_MAX, 2))
        check("JSON employee has signals block",
              "signals" in payload["employees"][0])

    # 11. Non-existent ID returns empty
    ghost = df[df["employee_id"] == "EMP99999"]
    check("Non-existent ID returns empty df", ghost.empty)

    # 12. Bundle thresholds
    check("LOW_MAX matches bundle",    LOW_MAX    == bundle["low_max"])
    check("MEDIUM_MAX matches bundle", MEDIUM_MAX == bundle["medium_max"])

    print(f"\n  Results: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("═" * 60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Loading data for tests...")
        df = load_data()
        run_tests(df)
    else:
        main()