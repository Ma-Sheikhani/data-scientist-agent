import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class JobCreate(BaseModel):
    pass  # we'll just use form fields directly in the route


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
    question: str
    created_at: datetime
    result: Optional[dict] = None
