# Leave, Availability, and Scheduling Policy
**Document ID:** POL-LEAVE-006  
**Version:** 2.0  
**Effective Date:** January 2025  
**Owner:** HR Department

---

## 1. Purpose
This policy defines how employee leave and availability information must be factored into task assignment, team formation, and workload calculations by the ePARS system.

---

## 2. Leave Types and System Treatment

| Leave Type | Code | Task Assignment Allowed? | Team Formation Allowed? |
|---|---|---|---|
| Annual Leave (Planned) | AL | No | No |
| Sick Leave | SL | No | No |
| Wellness / Burnout Leave | WL | No | No |
| Partial Leave (half-day) | PL | P4 tasks only, reduced hours | Only if duration < 3 days |
| Compensatory Off | CO | No | No |
| Training Leave | TL | No (training takes priority) | No |
| Work From Home | WFH | Yes, normal rules apply | Yes |
| Public Holiday | PH | No | No |

---

## 3. Availability Calculation
- An employee's **effective weekly capacity** is calculated as: `Base Hours (40) − Leave Hours − Meeting Hours − Admin Buffer (2 hours)`.
- Employees on WFH status retain full capacity unless they have flagged reduced availability.
- Effective capacity must be recalculated at the start of each week by the system.
- Task assignment algorithms must use **effective capacity**, not base hours, when checking workload thresholds.

---

## 4. Advance Leave Visibility
- Approved planned leave (AL) must be visible to the task assignment system **at least 5 business days** in advance.
- When an employee has approved leave in the next 7 days, the system must not assign tasks with a deadline falling within that leave window.
- Tasks with deadlines within 3 days of a known leave period must be flagged and reviewed by the manager.

---

## 5. Unplanned Absence Protocol
- When an employee goes on unplanned leave (sick leave), all their active P1/P2 tasks must be immediately reviewed.
- If the expected absence is **3 or more business days**, critical tasks must be temporarily reassigned.
- Temporary reassignment must be reversed when the employee returns and their workload allows.

---

## 6. Return to Work
- Employees returning from leave of **5 or more business days** must have their workload reviewed before new tasks are assigned.
- The system must not auto-assign any tasks on the employee's **first day back**.
- On day 2 of return, task assignments resume at up to **70% of normal workload capacity** unless the employee's manager confirms full availability.

---

## 7. Unused Leave Management
- Employees with **≥ 15 unused annual leave days** in a calendar year must be flagged.
- The system should factor unused vacation days as a secondary burnout risk indicator.
- Managers of flagged employees must initiate a conversation about scheduling leave within **10 business days** of the flag.

---

## 8. Holiday Coverage Planning
- For national public holidays, any P1 tasks due within 1 business day of the holiday must be reassigned or have their deadline adjusted **48 hours in advance**.
- On-call responsibilities during holidays must be agreed upon and logged at least **one week** in advance.
