from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from tenderhack_backend.app import create_app
from tenderhack_backend.config import Settings
from tenderhack_backend.fakes import FakeGenerator, FakeKnowledge, FakePolicy
from tenderhack_backend.service import BackendService
from tenderhack_backend.storage import Database
from tenderhack_contracts import (
    EvidenceItem,
    GateDecision,
    GenerationAnswer,
    KnowledgeResult,
    RoutingResult,
    SourceRecord,
)


def answer_dependencies():
    evidence = EvidenceItem(
        evidence_id="evidence-demo",
        source_id="source-demo",
        source_type="portal_knowledge_base_api",
        title="Инструкция",
        text="Поставщик открывает карточку контракта.",
        conditions=["Действуйте от имени поставщика."],
        applicable_roles=["supplier"],
        role_verified=True,
        content_status="complete",
        retrieval_method="dense",
        score=0.9,
    )
    knowledge = FakeKnowledge(
        KnowledgeResult(
            snapshot_id="mock-a02",
            candidates=[evidence],
            selected_evidence_ids=["evidence-demo"],
            decision=GateDecision.ANSWER_ALLOWED,
            route=RoutingResult(support_line="L1", basis_source_ids=["source-demo"]),
            timings_ms={"retrieval": 7},
        )
    )
    knowledge.sources["source-demo"] = SourceRecord(
        source_id="source-demo",
        source_type="portal_knowledge_base_api",
        title="Инструкция",
        excerpt=evidence.text,
        conditions=evidence.conditions,
        applicable_roles=["supplier"],
        content_status="complete",
    )
    generator = FakeGenerator(
        GenerationAnswer(
            summary="Откройте карточку контракта.",
            conditions=["Действуйте от имени поставщика."],
            steps=["Откройте карточку контракта."],
            source_ids=["source-demo"],
        )
    )
    return knowledge, generator


def client_for(tmp_path: Path, *, capacity: int = 4):
    knowledge, generator = answer_dependencies()
    settings = Settings(
        db_path=tmp_path / "app.sqlite",
        allowed_origin="http://testserver",
        cookie_secure=False,
        is_demo=True,
        auto_worker=False,
    )
    service = BackendService(
        Database(settings.db_path),
        FakePolicy(),
        knowledge,
        generator,
        queue_capacity=capacity,
    )
    app = create_app(settings=settings, service=service)
    return TestClient(app), app


def create_session(client: TestClient):
    response = client.post("/api/v1/sessions", headers={"Origin": "http://testserver"})
    assert response.status_code in (200, 201)
    return response.json()


def test_session_cookie_and_full_http_flow(tmp_path: Path) -> None:
    client, app = client_for(tmp_path)
    with client:
        session = create_session(client)
        cookie = client.cookies.get("tenderhack_session")
        assert cookie == session["session_id"]
        set_cookie = client.post(
            "/api/v1/sessions", headers={"Origin": "http://testserver"}
        ).headers["set-cookie"]
        assert "HttpOnly" in set_cookie
        assert "SameSite=strict" in set_cookie

        chat = client.post(
            "/api/v1/chat",
            headers={"Origin": "http://testserver"},
            json={"request_key": str(uuid4()), "text": "Как подписать контракт?"},
        )
        assert chat.status_code == 202
        accepted = chat.json()
        assert __import__("asyncio").run(app.state.service.process_next()) is True

        request = client.get(f"/api/v1/requests/{accepted['request_id']}")
        case = client.get(f"/api/v1/cases/{accepted['case_id']}")
        source = client.get("/api/v1/sources/source-demo")
        assert request.status_code == case.status_code == source.status_code == 200
        assert request.json()["status"] == "final"
        assert case.json()["messages"][-1]["structured_content"]["steps"]

        feedback = client.post(
            "/api/v1/feedback",
            headers={"Origin": "http://testserver"},
            json={
                "message_id": case.json()["messages"][-1]["message_id"],
                "useful": True,
            },
        )
        assert feedback.status_code == 201


def test_private_resources_return_same_404_to_other_session(tmp_path: Path) -> None:
    owner, app = client_for(tmp_path)
    with owner:
        create_session(owner)
        accepted = owner.post(
            "/api/v1/chat",
            headers={"Origin": "http://testserver"},
            json={"request_key": str(uuid4()), "text": "Вопрос"},
        ).json()
    stranger = TestClient(app)
    with stranger:
        create_session(stranger)
        for path in (
            f"/api/v1/cases/{accepted['case_id']}",
            f"/api/v1/requests/{accepted['request_id']}",
        ):
            response = stranger.get(path)
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "NOT_FOUND"


def test_origin_and_queue_overflow_use_contract_errors(tmp_path: Path) -> None:
    client, _ = client_for(tmp_path, capacity=1)
    with client:
        create_session(client)
        forbidden = client.post(
            "/api/v1/chat",
            headers={"Origin": "https://evil.example"},
            json={"request_key": str(uuid4()), "text": "Вопрос"},
        )
        assert forbidden.status_code == 403

        first = client.post(
            "/api/v1/chat",
            headers={"Origin": "http://testserver"},
            json={"request_key": str(uuid4()), "text": "Первый"},
        )
        assert first.status_code == 202
        overflow = client.post(
            "/api/v1/chat",
            headers={"Origin": "http://testserver"},
            json={"request_key": str(uuid4()), "text": "Второй"},
        )
        assert overflow.status_code == 429
        assert overflow.json()["error"]["code"] == "QUEUE_FULL"


def test_missing_session_is_unauthorized(tmp_path: Path) -> None:
    client, _ = client_for(tmp_path)
    with client:
        response = client.get(f"/api/v1/cases/{uuid4()}")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_forged_session_cookie_cannot_create_private_state(tmp_path: Path) -> None:
    client, _ = client_for(tmp_path)
    with client:
        client.cookies.set("tenderhack_session", str(uuid4()))
        response = client.post(
            "/api/v1/chat",
            headers={"Origin": "http://testserver"},
            json={"request_key": str(uuid4()), "text": "Вопрос"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_feedback_update_returns_200_and_comment_only_creation_is_rejected(
    tmp_path: Path,
) -> None:
    client, app = client_for(tmp_path)
    with client:
        create_session(client)
        accepted = client.post(
            "/api/v1/chat",
            headers={"Origin": "http://testserver"},
            json={"request_key": str(uuid4()), "text": "Вопрос"},
        ).json()
        __import__("asyncio").run(app.state.service.process_next())
        message_id = client.get(f"/api/v1/cases/{accepted['case_id']}").json()[
            "messages"
        ][-1]["message_id"]
        first = client.post(
            "/api/v1/feedback",
            headers={"Origin": "http://testserver"},
            json={"message_id": message_id, "useful": True},
        )
        update = client.post(
            "/api/v1/feedback",
            headers={"Origin": "http://testserver"},
            json={"message_id": message_id, "comment": "Понятный ответ"},
        )
        assert first.status_code == 201
        assert update.status_code == 200

        other_client, other_app = client_for(tmp_path / "other")
        with other_client:
            create_session(other_client)
            other_accepted = other_client.post(
                "/api/v1/chat",
                headers={"Origin": "http://testserver"},
                json={"request_key": str(uuid4()), "text": "Вопрос"},
            ).json()
            __import__("asyncio").run(other_app.state.service.process_next())
            other_message = other_client.get(
                f"/api/v1/cases/{other_accepted['case_id']}"
            ).json()["messages"][-1]["message_id"]
            invalid = other_client.post(
                "/api/v1/feedback",
                headers={"Origin": "http://testserver"},
                json={"message_id": other_message, "comment": "Нет оценки"},
            )
            assert invalid.status_code == 422
