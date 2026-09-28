from pydantic import BaseModel
from datetime import datetime

class IndexingRunResponse(BaseModel):
    id : int
    repository_id : int
    status : str
    started_at : datetime
    completed_at : datetime | None
    error_message : str | None


class ListOfIndexingRunResponse(BaseModel):
    indexing_runs: list[IndexingRunResponse]