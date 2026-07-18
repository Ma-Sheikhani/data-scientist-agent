import json
from unittest.mock import patch

from agent.graph import agent_app
from agent.state import AgentState, DataFrameInfo


@patch("agent.graph.call_llm")
def test_planner_returns_valid_plan(mock_call_llm):
    # Return a valid JSON plan without any real API call
    mock_call_llm.return_value = json.dumps(
        {
            "plan": [
                {
                    "action_type": "execute_code",
                    "code": "import pandas as pd\nimport matplotlib.pyplot as plt\n...",
                    "description": "Calculate correlation between sepal length and petal length",
                }
            ]
        }
    )

    state = AgentState(
        user_question="What is the correlation between sepal length and petal length?",
        dataframe_info=DataFrameInfo(
            columns=["sepal_length", "sepal_width", "petal_length", "petal_width", "species"],
            dtypes={
                "sepal_length": "float64",
                "sepal_width": "float64",
                "petal_length": "float64",
                "petal_width": "float64",
                "species": "object",
            },
            sample_rows=[
                {
                    "sepal_length": 5.1,
                    "sepal_width": 3.5,
                    "petal_length": 1.4,
                    "petal_width": 0.2,
                    "species": "setosa",
                },
                {
                    "sepal_length": 4.9,
                    "sepal_width": 3.0,
                    "petal_length": 1.4,
                    "petal_width": 0.2,
                    "species": "setosa",
                },
            ],
        ),
    )
    result = agent_app.invoke(state)
    assert len(result["plan"]) > 0
    assert result["plan"][0].action_type == "execute_code"
    assert "corr" in result["plan"][0].code or "correlation" in result["plan"][0].code
