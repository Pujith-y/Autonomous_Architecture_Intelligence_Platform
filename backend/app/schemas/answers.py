
from pydantic import BaseModel, Field


class AskRepositoryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
