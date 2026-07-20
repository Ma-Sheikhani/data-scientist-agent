import ast
import json
import logging
import os
import re
import time
from typing import Any

import httpx
from langgraph.graph import END, StateGraph

from agent.llm import call_llm
from agent.schemas import CodeAction, PlanSchema, ReflectorResponse
from agent.state import AgentState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SANDBOX_URL = os.getenv("SANDBOX_URL", "http://sandbox:8001")


# ---------------------------------------------------------------------------
# JSON / Python‑literal parsing helpers (unchanged)
# ---------------------------------------------------------------------------
def strip_json_comments(text: str) -> str:
    # Remove // single-line comments
    text = re.sub(r"//.*", "", text)
    # Remove /* multi-line comments */
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def sanitize_json_triple_quotes(json_str: str) -> str:
    """Replace triple-quoted Python strings with escaped double quotes."""
    return re.sub(r'"""(.*?)"""', r'\\"\1\\"', json_str, flags=re.DOTALL)


def _fix_code_quotes(candidate: str) -> str:
    def replace_code(match):
        code_content = match.group(1)
        escaped = code_content.replace("\\", "\\\\").replace('"', '\\"')
        return f'"code": "{escaped}"'

    pattern = r'"code":\s*\'([^\']*?)\'\s*(?=[,}\n])'
    return re.sub(pattern, replace_code, candidate, flags=re.DOTALL)


def _parse_json_with_fallbacks(raw: str) -> dict | None:
    # ... unchanged ...
    candidate = None
    if "```json" in raw:
        candidate = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        candidate = raw.split("```", 1)[1].split("```", 1)[0].strip()
    else:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            candidate = m.group(0).strip()

    if candidate:
        try:
            result = ast.literal_eval(candidate)
            if isinstance(result, dict):
                return result
        except Exception:
            logger.debug("ast.literal_eval fallback failed", exc_info=True)

        try:
            result = json.loads(sanitize_json_triple_quotes(candidate))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        try:
            result = json.loads(_fix_code_quotes(candidate))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    try:
        result = json.loads(sanitize_json_triple_quotes(raw))
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    try:
        result = ast.literal_eval(raw)
        if isinstance(result, dict):
            return result
    except Exception:
        logger.debug("Final ast.literal_eval fallback failed", exc_info=True)

    return None


# ---------------------------------------------------------------------------
# Prompt loading (unchanged)
# ---------------------------------------------------------------------------
with open("agent/prompts/planner_system.txt", "r") as f:
    PLANNER_SYSTEM = f.read()
with open("agent/prompts/planner_user.txt", "r") as f:
    PLANNER_USER_TEMPLATE = f.read()
with open("agent/prompts/reflector_system.txt", "r") as f:
    REFLECTOR_SYSTEM = f.read()
with open("agent/prompts/reflector_user.txt", "r") as f:
    REFLECTOR_USER_TEMPLATE = f.read()
with open("agent/prompts/final_answer_system.txt", "r") as f:
    FINAL_ANSWER_SYSTEM = f.read()
with open("agent/prompts/final_answer_user.txt", "r") as f:
    FINAL_ANSWER_USER_TEMPLATE = f.read()


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------
def planner_node(state: AgentState) -> dict:
    logger.info(
        "PLANNER | iteration %d | columns=%d | question=%s",
        state.iteration_count,
        len(state.dataframe_info.columns),
        state.user_question[:80],
    )
    user_prompt = PLANNER_USER_TEMPLATE.replace(
        "{{ columns }}", str(state.dataframe_info.columns)
    )
    user_prompt = user_prompt.replace(
        "{{ dtypes }}", json.dumps(state.dataframe_info.dtypes)
    )
    sample_rows_str = json.dumps(state.dataframe_info.sample_rows[:5], indent=2)
    user_prompt = user_prompt.replace("{{ sample_rows }}", sample_rows_str)
    user_prompt = user_prompt.replace("{{ question }}", state.user_question)
    user_prompt = user_prompt.replace("{{ file_path }}", state.file_path)

    try:
        plan_model = call_llm(
            system_prompt=PLANNER_SYSTEM,
            user_prompt=user_prompt,
            response_format={"type": "json_object"},
            pydantic_model=PlanSchema,
        )
        plan = plan_model.plan
        logger.info("PLANNER | success | plan size=%d", len(plan))
    except Exception as e:
        logger.error("PLANNER | failed | error=%s", e)
        fallback_code = f"print('Planner failed: {e}')"
        plan = [
            CodeAction(
                code=fallback_code, description="Fallback due to planner failure"
            )
        ]

    return {
        "plan": plan,
        "iteration_count": state.iteration_count + 1,
    }


def executor_node(state: AgentState) -> dict[str, Any]:
    logger.info(
        "EXECUTOR | iteration=%d | steps=%d",
        state.iteration_count,
        len(state.plan),
    )
    MAX_SANDBOX_RETRIES = 2

    def _execute_with_retry(client, code, timeout):
        last_exc = None
        for attempt in range(MAX_SANDBOX_RETRIES + 1):
            try:
                resp = client.post(
                    f"{SANDBOX_URL}/execute",
                    json={"code": code, "timeout": timeout},
                )
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_exc = e
                logger.warning("Sandbox call failed (attempt %d): %s", attempt + 1, e)
                time.sleep(2**attempt)
        return {
            "stdout": "",
            "stderr": "",
            "error": f"Sandbox failed after {MAX_SANDBOX_RETRIES + 1} attempts: {last_exc}",
            "images": [],
        }

    execution_results = []
    with httpx.Client(timeout=30.0) as client:
        for idx, action in enumerate(state.plan):
            if action.action_type != "execute_code":
                continue
            result = _execute_with_retry(client, action.code, timeout=15)
            logger.info(
                "EXECUTOR | step %d | code_len=%d | error=%s",
                idx,
                len(action.code),
                result.get("error"),
            )
            execution_results.append(
                {
                    "action_index": idx,
                    "action_type": action.action_type,
                    "description": action.description,
                    "code": action.code,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "error": result.get("error") or "",
                    "images": result.get("images", []),
                }
            )

    return {"execution_results": execution_results}


def reflector_node(state: AgentState) -> dict[str, Any]:
    logger.info(
        "REFLECTOR | iteration=%d | steps_executed=%d",
        state.iteration_count,
        len(state.execution_results),
    )
    if state.iteration_count >= state.max_iterations:
        logger.info("REFLECTOR | max iterations reached -> forcing complete")
        return {"is_complete": True, "iteration_count": state.iteration_count}

    # Build executed steps string (unchanged)
    steps_str = ""
    for i, res in enumerate(state.execution_results):
        code = state.plan[i].code if i < len(state.plan) else "N/A"
        steps_str += (
            f"Step {i}: {res.get('description', 'Unknown')}\n"
            f"Code:\n```\n{code}\n```\n"
            f"Output:\n"
            f"- stdout: {res.get('stdout', '')}\n"
            f"- stderr: {res.get('stderr', '')}\n"
            f"- error: {res.get('error', '')}\n"
            f"- images: {len(res.get('images', []))} figure(s)\n\n"
        )

    user_prompt = REFLECTOR_USER_TEMPLATE
    user_prompt = user_prompt.replace("{{ question }}", state.user_question)
    user_prompt = user_prompt.replace(
        "{{ columns }}", str(state.dataframe_info.columns)
    )
    user_prompt = user_prompt.replace("{{ dtypes }}", str(state.dataframe_info.dtypes))
    user_prompt = user_prompt.replace("--- Executed Plan ---", steps_str)

    try:
        reflector_model = call_llm(
            system_prompt=REFLECTOR_SYSTEM,
            user_prompt=user_prompt,
            pydantic_model=ReflectorResponse,
        )
        is_complete = reflector_model.is_complete
        logger.info("REFLECTOR | success | is_complete=%s", is_complete)
    except Exception as e:
        logger.error("REFLECTOR | failed | error=%s", e)
        return {"is_complete": True}

    if is_complete:
        return {"is_complete": True}
    else:
        revised_plan = reflector_model.revised_plan
        logger.info("REFLECTOR | new plan size=%d", len(revised_plan))
        return {
            "is_complete": False,
            "plan": revised_plan,
            "execution_results": [],
            "iteration_count": state.iteration_count + 1,
        }


def final_answer_node(state: AgentState) -> dict[str, Any]:
    logger.info("FINAL_ANSWER | steps=%d", len(state.execution_results))
    hist_str = ""
    for i, res in enumerate(state.execution_results):
        hist_str += (
            f"Step {i}: {res.get('description', '')}\n"
            f"stdout: {res.get('stdout', '')}\n"
            f"stderr: {res.get('stderr', '')}\n"
            f"error: {res.get('error', '')}\n"
            f"figures: {len(res.get('images', []))}\n\n"
        )

    user_prompt = FINAL_ANSWER_USER_TEMPLATE.replace(
        "{{ question }}", state.user_question
    )
    user_prompt = user_prompt.replace(
        "{{ columns }}", str(state.dataframe_info.columns)
    )
    user_prompt = user_prompt.replace("{{ dtypes }}", str(state.dataframe_info.dtypes))
    user_prompt = user_prompt.replace("--- Execution History ---", hist_str)

    try:
        raw = call_llm(system_prompt=FINAL_ANSWER_SYSTEM, user_prompt=user_prompt)
        logger.info("FINAL_ANSWER | raw response length=%d", len(raw))
    except Exception as e:
        logger.error("FINAL_ANSWER | LLM call failed: %s", e)
        return {
            "final_answer": {
                "summary": "Failed to generate final answer due to LLM error.",
                "statistics": {},
                "figures": [],
                "tables": [],
            }
        }

    response = _parse_json_with_fallbacks(raw)
    final_answer = (
        response
        if response
        else {
            "summary": "Failed to parse final answer.",
            "statistics": {},
            "figures": [],
        }
    )
    logger.info("FINAL_ANSWER | success=%s", response is not None)
    return {"final_answer": final_answer}


# ---------------------------------------------------------------------------
# Build the LangGraph agent (unchanged)
# ---------------------------------------------------------------------------
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
