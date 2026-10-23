from fastapi import HTTPException
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app
from app.routes import repositories as repository_routes
from app.services.auth.dependencies import get_current_user
from app.database.postgres import get_db


def test_ask_repository_returns_503_when_llm_provider_fails(monkeypatch):
    fake_user = Mock()
    fake_user.id = 4

    fake_repository = Mock()
    fake_repository.id = 9

    monkeypatch.setattr(
        repository_routes.repository_service,
        "get_by_id",
        lambda repository_id, current_user, db: fake_repository,
    )

    class FailingAnswerService:
        def __init__(self, **kwargs):
            pass

        def prepare_answer(self, **kwargs):
            raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(
        repository_routes,
        "AnswerService",
        FailingAnswerService,
    )

    monkeypatch.setattr(
        repository_routes,
        "create_llm_provider",
        lambda: Mock(),
    )

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: object()

    client = TestClient(app, raise_server_exceptions=False)

    try:
        response = client.post(
            "/repositories/9/ask",
            json={"query": "Explain the repository"},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == (
            "Answer generation is temporarily unavailable"
        )
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_ask_repository_rejects_repository_not_owned_by_user(monkeypatch):
    fake_user = Mock()
    fake_user.id = 4

    def reject_repository(repository_id, current_user, db):
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    monkeypatch.setattr(
        repository_routes.repository_service,
        "get_by_id",
        reject_repository,
    )

    def unexpected_answer_service(**kwargs):
        raise AssertionError(
            "Answer generation must not run for an inaccessible repository"
        )

    monkeypatch.setattr(
        repository_routes,
        "AnswerService",
        unexpected_answer_service,
    )

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: object()

    client = TestClient(app, raise_server_exceptions=False)

    try:
        response = client.post(
            "/repositories/9/ask",
            json={"query": "Explain the repository"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"
    finally:
        client.close()
        app.dependency_overrides.clear()
