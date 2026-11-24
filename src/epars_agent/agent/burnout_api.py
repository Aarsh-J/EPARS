"""
burnout_api.py  ->  put in dev-backend/ next to burnout_monitor.py

Web version of the terminal flow in burnout_monitor.py:
  GET  /burnout/scan     = run_step1_decide()  (read-only; LLM proposes an action per task)
  POST /burnout/execute  = the "Proceed with '<action>'? [y/N]" -> yes, for ONE task
  POST /burnout/alert    = the "Log burnout alert? [y/N]" -> yes, for ONE employee

Proposals are cached server-side at scan time, so execute only needs an
assignment_id; the client cannot inject its own decision.
"""
from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

import burnout_monitor as bm
from tools import flag_burnout_alert

router = APIRouter(prefix="/burnout", tags=["burnout"])

# assignment_id -> {"employee": {...}, "task": {...}, "decision": {...}}
PENDING: dict = {}


@router.get("/scan")
def scan():
    try:
        items = bm.run_step1_decide()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Burnout scan failed: {e}")

    PENDING.clear()
    grouped: dict = {}
    for it in items:
        emp, task = it["employee"], it["task"]
        PENDING[task["assignment_id"]] = it
        g = grouped.setdefault(emp["employee_id"], {
            "employee_id": emp["employee_id"],
            "name": emp.get("full_name"),
            "burnout_score": float(emp["burnout_score"]),
            "burnout_category": emp.get("burnout_category"),
            "tasks": [],
        })
        g["tasks"].append({
            "assignment_id": task["assignment_id"],
            "task_id": task["task_id"],
            "task_type": task.get("task_type"),
            "priority": task.get("priority"),
            "due_date": task.get("due_date"),
            "estimated_hours": task.get("estimated_hours"),
            "decision": it["decision"],
        })
    return jsonable_encoder({"employees": list(grouped.values())})


class ExecuteReq(BaseModel):
    assignment_id: str


@router.post("/execute")
def execute(req: ExecuteReq):
    item = PENDING.get(req.assignment_id)
    if not item:
        raise HTTPException(404, "No pending proposal for this task. Run the scan again.")
    if item["decision"].get("action", "none") == "none":
        raise HTTPException(400, "This task has no action to execute.")
    try:
        result = bm.execute_decision(item["employee"]["employee_id"], item["task"], item["decision"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if result.get("success"):
        PENDING.pop(req.assignment_id, None)   # never execute the same proposal twice
    return jsonable_encoder({"ok": bool(result.get("success")), "result": result})


class AlertReq(BaseModel):
    employee_id: str


@router.post("/alert")
def alert(req: AlertReq):
    emp = next((i["employee"] for i in PENDING.values()
                if i["employee"]["employee_id"] == req.employee_id), None)
    if not emp:
        raise HTTPException(404, "Employee not in the current scan. Run the scan again.")
    score = float(emp["burnout_score"])
    r = flag_burnout_alert(
        employee_id=req.employee_id,
        burnout_score=score,
        urgency="Immediate" if score >= 0.85 else "Recommend",
        recommended_action="Reviewed by automated burnout monitor for task rebalancing.",
    )
    return jsonable_encoder({"ok": bool(r.get("success")), "result": r})