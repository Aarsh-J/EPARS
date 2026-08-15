"""
modules/ml/justification.py
================================
Generates a manager-facing written explanation for an employee's
ai_predicted_score. Uses a direct single-shot ChatGroq call (same pattern as
src/epars_agent/agent/burnout_monitor.py::decide_action_for_task) rather than
the full LangGraph ReAct agent — this is a read-only explanation task with no
tools to call, so the tool-loop overhead isn't needed.

Grounds the explanation in the HR performance-evaluation policy via the
existing RAG pipeline (src/epars_policies/rag_query.py), so the output can
cite a concrete score band/rule instead of just narrating numbers back.
"""

import json

from rag_query import format_policy_context

from .llm_client import invoke_json, llm


def generate_justification(
    employee_profile: dict,
    ai_predicted_score: float,
    ai_confidence: str,
    score_signals: dict,
) -> dict:
    """
    Returns {"justification": str, "policy_citation": str}.
    Falls back to a plain, honest non-LLM message if the LLM is unavailable
    or its output can't be parsed — never raises, since this should never be
    the reason an Analyse click fails.
    """
    fallback = {
        "justification": (
            f"The model estimates a performance score of {ai_predicted_score} "
            f"({ai_confidence} confidence) based on this employee's available "
            "review, feedback, and workload data. Automated explanation is "
            "currently unavailable."
        ),
        "policy_citation": None,
    }

    if llm is None:
        return fallback

    # A static query, not one embedding the specific score — sentence embeddings
    # don't do numeric reasoning, so putting "74.6" in the query text doesn't
    # help retrieval. Let the LLM do the actual band lookup once the boundary
    # table itself is retrieved.
    policy_context = format_policy_context(
        "performance score band classification thresholds Exceptional High Performer "
        "Meets Expectations Developing Underperforming mandatory actions by score band",
        n_results=4,
    )

    prompt = f"""You are an HR performance-evaluation assistant. Explain, in plain language a
manager can read in a few seconds, why the model estimated this employee's performance score
the way it did. Ground your explanation in the actual data below — do not invent numbers.

IMPORTANT: this score estimates "normalized_performance_score" (a peer-adjusted metric), which
is a DIFFERENT column from the employee's officially recorded review score. Do not imply this
number IS the recorded review score or that it re-derives it — frame it as the model's
independent estimate, useful for sanity-checking or cross-referencing the recorded score, not
replacing it silently.

EMPLOYEE:
{json.dumps(employee_profile, indent=2, default=str)}

MODEL OUTPUT:
{json.dumps({"ai_predicted_score": ai_predicted_score, "confidence": ai_confidence}, indent=2)}

SCORE SIGNALS (real per-competency scores and engineered metrics that fed the model,
null = not enough live data for that signal):
{json.dumps(score_signals, indent=2, default=str)}

RELEVANT HR POLICY:
{policy_context}

Respond with ONLY a JSON object, no other text, no markdown fences:
{{
  "justification": "2-4 sentences explaining the score, citing specific numbers from SCORE SIGNALS above",
  "policy_citation": "short reference like 'POL-PERF-004 — Gold band' or null if no clear policy match"
}}"""

    parsed = invoke_json(prompt)
    if not parsed or "justification" not in parsed:
        return fallback
    return {
        "justification": parsed["justification"],
        "policy_citation": parsed.get("policy_citation"),
    }
