import base64
import os
from typing import Any, Dict, List, cast

import pandas as pd

from agent.graph import agent_app
from agent.state import AgentState, DataFrameInfo

# ---------------------------------------------------------------------------
# 1. Load and describe the dataset
# ---------------------------------------------------------------------------
csv_path = "/app/uploads/iris.csv"
df = pd.read_csv(csv_path)
sample_rows = cast(List[Dict[str, Any]], df.head(5).to_dict(orient="records"))
dtypes: Dict[str, str] = {str(k): str(v) for k, v in df.dtypes.items()}

df_info = DataFrameInfo(
    columns=df.columns.tolist(),
    dtypes=dtypes,
    sample_rows=sample_rows,
)

# ---------------------------------------------------------------------------
# 2. Build the agent state and run the full pipeline
# ---------------------------------------------------------------------------
state = AgentState(
    user_question="What is the average sepal length per species? Show a bar plot.",
    dataframe_info=df_info,
    file_path=csv_path,  # <-- tells the agent where the CSV is
)
result = agent_app.invoke(state)

# ---------------------------------------------------------------------------
# 3. Extract and save any generated figures
# ---------------------------------------------------------------------------
output_dir = "/app/uploads/figures"
os.makedirs(output_dir, exist_ok=True)

all_images = []
for exec_res in result.get("execution_results", []):
    for idx, img_b64 in enumerate(exec_res.get("images", [])):
        filename = f"step{exec_res['action_index']}_img{idx}.png"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(img_b64))
        all_images.append(filepath)
        print(f"Saved figure: {filename}")

# ---------------------------------------------------------------------------
# 4. Print the final answer and execution summary
# ---------------------------------------------------------------------------
print("\n=== FINAL ANSWER ===")
final = result.get("final_answer", {})
print("Summary:", final.get("summary", "No summary available"))
print("Statistics:", final.get("statistics", {}))
print("Figures referenced:", final.get("figures", []))
if all_images:
    print(f"\nAll saved figures are in: {output_dir}")
else:
    print("No figures were generated.")

print("\n=== EXECUTION RESULTS ===")
for step in result.get("execution_results", []):
    print(f"Step: {step.get('description')}")
    print(f"stdout: {step.get('stdout')}")
    print(f"error: {step.get('error')}")
    print(f"images: {len(step.get('images', []))} figure(s)")
    print("---")
