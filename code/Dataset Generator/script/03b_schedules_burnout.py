"""
03b_schedules_burnout.py — Generate schedules.csv and burnout_indicators.csv
- Schedule dates clamped to >= employee hire_date
- add_minutes() fixed for midnight wrap
- Burnout assessment dates clamped to >= hire_date
"""

import os, random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    HISTORY_START, HISTORY_END,
    EVENT_TYPES, EVENT_WEIGHTS, MTG_TYPES, ATTEND_STATUS, ATTEND_WEIGHTS,
    BURNOUT_TREND, INTERV_URGENCY, ASSESS_TYPE, ASSESS_WEIGHTS,
    TIMEZONES, PRIORITY,
    clamp, rand_date, rand_datetime,
)

random.seed(42)
np.random.seed(42)

NUM_SCHEDULE_ROWS = int(os.environ.get("NUM_SCHEDULE_ROWS", 6000))
NUM_BURNOUT_ROWS  = int(os.environ.get("NUM_BURNOUT_ROWS",  2000))
OUT_DIR           = os.environ.get("OUT_DIR", "./output")

EVENT_TITLES = {
    "Task":       ["Code Review Session", "Implementation Block", "Design Sprint",
                   "Bug Fixing", "Testing Block"],
    "Meeting":    ["Sprint Planning", "Daily Standup", "Retrospective",
                   "Stakeholder Review", "1:1 with Manager", "Design Critique",
                   "Architecture Discussion", "Team Sync", "All Hands"],
    "Focus Time": ["Deep Work Block", "No-Interruption Zone", "Research Block",
                   "Writing Time", "Strategy Session"],
    "Break":      ["Lunch Break", "Coffee Break", "Short Walk", "Mental Reset"],
    "Training":   ["AWS Training", "Leadership Workshop", "Agile Certification Prep",
                   "Technical Talk", "Onboarding"],
    "Leave":      ["Annual Leave", "Sick Leave", "Personal Day", "Public Holiday"],
}

DURATION_BY_TYPE = {
    "Task":       [60, 90, 120, 180, 240],
    "Meeting":    [30, 45, 60, 90],
    "Focus Time": [60, 90, 120],
    "Break":      [15, 30, 60],
    "Training":   [60, 120, 180, 240],
    "Leave":      [480],
}

LOCATIONS = ["Office", "Home", "Conference Room A", "Conference Room B", "Virtual", "Client Site"]


def add_minutes(time_str: str, minutes: int) -> str:
    """Add minutes to HH:MM:SS, capping at 23:59:00 to avoid midnight wrap."""
    h, m, s = map(int, time_str.split(":"))
    total = h * 60 + m + minutes
    total = min(total, 23 * 60 + 59)   # cap at 23:59
    return f"{total // 60:02d}:{total % 60:02d}:00"


def weekdays_in_range(start: date, end: date) -> list[date]:
    days, cur = [], start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULES
# ═══════════════════════════════════════════════════════════════════════════════
def generate_schedules(employees_df: pd.DataFrame,
                        tasks_df: pd.DataFrame,
                        n: int) -> pd.DataFrame:
    emp_ids  = employees_df["employee_id"].tolist()
    task_ids = tasks_df["task_id"].tolist()
    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}
    emp_tz   = dict(zip(employees_df["employee_id"], employees_df["timezone"]))
    emp_remote = dict(zip(employees_df["employee_id"], employees_df["remote_work_status"]))

    hist_start = date.fromisoformat(HISTORY_START)
    hist_end   = date.fromisoformat(HISTORY_END)
    all_workdays = weekdays_in_range(hist_start, hist_end)

    # Pre-build per-employee valid day pools (on/after hire_date)
    emp_valid_days: dict[str, list[date]] = {}
    for emp_id in emp_ids:
        hire_dt = hire_map[emp_id]
        emp_valid_days[emp_id] = [d for d in all_workdays if d >= hire_dt]

    rows = []
    for i in range(1, n + 1):
        sch_id = f"SCH{i:05d}"
        emp_id = random.choice(emp_ids)

        valid_days = emp_valid_days[emp_id]
        if not valid_days:
            continue
        day = random.choice(valid_days)

        ev_type  = np.random.choice(EVENT_TYPES, p=EVENT_WEIGHTS)
        title    = random.choice(EVENT_TITLES[ev_type])
        duration = random.choice(DURATION_BY_TYPE[ev_type])

        start_h = random.randint(8, 17)
        start_m = random.choice([0, 15, 30, 45])
        start_t = f"{start_h:02d}:{start_m:02d}:00"
        end_t   = add_minutes(start_t, duration)  # fixed: no midnight wrap

        related_id = random.choice(task_ids) if ev_type == "Task" else None

        priority     = np.random.choice(PRIORITY, p=[0.20, 0.40, 0.30, 0.10])
        is_flex      = random.random() > 0.5
        buf_req      = random.random() > 0.6
        buf_mins     = random.choice([0, 15, 30]) if buf_req else 0

        has_conflict = random.random() < 0.08
        conflict_ids = f"SCH{random.randint(1, n):05d}" if has_conflict else None
        opt_score    = clamp(round(np.random.normal(75, 15), 1), 20, 100)
        rec_time_str = f"{random.randint(9,16):02d}:{random.choice([0,15,30,45]):02d}:00" \
                       if opt_score < 60 else None

        attend       = np.random.choice(ATTEND_STATUS, p=ATTEND_WEIGHTS)
        completed_ev = attend == "Completed"

        act_start  = add_minutes(start_t, random.randint(-5, 10)) if completed_ev else None
        act_end    = add_minutes(act_start, duration + random.randint(-10, 15)) \
                     if completed_ev else None
        act_dur    = duration + random.randint(-10, 15) if completed_ev else None
        prod_during= clamp(round(np.random.normal(7.0, 1.3), 1), 3, 10) if completed_ev else None

        involves_team  = ev_type in ["Meeting", "Training"] or random.random() < 0.3
        participant_cnt= random.randint(2, 12) if involves_team else 1
        participant_ids= ",".join(
            random.sample([e for e in emp_ids if e != emp_id],
                          min(participant_cnt - 1, len(emp_ids) - 1))
        ) if involves_team else None
        mtg_type = random.choice(MTG_TYPES) if ev_type == "Meeting" else None

        remote_status = emp_remote.get(emp_id, "Office")
        is_remote  = remote_status in ["Remote", "Hybrid"] and random.random() > 0.4
        location   = "Virtual" if is_remote else random.choice(LOCATIONS[:-1])
        mtg_link   = f"https://zoom.us/j/{random.randint(10000000, 99999999)}" \
                     if is_remote else None

        rows.append({
            "schedule_id":             sch_id,
            "employee_id":             emp_id,
            "event_type":              ev_type,
            "related_id":              related_id,
            "event_title":             title,
            "date":                    day.isoformat(),
            "start_time":              start_t,
            "end_time":                end_t,
            "duration_minutes":        duration,
            "timezone":                emp_tz.get(emp_id, "IST"),
            "priority":                priority,
            "is_flexible":             is_flex,
            "buffer_required":         buf_req,
            "buffer_minutes":          buf_mins,
            "has_conflict":            has_conflict,
            "conflict_with_ids":       conflict_ids,
            "optimization_score":      opt_score,
            "recommended_time":        rec_time_str,
            "attendance_status":       attend,
            "actual_start_time":       act_start,
            "actual_end_time":         act_end,
            "actual_duration_minutes": act_dur,
            "productivity_during":     prod_during,
            "involves_team":           involves_team,
            "participant_ids":         participant_ids,
            "participant_count":       participant_cnt,
            "meeting_type":            mtg_type,
            "location":                location,
            "is_remote":               is_remote,
            "meeting_link":            mtg_link,
            "created_at":              rand_datetime(day - timedelta(days=random.randint(1, 7))),
            "last_updated":            rand_datetime(day),
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# BURNOUT INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════
def generate_burnout_indicators(employees_df: pd.DataFrame,
                                 stress_profiles: dict,
                                 n: int) -> pd.DataFrame:
    emp_ids  = employees_df["employee_id"].tolist()
    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}

    hist_start = date.fromisoformat(HISTORY_START)
    hist_end   = date.fromisoformat(HISTORY_END)
    total_days = (hist_end - hist_start).days

    # Weight high-stress employees for more assessments
    stress_weights = np.array([
        {"Low": 1, "Medium": 2, "High": 4}[
            employees_df[employees_df["employee_id"] == e]["stress_level"].values[0]
        ] for e in emp_ids
    ], dtype=float)
    stress_weights /= stress_weights.sum()
    sampled_emps = np.random.choice(emp_ids, size=n, replace=True, p=stress_weights)

    rows = []
    for i, emp_id in enumerate(sampled_emps):
        ind_id   = f"BI{i+1:04d}"
        profile  = stress_profiles[emp_id]
        base_b   = profile["base_burnout"]
        trend    = profile["trend"]
        hire_dt  = hire_map[emp_id]

        # Assessment date clamped to >= hire_date
        days_available = (hist_end - max(hire_dt, hist_start)).days
        if days_available <= 0:
            days_available = 1
        assess_date = max(hire_dt, hist_start) + timedelta(days=random.randint(0, days_available))
        assess_type = np.random.choice(ASSESS_TYPE, p=ASSESS_WEIGHTS)

        days_elapsed = (assess_date - hist_start).days
        drift = {"stable": 0, "increasing": 25 * (days_elapsed / max(total_days, 1)),
                 "decreasing": -20 * (days_elapsed / max(total_days, 1))}[trend]
        burnout = clamp(base_b + drift + np.random.normal(0, 8), 5, 98)

        emo_exhaust = clamp(round(burnout * 0.90 + np.random.normal(0, 8), 1), 5, 100)
        deperson    = clamp(round(burnout * 0.75 + np.random.normal(0, 8), 1), 5, 100)
        reduced_acc = clamp(round(burnout * 0.65 + np.random.normal(0, 8), 1), 5, 100)

        cat = ("Critical"     if burnout > 75 else
               "High Risk"    if burnout > 55 else
               "Moderate Risk"if burnout > 30 else "Low Risk")

        wl_pressure  = clamp(round(burnout * 0.85 + np.random.normal(0, 10), 1), 5, 100)
        role_amb     = clamp(round(np.random.normal(35, 18), 1), 5, 90)
        wl_conflict  = clamp(round(burnout * 0.70 + np.random.normal(0, 10), 1), 5, 100)
        job_demands  = clamp(round(burnout * 0.80 + np.random.normal(0, 8),  1), 5, 100)
        job_control  = clamp(round(70 - burnout * 0.4 + np.random.normal(0, 10), 1), 10, 95)
        role_conflict= clamp(round(burnout * 0.60 + np.random.normal(0, 10), 1), 5, 90)

        late_freq    = int(clamp(burnout / 6  + np.random.normal(0, 2),   0, 20))
        wknd_work    = int(clamp(burnout / 15 + np.random.normal(0, 1),   0,  8))
        missed_brks  = int(clamp(burnout / 12 + np.random.normal(0, 1),   0, 10))
        vac_unused   = int(clamp(burnout / 6  + np.random.normal(0, 2),   0, 20))
        sick_days    = int(clamp(burnout / 12 + np.random.normal(0, 1.5), 0, 12))
        absence_rate = clamp(round(sick_days / 130 * 100, 1), 0, 15)

        stress_rep  = ("Very High" if burnout > 75 else "High" if burnout > 55
                       else "Medium" if burnout > 30 else "Low")
        fatigue_rep = ("Severe" if burnout > 80 else "High" if burnout > 60
                       else "Medium" if burnout > 35 else "Low")
        sleep_qual  = ("Very Poor" if burnout > 78 else "Poor" if burnout > 58
                       else "Fair" if burnout > 35 else "Good")
        phys_concern= burnout > 70 and random.random() > 0.5
        mh_support  = burnout > 65 and random.random() > 0.4
        energy      = clamp(round(10 - burnout / 12 + np.random.normal(0, 0.8), 1), 1, 10)

        job_sat      = clamp(round(9.5 - burnout / 12 + np.random.normal(0, 0.8), 1), 1, 10)
        engagement   = clamp(round(9.0 - burnout / 12 + np.random.normal(0, 0.8), 1), 1, 10)
        motivation   = clamp(round(9.0 - burnout / 11 + np.random.normal(0, 0.9), 1), 1, 10)
        accomplish   = clamp(round(9.0 - burnout / 13 + np.random.normal(0, 0.8), 1), 1, 10)
        org_commit   = clamp(round(8.5 - burnout / 15 + np.random.normal(0, 0.9), 1), 1, 10)

        soc_support  = clamp(round(np.random.normal(6.5, 1.5), 1), 1, 10)
        mgr_support  = clamp(round(np.random.normal(6.5, 1.5), 1), 1, 10)
        team_coh     = clamp(round(np.random.normal(7.0, 1.3), 1), 1, 10)
        wp_rel       = clamp(round(np.random.normal(7.0, 1.2), 1), 1, 10)
        isolation    = clamp(round(burnout * 0.5 + np.random.normal(0, 10), 1), 0, 100)

        coping       = clamp(round(8.0 - burnout / 15 + np.random.normal(0, 0.9), 1), 1, 10)
        resources    = clamp(round(np.random.normal(6.5, 1.4), 1), 1, 10)
        recovery     = clamp(round(8.0 - burnout / 14 + np.random.normal(0, 0.9), 1), 1, 10)
        resilience   = clamp(round(8.5 - burnout / 16 + np.random.normal(0, 0.8), 1), 1, 10)

        b_trend_cat  = ("Rapidly Increasing" if trend == "increasing" and burnout > 60 else
                        "Increasing"         if trend == "increasing" else
                        "Decreasing"         if trend == "decreasing" else "Stable")
        pred_30d     = clamp(round(burnout + (5 if trend == "increasing" else
                                              -3 if trend == "decreasing" else 0)
                                   + np.random.normal(0, 5), 1), 5, 98)
        pred_90d     = clamp(round(burnout + (12 if trend == "increasing" else
                                              -8 if trend == "decreasing" else 2)
                                   + np.random.normal(0, 8), 1), 5, 98)
        urgency      = ("Immediate" if burnout > 78 else "Recommend" if burnout > 58
                        else "Monitor" if burnout > 38 else "None")

        n_interv     = int(clamp(burnout / 30 + np.random.normal(0, 0.5), 0, 4))
        # last_intervention_date must be BEFORE assessment_date
        last_interv  = (assess_date - timedelta(days=random.randint(5, 60))).isoformat() \
                       if n_interv > 0 else None
        interv_eff   = clamp(round(np.random.normal(6.5, 1.5), 1), 2, 10) \
                       if n_interv > 0 else None

        rows.append({
            "indicator_id":                 ind_id,
            "employee_id":                  emp_id,
            "assessment_date":              assess_date.isoformat(),
            "assessment_type":              assess_type,
            "overall_burnout_risk":         round(burnout, 1),
            "emotional_exhaustion_score":   emo_exhaust,
            "depersonalization_score":      deperson,
            "reduced_accomplishment_score": reduced_acc,
            "burnout_category":             cat,
            "workload_pressure":            wl_pressure,
            "role_ambiguity":               role_amb,
            "work_life_conflict":           wl_conflict,
            "job_demands":                  job_demands,
            "job_control":                  job_control,
            "role_conflict":                role_conflict,
            "late_hours_frequency":         late_freq,
            "weekend_work_frequency":       wknd_work,
            "missed_breaks_count":          missed_brks,
            "vacation_days_unused":         vac_unused,
            "sick_days_taken":              sick_days,
            "absence_rate":                 absence_rate,
            "reported_stress_level":        stress_rep,
            "reported_fatigue_level":       fatigue_rep,
            "sleep_quality":                sleep_qual,
            "physical_health_concerns":     phys_concern,
            "mental_health_support_needed": mh_support,
            "energy_level":                 energy,
            "job_satisfaction":             job_sat,
            "engagement_score":             engagement,
            "motivation_level":             motivation,
            "sense_of_accomplishment":      accomplish,
            "organizational_commitment":    org_commit,
            "social_support_score":         soc_support,
            "manager_support_score":        mgr_support,
            "team_cohesion":                team_coh,
            "workplace_relationships":      wp_rel,
            "isolation_feeling":            isolation,
            "coping_effectiveness":         coping,
            "resource_adequacy":            resources,
            "work_recovery_ability":        recovery,
            "resilience_score":             resilience,
            "burnout_trend":                b_trend_cat,
            "predicted_burnout_30days":     pred_30d,
            "predicted_burnout_90days":     pred_90d,
            "intervention_urgency":         urgency,
            "interventions_received":       n_interv,
            "last_intervention_date":       last_interv,
            "intervention_effectiveness":   interv_eff,
            "created_at":                   rand_datetime(assess_date),
            "last_updated":                 rand_datetime(assess_date),
        })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
def _build_stress_profiles(employees_df: pd.DataFrame) -> dict:
    """Local copy of stress profile builder (mirrors 03a logic)."""
    profiles = {}
    for _, row in employees_df.iterrows():
        base_stress = {"Low": 20, "Medium": 45, "High": 68}[row["stress_level"]]
        base_stress = clamp(base_stress + np.random.normal(0, 8), 5, 90)
        profiles[row["employee_id"]] = {
            "base_stress":  base_stress,
            "trend":        np.random.choice(["stable", "increasing", "decreasing"],
                                              p=[0.55, 0.25, 0.20]),
            "base_burnout": row["burnout_risk_score"],
            "capacity":     row["weekly_capacity_hours"],
            "perf_score":   row["historical_performance_score"],
        }
    return profiles


if __name__ == "__main__":
    print("Loading data...")
    emp_df   = pd.read_csv(f"{OUT_DIR}/employees.csv")
    tasks_df = pd.read_csv(f"{OUT_DIR}/tasks.csv")

    print(f"Generating {NUM_SCHEDULE_ROWS} schedules...")
    sch_df = generate_schedules(emp_df, tasks_df, NUM_SCHEDULE_ROWS)
    sch_df.to_csv(f"{OUT_DIR}/schedules.csv", index=False)
    print(f"  ✓ {len(sch_df)} rows → schedules.csv")

    print("Building stress profiles for burnout...")
    stress_profiles = _build_stress_profiles(emp_df)

    print(f"Generating {NUM_BURNOUT_ROWS} burnout indicators...")
    bi_df = generate_burnout_indicators(emp_df, stress_profiles, NUM_BURNOUT_ROWS)
    bi_df.to_csv(f"{OUT_DIR}/burnout_indicators.csv", index=False)
    print(f"  ✓ {len(bi_df)} rows → burnout_indicators.csv")

    print("\nSanity checks:")
    hire_map = dict(zip(emp_df["employee_id"], pd.to_datetime(emp_df["hire_date"])))

    sch_df["_hire"] = pd.to_datetime(sch_df["employee_id"].map(hire_map))
    sch_df["_date"] = pd.to_datetime(sch_df["date"])
    print(f"  schedules before hire_date: {(sch_df['_date'] < sch_df['_hire']).sum()}  (should be 0)")

    # Check end_time > start_time
    def to_mins(t):
        h, m, s = str(t).split(":")
        return int(h) * 60 + int(m)
    bad_times = (sch_df["end_time"].apply(to_mins) < sch_df["start_time"].apply(to_mins)).sum()
    print(f"  end_time < start_time: {bad_times}  (should be 0)")

    bi_df["_hire"] = pd.to_datetime(bi_df["employee_id"].map(hire_map))
    bi_df["_adate"] = pd.to_datetime(bi_df["assessment_date"])
    print(f"  burnout before hire_date: {(bi_df['_adate'] < bi_df['_hire']).sum()}  (should be 0)")
    print(f"  burnout category dist:\n{bi_df['burnout_category'].value_counts().to_string()}")
