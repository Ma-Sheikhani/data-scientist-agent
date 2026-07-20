import pandas as pd

from agent.data_utils import build_dataframe_info
from agent.graph import agent_app
from agent.state import AgentState

csv_path = "/app/uploads/iris.csv"  # make sure this file exists
df = pd.read_csv(csv_path)
df_info = build_dataframe_info(df)

state = AgentState(
    user_question="which type has the largest petals?",
    dataframe_info=df_info,
    file_path=csv_path,
)

for step_output in agent_app.stream(state):
    for node_name, update in step_output.items():
        print("=" * 60)
        print(f"After node: {node_name}")
        if node_name == "planner":
            print("Plan:")
            for i, action in enumerate(update.get("plan", [])):
                print(f"  Step {i}: {action.description}")
                print(f"    Code:\n{action.code}")
        elif node_name == "executor":
            for res in update.get("execution_results", []):
                print(f"  Step {res['action_index']}:")
                print(f"    stdout:\n{res['stdout']}")
                print(f"    stderr:\n{res['stderr']}")
                print(f"    error: {res['error']}")
        elif node_name == "reflector":
            print(f"  is_complete: {update.get('is_complete')}")
            if not update.get("is_complete"):
                new_plan = update.get("plan", [])
                print(f"  New plan size: {len(new_plan)}")
                for i, action in enumerate(new_plan):
                    print(f"    New step {i}: {action.description}")
        elif node_name == "final_answer":
            print(f"  Final answer: {update.get('final_answer')}")
        print()

# Print the final generated code from the state (after all loops)
final_state = agent_app.invoke(state)  # get final state
if final_state.get("plan"):
    print("=== FINAL PLAN CODE ===")
    for i, action in enumerate(final_state["plan"]):
        print(f"--- Step {i} ---")
        print(action.code)
