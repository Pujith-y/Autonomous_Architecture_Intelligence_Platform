
from pathlib import Path

from app.repository_model.entities import Entity


class SourceExtractor:
    """Extract exact source text for repository entities."""

    def __init__(self, repository_root: Path):
        self.repository_root = repository_root.resolve()

    def extract(self, entity: Entity) -> str | None:
        """Return the entity's source text, or None if unavailable."""
        location = entity.location

        if location is None:
            return None

        relative_path = Path(location.file)

        # Reject absolute paths and paths that escape the repository.
        if relative_path.is_absolute():
            return None

        try:
            source_path = (self.repository_root / relative_path).resolve()
            source_path.relative_to(self.repository_root)
        except (OSError, ValueError):
            return None

        if not source_path.is_file():
            return None

        try:
            with source_path.open("r", encoding="utf-8") as source_file:
                lines = source_file.readlines()
        except (OSError, UnicodeError):
            return None

        start = location.start_line
        end = location.end_line

        # SourceLocation uses 1-based, inclusive line numbers.
        if start < 1 or end < start or end > len(lines):
            return None

        return "".join(lines[start - 1:end])
