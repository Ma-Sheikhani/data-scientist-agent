from unittest.mock import MagicMock, patch

from agent.graph import executor_node
from agent.schemas import CodeAction
from agent.state import AgentState, DataFrameInfo


@patch("agent.graph.httpx.Client.post")
def test_executor_node(mock_post):
    # Mock sandbox response
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "stdout": "2.0\n",
        "stderr": "",
        "error": None,
        "images": [],
    }
    mock_post.return_value = mock_response

    state = AgentState(
        user_question="test",
        dataframe_info=DataFrameInfo(
            columns=["a"], dtypes={"a": "float64"}, sample_rows=[{"a": 1}]
        ),
        plan=[
            CodeAction(action_type="execute_code", code="print(1+1)", description="add")
        ],
    )
    result = executor_node(state)
    assert len(result["execution_results"]) == 1
    assert result["execution_results"][0]["stdout"] == "2.0\n"
