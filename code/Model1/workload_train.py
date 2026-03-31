"""
=============================================================================
STEP 2 — TRAINING
Model 1: Burnout Risk Classification (Gradient Boosting)
=============================================================================
Input  : processed_data.csv, feature_columns.json, label_encoder.json
Output : burnout_gbm_model.pkl   — trained GBM pipeline (imputer + model)
         model_metadata.json     — feature list, thresholds, metrics,
                                   feature importances (for dashboard)

Run    : python step2_training.py
         (must run step1_preprocessing.py first)
=============================================================================
"""

import os, json, warnings, pickle
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

from sklearn.model_selection   import train_test_split, cross_val_score, StratifiedKFold
from sklearn.ensemble          import GradientBoostingClassifier
from sklearn.impute            import SimpleImputer
from sklearn.pipeline          import Pipeline
from sklearn.metrics           import (
    classification_report, confusion_matrix,
    f1_score, accuracy_score
)

# ── CONFIG ───────────────────────────────────────────────────────────────────
DATA_DIR     = "."
OUT_DIR      = "."
RANDOM_STATE = 42
# ─────────────────────────────────────────────────────────────────────────────


# =============================================================================
# SECTION 1 — LOAD PREPROCESSED DATA
# =============================================================================

def load_processed():
    print("\n" + "="*60)
    print("SECTION 1 — LOADING PREPROCESSED DATA")
    print("="*60)

    df = pd.read_csv(os.path.join(DATA_DIR, "processed_data.csv"))

    with open(os.path.join(DATA_DIR, "feature_columns.json")) as f:
        feature_cols = json.load(f)

    with open(os.path.join(DATA_DIR, "label_encoder.json")) as f:
        label_map = json.load(f)
    label_map = {int(k): v for k, v in label_map.items()}

    # Keep only features that exist in the loaded CSV
    feature_cols = [c for c in feature_cols if c in df.columns]

    print(f"  Dataset      : {df.shape[0]:,} rows x {df.shape[1]} cols")
    print(f"  Features     : {len(feature_cols)}")
    print(f"  Target dist  : {df['burnout_class'].map(label_map).value_counts().to_dict()}")

    return df, feature_cols, label_map


# =============================================================================
# SECTION 2 — PREPARE X AND y
# =============================================================================

def prepare_xy(df, feature_cols):
    print("\n" + "="*60)
    print("SECTION 2 — PREPARING FEATURE MATRIX")
    print("="*60)

    X = df[feature_cols].copy()
    y = df["burnout_class"]

    print(f"  X shape : {X.shape}")
    print(f"  y shape : {y.shape}")
    print(f"  Nulls in X : {X.isnull().sum().sum()}")

    return X, y


# =============================================================================
# SECTION 3 — TRAIN / TEST SPLIT
# =============================================================================

def split_data(X, y):
    print("\n" + "="*60)
    print("SECTION 3 — TRAIN / TEST SPLIT  (80% / 20%)")
    print("="*60)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size    = 0.2,
        random_state = RANDOM_STATE,
        stratify     = y,    # preserves class ratios in both splits
    )

    print(f"  Train : {len(X_train):,} rows")
    print(f"  Test  : {len(X_test):,} rows")

    return X_train, X_test, y_train, y_test


# =============================================================================
# SECTION 4 — BUILD + TRAIN MODEL
# =============================================================================

def build_and_train(X_train, y_train):
    print("\n" + "="*60)
    print("SECTION 4 — TRAINING GRADIENT BOOSTING CLASSIFIER")
    print("="*60)
    print("""
  Why Gradient Boosting:
    - Builds 300 trees sequentially, each fixing errors of the previous
    - learning_rate=0.05: small steps per tree, more stable generalisation
    - max_depth=4: captures 4-level feature interactions without overfitting
    - min_samples_leaf=10: no leaf based on fewer than 10 employees
    - subsample=0.8: each tree sees 80% of rows, adds healthy randomness
    - Outperforms Random Forest on class boundaries (Moderate/High edge)
    """)

    # Pipeline: median imputation first, then model
    # Median is used (not mean) because burnout scores are skewed
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model",   GradientBoostingClassifier(
            n_estimators     = 300,
            learning_rate    = 0.05,
            max_depth        = 4,
            min_samples_leaf = 10,
            subsample        = 0.8,
            random_state     = RANDOM_STATE,
        )),
    ])

    print("  Training... (this takes ~30 seconds)")
    pipe.fit(X_train, y_train)
    print("  Training complete.")

    return pipe


# =============================================================================
# SECTION 5 — EVALUATE
# =============================================================================

def evaluate(pipe, X_train, X_test, y_train, y_test, feature_cols, label_map):
    print("\n" + "="*60)
    print("SECTION 5 — EVALUATION")
    print("="*60)

    y_pred     = pipe.predict(X_test)
    y_pred_all = pipe.predict(pd.concat([X_train, X_test]))

    # Classification report
    print("\n=== CLASSIFICATION REPORT (test set) ===")
    report = classification_report(
        y_test, y_pred,
        labels       = [0, 1, 2, 3],
        target_names = ["Low", "Moderate", "High", "Critical"],
        output_dict  = True,
    )
    print(classification_report(
        y_test, y_pred,
        labels       = [0, 1, 2, 3],
        target_names = ["Low", "Moderate", "High", "Critical"],
    ))

    # Confusion matrix
    print("=== CONFUSION MATRIX ===")
    print("Rows=Actual  Cols=Predicted  [Low, Moderate, High, Critical]")
    cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2, 3])
    print(cm)

    # Cross-validation
    print("\nRunning 5-fold cross-validation...")
    X_all = pd.concat([X_train, X_test])
    y_all = pd.concat([y_train, y_test])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_scores = cross_val_score(pipe, X_all, y_all, cv=cv, scoring="f1_macro", n_jobs=-1)
    print(f"CV F1-macro : {cv_scores.mean():.4f}  ±  {cv_scores.std():.4f}")
    print(f"Per-fold    : {[round(float(s), 4) for s in cv_scores]}")

    # Feature importances
    model      = pipe.named_steps["model"]
    importances = pd.Series(
        model.feature_importances_, index=feature_cols
    ).sort_values(ascending=False)

    print("\n=== TOP 15 FEATURE IMPORTANCES ===")
    for feat, val in importances.head(15).items():
        bar = "█" * max(1, int(val * 300))
        print(f"  {feat:<48} {val:.4f}  {bar}")

    # Leakage check
    top_feat = importances.idxmax()
    if "overall_burnout_risk" in top_feat or "burnout_category" in top_feat:
        print(f"\n  WARNING: possible leakage — top feature is '{top_feat}'")
    else:
        print(f"\n  Leakage check PASSED — top feature: '{top_feat}'")

    metrics = {
        "accuracy"     : round(accuracy_score(y_test, y_pred), 4),
        "f1_macro"     : round(f1_score(y_test, y_pred, average="macro"), 4),
        "cv_f1_mean"   : round(float(cv_scores.mean()), 4),
        "cv_f1_std"    : round(float(cv_scores.std()), 4),
        "test_size"    : len(y_test),
        "train_size"   : len(y_train),
        "n_features"   : len(feature_cols),
        "per_class"    : {
            label_map[int(k)]: {
                "precision" : round(v["precision"], 4),
                "recall"    : round(v["recall"], 4),
                "f1"        : round(v["f1-score"], 4),
                "support"   : int(v["support"]),
            }
            for k, v in report.items()
            if k.isdigit()
        },
        "confusion_matrix": cm.tolist(),
    }

    return metrics, importances


# =============================================================================
# SECTION 6 — SAVE MODEL + METADATA
# =============================================================================

def save_outputs(pipe, metrics, importances, feature_cols, label_map):
    print("\n" + "="*60)
    print("SECTION 6 — SAVING OUTPUTS")
    print("="*60)

    # Save model as pickle
    model_path = os.path.join(OUT_DIR, "burnout_gbm_model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(pipe, f)
    print(f"  Saved model  : {model_path}")

    # Save metadata JSON (consumed by step3_inference.py and dashboard)
    metadata = {
        "model_name"          : "Gradient Boosting Classifier",
        "model_type"          : "GradientBoostingClassifier",
        "n_estimators"        : 300,
        "learning_rate"       : 0.05,
        "max_depth"           : 4,
        "class_thresholds"    : {
            "Low"      : "score < 30",
            "Moderate" : "30 <= score < 60",
            "High"     : "60 <= score < 80",
            "Critical" : "score >= 80",
        },
        "label_map"           : label_map,
        "feature_columns"     : feature_cols,
        "metrics"             : metrics,
        "top_features"        : importances.head(20).round(4).to_dict(),
    }

    meta_path = os.path.join(OUT_DIR, "model_metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"  Saved metadata: {meta_path}")

    print(f"\n  Model accuracy : {metrics['accuracy']*100:.1f}%")
    print(f"  CV F1-macro    : {metrics['cv_f1_mean']:.4f} ± {metrics['cv_f1_std']:.4f}")
    print(f"\n  Run next: python step3_inference.py")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("STEP 2 — TRAINING PIPELINE")
    print("="*60)

    df, feature_cols, label_map       = load_processed()
    X, y                              = prepare_xy(df, feature_cols)
    X_train, X_test, y_train, y_test  = split_data(X, y)
    pipe                              = build_and_train(X_train, y_train)
    metrics, importances              = evaluate(pipe, X_train, X_test,
                                                  y_train, y_test,
                                                  feature_cols, label_map)
    save_outputs(pipe, metrics, importances, feature_cols, label_map)

    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)