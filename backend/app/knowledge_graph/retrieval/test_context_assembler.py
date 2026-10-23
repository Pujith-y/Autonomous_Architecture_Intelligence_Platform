import pytest

from app.knowledge_graph.retrieval.context_assembler import ContextAssembler


def test_assembles_entity_and_relationship_evidence():
    assembler = ContextAssembler()

    result = assembler.assemble(
        {
            "query": "Where is authentication handled?",
            "repository_id": 7,
            "matches": [
                {
                    "entity": {
                        "id": "user:1::repo:7::auth.login",
                        "name": "login",
                        "qualified_name": "auth.login",
                        "labels": ["Entity", "method"],
                        "language": "python",
                        "file": "app/auth.py",
                        "start_line": 10,
                        "end_line": 20,
                    },
                    "score": 0.91,
                    "text": "def login(): pass",
                    "relationships": [
                        {
                            "source": {"name": "login"},
                            "target": {"name": "verify_password"},
                            "relationship_type": "CALLS",
                            "direction": "outgoing",
                        }
                    ],
                }
            ],
        }
    )

    assert result["evidence_count"] == 1

    evidence = result["evidence"][0]
    assert evidence["name"] == "login"
    assert evidence["kind"] == "method"
    assert evidence["score"] == 0.91
    assert evidence["file"] == "app/auth.py"
    assert evidence["relationships"][0]["relationship_type"] == "CALLS"


def test_empty_matches_return_empty_evidence():
    result = ContextAssembler().assemble(
        {"query": "unknown symbol", "repository_id": 7, "matches": []}
    )

    assert result["evidence_count"] == 0
    assert result["evidence"] == []


def test_rejects_invalid_result():
    with pytest.raises(ValueError):
        ContextAssembler().assemble("not a dictionary")
