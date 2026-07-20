import logging
import os

import pandas as pd

from agent.state import DataFrameInfo

logger = logging.getLogger(__name__)


MAX_COLUMNS = int(os.getenv("AGENT_MAX_COLUMNS", "50"))
MAX_SAMPLE_ROWS = int(os.getenv("AGENT_MAX_SAMPLE_ROWS", "10"))


def validate_csv(df: pd.DataFrame) -> None:
    """
    Raise ValueError if the DataFrame is empty or has no columns.
    """
    if df.empty:
        raise ValueError("CSV file is empty (no rows).")
    if len(df.columns) == 0:
        raise ValueError("CSV file has no columns.")


def build_dataframe_info(
    df: pd.DataFrame,
    max_columns: int = MAX_COLUMNS,
    max_sample_rows: int = MAX_SAMPLE_ROWS,
) -> DataFrameInfo:
    """
    Create a DataFrameInfo object from a DataFrame.
    - Truncates columns to the first `max_columns` if there are more.
    - Limits sample rows to `max_sample_rows`.
    """
    validate_csv(df)

    columns = df.columns.tolist()
    truncated = len(columns) > max_columns

    if truncated:
        logger.warning(
            f"Dataset has {len(columns)} columns; only the first {max_columns} will be visible to the agent."
        )
        columns = columns[:max_columns]

    # dtypes for selected columns only
    dtypes = {col: str(df[col].dtype) for col in columns}
    sample_rows_raw = df[columns].head(max_sample_rows).to_dict(orient="records")
    sample_rows = [{str(k): v for k, v in row.items()} for row in sample_rows_raw]

    return DataFrameInfo(
        columns=columns,
        dtypes=dtypes,
        sample_rows=sample_rows,
    )
