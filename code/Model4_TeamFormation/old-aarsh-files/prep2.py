# =============================================================
# TEAM FORMATION MODEL — DATA PREP & FEATURE EXTRACTION
# Each cell is separated by a comment block
# Paste each cell into a new notebook cell
# =============================================================


# ── Cell 1 — Imports ─────────────────────────────────────────

import pandas as pd
import numpy as np
import json
from sklearn.preprocessing import MinMaxScaler
import os
import warnings
warnings.filterwarnings('ignore')

pd.set_option('display.max_columns', None)
print("Libraries loaded ✅")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(SCRIPT_DIR, "../../dataset")  # folder containing your CSVs
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "./FeatureTables")  # output folder
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Cell 2 — Load Datasets ───────────────────────────────────
# Only loading what team formation actually needs.
# tasks.csv and task_assignments.csv are NOT used here —
# they belong to the task allocation module (post team formation).

emp  = pd.read_csv(f"{INPUT_DIR}/employees.csv")
tf   = pd.read_csv(f"{INPUT_DIR}/team_formations.csv")
pr   = pd.read_csv(f"{INPUT_DIR}/performance_reviews.csv")
# ta   = pd.read_csv(f"{INPUT_DIR}/task_assignments.csv")
wh   = pd.read_csv(f"{INPUT_DIR}/workload_history.csv")
proj = pd.read_csv(f"{INPUT_DIR}/projects.csv")
# tasks = pd.read_csv(f"{INPUT_DIR}/tasks.csv")

print("Shapes:")
print(f"  employees        : {emp.shape}")
print(f"  team_formations  : {tf.shape}")
print(f"  performance_rev  : {pr.shape}")
print(f"  workload_history : {wh.shape}")
print(f"  projects         : {proj.shape}")


# ── Cell 3 — Clean employees.csv ─────────────────────────────

# Datetime
emp['hire_date']  = pd.to_datetime(emp['hire_date'], format='mixed')
emp['tenure_days'] = (pd.Timestamp.today() - emp['hire_date']).dt.days

# Booleans
for col in ['is_available', 'cross_functional_experience', 'mentoring_experience']:
    emp[col] = emp[col].astype(bool)

# Nulls
emp['certifications'] = emp['certifications'].fillna('')
emp.drop(columns=['past_team_members'], inplace=True)  # all null, unusable

# Ordinal encoding
seniority_order = {'Junior': 1, 'Mid': 2, 'Senior': 3, 'Lead': 4, 'Principal': 5}
stress_order    = {'Low': 1, 'Medium': 2, 'High': 3}
emp['seniority_encoded'] = emp['seniority_level'].map(seniority_order)
emp['stress_encoded']    = emp['stress_level'].map(stress_order)

# Skills → lowercase lists (lowercase fixes exact matching with project skills)
emp['all_skills_list'] = (
    emp['primary_skills'].fillna('') + ',' + emp['secondary_skills'].fillna('')
).str.split(',').apply(lambda x: [s.strip().lower() for s in x if s.strip()])

# Derived
emp['project_success_rate'] = (
    emp['successful_project_count'] /
    (emp['successful_project_count'] + emp['failed_project_count'])
).fillna(0)

print("employees.csv cleaned ✅")
print(f"Columns: {emp.shape[1]} | Rows: {emp.shape[0]}")


# ── Cell 4 — Clean performance_reviews.csv ───────────────────
# Keep latest review per employee.
# Using review-specific scores that don't exist in employees.csv.

pr['review_date'] = pd.to_datetime(pr['review_date'])

pr_latest = (
    pr.sort_values('review_date', ascending=False)
      .groupby('employee_id', as_index=False)
      .first()
)

pr_keep = [
    'employee_id',
    'overall_performance_score',   # review-based, more objective than self-reported
    'on_time_delivery_rate',       # how often they deliver on time
    'productivity_vs_peers',       # relative productivity benchmark
    'problem_solving_score',
    'innovation_score',
    'reliability_score',
    'time_management_score',
    'adaptability_score',
    'technical_competence_score',
]
pr_latest = pr_latest[pr_keep]

print("performance_reviews.csv cleaned ✅")
print(f"Employees with reviews: {pr_latest['employee_id'].nunique()}")


# ── Cell 5 — Clean workload_history.csv ──────────────────────
# Use last 8 weeks — recent enough to reflect current state,
# wide enough to avoid empty aggregations.

wh['date'] = pd.to_datetime(wh['date'])
cutoff = wh['date'].max() - pd.Timedelta(weeks=8)
wh_recent = wh[wh['date'] >= cutoff].copy()

print(f"Workload records in last 8 weeks: {len(wh_recent)}")
print(f"Employees covered: {wh_recent['employee_id'].nunique()} / {emp['employee_id'].nunique()}")

wh_agg = wh_recent.groupby('employee_id').agg(
    recent_avg_hours        = ('total_hours_worked',    'mean'),
    recent_avg_overtime     = ('overtime_hours',         'mean'),
    recent_workload_pct     = ('workload_vs_capacity',   'mean'),  # % of capacity used
    recent_avg_productivity = ('productivity_score',     'mean'),
    recent_focus_hours      = ('focused_work_hours',     'mean'),
    late_hours_count        = ('late_hours_indicator',   'sum'),   # raw count of late days
    weekend_work_count      = ('weekend_work_indicator', 'sum'),
).reset_index()

print("workload_history.csv aggregated ✅")


# ── Cell 6 — Build Master Employee Table ─────────────────────
# One row per employee with all features needed for team-level aggregation.
# NOTE: burnout_risk_score comes directly from employees.csv (always populated).
#       We do NOT use workload burnout (had too many nulls after cutoff filter).

master = emp.copy()

# Merge review scores (rename to avoid collision with employees.csv cols)
pr_latest = pr_latest.rename(columns={
    'overall_performance_score' : 'review_performance_score',
    'technical_competence_score': 'review_technical_score',
})
master = master.merge(pr_latest, on='employee_id', how='left')

# Merge recent workload
master = master.merge(wh_agg, on='employee_id', how='left')

# Derived: remaining available capacity this week
master['available_hours'] = (
    master['weekly_capacity_hours'] - master['recent_avg_hours'].fillna(
        master['weekly_capacity_hours'] * 0.7  # assume 70% utilized if no data
    )
).clip(lower=0)

# Verify no _x/_y conflicts
conflicts = [c for c in master.columns if c.endswith('_x') or c.endswith('_y')]
print(f"Column conflicts: {conflicts}")  # must be []
print(f"Master table shape: {master.shape}")


# ── Cell 7 — Clean projects.csv ──────────────────────────────

complexity_order = {'Low': 1, 'Medium': 2, 'High': 3, 'Very High': 4}
priority_order   = {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4}

proj['complexity_encoded'] = proj['complexity_level'].map(complexity_order)
proj['priority_encoded']   = proj['priority'].map(priority_order).fillna(2)

# Skills → lowercase lists (matches employee skill format)
proj['required_skills_list'] = proj['required_skills'].fillna('').str.split(',').apply(
    lambda x: [s.strip().lower() for s in x if s.strip()]
)

# Budget per required team member — proxy for seniority budget constraint
# i.e. can this project afford senior/lead employees?
proj['budget_per_head'] = proj['budget'] / proj['team_size'].replace(0, np.nan)

proj_keep = proj[[
    'project_id',
    'complexity_encoded',
    'priority_encoded',
    'budget',
    'budget_per_head',
    'team_size',           # expected team size for this project
    'delay_risk_score',
    'quality_risk_score',
    'strategic_importance',
    'required_skills_list',
]]

print("projects.csv cleaned ✅")
print(proj_keep[['project_id','complexity_encoded','budget_per_head','team_size']].head(3))


# ── Cell 8 — Clean team_formations.csv ───────────────────────

tf['formation_date'] = pd.to_datetime(tf['formation_date'])

# Parse member_ids
tf['member_ids_list'] = tf['member_ids'].str.split(',').apply(
    lambda x: [s.strip() for s in x]
)

# Parse seniority_mix JSON string
def parse_json(val):
    try:
        return json.loads(str(val).replace("'", '"'))
    except:
        return {}

tf['seniority_mix_parsed'] = tf['seniority_mix'].apply(parse_json)

# Fix met_deadline boolean
tf['met_deadline'] = tf['met_deadline'].map(
    {True: 1, False: 0, 'True': 1, 'False': 0}
)

# Drop 2 rows with null actual_performance_score (can't train without target)
tf = tf.dropna(subset=['actual_performance_score']).reset_index(drop=True)

# Target: binary success (>=80 = good team)
tf['team_success'] = (tf['actual_performance_score'] >= 80).astype(int)

print(f"team_formations.csv cleaned ✅")
print(f"Rows: {len(tf)}")
print(f"Target balance:\n{tf['team_success'].value_counts()}")


# ── Cell 9 — Feature Extraction per Team ─────────────────────
# Each team row becomes one feature vector.
# We aggregate member-level features into team-level statistics.

def compute_skill_coverage(member_ids, required_skills):
    """
    What fraction of the project's required skills does
    this team collectively cover?
    Lowercase match — no fuzzy needed (verified overlap is exact).
    """
    if not required_skills:
        return np.nan
    members = master[master['employee_id'].isin(member_ids)]
    team_skills = set()
    for skills in members['all_skills_list']:
        team_skills.update(skills)
    covered = set(required_skills) & team_skills
    return len(covered) / len(required_skills)


def compute_budget_seniority_fit(member_ids, budget_per_head):
    """
    Are the employees' salary levels affordable given the project budget per head?
    Returns fraction of members whose salary <= budget_per_head.
    A score of 1.0 means all members are within budget.
    """
    if pd.isna(budget_per_head):
        return np.nan
    members = master[master['employee_id'].isin(member_ids)]
    if members.empty:
        return np.nan
    return (members['current_salary'] <= budget_per_head).mean()


def extract_team_features(tf_row, proj_row):
    """
    Given one team row and its corresponding project row,
    produce a flat feature dict representing this team.
    """
    member_ids = tf_row['member_ids_list']
    members    = master[master['employee_id'].isin(member_ids)]

    if members.empty:
        return None

    f = {}

    # ── Identifiers (kept for reference, dropped before modeling) ──
    f['team_id']        = tf_row['team_id']
    f['project_id']     = tf_row['project_id']
    f['formation_date'] = tf_row['formation_date']

    # ── Team size ──
    f['team_size'] = len(members)

    # ── Skill features ──
    req_skills = proj_row['required_skills_list'] if proj_row is not None else []
    f['skill_coverage']      = compute_skill_coverage(member_ids, req_skills)
    f['unique_skill_count']  = len(set(s for sl in members['all_skills_list'] for s in sl))
    f['avg_skills_per_member'] = f['unique_skill_count'] / max(f['team_size'], 1)

    # ── Seniority mix ──
    sen_mix = tf_row['seniority_mix_parsed']
    f['junior_ratio']   = sen_mix.get('Junior', 0)    / max(f['team_size'], 1)
    f['mid_ratio']      = sen_mix.get('Mid', 0)       / max(f['team_size'], 1)
    f['senior_ratio']   = sen_mix.get('Senior', 0)    / max(f['team_size'], 1)
    f['lead_ratio']     = (sen_mix.get('Lead', 0) + sen_mix.get('Principal', 0)) / max(f['team_size'], 1)
    f['seniority_diversity'] = len([v for v in sen_mix.values() if v > 0])  # distinct levels
    f['avg_seniority']  = members['seniority_encoded'].mean()
    f['max_seniority']  = members['seniority_encoded'].max()

    # ── Budget fit ──
    budget_per_head = proj_row['budget_per_head'] if proj_row is not None else np.nan
    f['budget_per_head']       = budget_per_head
    f['budget_seniority_fit']  = compute_budget_seniority_fit(member_ids, budget_per_head)

    # ── Performance features ──
    f['avg_performance']    = members['review_performance_score'].mean()
    f['min_performance']    = members['review_performance_score'].min()
    f['std_performance']    = members['review_performance_score'].std()
    f['avg_on_time_rate']   = members['on_time_delivery_rate'].mean()
    f['avg_reliability']    = members['reliability_score'].mean()
    f['avg_adaptability']   = members['adaptability_score'].mean()
    f['avg_problem_solving']= members['problem_solving_score'].mean()
    f['avg_innovation']     = members['innovation_score'].mean()

    # ── Collaboration & communication ──
    f['avg_collaboration']  = members['collaboration_score'].mean()
    f['avg_communication']  = members['communication_effectiveness'].mean()
    f['avg_leadership']     = members['leadership_potential'].mean()
    f['cross_func_ratio']   = members['cross_functional_experience'].mean()
    f['mentoring_ratio']    = members['mentoring_experience'].mean()

    # ── Burnout & workload (from employees.csv — always populated) ──
    f['avg_burnout_risk']   = members['burnout_risk_score'].mean()
    f['max_burnout_risk']   = members['burnout_risk_score'].max()
    f['avg_stress']         = members['stress_encoded'].mean()
    f['high_stress_ratio']  = (members['stress_encoded'] == 3).mean()
    f['avg_available_hours']= members['available_hours'].mean()
    f['avg_workload_recent']= members['recent_workload_pct'].mean()  # % capacity used

    # ── Experience ──
    f['avg_experience']     = members['years_of_experience'].mean()
    f['experience_range']   = members['years_of_experience'].max() - members['years_of_experience'].min()
    f['avg_project_success']= members['project_success_rate'].mean()
    f['avg_technical_score']= members['technical_proficiency_score'].mean()
    f['avg_domain_score']   = members['domain_expertise_score'].mean()

    # ── Project-level features ──
    if proj_row is not None:
        f['proj_complexity']       = proj_row['complexity_encoded']
        f['proj_priority']         = proj_row['priority_encoded']
        f['proj_budget']           = proj_row['budget']
        f['proj_delay_risk']       = proj_row['delay_risk_score']
        f['proj_quality_risk']     = proj_row['quality_risk_score']
        f['proj_strategic_imp']    = proj_row['strategic_importance']
        f['proj_required_team_size']= proj_row['team_size']
        f['team_size_match']       = len(members) / max(proj_row['team_size'], 1)
    else:
        for col in ['proj_complexity','proj_priority','proj_budget','proj_delay_risk',
                    'proj_quality_risk','proj_strategic_imp','proj_required_team_size','team_size_match']:
            f[col] = np.nan

    # ── Targets ──
    f['actual_performance_score'] = tf_row['actual_performance_score']
    f['team_success']             = tf_row['team_success']   # binary: >=80
    f['met_deadline']             = tf_row['met_deadline']
    f['quality_rating']           = tf_row['quality_rating']

    return f

print("Feature extraction functions defined ✅")


# ── Cell 10 — Run Extraction on All Teams ────────────────────

proj_indexed = proj_keep.set_index('project_id')

rows = []
for _, tf_row in tf.iterrows():
    pid      = tf_row['project_id']
    proj_row = proj_indexed.loc[pid] if pid in proj_indexed.index else None
    feats    = extract_team_features(tf_row, proj_row)
    if feats:
        rows.append(feats)

team_df = pd.DataFrame(rows)

print(f"Team feature table shape: {team_df.shape}")
print(f"\nNull counts:\n{team_df.isnull().sum().sort_values(ascending=False).head(10)}")
print(f"\nSample row:\n{team_df.iloc[0]}")


# ── Cell 11 — Sanity Checks ───────────────────────────────────

print("=== skill_coverage distribution ===")
print(team_df['skill_coverage'].describe())

print("\n=== budget_seniority_fit distribution ===")
print(team_df['budget_seniority_fit'].describe())

print("\n=== team_success balance ===")
print(team_df['team_success'].value_counts())

print("\n=== avg_burnout_risk (should NOT be all 0) ===")
print(team_df['avg_burnout_risk'].describe())

print("\n=== seniority ratios sample ===")
print(team_df[['junior_ratio','mid_ratio','senior_ratio','lead_ratio']].head(5))

# All ratios should sum to ~1.0 per row
ratio_sum = team_df[['junior_ratio','mid_ratio','senior_ratio','lead_ratio']].sum(axis=1)
print(f"\nRatio sum min/max (should be ~1.0): {ratio_sum.min():.2f} / {ratio_sum.max():.2f}")


# ── Cell 12 — Normalize & Finalize ───────────────────────────

# Columns that are identifiers or targets — not features
id_cols     = ['team_id', 'project_id', 'formation_date']
target_cols = ['actual_performance_score', 'team_success', 'met_deadline', 'quality_rating']

# Separate targets
targets = team_df[id_cols + target_cols].copy()

# Feature matrix
X = team_df.drop(columns=id_cols + target_cols)

# Fill remaining nulls with column median
X = X.fillna(X.median(numeric_only=True))

# Normalize all numeric columns
scaler   = MinMaxScaler()
X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)

print(f"Final feature matrix shape: {X_scaled.shape}")
print(f"Features: {X_scaled.columns.tolist()}")
print(f"\nValue range after scaling: {X_scaled.min().min():.2f} to {X_scaled.max().max():.2f}")


# ── Cell 13 — Time-Based Train/Test Split ────────────────────
# Split by formation_date NOT randomly — avoids data leakage.
# Train on older teams, test on newer ones.

formation_dates = pd.to_datetime(team_df['formation_date'])
split_date      = formation_dates.quantile(0.8)

train_mask = formation_dates <= split_date
test_mask  = ~train_mask

X_train = X_scaled[train_mask].reset_index(drop=True)
X_test  = X_scaled[test_mask].reset_index(drop=True)

# Regression target
y_train_reg = targets.loc[train_mask, 'actual_performance_score'].reset_index(drop=True)
y_test_reg  = targets.loc[test_mask,  'actual_performance_score'].reset_index(drop=True)

# Classification target
y_train_cls = targets.loc[train_mask, 'team_success'].reset_index(drop=True)
y_test_cls  = targets.loc[test_mask,  'team_success'].reset_index(drop=True)

print(f"Train: {X_train.shape} | Test: {X_test.shape}")
print(f"\nClass balance — Train:\n{y_train_cls.value_counts()}")
print(f"\nClass balance — Test:\n{y_test_cls.value_counts()}")

# Save
X_train.to_csv(f"{OUTPUT_DIR}/X_train.csv", index=False)
X_test.to_csv(f"{OUTPUT_DIR}/X_test.csv",   index=False)
y_train_reg.to_csv(f"{OUTPUT_DIR}/y_train_reg.csv", index=False)
y_test_reg.to_csv(f"{OUTPUT_DIR}/y_test_reg.csv",   index=False)
y_train_cls.to_csv(f"{OUTPUT_DIR}/y_train_cls.csv", index=False)
y_test_cls.to_csv(f"{OUTPUT_DIR}/y_test_cls.csv",   index=False)
targets.to_csv(f"{OUTPUT_DIR}/team_targets.csv", index=False)  # full reference with team_id/project_id

print("\n✅ Data prep complete — all CSVs saved, ready for modeling")
