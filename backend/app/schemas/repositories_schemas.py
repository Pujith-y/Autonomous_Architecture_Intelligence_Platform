from pydantic import BaseModel
from datetime import datetime


class NewRepository(BaseModel):
    name : str
    path : str

class RepositoryResponse(BaseModel):
    id : int
    name : str
    path : str
    status : str
    last_indexed_at : datetime | None
    updated_at : datetime | None
    created_at : datetime
    last_indexing_error : str | None

class ListOfRepositoryResponse(BaseModel):
    repositories : list[RepositoryResponse]


