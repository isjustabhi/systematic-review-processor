from pydantic import BaseModel, Field


class BatchCreateResponse(BaseModel):
    batch_id: str
    message: str


class BatchStatusResponse(BaseModel):
    batch_id: str
    status: str
    total_pdfs: int = 0
    successful: int = 0
    failed: int = 0
    parse_errors: int = 0
    skipped: int = 0
    message: str = ""


class RunBatchRequest(BaseModel):
    workers: int = Field(default=2, ge=1, le=4)
    max_pdfs: int | None = Field(default=None, ge=1, le=50)
