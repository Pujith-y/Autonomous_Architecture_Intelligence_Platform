from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.repository_model.entities import Entity


@dataclass(frozen=True)
class SemanticDocument:
    entity_id: str
    text: str
    metadata: dict[str, Any]


class SemanticDocumentBuilder:
    """Build searchable documents from repository entities and source text."""

    def build(
        self,
        entity: Entity,
        source_text: str,
    ) -> SemanticDocument | None:
        if not source_text or not source_text.strip():
            return None

        parts = [
            f"Entity kind: {entity.kind.value}",
            f"Name: {entity.name}",
        ]

        if entity.qualified_name:
            parts.append(f"Qualified name: {entity.qualified_name}")

        if entity.language:
            parts.append(f"Language: {entity.language}")

        parts.extend([
            "Source code:",
            source_text.strip(),
        ])

        metadata: dict[str, Any] = {
            "entity_id": entity.id,
            "kind": entity.kind.value,
            "name": entity.name,
        }

        if entity.qualified_name:
            metadata["qualified_name"] = entity.qualified_name

        if entity.language:
            metadata["language"] = entity.language

        if entity.location:
            metadata["file"] = str(entity.location.file)
            metadata["start_line"] = entity.location.start_line
            metadata["end_line"] = entity.location.end_line

        return SemanticDocument(
            entity_id=entity.id,
            text="\n".join(parts),
            metadata=metadata,
        )
