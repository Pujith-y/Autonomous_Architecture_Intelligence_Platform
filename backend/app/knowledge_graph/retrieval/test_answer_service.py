from unittest.mock import Mock

from app.ai.mock_provider import MockLLMProvider
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

    service = AnswerService(
        retrieval_service=retrieval_service,
        llm_provider=MockLLMProvider(),
    )

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
    assert "Where is login implemented?" in result["answer"]
    assert "1 pieces" in result["answer"]


def test_prepare_answer_handles_no_evidence():
    retrieval_service = Mock()
    retrieval_service.retrieve.return_value = {
        "query": "unknown",
        "user_id": 4,
        "repository_id": 9,
        "matches": [],
    }

    service = AnswerService(
        retrieval_service=retrieval_service,
        llm_provider=MockLLMProvider(),
    )

    result = service.prepare_answer(
        query="unknown",
        user_id=4,
        repository_id=9,
    )

    assert result["evidence_count"] == 0
    assert result["evidence"] == []
    assert result["answer"] == (
        "I couldn't find relevant evidence in this repository."
    )



def test_prepare_answer_passes_assembled_context_to_llm():
    retrieval_service = Mock()
    retrieval_service.retrieve.return_value = {
        "query": "Where is login implemented?",
        "user_id": 4,
        "repository_id": 9,
        "matches": [
            {
                "entity": {
                    "id": "login",
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

    llm_provider = Mock()
    llm_provider.generate_answer.return_value = (
        "The login function is implemented in auth.py."
    )

    service = AnswerService(
        retrieval_service=retrieval_service,
        llm_provider=llm_provider,
    )

    result = service.prepare_answer(
        query="Where is login implemented?",
        user_id=4,
        repository_id=9,
    )

    llm_provider.generate_answer.assert_called_once()

    call_kwargs = llm_provider.generate_answer.call_args.kwargs

    assert call_kwargs["query"] == "Where is login implemented?"
    assert call_kwargs["context"]["evidence_count"] == 1
    assert call_kwargs["context"]["evidence"][0]["qualified_name"] == "auth.login"
    assert result["answer"] == (
        "The login function is implemented in auth.py."
    )


def test_prepare_answer_passes_source_code_and_relationships_to_llm():
    retrieval_service = Mock()
    retrieval_service.retrieve.return_value = {
        "query": "How does login use the database?",
        "user_id": 4,
        "repository_id": 9,
        "matches": [
            {
                "entity": {
                    "id": "login",
                    "name": "login",
                    "qualified_name": "auth.login",
                    "labels": ["Entity", "method"],
                    "language": "python",
                    "file": "auth.py",
                    "start_line": 1,
                    "end_line": 5,
                },
                "score": 0.9,
                "text": "def login(): return db.find_user()",
                "relationships": [
                    {
                        "relationship_type": "calls",
                        "direction": "outgoing",
                        "target": {
                            "name": "find_user",
                            "qualified_name": "database.find_user",
                            "file": "database.py",
                            "language": "python",
                        },
                    }
                ],
            }
        ],
    }

    llm_provider = Mock()
    llm_provider.generate_answer.return_value = (
        "The login function calls database.find_user."
    )

    service = AnswerService(
        retrieval_service=retrieval_service,
        llm_provider=llm_provider,
    )

    result = service.prepare_answer(
        query="How does login use the database?",
        user_id=4,
        repository_id=9,
    )

    context = llm_provider.generate_answer.call_args.kwargs["context"]

    assert context["evidence_count"] == 1
    evidence = context["evidence"][0]
    assert evidence["source_text"] == "def login(): return db.find_user()"
    assert evidence["relationships"][0]["relationship_type"] == "calls"
    assert evidence["relationships"][0]["target"]["name"] == "find_user"
    assert result["answer"] == (
        "The login function calls database.find_user."
    )


import pytest


def test_prepare_answer_propagates_llm_provider_error():
    retrieval_service = Mock()
    retrieval_service.retrieve.return_value = {
        "query": "Where is login implemented?",
        "user_id": 4,
        "repository_id": 9,
        "matches": [],
    }

    llm_provider = Mock()
    llm_provider.generate_answer.side_effect = RuntimeError(
        "LLM provider unavailable"
    )

    service = AnswerService(
        retrieval_service=retrieval_service,
        llm_provider=llm_provider,
    )

    with pytest.raises(RuntimeError, match="LLM provider unavailable"):
        service.prepare_answer(
            query="Where is login implemented?",
            user_id=4,
            repository_id=9,
        )
