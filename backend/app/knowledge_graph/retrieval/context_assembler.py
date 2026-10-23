from typing import Any


class ContextAssembler:
    """Convert retrieval results into structured code evidence."""

    def assemble(self, retrieval_result: dict) -> dict:
        if not isinstance(retrieval_result, dict):
            raise ValueError("retrieval_result must be a dictionary")

        matches = retrieval_result.get("matches", [])

        if not isinstance(matches, list):
            raise ValueError("retrieval_result.matches must be a list")

        evidence = []

        for match in matches:
            if not isinstance(match, dict):
                continue

            entity = match.get("entity")

            if not isinstance(entity, dict):
                continue

            evidence.append(
                {
                    "entity_id": entity.get("id"),
                    "name": entity.get("name"),
                    "qualified_name": entity.get("qualified_name"),
                    "kind": self._get_kind(entity.get("labels", [])),
                    "language": entity.get("language"),
                    "file": entity.get("file"),
                    "start_line": entity.get("start_line"),
                    "end_line": entity.get("end_line"),
                    "score": match.get("score"),
                    "source_text": match.get("text", ""),
                    "relationships": self._format_relationships(
                        match.get("relationships", [])
                    ),
                }
            )

        return {
            "query": retrieval_result.get("query", ""),
            "repository_id": retrieval_result.get("repository_id"),
            "evidence_count": len(evidence),
            "evidence": evidence,
        }

    @staticmethod
    def _get_kind(labels: Any) -> str | None:
        if not isinstance(labels, list):
            return None

        # Neo4j labels include "Entity" and the entity's kind.
        kinds = [label for label in labels if label != "Entity"]

        return kinds[0] if kinds else None

    @staticmethod
    def _format_relationships(relationships: Any) -> list[dict]:
        if not isinstance(relationships, list):
            return []

        formatted = []

        for relationship in relationships:
            if not isinstance(relationship, dict):
                continue

            formatted.append(
                {
                    "source": relationship.get("source"),
                    "target": relationship.get("target"),
                    "relationship_type": relationship.get(
                        "relationship_type"
                    ),
                    "direction": relationship.get("direction"),
                }
            )

        return formatted
