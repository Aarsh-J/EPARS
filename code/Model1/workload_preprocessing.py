"""
=============================================================================
STEP 1 — PREPROCESSING
Model 1: Burnout Risk Classification (Gradient Boosting)
=============================================================================
Input  : employees.csv, burnout_indicators.csv, task_assignments.csv
Output : processed_data.csv     — one row per employee, features + target
         feature_columns.json   — ordered list of 135 feature names
         label_encoder.json     — class index ↔ label mapping

Run    : python step1_preprocessing.py
=============================================================================
"""

import os, json, warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ── CONFIG ───────────────────────────────────────────────────────────────────
DATA_DIR = "."           # folder containing the 3 CSVs
OUT_DIR  = "."           # where output files are saved
# ─────────────────────────────────────────────────────────────────────────────

os.makedirs(OUT_DIR, exist_ok=True)

# Ordinal maps
STRESS_MAP   = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}
FATIGUE_MAP  = {"Low": 1, "Medium": 2, "High": 3, "Severe": 4}
SLEEP_MAP    = {"Very Poor": 1, "Poor": 2, "Fair": 3, "Good": 4}
TREND_MAP    = {"Decreasing": -1, "Stable": 0, "Increasing": 1, "Rapidly Increasing": 2}
SENIORITY_MAP= {"Junior": 1, "Mid": 2, "Senior": 3, "Lead": 4, "Principal": 5}
PROD_MAP     = {"Decreasing": -1, "Stable": 0, "Increasing": 1}
EMP_STRESS_MAP={"Low": 1, "Medium": 2, "High": 3, "Very High": 4}

LABEL_MAP = {0: "Low", 1: "Moderate", 2: "High", 3: "Critical"}

# Symptom columns from burnout_indicators that are safe to use as features
# (overall_burnout_risk is excluded — it IS the target)
SYMPTOM_COLS = [
    "emotional_exhaustion_score", "depersonalization_score",
    "reduced_accomplishment_score", "workload_pressure", "role_ambiguity",
    "work_life_conflict", "job_demands", "job_control", "role_conflict",
    "late_hours_frequency", "weekend_work_frequency", "missed_breaks_count",
    "vacation_days_unused", "sick_days_taken", "absence_rate",
    "phys_health", "mental_supp",
    "energy_level", "job_satisfaction", "engagement_score", "motivation_level",
    "sense_of_accomplishment", "organizational_commitment", "social_support_score",
    "manager_support_score", "team_cohesion", "workplace_relationships",
    "isolation_feeling", "coping_effectiveness", "resource_adequacy",
    "work_recovery_ability", "resilience_score",
    "stress_enc", "fatigue_enc", "sleep_enc", "trend_enc",
]

EMP_FEATURE_COLS = [
    "years_of_experience", "weekly_capacity_hours", "current_project_count",
    "technical_proficiency_score", "domain_expertise_score",
    "historical_performance_score", "average_task_completion_rate",
    "collaboration_score", "communication_effectiveness", "leadership_potential",
    "burnout_risk_score", "recent_overtime_hours", "days_since_last_leave",
    "work_life_balance_score", "successful_project_count", "failed_project_count",
    "seniority_enc", "prod_enc", "stress_emp_enc",
    "is_available", "cross_functional_experience", "mentoring_experience",
]


# =============================================================================
# SECTION 1 — LOAD
# =============================================================================

def load_raw():
    print("\n" + "="*60)
    print("SECTION 1 — LOADING")
    print("="*60)

    emp = pd.read_csv(os.path.join(DATA_DIR, "employees.csv"))
    bi  = pd.read_csv(os.path.join(DATA_DIR, "burnout_indicators.csv"))
    ta  = pd.read_csv(os.path.join(DATA_DIR, "task_assignments.csv"))

    print(f"  employees          : {emp.shape[0]:>6,} rows")
    print(f"  burnout_indicators : {bi.shape[0]:>6,} rows")
    print(f"  task_assignments   : {ta.shape[0]:>6,} rows")

    return emp, bi, ta


# =============================================================================
# SECTION 2 — BUILD TARGET
# =============================================================================

def build_target(bi: pd.DataFrame) -> pd.DataFrame:
    """
    Target = MAX overall_burnout_risk per employee.
    Using max (not mean) because:
      - Mean per employee never exceeds 59.99 (averages Low episodes)
      - Max correctly captures the worst burnout episode
      - Intervention decisions are based on peak risk, not average
    """
    print("\n" + "="*60)
    print("SECTION 2 — BUILDING TARGET")
    print("="*60)

    target = bi.groupby("employee_id")["overall_burnout_risk"].max().reset_index()
    target.columns = ["employee_id", "max_burnout_risk"]
    target["burnout_class"] = target["max_burnout_risk"].apply(
        lambda s: 0 if s < 30 else 1 if s < 60 else 2 if s < 80 else 3
    )

    dist = target["burnout_class"].map(LABEL_MAP).value_counts()
    print("  Class distribution (target):")
    for label, count in dist.items():
        pct = count / len(target) * 100
        bar = "█" * int(pct / 2)
        print(f"    {label:<10} {count:>5}  ({pct:5.1f}%)  {bar}")

    return target


# =============================================================================
# SECTION 3 — CLEAN & ENCODE burnout_indicators
# =============================================================================

def encode_burnout(bi: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "="*60)
    print("SECTION 3 — ENCODING burnout_indicators")
    print("="*60)

    df = bi.copy()

    # Encode categoricals
    df["stress_enc"]  = df["reported_stress_level"].map(STRESS_MAP).fillna(2)
    df["fatigue_enc"] = df["reported_fatigue_level"].map(FATIGUE_MAP).fillna(2)
    df["sleep_enc"]   = df["sleep_quality"].map(SLEEP_MAP).fillna(3)
    df["trend_enc"]   = df["burnout_trend"].map(TREND_MAP).fillna(0)
    df["phys_health"] = df["physical_health_concerns"].astype(int)
    df["mental_supp"] = df["mental_health_support_needed"].astype(int)

    print(f"  Encoded 6 categorical columns")
    print(f"  Symptom columns to aggregate: {len(SYMPTOM_COLS)}")

    return df


# =============================================================================
# SECTION 4 — AGGREGATE burnout (20k rows → 2k employees)
# =============================================================================

def aggregate_burnout(bi_encoded: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "="*60)
    print("SECTION 4 — AGGREGATING burnout_indicators")
    print("="*60)

    # Mean  = chronic / average symptom level
    # Max   = worst episode experienced
    # Std   = volatility / inconsistency in symptoms
    bi_mean = bi_encoded.groupby("employee_id")[SYMPTOM_COLS].mean()
    bi_max  = bi_encoded.groupby("employee_id")[SYMPTOM_COLS].max()
    bi_std  = bi_encoded.groupby("employee_id")[SYMPTOM_COLS].std().fillna(0)

    bi_mean.columns = [f"{c}_mean" for c in bi_mean.columns]
    bi_max.columns  = [f"{c}_max"  for c in bi_max.columns]
    bi_std.columns  = [f"{c}_std"  for c in bi_std.columns]

    bi_feat = bi_mean.join(bi_max).join(bi_std).reset_index()

    print(f"  Aggregated {len(bi_encoded):,} rows → {len(bi_feat):,} employees")
    print(f"  Feature columns from burnout: {bi_feat.shape[1] - 1}")

    return bi_feat


# =============================================================================
# SECTION 5 — CLEAN & ENCODE employees
# =============================================================================

def encode_employees(emp: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "="*60)
    print("SECTION 5 — ENCODING employees")
    print("="*60)

    df = emp.copy()

    # Ordinal encode
    df["seniority_enc"]   = df["seniority_level"].map(SENIORITY_MAP).fillna(2)
    df["prod_enc"]        = df["productivity_trend"].map(PROD_MAP).fillna(0)
    df["stress_emp_enc"]  = df["stress_level"].map(EMP_STRESS_MAP).fillna(2)

    # Boolean → int
    for col in ["is_available", "cross_functional_experience", "mentoring_experience"]:
        df[col] = df[col].astype(int)

    # Select only needed columns
    keep = ["employee_id"] + [c for c in EMP_FEATURE_COLS if c in df.columns]
    df   = df[keep]

    # Fill any remaining nulls with median
    num = df.select_dtypes(include=[np.number]).columns
    df[num] = df[num].fillna(df[num].median())

    print(f"  Employee feature columns: {len(keep) - 1}")

    return df


# =============================================================================
# SECTION 6 — AGGREGATE task_assignments
# =============================================================================

def aggregate_tasks(ta: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "="*60)
    print("SECTION 6 — AGGREGATING task_assignments")
    print("="*60)

    agg = ta.groupby("employee_id").agg(
        ta_skill_match = ("skill_match_score",            "mean"),
        ta_suitability = ("overall_suitability_score",    "mean"),
        ta_wl_compat   = ("workload_compatibility_score", "mean"),
        ta_reassign    = ("reassignment_count",           "sum"),
        ta_complete    = ("completion_status",
                          lambda x: (x == "Completed").mean()),
    ).reset_index()

    # Fill nulls
    num = agg.select_dtypes(include=[np.number]).columns
    agg[num] = agg[num].fillna(agg[num].median())

    print(f"  Aggregated {len(ta):,} rows → {len(agg):,} employees")
    print(f"  Task feature columns: {agg.shape[1] - 1}")

    return agg


# =============================================================================
# SECTION 7 — MERGE
# =============================================================================

def merge_all(bi_feat, emp_feat, ta_agg, target) -> pd.DataFrame:
    print("\n" + "="*60)
    print("SECTION 7 — MERGING")
    print("="*60)

    df = bi_feat.merge(emp_feat, on="employee_id", how="left")
    df = df.merge(ta_agg,       on="employee_id", how="left")
    df = df.merge(target,       on="employee_id", how="left")

    # Final null fill
    num = df.select_dtypes(include=[np.number]).columns.difference(
        ["burnout_class", "max_burnout_risk"]
    )
    df[num] = df[num].fillna(df[num].median())

    print(f"  Final shape: {df.shape[0]:,} rows  x  {df.shape[1]} cols")

    # Verify no nulls in features
    feat_cols = [c for c in df.columns
                 if c not in {"employee_id", "max_burnout_risk", "burnout_class"}]
    null_count = df[feat_cols].isnull().sum().sum()
    if null_count == 0:
        print("  Null check: PASSED (0 nulls in feature columns)")
    else:
        print(f"  WARNING: {null_count} nulls remain in features")

    return df


# =============================================================================
# SECTION 8 — SAVE OUTPUTS
# =============================================================================

def save_outputs(df: pd.DataFrame):
    print("\n" + "="*60)
    print("SECTION 8 — SAVING OUTPUTS")
    print("="*60)

    feature_cols = [
        c for c in df.columns
        if c not in {"employee_id", "max_burnout_risk", "burnout_class"}
    ]

    # Save processed CSV
    csv_path = os.path.join(OUT_DIR, "processed_data.csv")
    df.to_csv(csv_path, index=False)
    print(f"  Saved: {csv_path}  ({df.shape[0]:,} rows x {df.shape[1]} cols)")

    # Save feature column order (MUST match this exact order at inference time)
    json_path = os.path.join(OUT_DIR, "feature_columns.json")
    with open(json_path, "w") as f:
        json.dump(feature_cols, f, indent=2)
    print(f"  Saved: {json_path}  ({len(feature_cols)} features)")

    # Save label map
    label_path = os.path.join(OUT_DIR, "label_encoder.json")
    with open(label_path, "w") as f:
        json.dump(LABEL_MAP, f, indent=2)
    print(f"  Saved: {label_path}")

    print(f"\n  Features: {len(feature_cols)}")
    print(f"  Targets : {df['burnout_class'].map(LABEL_MAP).value_counts().to_dict()}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("STEP 1 — PREPROCESSING PIPELINE")
    print("="*60)

    emp_raw, bi_raw, ta_raw = load_raw()
    target    = build_target(bi_raw)
    bi_enc    = encode_burnout(bi_raw)
    bi_feat   = aggregate_burnout(bi_enc)
    emp_feat  = encode_employees(emp_raw)
    ta_agg    = aggregate_tasks(ta_raw)
    df        = merge_all(bi_feat, emp_feat, ta_agg, target)
    save_outputs(df)

    print("\n" + "="*60)
    print("PREPROCESSING COMPLETE")
    print("  Run next: python step2_training.py")
    print("="*60)