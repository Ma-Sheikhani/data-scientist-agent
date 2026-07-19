import json
from unittest.mock import patch

from agent.graph import agent_app, final_answer_node, reflector_node
from agent.state import AgentState, CodeAction, DataFrameInfo


@patch("agent.graph.call_llm")
def test_planner_returns_valid_plan(mock_call_llm):
    # Return a valid JSON plan
    mock_call_llm.return_value = json.dumps(
        {
            "plan": [
                {
                    "action_type": "execute_code",
                    "code": "import pandas as pd\nprint('hello')",
                    "description": "a test step",
                }
            ]
        }
    )

    state = AgentState(
        user_question="test question",
        dataframe_info=DataFrameInfo(
            columns=["a", "b"],
            dtypes={"a": "int64", "b": "int64"},
            sample_rows=[{"a": 1, "b": 2}],
        ),
    )
    result = agent_app.invoke(state)

    # The planner should have returned a plan with at least one action
    assert len(result["plan"]) > 0
    # The action should have the correct type and fields
    action = result["plan"][0]
    assert action.action_type == "execute_code"
    assert action.code == "import pandas as pd\nprint('hello')"
    assert action.description == "a test step"


@patch("agent.graph.call_llm")
def test_reflector_complete(mock_llm):
    mock_llm.return_value = '{"is_complete": true}'
    state = AgentState(
        user_question="test",
        dataframe_info=DataFrameInfo(
            columns=["a"], dtypes={"a": "float64"}, sample_rows=[{"a": 1}]
        ),
        plan=[CodeAction(action_type="execute_code", code="print(1)", description="print")],
        execution_results=[
            {"action_index": 0, "stdout": "1\n", "stderr": "", "error": None, "images": []}
        ],
        iteration_count=0,
    )
    result = reflector_node(state)  # <-- direct call
    assert result["is_complete"]


@patch("agent.graph.call_llm")
def test_final_answer(mock_llm):
    mock_llm.return_value = '{"summary": "done", "statistics": {}, "figures": []}'
    state = AgentState(
        user_question="test",
        dataframe_info=DataFrameInfo(
            columns=["a"], dtypes={"a": "float64"}, sample_rows=[{"a": 1}]
        ),
        plan=[CodeAction(action_type="execute_code", code="print(1)", description="print")],
        execution_results=[
            {"action_index": 0, "stdout": "1\n", "stderr": "", "error": None, "images": []}
        ],
        iteration_count=0,
    )
    result = final_answer_node(state)  # <-- direct call
    assert result["final_answer"]["summary"] == "done"
