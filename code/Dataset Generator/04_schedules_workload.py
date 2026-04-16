"""
04_schedules_workload.py — Generate schedules.csv and workload_history.csv (V3 schema).
- Schedule dates clamped >= employee hire_date
- Workload records are per employee × sampled workday
"""

import os, random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from config import (
    HISTORY_START, HISTORY_END,
    EVENT_TYPES, EVENT_WEIGHTS, MTG_TYPES, ATTEND_STATUS, ATTEND_WEIGHTS,
    DURATION_BY_TYPE, EVENT_TITLES, SPECIAL_CIRC, WORK_LOCATIONS,
    PRIORITY, EMP_TYPE_BILLABLE,
    clamp, rand_date, rand_datetime, add_minutes, weekdays_in_range,
)

random.seed(42)
np.random.seed(42)

NUM_SCHEDULE_ROWS = int(os.environ.get("NUM_SCHEDULE_ROWS", 4000))
NUM_WORKLOAD_ROWS = int(os.environ.get("NUM_WORKLOAD_ROWS", 1000))
OUT_DIR           = os.environ.get("OUT_DIR", "./output")


# ─── Score helpers ────────────────────────────────────────────────────────────

def calc_workload_intensity(active_tasks: int, overtime_hrs: float,
                             high_priority: int) -> float:
    """
    workload_intensity_score:
      = (active_tasks / 8) × 40 + (overtime_hrs / 4) × 30 + (high_priority / 3) × 30
      clamped 0-100
    """
    task_contrib     = min(active_tasks / 8.0, 1.0) * 40
    overtime_contrib = min(overtime_hrs  / 4.0, 1.0) * 30
    hipri_contrib    = min(high_priority / 3.0, 1.0) * 30
    base = task_contrib + overtime_contrib + hipri_contrib
    return clamp(round(base + np.random.normal(0, 5), 1), 0.0, 100.0)


def calc_deadline_pressure(high_priority: int, blocked: int,
                            intensity: float) -> float:
    """
    deadline_pressure_score:
      = (high_priority / 3) × 50 + (blocked / 2) × 20 + intensity × 0.30
      clamped 0-100
    """
    hipri_contrib   = min(high_priority / 3.0, 1.0) * 50
    blocked_contrib = min(blocked       / 2.0, 1.0) * 20
    intensity_part  = intensity * 0.30
    base = hipri_contrib + blocked_contrib + intensity_part
    return clamp(round(base + np.random.normal(0, 8), 1), 0.0, 100.0)


def calc_productivity_score(tasks_completed: int, active_tasks: int,
                             quality_of_work, efficiency_ratio: float,
                             base_perf: float, stress_today: float) -> float:
    """
    productivity_score:
      = tcr × 35% + quality_norm × 35% + efficiency_norm × 15%
        + base_perf_scaled × 15%
      — penalised by stress: subtract stress × 0.25
      clamped 0-100
    """
    total = tasks_completed + active_tasks
    tcr   = (tasks_completed / max(total, 1)) * 100

    q_val = float(quality_of_work) if quality_of_work is not None else 7.0
    quality_norm = (q_val / 10.0) * 100

    eff_norm = min(efficiency_ratio, 1.5) / 1.5 * 100

    stress_penalty = stress_today * 0.25
    base = (tcr * 0.35 + quality_norm * 0.35 + eff_norm * 0.15
            + base_perf * 0.15 - stress_penalty)
    return clamp(round(base + np.random.normal(0, 5), 1), 10.0, 100.0)


def calc_efficiency_ratio(tasks_completed: int, total_hours: float) -> float:
    """
    efficiency_ratio (0-100+):
      tasks_completed × 10 / total_hours × 100, normalised
      Values > 100 are valid (faster than baseline)
    """
    if total_hours < 0.1:
        return 80.0
    raw = (tasks_completed * 10.0 / total_hours) * 10   # ×10 tuning factor
    return clamp(round(raw + np.random.normal(0, 5), 1), 20.0, 140.0)


def calc_burnout_risk_today(intensity: float, deadline_pressure: float,
                             overtime_hrs: float, wl_vs_cap: float) -> float:
    """
    burnout_risk_today:
      = intensity × 0.35 + deadline_pressure × 0.25
        + overtime_norm × 0.25 + overcapacity_norm × 0.15
      clamped 0-100
    """
    overtime_norm    = min(overtime_hrs  / 4.0, 1.0) * 100
    overcap_norm     = max(wl_vs_cap - 100, 0) * 0.5   # only kicks in above 100%
    base = (intensity * 0.35 + deadline_pressure * 0.25
            + overtime_norm * 0.25 + overcap_norm * 0.15)
    return clamp(round(base + np.random.normal(0, 5), 1), 0.0, 100.0)


def calc_optimization_score(has_conflict: bool, start_h: int,
                              pref_work_hours: str) -> float:
    """
    optimization_score:
      base = 100
      - 30 if conflict present
      + 15 if start_h aligns with preferred_work_hours window
      + Normal(0, 8) noise
    """
    conflict_penalty = 30 if has_conflict else 0
    pref_bonus = 0
    pref_map = {
        "9am-5pm":  (9, 17),
        "10am-6pm": (10, 18),
        "8am-4pm":  (8, 16),
        "Flexible": (0, 23),
    }
    lo, hi = pref_map.get(pref_work_hours, (9, 17))
    if lo <= start_h <= hi - 1:
        pref_bonus = 15
    base = 100 - conflict_penalty + pref_bonus
    return clamp(round(base + np.random.normal(0, 8), 1), 10.0, 100.0)


# ─── SCHEDULES ────────────────────────────────────────────────────────────────
def generate_schedules(employees_df: pd.DataFrame,
                        tasks_df: pd.DataFrame,
                        n: int) -> pd.DataFrame:
    emp_ids  = employees_df["employee_id"].tolist()
    task_ids = tasks_df["task_id"].tolist()
    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}
    pref_hrs_map = dict(zip(employees_df["employee_id"],
                            employees_df["preferred_work_hours"]))
    remote_map   = dict(zip(employees_df["employee_id"],
                            employees_df["remote_work_status"]))

    hist_start   = date.fromisoformat(HISTORY_START)
    hist_end     = date.fromisoformat(HISTORY_END)
    all_workdays = weekdays_in_range(hist_start, hist_end)

    emp_valid_days: dict = {}
    for emp_id in emp_ids:
        hire_dt = hire_map[emp_id]
        emp_valid_days[emp_id] = [d for d in all_workdays if d >= hire_dt]

    rows = []
    for i in range(1, n + 1):
        sch_id = f"SCH{i:05d}"
        emp_id = random.choice(emp_ids)
        valid  = emp_valid_days[emp_id]
        if not valid:
            continue
        day = random.choice(valid)

        ev_type  = np.random.choice(EVENT_TYPES, p=EVENT_WEIGHTS)
        title    = random.choice(EVENT_TITLES[ev_type])
        duration = random.choice(DURATION_BY_TYPE[ev_type])

        start_h  = random.randint(8, 17)
        start_m  = random.choice([0, 15, 30, 45])
        start_t  = f"{start_h:02d}:{start_m:02d}:00"
        end_t    = add_minutes(start_t, duration)

        related_id = random.choice(task_ids) if ev_type == "Task" else None

        priority     = np.random.choice(PRIORITY, p=[0.20, 0.40, 0.30, 0.10])
        is_flex      = random.random() > 0.50
        buf_mins     = random.choice([0, 15, 30]) if random.random() > 0.60 else 0

        has_conflict   = random.random() < 0.08
        conflict_ids   = f"SCH{random.randint(1, n):05d}" if has_conflict else None

        pref_hrs     = pref_hrs_map.get(emp_id, "9am-5pm")
        opt_score    = calc_optimization_score(has_conflict, start_h, pref_hrs)
        rec_time_str = f"{random.randint(9,16):02d}:{random.choice([0,15,30,45]):02d}:00" \
                       if opt_score < 55 else None

        attend       = np.random.choice(ATTEND_STATUS, p=ATTEND_WEIGHTS)
        completed_ev = attend == "Completed"

        act_start = add_minutes(start_t, random.randint(-5, 10)) if completed_ev else None
        act_dur   = duration + random.randint(-10, 15) if completed_ev else None
        act_end   = add_minutes(act_start, act_dur) if completed_ev else None

        # productivity_during: from event_type proxy (Focus Time most productive)
        if completed_ev:
            prod_base = {"Focus Time": 80, "Task": 72, "Meeting": 55,
                         "Training": 60, "Break": 40, "Leave": 20}.get(ev_type, 65)
            prod_during = clamp(round(prod_base + np.random.normal(0, 10), 1), 20.0, 100.0)
        else:
            prod_during = None

        involves_team  = ev_type in ("Meeting", "Training") or random.random() < 0.30
        part_cnt       = random.randint(2, 10) if involves_team else 1
        participant_ids= ",".join(
            random.sample([e for e in emp_ids if e != emp_id],
                          min(part_cnt - 1, len(emp_ids) - 1))
        ) if involves_team and len(emp_ids) > 1 else None
        mtg_type = random.choice(MTG_TYPES) if ev_type == "Meeting" else None

        remote_status = remote_map.get(emp_id, "Office")
        is_remote  = remote_status in ("Remote", "Hybrid") and random.random() > 0.40
        location   = "Virtual" if is_remote else random.choice(
            ["Office", "Home", "Conference Room A", "Conference Room B"])
        mtg_link   = f"https://zoom.us/j/{random.randint(10_000_000, 99_999_999)}" \
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
            "priority":                priority,
            "is_flexible":             is_flex,
            "buffer_minutes":          buf_mins,
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
            "participant_count":       part_cnt,
            "meeting_type":            mtg_type,
            "location":                location,
            "is_remote":               is_remote,
            "meeting_link":            mtg_link,
            "created_at":              f"{day} 09:00:00",
            "last_updated":            rand_datetime(day),
        })

    return pd.DataFrame(rows)


# ─── WORKLOAD HISTORY ─────────────────────────────────────────────────────────
def build_stress_profiles(employees_df: pd.DataFrame) -> dict:
    profiles = {}
    for _, row in employees_df.iterrows():
        base_burnout = float(row.get("burnout_risk_score", 30))
        base_stress  = {"Low": 20, "Medium": 45, "High": 68}.get(
            str(row.get("stress_level", "Low")), 30
        )
        base_stress  = clamp(base_stress + np.random.normal(0, 8), 5, 90)
        trend        = np.random.choice(["stable", "increasing", "decreasing"],
                                         p=[0.55, 0.25, 0.20])
        profiles[row["employee_id"]] = {
            "base_stress":  base_stress,
            "trend":        trend,
            "base_burnout": base_burnout,
            "capacity":     float(row.get("weekly_capacity_hours", 40)),
            "perf_score":   float(row.get("historical_performance_score", 73)),
            "emp_type":     str(row.get("employment_type", "Full-time")),
            "remote":       str(row.get("remote_work_status", "Office")),
            "pref_hours":   str(row.get("preferred_work_hours", "9am-5pm")),
        }
    return profiles


def _oof_record(rec_id: int, emp_id: str, day: date) -> dict:
    return {
        "record_id":               f"WH{rec_id:05d}",
        "employee_id":             emp_id,
        "date":                    day.isoformat(),
        "week_number":             day.isocalendar()[1],
        "total_hours_worked":      0.0,
        "overtime_hours":          0.0,
        "billable_hours":          0.0,
        "non_billable_hours":      0.0,
        "meeting_hours":           0.0,
        "focused_work_hours":      0.0,
        "context_switching_count": 0,
        "active_tasks_count":      0,
        "active_projects_count":   0,
        "tasks_completed":         0,
        "tasks_started":           0,
        "blocked_tasks_count":     0,
        "high_priority_tasks":     0,
        "workload_intensity_score":0.0,
        "deadline_pressure_score": 0.0,
        "productivity_score":      0.0,
        "efficiency_ratio":        0.0,
        "task_completion_rate":    0.0,
        "quality_of_work":         None,
        "rework_time_hours":       0.0,
        "meetings_attended":       0,
        "collaboration_hours":     0.0,
        "stress_level":            "Low",
        "weekend_work_indicator":  day.weekday() >= 5,
        "break_time_minutes":      0.0,
        "productivity_vs_avg":     0.0,
        "workload_vs_capacity":    0.0,
        "burnout_risk_today":      0.0,
        "special_circumstances":   "Leave",
        "out_of_office":           True,
        "worked_from":             "Home",
        "created_at":              f"{day} 09:00:00",
    }


def generate_workload_history(employees_df: pd.DataFrame,
                               stress_profiles: dict,
                               n: int) -> pd.DataFrame:
    emp_ids  = employees_df["employee_id"].tolist()
    hire_map = {row["employee_id"]: date.fromisoformat(row["hire_date"])
                for _, row in employees_df.iterrows()}

    hist_start   = date.fromisoformat(HISTORY_START)
    hist_end     = date.fromisoformat(HISTORY_END)
    all_workdays = weekdays_in_range(hist_start, hist_end)

    days_per_emp = max(10, n // max(len(emp_ids), 1))
    rows, rec_id = [], 1

    for emp_id in emp_ids:
        prof     = stress_profiles[emp_id]
        hire_dt  = hire_map[emp_id]
        valid_wd = [d for d in all_workdays if d >= hire_dt]
        if not valid_wd:
            continue

        day_list = sorted(random.sample(valid_wd, min(days_per_emp, len(valid_wd))))
        n_days   = len(day_list)
        base_s   = prof["base_stress"]
        trend    = prof["trend"]
        cap      = prof["capacity"]
        perf     = prof["perf_score"]
        emp_type = prof["emp_type"]
        billable_r = EMP_TYPE_BILLABLE.get(emp_type, 0.80)

        for idx, day in enumerate(day_list):
            # 8% chance of OOF
            if random.random() < 0.08:
                rows.append(_oof_record(rec_id, emp_id, day))
                rec_id += 1
                continue

            drift = {"stable": 0,
                     "increasing":  30 * (idx / max(n_days, 1)),
                     "decreasing": -20 * (idx / max(n_days, 1))}[trend]
            stress_today = clamp(base_s + drift + np.random.normal(0, 6), 5, 95)

            daily_cap       = cap / 5
            overload_factor = clamp(0.90 + (stress_today - 40) / 200, 0.85, 1.40)
            total_hours     = clamp(round(daily_cap * overload_factor + np.random.normal(0, 0.6), 1), 5, 14)
            overtime_hrs    = max(0.0, round(total_hours - daily_cap, 1))
            billable        = round(total_hours * random.uniform(billable_r - 0.10, billable_r + 0.05), 1)
            non_bill        = round(total_hours - billable, 1)
            mtg_hrs         = clamp(round(np.random.normal(2.0, 1.0), 1), 0, min(4, total_hours))
            break_mins      = clamp(round(np.random.normal(45, 15)), 10, 90)
            focused_hrs     = clamp(round(total_hours - mtg_hrs - break_mins / 60, 1), 0.5, total_hours)
            ctx_switches    = random.randint(3, 25)

            active_tasks    = random.randint(1, 8)
            active_projects = random.randint(1, 3)
            tasks_done      = random.randint(0, min(3, active_tasks))
            tasks_started   = random.randint(0, 2)
            blocked         = random.randint(0, min(2, max(active_tasks - tasks_done, 0)))
            hi_pri          = random.randint(0, min(3, active_tasks))

            intensity  = calc_workload_intensity(active_tasks, overtime_hrs, hi_pri)
            dl_pressure= calc_deadline_pressure(hi_pri, blocked, intensity)

            eff_ratio  = calc_efficiency_ratio(tasks_done, total_hours)
            quality_wk = clamp(round(8.0 - stress_today / 40 + np.random.normal(0, 0.7), 1), 3, 10) \
                         if tasks_done > 0 else None
            productivity = calc_productivity_score(
                tasks_done, active_tasks, quality_wk, eff_ratio / 100, perf, stress_today
            )

            tcr         = round(tasks_done / max(tasks_done + active_tasks, 1) * 100, 1)
            rework_time = round(max(0, np.random.exponential(0.3)) if quality_wk and quality_wk < 7 else 0, 1)

            mtgs_attended = random.randint(0, int(mtg_hrs) + 1)
            collab_hrs    = clamp(round(mtg_hrs + random.uniform(0, 1.5), 1), 0, total_hours)

            stress_cat = ("High"   if stress_today > 66
                          else "Medium" if stress_today > 33 else "Low")

            weekend = day.weekday() >= 5
            prod_vs_avg = clamp(round(productivity - perf + np.random.normal(0, 5), 1), -40, 40)
            wl_vs_cap   = clamp(round(total_hours / max(daily_cap, 1) * 100, 1), 50, 140)
            burnout_today = calc_burnout_risk_today(intensity, dl_pressure, overtime_hrs, wl_vs_cap)

            remote_pref = prof["remote"]
            worked_from = (np.random.choice(["Home", "Remote"], p=[0.6, 0.4])
                           if remote_pref == "Remote"
                           else np.random.choice(["Office", "Home"], p=[0.6, 0.4])
                           if remote_pref == "Hybrid"
                           else "Office")

            rows.append({
                "record_id":               f"WH{rec_id:05d}",
                "employee_id":             emp_id,
                "date":                    day.isoformat(),
                "week_number":             day.isocalendar()[1],
                "total_hours_worked":      total_hours,
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
                "deadline_pressure_score": dl_pressure,
                "productivity_score":      productivity,
                "efficiency_ratio":        eff_ratio,
                "task_completion_rate":    tcr,
                "quality_of_work":         quality_wk,
                "rework_time_hours":       rework_time,
                "meetings_attended":       mtgs_attended,
                "collaboration_hours":     collab_hrs,
                "stress_level":            stress_cat,
                "weekend_work_indicator":  weekend,
                "break_time_minutes":      float(break_mins),
                "productivity_vs_avg":     prod_vs_avg,
                "workload_vs_capacity":    wl_vs_cap,
                "burnout_risk_today":      burnout_today,
                "special_circumstances":   random.choice(SPECIAL_CIRC),
                "out_of_office":           False,
                "worked_from":             worked_from,
                "created_at":              f"{day} 09:00:00",
            })
            rec_id += 1

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading data...")
    emp_df   = pd.read_csv(f"{OUT_DIR}/employees.csv")
    tasks_df = pd.read_csv(f"{OUT_DIR}/tasks.csv")

    print(f"Generating {NUM_SCHEDULE_ROWS} schedules...")
    sch_df = generate_schedules(emp_df, tasks_df, NUM_SCHEDULE_ROWS)
    sch_df.to_csv(f"{OUT_DIR}/schedules.csv", index=False)
    print(f"  OK {len(sch_df)} rows -> schedules.csv")

    print("Building stress profiles...")
    stress_profiles = build_stress_profiles(emp_df)

    print(f"Generating workload_history (target ~{NUM_WORKLOAD_ROWS} rows)...")
    wh_df = generate_workload_history(emp_df, stress_profiles, NUM_WORKLOAD_ROWS)
    wh_df.to_csv(f"{OUT_DIR}/workload_history.csv", index=False)
    print(f"  OK {len(wh_df)} rows -> workload_history.csv")

    print("\nSanity checks:")
    hire_map = dict(zip(emp_df["employee_id"], pd.to_datetime(emp_df["hire_date"])))
    sch_df["_hire"] = pd.to_datetime(sch_df["employee_id"].map(hire_map))
    sch_df["_date"] = pd.to_datetime(sch_df["date"])
    print(f"  schedules before hire_date: {(sch_df['_date'] < sch_df['_hire']).sum()} (should be 0)")

    def to_mins(t):
        h, m, _ = str(t).split(":")
        return int(h) * 60 + int(m)
    bad_times = (sch_df["end_time"].apply(to_mins) < sch_df["start_time"].apply(to_mins)).sum()
    print(f"  end_time < start_time: {bad_times} (should be 0)")

    wh_df["_hire"] = pd.to_datetime(wh_df["employee_id"].map(hire_map))
    wh_df["_date"] = pd.to_datetime(wh_df["date"])
    print(f"  workload before hire_date: {(wh_df['_date'] < wh_df['_hire']).sum()} (should be 0)")
    working = wh_df[~wh_df["out_of_office"]]
    print(f"  avg daily hours (working): {working['total_hours_worked'].mean():.2f}")
    print(f"  stress dist:\n{wh_df['stress_level'].value_counts().to_string()}")
