from fastapi import APIRouter, HTTPException
from .inference import score_assignment, recommend_employees

router = APIRouter(prefix="/api/task_assignment", tags=["Task Assignment"])

@router.get("/score")
def score(task_id: str, employee_id: str):
    try:
        result = score_assignment(task_id, employee_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/top_employees/{task_id}")
def top_employees(task_id: str, top_n: int = 3):
    try:
        result = recommend_employees(task_id, top_n=top_n)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))