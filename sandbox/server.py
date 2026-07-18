import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from safe_exec import execute_code

app = FastAPI()


class ExecuteRequest(BaseModel):
    code: str
    timeout: int = Field(default=10, ge=1, le=30)


class ExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    error: str | None
    images: list[str]


@app.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest):
    try:
        result = execute_code(request.code, request.timeout)
        return result
    except Exception as e:
        logging.exception("Sandbox execution failed")
        raise HTTPException(status_code=500, detail=str(e))
