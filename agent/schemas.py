from typing import List, Literal

from pydantic import BaseModel, Field


class CodeAction(BaseModel):
    action_type: Literal["execute_code"] = "execute_code"
    code: str = Field(..., min_length=1)
    description: str = Field(default="")


class PlanSchema(BaseModel):
    plan: List[CodeAction] = Field(..., min_length=1)


class ReflectorResponse(BaseModel):
    is_complete: bool
    revised_plan: List[CodeAction] = Field(default_factory=list)


class FinalAnswerSchema(BaseModel):
    summary: str
    statistics: dict = Field(default_factory=dict)
    figures: List[int] = Field(default_factory=list)
    tables: List[dict] = Field(default_factory=list)
