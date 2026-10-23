
from unittest.mock import Mock

from app.knowledge_graph.retrieval.answer_service import AnswerService


def test_prepare_answer_retrieves_and_assembles_evidence():
    retrieval_service = Mock()
    retrieval_service.retrieve.return_value = {
        "query": "Where is login implemented?",
        "user_id": 4,
        "repository_id": 9,
        "matches": [
            {
                "entity": {
                    "id": "user:4::repo:9::login",
                    "name": "login",
                    "qualified_name": "auth.login",
                    "labels": ["Entity", "method"],
                    "language": "python",
                    "file": "auth.py",
                    "start_line": 1,
                    "end_line": 5,
                },
                "score": 0.9,
                "text": "def login(): pass",
                "relationships": [],
            }
        ],
    }

    service = AnswerService(retrieval_service)

    result = service.prepare_answer(
        query="Where is login implemented?",
        user_id=4,
        repository_id=9,
    )

    retrieval_service.retrieve.assert_called_once_with(
        query="Where is login implemented?",
        user_id=4,
        repository_id=9,
        limit=5,
    )
    assert result["evidence_count"] == 1
    assert result["evidence"][0]["qualified_name"] == "auth.login"


def test_prepare_answer_handles_no_evidence():
    retrieval_service = Mock()
    retrieval_service.retrieve.return_value = {
        "query": "unknown",
        "user_id": 4,
        "repository_id": 9,
        "matches": [],
    }

    result = AnswerService(retrieval_service).prepare_answer(
        query="unknown",
        user_id=4,
        repository_id=9,
    )

    assert result["evidence_count"] == 0
    assert result["evidence"] == []
