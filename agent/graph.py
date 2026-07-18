import json
import os

import httpx
from langgraph.graph import END, StateGraph

from agent.llm import call_llm
from agent.state import AgentState, CodeAction

SANDBOX_URL = os.getenv("SANDBOX_URL", "http://sandbox:8001")  # Docker service name


# Load prompts
with open("agent/prompts/planner_system.txt", "r") as f:
    PLANNER_SYSTEM = f.read()
with open("agent/prompts/planner_user.txt", "r") as f:
    PLANNER_USER_TEMPLATE = f.read()


def planner_node(state: AgentState) -> dict:
    # Build user prompt
    user_prompt = PLANNER_USER_TEMPLATE.replace("{{ columns }}", str(state.dataframe_info.columns))
    user_prompt = user_prompt.replace("{{ dtypes }}", json.dumps(state.dataframe_info.dtypes))
    sample_rows_str = json.dumps(state.dataframe_info.sample_rows[:5], indent=2)
    user_prompt = user_prompt.replace("{{ sample_rows }}", sample_rows_str)
    user_prompt = user_prompt.replace("{{ question }}", state.user_question)

    # Call LLM
    raw = call_llm(
        system_prompt=PLANNER_SYSTEM,
        user_prompt=user_prompt,
        # response_format={"type": "json_object"},  # works for gpt-4o-mini
    )

    # Parse JSON (with fallback)
    try:
        response_json = json.loads(raw)
    except json.JSONDecodeError:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
            response_json = json.loads(raw)
        else:
            raise ValueError("Planner output is not valid JSON")

    plan = [CodeAction(**item) for item in response_json.get("plan", [])]
    return {"plan": plan, "iteration_count": state.iteration_count + 1}


def executor_node(state: AgentState) -> dict:
    """Execute each code action in the plan by calling the sandbox."""
    sandbox_url = os.getenv("SANDBOX_URL", "http://sandbox:8001")
    execution_results = []

    with httpx.Client(timeout=30.0) as client:
        for idx, action in enumerate(state.plan):
            if action.action_type != "execute_code":
                continue

            try:
                resp = client.post(
                    f"{sandbox_url}/execute",
                    json={"code": action.code, "timeout": 15},
                )
                resp.raise_for_status()
                result = resp.json()
            except httpx.HTTPStatusError as e:
                result = {
                    "stdout": "",
                    "stderr": "",
                    "error": f"Sandbox HTTP error: {e.response.status_code} - {e.response.text}",
                    "images": [],
                }
            except httpx.RequestError as e:
                result = {
                    "stdout": "",
                    "stderr": "",
                    "error": f"Sandbox connection failed: {str(e)}",
                    "images": [],
                }

            execution_results.append(
                {
                    "action_index": idx,
                    "action_type": action.action_type,
                    "description": action.description,
                    "code": action.code,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "error": result.get("error"),
                    "images": result.get("images", []),
                }
            )

    return {"execution_results": execution_results}


def reflector_node(state: AgentState) -> dict:
    # If all actions have been executed, we are done
    if len(state.execution_results) >= len(state.plan) and len(state.plan) > 0:
        return {"is_complete": True}
    # Otherwise, just increment iteration (planner already incremented)
    # and let the loop continue. But with the stub, we shouldn't hit this.
    return {}


def final_answer_node(state: AgentState) -> dict:
    return {
        "final_answer": {"summary": "Analysis completed (stub).", "figures": [], "statistics": []}
    }


# Build graph
workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)
workflow.add_node("reflector", reflector_node)
workflow.add_node("final_answer", final_answer_node)

workflow.set_entry_point("planner")

workflow.add_edge("planner", "executor")
workflow.add_edge("executor", "reflector")
workflow.add_conditional_edges(
    "reflector",
    lambda state: "final_answer" if state.is_complete else "executor",
    {"final_answer": "final_answer", "executor": "executor"},
)
workflow.add_edge("final_answer", END)

agent_app = workflow.compile()
