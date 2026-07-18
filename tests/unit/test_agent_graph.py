import json
from unittest.mock import patch

from agent.graph import agent_app
from agent.state import AgentState, DataFrameInfo


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
