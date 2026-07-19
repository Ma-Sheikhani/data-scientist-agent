from unittest.mock import patch

from agent.graph import final_answer_node, planner_node, reflector_node
from agent.schemas import CodeAction, PlanSchema, ReflectorResponse
from agent.state import AgentState, DataFrameInfo


@patch("agent.graph.call_llm")
def test_planner_returns_valid_plan(mock_call_llm):
    # Return a valid PlanSchema (a list of CodeActions)
    mock_call_llm.return_value = PlanSchema(
        plan=[
            CodeAction(
                action_type="execute_code",
                code="import pandas as pd\nprint('hello')",
                description="a test step",
            )
        ]
    )

    state = AgentState(
        user_question="test question",
        dataframe_info=DataFrameInfo(
            columns=["a", "b"],
            dtypes={"a": "int64", "b": "int64"},
            sample_rows=[{"a": 1, "b": 2}],
        ),
        file_path="/app/uploads/test.csv",
    )

    # Test the planner alone – avoid the rest of the graph
    result = planner_node(state)

    plan = result["plan"]
    assert len(plan) == 1
    assert plan[0].action_type == "execute_code"
    assert plan[0].code == "import pandas as pd\nprint('hello')"
    assert plan[0].description == "a test step"
    assert result["iteration_count"] == state.iteration_count + 1


@patch("agent.graph.call_llm")
def test_reflector_complete(mock_llm):
    # Reflector now expects a ReflectorResponse object
    mock_llm.return_value = ReflectorResponse(is_complete=True)

    state = AgentState(
        user_question="test",
        dataframe_info=DataFrameInfo(
            columns=["a"], dtypes={"a": "float64"}, sample_rows=[{"a": 1}]
        ),
        plan=[
            CodeAction(action_type="execute_code", code="print(1)", description="print")
        ],
        execution_results=[
            {
                "action_index": 0,
                "stdout": "1\n",
                "stderr": "",
                "error": None,
                "images": [],
            }
        ],
        iteration_count=0,
    )
    result = reflector_node(state)
    assert result["is_complete"]


@patch("agent.graph.call_llm")
def test_final_answer(mock_llm):
    # Final answer node calls call_llm without pydantic_model, so raw string is fine
    mock_llm.return_value = '{"summary": "done", "statistics": {}, "figures": []}'

    state = AgentState(
        user_question="test",
        dataframe_info=DataFrameInfo(
            columns=["a"], dtypes={"a": "float64"}, sample_rows=[{"a": 1}]
        ),
        plan=[
            CodeAction(action_type="execute_code", code="print(1)", description="print")
        ],
        execution_results=[
            {
                "action_index": 0,
                "stdout": "1\n",
                "stderr": "",
                "error": None,
                "images": [],
            }
        ],
        iteration_count=0,
    )
    result = final_answer_node(state)
    assert result["final_answer"]["summary"] == "done"


@patch("agent.graph.call_llm")
def test_planner_retry_on_invalid_json(mock_call_llm):
    # Raise an exception → planner uses fallback (no retry at this level)
    mock_call_llm.side_effect = Exception("Invalid JSON")

    state = AgentState(
        user_question="?",
        dataframe_info=DataFrameInfo(
            columns=["a"], dtypes={"a": "float64"}, sample_rows=[{"a": 1}]
        ),
        file_path="/app/uploads/test.csv",
    )

    result = planner_node(state)

    # Fallback plan should contain exactly one action with the error message
    assert len(result["plan"]) == 1
    assert "Planner failed" in result["plan"][0].code

    # call_llm is only called once (the retry decorator isn't triggered)
    assert mock_call_llm.call_count == 1
