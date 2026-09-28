from enum import Enum


class IndexingStatus(str, Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"