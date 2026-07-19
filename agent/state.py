from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel

from agent.schemas import CodeAction


def overwrite_list(_, new):
    return new


class DataFrameInfo(BaseModel):
    columns: List[str]
    dtypes: Dict[str, str]
    sample_rows: List[Dict[str, Any]]


class AgentState(BaseModel):
    # User inputs
    user_question: str
    dataframe_info: DataFrameInfo
    file_path: str = ""  # path to the uploaded CSV inside the container

    # Planner output
    plan: List[CodeAction] = []

    # Execution results
    execution_results: Annotated[List[Dict[str, Any]], overwrite_list] = []
    # Each dict: {"action_index": int, "stdout": str, "stderr": str,
    #  "error": str, "images": List[str] (base64)}

    # Reflector loop
    iteration_count: int = 0
    max_iterations: int = 3
    is_complete: bool = False

    # Final answer
    final_answer: Optional[Dict[str, Any]] = None
    # e.g., {"summary": "...", "figures": [...], "statistics": [...]}
