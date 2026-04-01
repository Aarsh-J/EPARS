"""
03a_workload.py — Generate workload_history.csv
All records clamped to >= employee hire_date.
"""

import os, random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    HISTORY_START, HISTORY_END, SPECIAL_CIRC, WORK_LOCATIONS,
    clamp, rand_datetime,
)

random.seed(42)
np.random.seed(42)

NUM_WORKLOAD_ROWS = int(os.environ.get("NUM_WORKLOAD_ROWS", 1000))
OUT_DIR           = os.environ.get("OUT_DIR", "./output")

MULTITASK_LEVEL = ["Low", "Medium", "High"]
STRESS_CATS     = ["Low", "Medium", "High", "Very High"]
FATIGUE_LEVELS  = ["Low", "Medium", "High"]


def weekdays_in_range(start: date, end: date) -> list[date]:
    days, cur = [], start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def build_stress_profiles(employees_df: pd.DataFrame) -> dict:
    profiles = {}
    for _, row in employees_df.iterrows():
        base_stress = {"Low": 20, "Medium": 45, "High": 68}[row["stress_level"]]
        base_stress = clamp(base_stress + np.random.normal(0, 8), 5, 90)
        profiles[row["employee_id"]] = {
            "base_stress":   base_stress,
            "trend":         np.random.choice(["stable", "increasing", "decreasing"],
                                               p=[0.55, 0.25, 0.20]),
            "base_burnout":  row["burnout_risk_score"],
            "capacity":      row["weekly_capacity_hours"],
            "perf_score":    row["historical_performance_score"],
        }
    return profiles


def _make_oof_record(rec_id: int, emp_id: str, day: date) -> dict:
    return {
        "record_id": f"WH{rec_id:05d}", "employee_id": emp_id,
        "date": day.isoformat(), "week_number": day.isocalendar()[1],
        "month": day.strftime("%B"), "year": day.year,
        "total_hours_worked": 0.0, "regular_hours": 0.0, "overtime_hours": 0.0,
        "billable_hours": 0.0, "non_billable_hours": 0.0, "meeting_hours": 0.0,
        "focused_work_hours": 0.0, "context_switching_count": 0,
        "active_tasks_count": 0, "active_projects_count": 0,
        "tasks_completed": 0, "tasks_started": 0, "blocked_tasks_count": 0,
        "high_priority_tasks": 0, "workload_intensity_score": 0.0,
        "task_density": 0.0, "deadline_pressure_score": 0.0,
        "multitasking_level": "Low", "cognitive_load_estimate": 0.0,
        "productivity_score": 0.0, "efficiency_ratio": 0.0,
        "task_completion_rate": 0.0, "quality_of_work": None,
        "rework_time_hours": 0.0, "emails_sent": 0, "emails_received": 0,
        "chat_messages_sent": 0, "meetings_attended": 0, "collaboration_hours": 0.0,
        "stress_level": "Low", "stress_score": 0.0, "fatigue_level": "Low",
        "work_life_balance_today": 9.0, "late_hours_indicator": False,
        "weekend_work_indicator": False, "break_time_minutes": 0.0,
        "productivity_vs_avg": 0.0, "workload_vs_capacity": 0.0,
        "burnout_risk_today": 0.0, "engagement_score": 0.0,
        "special_circumstances": "Leave", "out_of_office": True,
        "worked_from": "Home",
    }


def generate_workload_history(employees_df: pd.DataFrame,
                               stress_profiles: dict,
                               n: int) -> pd.DataFrame:
    emp_ids  = employees_df["employee_id"].tolist()
    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}

    hist_start = date.fromisoformat(HISTORY_START)
    hist_end   = date.fromisoformat(HISTORY_END)
    all_workdays = weekdays_in_range(hist_start, hist_end)

    days_per_emp = max(10, n // len(emp_ids))
    rows, rec_id = [], 1

    for emp_id in emp_ids:
        profile  = stress_profiles[emp_id]
        hire_dt  = hire_map[emp_id]

        # Only sample workdays on/after hire_date
        valid_workdays = [d for d in all_workdays if d >= hire_dt]
        if not valid_workdays:
            continue

        day_list = sorted(random.sample(valid_workdays, min(days_per_emp, len(valid_workdays))))
        n_days   = len(day_list)
        base_s   = profile["base_stress"]
        trend    = profile["trend"]
        cap      = profile["capacity"]
        perf     = profile["perf_score"]

        for idx, day in enumerate(day_list):
            if random.random() < 0.08:
                rows.append(_make_oof_record(rec_id, emp_id, day))
                rec_id += 1
                continue

            drift = {"stable": 0, "increasing": 30 * (idx / n_days),
                     "decreasing": -20 * (idx / n_days)}[trend]
            stress_today = clamp(base_s + drift + np.random.normal(0, 6), 5, 95)

            daily_cap        = cap / 5
            overload_factor  = clamp(0.9 + (stress_today - 40) / 200, 0.85, 1.40)
            total_hours      = clamp(round(daily_cap * overload_factor + np.random.normal(0, 0.6), 1), 5, 14)
            regular_hrs      = min(total_hours, daily_cap)
            overtime_hrs     = max(0, round(total_hours - regular_hrs, 1))
            billable         = round(total_hours * random.uniform(0.6, 0.9), 1)
            non_bill         = round(total_hours - billable, 1)
            mtg_hrs          = clamp(round(np.random.normal(2.0, 1.0), 1), 0, min(4, total_hours))
            focused_hrs      = clamp(round(total_hours - mtg_hrs - random.uniform(0.5, 1.5), 1), 0.5, total_hours)
            ctx_switches     = random.randint(3, 25)

            active_tasks     = random.randint(1, 8)
            active_projects  = random.randint(1, 3)
            tasks_done       = random.randint(0, min(3, active_tasks))
            tasks_started    = random.randint(0, 2)
            blocked          = random.randint(0, min(2, active_tasks - tasks_done))
            hi_pri           = random.randint(0, min(3, active_tasks))

            intensity    = clamp(round(stress_today * 0.9 + np.random.normal(0, 8), 1), 10, 100)
            task_density = clamp(round(active_tasks / max(focused_hrs, 1), 2), 0.1, 3.0)
            dl_pressure  = clamp(round(intensity * 0.85 + np.random.normal(0, 10), 1), 5, 100)
            multitask    = "High" if active_tasks >= 6 else ("Medium" if active_tasks >= 3 else "Low")
            cog_load     = clamp(round(intensity / 10 + np.random.normal(0, 0.5), 1), 1, 10)

            # Linear penalty across full stress range: mild at low stress, strong at high
            # At stress=5 → penalty~1.5, at stress=50 → penalty~15, at stress=95 → penalty~28.5
            stress_penalty = stress_today * 0.3
            productivity   = clamp(round(perf - stress_penalty + np.random.normal(0, 8), 1), 20, 100)
            efficiency     = clamp(round(productivity / 80, 2), 0.4, 1.5)
            comp_rate      = clamp(round(productivity * 0.9 + np.random.normal(0, 8), 1), 20, 100)
            quality        = clamp(round(8.0 - stress_today / 40 + np.random.normal(0, 0.7), 1), 3, 10)
            rework_time    = round(max(0, np.random.exponential(0.3) if quality < 7 else 0), 1)

            emails_sent    = random.randint(3, 35)
            emails_recv    = random.randint(10, 80)
            chat_msgs      = random.randint(10, 150)
            mtgs_attended  = random.randint(0, int(mtg_hrs) + 1)
            collab_hrs     = clamp(round(mtg_hrs + random.uniform(0, 2), 1), 0, total_hours)

            stress_cat     = ("Very High" if stress_today > 75 else "High" if stress_today > 55
                              else "Medium" if stress_today > 35 else "Low")
            fatigue        = "High" if stress_today > 65 else ("Medium" if stress_today > 40 else "Low")
            wlb            = clamp(round(9 - stress_today / 15 + np.random.normal(0, 0.6), 1), 1, 10)
            late_hours     = overtime_hrs > 1.5
            weekend        = day.weekday() >= 5
            break_mins     = clamp(round(np.random.normal(45, 15), 0), 10, 90)

            prod_vs_avg    = clamp(round(productivity - perf + np.random.normal(0, 5), 1), -40, 40)
            wl_vs_cap      = clamp(round((total_hours / daily_cap) * 100, 1), 50, 140)
            burnout_today  = clamp(round(stress_today * 0.85 + overtime_hrs * 2 + np.random.normal(0, 5), 1), 5, 100)
            engagement     = clamp(round(10 - burnout_today / 15 + np.random.normal(0, 0.6), 1), 2, 10)

            rows.append({
                "record_id":               f"WH{rec_id:05d}",
                "employee_id":             emp_id,
                "date":                    day.isoformat(),
                "week_number":             day.isocalendar()[1],
                "month":                   day.strftime("%B"),
                "year":                    day.year,
                "total_hours_worked":      total_hours,
                "regular_hours":           round(regular_hrs, 1),
                "overtime_hours":          overtime_hrs,
                "billable_hours":          billable,
                "non_billable_hours":      non_bill,
                "meeting_hours":           mtg_hrs,
                "focused_work_hours":      focused_hrs,
                "context_switching_count": ctx_switches,
                "active_tasks_count":      active_tasks,
                "active_projects_count":   active_projects,
                "tasks_completed":         tasks_done,
                "tasks_started":           tasks_started,
                "blocked_tasks_count":     blocked,
                "high_priority_tasks":     hi_pri,
                "workload_intensity_score":intensity,
                "task_density":            task_density,
                "deadline_pressure_score": dl_pressure,
                "multitasking_level":      multitask,
                "cognitive_load_estimate": cog_load,
                "productivity_score":      productivity,
                "efficiency_ratio":        efficiency,
                "task_completion_rate":    comp_rate,
                "quality_of_work":         quality,
                "rework_time_hours":       rework_time,
                "emails_sent":             emails_sent,
                "emails_received":         emails_recv,
                "chat_messages_sent":      chat_msgs,
                "meetings_attended":       mtgs_attended,
                "collaboration_hours":     collab_hrs,
                "stress_level":            stress_cat,
                "stress_score":            round(stress_today, 1),
                "fatigue_level":           fatigue,
                "work_life_balance_today": wlb,
                "late_hours_indicator":    late_hours,
                "weekend_work_indicator":  weekend,
                "break_time_minutes":      break_mins,
                "productivity_vs_avg":     prod_vs_avg,
                "workload_vs_capacity":    wl_vs_cap,
                "burnout_risk_today":      burnout_today,
                "engagement_score":        engagement,
                "special_circumstances":   random.choice(SPECIAL_CIRC),
                "out_of_office":           False,
                "worked_from":             np.random.choice(WORK_LOCATIONS, p=[0.30, 0.45, 0.15, 0.10]),
            })
            rec_id += 1

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading employees...")
    emp_df = pd.read_csv(f"{OUT_DIR}/employees.csv")

    print("Building stress profiles...")
    stress_profiles = build_stress_profiles(emp_df)

    print(f"Generating workload_history (target ~{NUM_WORKLOAD_ROWS} rows)...")
    wh_df = generate_workload_history(emp_df, stress_profiles, NUM_WORKLOAD_ROWS)
    wh_df.to_csv(f"{OUT_DIR}/workload_history.csv", index=False)
    print(f"  ✓ {len(wh_df)} rows → workload_history.csv")

    print("\nSanity checks:")
    print(f"  all employee_ids valid: {wh_df['employee_id'].isin(emp_df['employee_id']).all()}")
    avg_hrs = wh_df[~wh_df['out_of_office']]['total_hours_worked'].mean()
    print(f"  avg daily hours (working days): {avg_hrs:.2f}")
    print(f"  stress distribution:\n{wh_df['stress_level'].value_counts().to_string()}")

    hire_map = dict(zip(emp_df["employee_id"], pd.to_datetime(emp_df["hire_date"])))
    wh_df["_hire"] = pd.to_datetime(wh_df["employee_id"].map(hire_map))
    wh_df["_date"] = pd.to_datetime(wh_df["date"])
    before_hire = (wh_df["_date"] < wh_df["_hire"]).sum()
    print(f"  records before hire_date: {before_hire}  (should be 0)")
