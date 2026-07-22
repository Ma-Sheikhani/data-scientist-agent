import logging

import pandas as pd
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

logger = logging.getLogger(__name__)

# Initialize once (expensive)
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()


def redact_pii_from_csv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scan each cell for PII and replace with anonymized text.
    Returns a new DataFrame with PII redacted.
    """
    for col in df.columns:
        # Apply to each cell as string
        for idx, value in df[col].items():
            if pd.isna(value):
                continue
            text = str(value)
            results = analyzer.analyze(text=text, language="en")
            if results:
                anonymized = anonymizer.anonymize(
                    text=text,
                    analyzer_results=results,  # type: ignore[arg-type]
                    operators={
                        "DEFAULT": OperatorConfig(
                            "replace", {"new_value": "[REDACTED]"}
                        )
                    },
                )
                df.at[idx, col] = anonymized.text
    return df
