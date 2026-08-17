from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceLocation:
    file: Path

    start_line: int
    end_line: int

    start_column: int | None = None
    end_column: int | None = None