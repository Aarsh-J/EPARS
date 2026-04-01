"""
Part 3: Generate workload_history.csv, schedules.csv, burnout_indicators.csv
Dependencies: numpy, pandas
Requires: employees.csv, projects.csv, tasks.csv (from Parts 1 & 2)
Usage: python generate_part3.py
Output: workload_history.csv, schedules.csv, burnout_indicators.csv
"""

import random
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta

random.seed(42)
np.random.seed(42)

OUT_DIR = "."

# ─── Date range for time-series data ─────────────────────────────────────────
HISTORY_START = date(2024, 1, 1)
HISTORY_END   = date(2025, 2, 28)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def rand_time(h_lo=8, h_hi=18):
    h = random.randint(h_lo, h_hi)
    m = random.choice([0, 15, 30, 45])
    return f"{h:02d}:{m:02d}:00"

def add_minutes(time_str, minutes):
    h, m, s = map(int, time_str.split(":"))
    total = h * 60 + m + minutes
    return f"{(total // 60) % 24:02d}:{total % 60:02d}:00"

def rand_datetime_str(d: date) -> str:
    h, m = random.randint(8, 18), random.choice([0, 15, 30, 45])
    return f"{d} {h:02d}:{m:02d}:00"

def weekdays_in_range(start: date, end: date):
    """Return list of weekday dates (Mon-Fri) in range."""
    days = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days

# ─── Employee stress profiles (stable per employee, slight drift over time) ───
def build_stress_profiles(employees_df):
    """Assign each employee a base stress level and burnout trajectory."""
    profiles = {}
    for _, row in employees_df.iterrows():
        base_stress = {"Low": 20, "Medium": 45, "High": 68}[row["stress_level"]]
        # Add individual noise
        base_stress = clamp(base_stress + np.random.normal(0, 8), 5, 90)
        trend = np.random.choice(["stable", "increasing", "decreasing"], p=[0.55, 0.25, 0.20])
        profiles[row["employee_id"]] = {
            "base_stress":   base_stress,
            "trend":         trend,
            "base_burnout":  row["burnout_risk_score"],
            "overtime_rate": row["recent_overtime_hours"] / 30,  # daily avg
            "capacity":      row["weekly_capacity_hours"],
            "perf_score":    row["historical_performance_score"],
        }
    return profiles


# ═══════════════════════════════════════════════════════════════════════════════
# 1. WORKLOAD HISTORY
# ═══════════════════════════════════════════════════════════════════════════════
MULTITASK_LEVEL = ["Low", "Medium", "High"]
STRESS_LEVELS   = ["Low", "Medium", "High", "Very High"]
FATIGUE_LEVELS  = ["Low", "Medium", "High"]
WORK_LOCATIONS  = ["Office", "Home", "Remote", "Client Site"]
SPECIAL_CIRC    = ["Holiday", "Training Day", "Client Visit", "Team Offsite", None, None, None, None]

MAX_WH_ROWS = 12000   # cap total rows to stay within schema recommendation

def generate_workload_history(employees_df, stress_profiles):
    """Sampled working-day records per employee, capped at MAX_WH_ROWS total."""
    emp_ids   = employees_df["employee_id"].tolist()
    workdays  = weekdays_in_range(HISTORY_START, HISTORY_END)

    # Each employee gets ~MAX_WH_ROWS / n_employees sampled days
    days_per_emp = max(10, MAX_WH_ROWS // len(emp_ids))

    rows   = []
    rec_id = 1

    for emp_id in emp_ids:
        profile  = stress_profiles[emp_id]
        base_s   = profile["base_stress"]
        trend    = profile["trend"]
        cap      = profile["capacity"]
        day_list = sorted(random.sample(workdays, min(days_per_emp, len(workdays))))
        n_days   = len(day_list)

        for idx, day in enumerate(day_list):
            # Skip ~8% days (leave / absence)
            if random.random() < 0.08:
                rows.append(_make_oof_record(rec_id, emp_id, day))
                rec_id += 1
                continue

            # Drift stress over time
            drift = {"stable": 0, "increasing": 30 * (idx / n_days),
                     "decreasing": -20 * (idx / n_days)}[trend]
            stress_today = clamp(base_s + drift + np.random.normal(0, 6), 5, 95)

            # Work hours — base ~8h/day, stress pushes overtime
            daily_cap    = cap / 5
            overload_factor = clamp(0.9 + (stress_today - 40) / 200, 0.85, 1.40)
            total_hours  = clamp(round(daily_cap * overload_factor + np.random.normal(0, 0.6), 1), 5, 14)
            regular_hrs  = min(total_hours, daily_cap)
            overtime_hrs = max(0, round(total_hours - regular_hrs, 1))
            billable     = round(total_hours * random.uniform(0.6, 0.9), 1)
            non_bill     = round(total_hours - billable, 1)
            mtg_hrs      = clamp(round(np.random.normal(2.0, 1.0), 1), 0, min(4, total_hours))
            focused_hrs  = clamp(round(total_hours - mtg_hrs - random.uniform(0.5, 1.5), 1), 0.5, total_hours)
            ctx_switches = random.randint(3, 25)

            # Task/project load
            active_tasks    = random.randint(1, 8)
            active_projects = random.randint(1, 3)
            tasks_done      = random.randint(0, min(3, active_tasks))
            tasks_started   = random.randint(0, 2)
            blocked         = random.randint(0, min(2, active_tasks - tasks_done))
            hi_pri          = random.randint(0, min(3, active_tasks))

            # Workload intensity driven by stress
            intensity    = clamp(round(stress_today * 0.9 + np.random.normal(0, 8), 1), 10, 100)
            task_density = clamp(round(active_tasks / max(focused_hrs, 1), 2), 0.1, 3.0)
            dl_pressure  = clamp(round(intensity * 0.85 + np.random.normal(0, 10), 1), 5, 100)
            multitask    = "High" if active_tasks >= 6 else ("Medium" if active_tasks >= 3 else "Low")
            cog_load     = clamp(round(intensity / 10 + np.random.normal(0, 0.5), 1), 1, 10)

            # Productivity — inversely related to high stress
            prod_base    = profile["perf_score"]
            stress_penalty = max(0, (stress_today - 50) * 0.3)
            productivity = clamp(round(prod_base - stress_penalty + np.random.normal(0, 8), 1), 20, 100)
            efficiency   = clamp(round(productivity / 80, 2), 0.4, 1.5)
            comp_rate    = clamp(round(productivity * 0.9 + np.random.normal(0, 8), 1), 20, 100)
            quality      = clamp(round(8.0 - stress_today / 40 + np.random.normal(0, 0.7), 1), 3, 10)
            rework_time  = round(max(0, np.random.exponential(0.3) if quality < 7 else 0), 1)

            # Communication
            emails_sent  = random.randint(3, 35)
            emails_recv  = random.randint(10, 80)
            chat_msgs    = random.randint(10, 150)
            mtgs_attended= random.randint(0, int(mtg_hrs) + 1)
            collab_hrs   = clamp(round(mtg_hrs + random.uniform(0, 2), 1), 0, total_hours)

            # Well-being
            stress_cat   = "Very High" if stress_today > 75 else ("High" if stress_today > 55
                           else ("Medium" if stress_today > 35 else "Low"))
            fatigue      = "High" if stress_today > 65 else ("Medium" if stress_today > 40 else "Low")
            wlb          = clamp(round(9 - stress_today / 15 + np.random.normal(0, 0.6), 1), 1, 10)
            late_hours   = overtime_hrs > 1.5
            weekend      = day.weekday() >= 5
            break_mins   = clamp(round(np.random.normal(45, 15), 0), 10, 90)

            # Performance trends
            prod_vs_avg  = clamp(round(productivity - prod_base + np.random.normal(0, 5), 1), -40, 40)
            wl_vs_cap    = clamp(round((total_hours / daily_cap) * 100, 1), 50, 140)
            burnout_today= clamp(round(stress_today * 0.85 + overtime_hrs * 2 + np.random.normal(0, 5), 1), 5, 100)
            engagement   = clamp(round(10 - burnout_today / 15 + np.random.normal(0, 0.6), 1), 2, 10)

            rows.append({
                "record_id":              f"WH{rec_id:05d}",
                "employee_id":            emp_id,
                "date":                   day.isoformat(),
                "week_number":            day.isocalendar()[1],
                "month":                  day.strftime("%B"),
                "year":                   day.year,
                "total_hours_worked":     total_hours,
                "regular_hours":          round(regular_hrs, 1),
                "overtime_hours":         overtime_hrs,
                "billable_hours":         billable,
                "non_billable_hours":     non_bill,
                "meeting_hours":          mtg_hrs,
                "focused_work_hours":     focused_hrs,
                "context_switching_count":ctx_switches,
                "active_tasks_count":     active_tasks,
                "active_projects_count":  active_projects,
                "tasks_completed":        tasks_done,
                "tasks_started":          tasks_started,
                "blocked_tasks_count":    blocked,
                "high_priority_tasks":    hi_pri,
                "workload_intensity_score":intensity,
                "task_density":           task_density,
                "deadline_pressure_score":dl_pressure,
                "multitasking_level":     multitask,
                "cognitive_load_estimate":cog_load,
                "productivity_score":     productivity,
                "efficiency_ratio":       efficiency,
                "task_completion_rate":   comp_rate,
                "quality_of_work":        quality,
                "rework_time_hours":      rework_time,
                "emails_sent":            emails_sent,
                "emails_received":        emails_recv,
                "chat_messages_sent":     chat_msgs,
                "meetings_attended":      mtgs_attended,
                "collaboration_hours":    collab_hrs,
                "stress_level":           stress_cat,
                "stress_score":           round(stress_today, 1),
                "fatigue_level":          fatigue,
                "work_life_balance_today":wlb,
                "late_hours_indicator":   late_hours,
                "weekend_work_indicator": weekend,
                "break_time_minutes":     break_mins,
                "productivity_vs_avg":    prod_vs_avg,
                "workload_vs_capacity":   wl_vs_cap,
                "burnout_risk_today":     burnout_today,
                "engagement_score":       engagement,
                "special_circumstances":  random.choice(SPECIAL_CIRC),
                "out_of_office":          False,
                "worked_from":            np.random.choice(WORK_LOCATIONS, p=[0.30, 0.45, 0.15, 0.10]),
            })
            rec_id += 1

    return pd.DataFrame(rows)


def _make_oof_record(rec_id, emp_id, day):
    """Out-of-office day record — minimal hours, flagged."""
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


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SCHEDULES
# ═══════════════════════════════════════════════════════════════════════════════
EVENT_TYPES  = ["Task", "Meeting", "Focus Time", "Break", "Training", "Leave"]
EVENT_WEIGHTS= [0.30, 0.30, 0.20, 0.08, 0.07, 0.05]
MTG_TYPES    = ["One-on-One", "Team Meeting", "All-Hands", "Training", "Standup"]
ATTEND_STATUS= ["Scheduled", "Completed", "Missed", "Rescheduled", "Cancelled"]
ATTEND_WEIGHTS=[0.15, 0.60, 0.08, 0.10, 0.07]
LOCATIONS    = ["Office", "Home", "Conference Room A", "Conference Room B", "Virtual", "Client Site"]
TIMEZONES    = ["IST", "UTC", "EST", "PST", "CST"]
PRIORITY     = ["Low", "Medium", "High", "Critical"]

EVENT_TITLES = {
    "Task":       ["Code Review Session","Implementation Block","Design Sprint","Bug Fixing","Testing Block"],
    "Meeting":    ["Sprint Planning","Daily Standup","Retrospective","Stakeholder Review","1:1 with Manager",
                   "Design Critique","Architecture Discussion","Team Sync","All Hands"],
    "Focus Time": ["Deep Work Block","No-Interruption Zone","Research Block","Writing Time","Strategy Session"],
    "Break":      ["Lunch Break","Coffee Break","Short Walk","Mental Reset"],
    "Training":   ["AWS Training","Leadership Workshop","Agile Certification Prep","Technical Talk","Onboarding"],
    "Leave":      ["Annual Leave","Sick Leave","Personal Day","Public Holiday"],
}

DURATION_BY_TYPE = {
    "Task":       [60, 90, 120, 180, 240],
    "Meeting":    [30, 45, 60, 90],
    "Focus Time": [60, 90, 120],
    "Break":      [15, 30, 60],
    "Training":   [60, 120, 180, 240],
    "Leave":      [480],
}

def generate_schedules(employees_df, tasks_df, n=6000):
    emp_ids  = employees_df["employee_id"].tolist()
    task_ids = tasks_df["task_id"].tolist()
    workdays = weekdays_in_range(HISTORY_START, HISTORY_END)

    # sample n (employee, day) pairs with replacement
    rows = []
    for i in range(1, n + 1):
        sch_id   = f"SCH{i:05d}"
        emp_id   = random.choice(emp_ids)
        emp_row  = employees_df[employees_df["employee_id"] == emp_id].iloc[0]
        day      = random.choice(workdays)

        ev_type  = np.random.choice(EVENT_TYPES, p=EVENT_WEIGHTS)
        title    = random.choice(EVENT_TITLES[ev_type])
        duration = random.choice(DURATION_BY_TYPE[ev_type])

        # start time — most events 8am–6pm
        start_h  = random.randint(8, 17)
        start_m  = random.choice([0, 15, 30, 45])
        start_t  = f"{start_h:02d}:{start_m:02d}:00"
        end_t    = add_minutes(start_t, duration)

        # Related ID
        related_id = None
        if ev_type == "Task":
            related_id = random.choice(task_ids)

        priority    = np.random.choice(PRIORITY, p=[0.20, 0.40, 0.30, 0.10])
        is_flex     = random.random() > 0.5
        buf_req     = random.random() > 0.6
        buf_mins    = random.choice([0, 15, 30]) if buf_req else 0

        has_conflict = random.random() < 0.08
        conflict_ids = f"SCH{random.randint(1,n):05d}" if has_conflict else None
        opt_score    = clamp(round(np.random.normal(75, 15), 1), 20, 100)
        rec_time     = rand_time(9, 16) if opt_score < 60 else None

        attend = np.random.choice(ATTEND_STATUS, p=ATTEND_WEIGHTS)
        completed_ev = attend == "Completed"

        act_start  = add_minutes(start_t, random.randint(-5, 10)) if completed_ev else None
        act_end    = add_minutes(act_start, duration + random.randint(-10, 15)) if completed_ev else None
        act_dur    = duration + random.randint(-10, 15) if completed_ev else None
        prod_during= clamp(round(np.random.normal(7.0, 1.3), 1), 3, 10) if completed_ev else None

        involves_team   = ev_type in ["Meeting", "Training"] or random.random() < 0.3
        participant_cnt = random.randint(2, 12) if involves_team else 1
        participant_ids = ",".join(random.sample(
            [e for e in emp_ids if e != emp_id], min(participant_cnt - 1, len(emp_ids) - 1)
        )) if involves_team else None
        mtg_type    = random.choice(MTG_TYPES) if ev_type == "Meeting" else None

        is_remote   = emp_row["remote_work_status"] in ["Remote", "Hybrid"] and random.random() > 0.4
        location    = "Virtual" if is_remote else random.choice(LOCATIONS[:-1])
        mtg_link    = f"https://zoom.us/j/{random.randint(10000000,99999999)}" if is_remote else None

        rows.append({
            "schedule_id":          sch_id,
            "employee_id":          emp_id,
            "event_type":           ev_type,
            "related_id":           related_id,
            "event_title":          title,
            "date":                 day.isoformat(),
            "start_time":           start_t,
            "end_time":             end_t,
            "duration_minutes":     duration,
            "timezone":             emp_row.get("timezone", "IST"),
            "priority":             priority,
            "is_flexible":          is_flex,
            "buffer_required":      buf_req,
            "buffer_minutes":       buf_mins,
            "has_conflict":         has_conflict,
            "conflict_with_ids":    conflict_ids,
            "optimization_score":   opt_score,
            "recommended_time":     rec_time,
            "attendance_status":    attend,
            "actual_start_time":    act_start,
            "actual_end_time":      act_end,
            "actual_duration_minutes": act_dur,
            "productivity_during":  prod_during,
            "involves_team":        involves_team,
            "participant_ids":      participant_ids,
            "participant_count":    participant_cnt,
            "meeting_type":         mtg_type,
            "location":             location,
            "is_remote":            is_remote,
            "meeting_link":         mtg_link,
            "created_at":           rand_datetime_str(day - timedelta(days=random.randint(1, 7))),
            "last_updated":         rand_datetime_str(day),
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BURNOUT INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════
BURNOUT_CAT       = ["Low Risk", "Moderate Risk", "High Risk", "Critical"]
BURNOUT_TREND     = ["Decreasing", "Stable", "Increasing", "Rapidly Increasing"]
INTERV_URGENCY    = ["None", "Monitor", "Recommend", "Immediate"]
STRESS_REPORTED   = ["Low", "Medium", "High", "Very High"]
FATIGUE_REPORTED  = ["Low", "Medium", "High", "Severe"]
SLEEP_QUALITY     = ["Good", "Fair", "Poor", "Very Poor"]
ASSESS_TYPE       = ["Weekly", "Monthly", "On-Demand"]
ASSESS_WEIGHTS    = [0.55, 0.35, 0.10]

# Roughly 2000 records: ~10 assessments per employee
NUM_BURNOUT = 2000

def generate_burnout_indicators(employees_df, wh_df, stress_profiles, n=NUM_BURNOUT):
    emp_ids  = employees_df["employee_id"].tolist()
    rows     = []

    # Sample employees with weighted frequency (high-stress employees assessed more)
    stress_weights = np.array([
        {"Low": 1, "Medium": 2, "High": 4}[
            employees_df[employees_df["employee_id"] == e]["stress_level"].values[0]
        ] for e in emp_ids
    ], dtype=float)
    stress_weights /= stress_weights.sum()

    sampled_emps = np.random.choice(emp_ids, size=n, replace=True, p=stress_weights)

    for i, emp_id in enumerate(sampled_emps):
        ind_id   = f"BI{i+1:04d}"
        profile  = stress_profiles[emp_id]
        base_b   = profile["base_burnout"]
        trend    = profile["trend"]
        emp_row  = employees_df[employees_df["employee_id"] == emp_id].iloc[0]

        # Pick assessment date — spread across history
        assess_date = HISTORY_START + timedelta(days=random.randint(0, (HISTORY_END - HISTORY_START).days))
        assess_type = np.random.choice(ASSESS_TYPE, p=ASSESS_WEIGHTS)

        # Trend-adjusted burnout at this point in time
        days_elapsed = (assess_date - HISTORY_START).days
        total_days   = (HISTORY_END - HISTORY_START).days
        drift = {"stable": 0, "increasing": 25 * (days_elapsed / total_days),
                 "decreasing": -20 * (days_elapsed / total_days)}[trend]
        burnout = clamp(base_b + drift + np.random.normal(0, 8), 5, 98)

        # Sub-scores correlated with overall burnout
        emo_exhaust  = clamp(round(burnout * 0.9  + np.random.normal(0, 8), 1), 5, 100)
        deperson     = clamp(round(burnout * 0.75 + np.random.normal(0, 8), 1), 5, 100)
        reduced_acc  = clamp(round(burnout * 0.65 + np.random.normal(0, 8), 1), 5, 100)

        cat = ("Critical" if burnout > 75 else "High Risk" if burnout > 55
               else "Moderate Risk" if burnout > 30 else "Low Risk")

        # Work-related factors
        wl_pressure  = clamp(round(burnout * 0.85 + np.random.normal(0, 10), 1), 5, 100)
        role_amb     = clamp(round(np.random.normal(35, 18), 1), 5, 90)
        wl_conflict  = clamp(round(burnout * 0.7  + np.random.normal(0, 10), 1), 5, 100)
        job_demands  = clamp(round(burnout * 0.8  + np.random.normal(0, 8),  1), 5, 100)
        job_control  = clamp(round(70 - burnout * 0.4 + np.random.normal(0, 10), 1), 10, 95)
        role_conflict= clamp(round(burnout * 0.6  + np.random.normal(0, 10), 1), 5, 90)

        # Behavioral indicators
        late_freq    = int(clamp(burnout / 6 + np.random.normal(0, 2), 0, 20))
        wknd_work    = int(clamp(burnout / 15 + np.random.normal(0, 1), 0, 8))
        missed_brks  = int(clamp(burnout / 12 + np.random.normal(0, 1), 0, 10))
        vac_unused   = int(clamp(burnout / 6  + np.random.normal(0, 2), 0, 20))
        sick_days    = int(clamp(burnout / 12 + np.random.normal(0, 1.5), 0, 12))
        absence_rate = clamp(round(sick_days / 130 * 100, 1), 0, 15)

        # Health signals — correlated with burnout
        stress_rep   = ("Very High" if burnout > 75 else "High" if burnout > 55
                        else "Medium" if burnout > 30 else "Low")
        fatigue_rep  = ("Severe" if burnout > 80 else "High" if burnout > 60
                        else "Medium" if burnout > 35 else "Low")
        sleep_qual   = ("Very Poor" if burnout > 78 else "Poor" if burnout > 58
                        else "Fair" if burnout > 35 else "Good")
        phys_concerns= burnout > 70 and random.random() > 0.5
        mh_support   = burnout > 65 and random.random() > 0.4
        energy       = clamp(round(10 - burnout / 12 + np.random.normal(0, 0.8), 1), 1, 10)

        # Engagement & satisfaction — inverse of burnout
        job_sat      = clamp(round(9.5 - burnout / 12 + np.random.normal(0, 0.8), 1), 1, 10)
        engagement   = clamp(round(9.0 - burnout / 12 + np.random.normal(0, 0.8), 1), 1, 10)
        motivation   = clamp(round(9.0 - burnout / 11 + np.random.normal(0, 0.9), 1), 1, 10)
        accomplishment= clamp(round(9.0 - burnout / 13 + np.random.normal(0, 0.8), 1), 1, 10)
        org_commit   = clamp(round(8.5 - burnout / 15 + np.random.normal(0, 0.9), 1), 1, 10)

        # Social/support factors
        soc_support  = clamp(round(np.random.normal(6.5, 1.5), 1), 1, 10)
        mgr_support  = clamp(round(np.random.normal(6.5, 1.5), 1), 1, 10)
        team_coh     = clamp(round(np.random.normal(7.0, 1.3), 1), 1, 10)
        wp_rel       = clamp(round(np.random.normal(7.0, 1.2), 1), 1, 10)
        isolation    = clamp(round(burnout * 0.5 + np.random.normal(0, 10), 1), 0, 100)

        # Coping & resilience
        coping       = clamp(round(8.0 - burnout / 15 + np.random.normal(0, 0.9), 1), 1, 10)
        resources    = clamp(round(np.random.normal(6.5, 1.4), 1), 1, 10)
        recovery     = clamp(round(8.0 - burnout / 14 + np.random.normal(0, 0.9), 1), 1, 10)
        resilience   = clamp(round(8.5 - burnout / 16 + np.random.normal(0, 0.8), 1), 1, 10)

        # Predictive
        b_trend_cat  = ("Rapidly Increasing" if trend == "increasing" and burnout > 60
                        else "Increasing" if trend == "increasing"
                        else "Decreasing" if trend == "decreasing" else "Stable")
        pred_30d     = clamp(round(burnout + (5 if trend == "increasing" else -3 if trend == "decreasing" else 0)
                                   + np.random.normal(0, 5), 1), 5, 98)
        pred_90d     = clamp(round(burnout + (12 if trend == "increasing" else -8 if trend == "decreasing" else 2)
                                   + np.random.normal(0, 8), 1), 5, 98)
        urgency      = ("Immediate" if burnout > 78 else "Recommend" if burnout > 58
                        else "Monitor" if burnout > 38 else "None")

        # Intervention history
        n_interv     = int(clamp(burnout / 30 + np.random.normal(0, 0.5), 0, 4))
        last_interv  = (assess_date - timedelta(days=random.randint(5, 60))).isoformat() \
                       if n_interv > 0 else None
        interv_eff   = clamp(round(np.random.normal(6.5, 1.5), 1), 2, 10) if n_interv > 0 else None

        rows.append({
            "indicator_id":               ind_id,
            "employee_id":                emp_id,
            "assessment_date":            assess_date.isoformat(),
            "assessment_type":            assess_type,
            "overall_burnout_risk":       round(burnout, 1),
            "emotional_exhaustion_score": emo_exhaust,
            "depersonalization_score":    deperson,
            "reduced_accomplishment_score": reduced_acc,
            "burnout_category":           cat,
            "workload_pressure":          wl_pressure,
            "role_ambiguity":             role_amb,
            "work_life_conflict":         wl_conflict,
            "job_demands":                job_demands,
            "job_control":                job_control,
            "role_conflict":              role_conflict,
            "late_hours_frequency":       late_freq,
            "weekend_work_frequency":     wknd_work,
            "missed_breaks_count":        missed_brks,
            "vacation_days_unused":       vac_unused,
            "sick_days_taken":            sick_days,
            "absence_rate":               absence_rate,
            "reported_stress_level":      stress_rep,
            "reported_fatigue_level":     fatigue_rep,
            "sleep_quality":              sleep_qual,
            "physical_health_concerns":   phys_concerns,
            "mental_health_support_needed": mh_support,
            "energy_level":               energy,
            "job_satisfaction":           job_sat,
            "engagement_score":           engagement,
            "motivation_level":           motivation,
            "sense_of_accomplishment":    accomplishment,
            "organizational_commitment":  org_commit,
            "social_support_score":       soc_support,
            "manager_support_score":      mgr_support,
            "team_cohesion":              team_coh,
            "workplace_relationships":    wp_rel,
            "isolation_feeling":          isolation,
            "coping_effectiveness":       coping,
            "resource_adequacy":          resources,
            "work_recovery_ability":      recovery,
            "resilience_score":           resilience,
            "burnout_trend":              b_trend_cat,
            "predicted_burnout_30days":   pred_30d,
            "predicted_burnout_90days":   pred_90d,
            "intervention_urgency":       urgency,
            "interventions_received":     n_interv,
            "last_intervention_date":     last_interv,
            "intervention_effectiveness": interv_eff,
            "created_at":                 rand_datetime_str(assess_date),
            "last_updated":               rand_datetime_str(assess_date),
        })

    return pd.DataFrame(rows)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loading Part 1 & 2 data...")
    emp_df   = pd.read_csv(f"{OUT_DIR}/employees.csv")
    proj_df  = pd.read_csv(f"{OUT_DIR}/projects.csv")
    tasks_df = pd.read_csv(f"{OUT_DIR}/tasks.csv")
    print(f"  Loaded {len(emp_df)} employees | {len(proj_df)} projects | {len(tasks_df)} tasks")

    print("Building stress profiles...")
    stress_profiles = build_stress_profiles(emp_df)

    print("Generating workload_history  (this may take ~20s)...")
    wh_df = generate_workload_history(emp_df, stress_profiles)
    wh_df.to_csv(f"{OUT_DIR}/workload_history.csv", index=False)
    print(f"  ✓ {len(wh_df)} rows → workload_history.csv")

    print("Generating schedules...")
    sch_df = generate_schedules(emp_df, tasks_df, n=6000)
    sch_df.to_csv(f"{OUT_DIR}/schedules.csv", index=False)
    print(f"  ✓ {len(sch_df)} rows → schedules.csv")

    print("Generating burnout_indicators...")
    bi_df = generate_burnout_indicators(emp_df, wh_df, stress_profiles, n=NUM_BURNOUT)
    bi_df.to_csv(f"{OUT_DIR}/burnout_indicators.csv", index=False)
    print(f"  ✓ {len(bi_df)} rows → burnout_indicators.csv")

    # ── Sanity checks ──────────────────────────────────────────────────────────
    print("\nSanity checks:")

    print(f"  WH  — all employee_ids valid     : {wh_df['employee_id'].isin(emp_df['employee_id']).all()}")
    print(f"  WH  — out-of-office rows         : {wh_df['out_of_office'].sum()}")
    avg_hrs = wh_df[~wh_df['out_of_office']]['total_hours_worked'].mean()
    print(f"  WH  — avg daily hours (working)  : {avg_hrs:.2f}")
    print(f"  WH  — stress distribution:\n{wh_df['stress_level'].value_counts().to_string()}")

    print(f"  SCH — all employee_ids valid     : {sch_df['employee_id'].isin(emp_df['employee_id']).all()}")
    print(f"  SCH — event type distribution:\n{sch_df['event_type'].value_counts().to_string()}")
    print(f"  SCH — attendance distribution:\n{sch_df['attendance_status'].value_counts().to_string()}")

    print(f"  BI  — all employee_ids valid     : {bi_df['employee_id'].isin(emp_df['employee_id']).all()}")
    print(f"  BI  — burnout category distribution:\n{bi_df['burnout_category'].value_counts().to_string()}")
    print(f"  BI  — avg overall burnout risk   : {bi_df['overall_burnout_risk'].mean():.1f}")
    print(f"  BI  — intervention urgency:\n{bi_df['intervention_urgency'].value_counts().to_string()}")

    print("\nDone.")
