"""Focused tests for project binding at conversation creation (Phase 1.1).

Covers:
- /chat/stream with project_id binds a NEW conversation to the project
- the pipeline invocation receives the bound project_id
- foreign (unowned) project_id -> 404 project_not_found
- an EXISTING conversation is never re-bound by a message (creation-time only)
- PATCH rebinding remains the explicit route (already covered in test_endpoints,
  re-asserted here for the project scope)
"""

import pytest


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_project(db, owner, name: str):
    from sqlalchemy import select

    from app.models.project import Project

    project = Project(owner_id=owner.id, name=name)
    db.add(project)
    db.commit()
    return project


@pytest.fixture
def alice_project(db, user):
    return _create_project(db, user, "Alpha")


@pytest.fixture
def bob_project(db, second_user):
    return _create_project(db, second_user, "Beta")


def _stream(client, headers, session_id, message, **extra):
    body = {"session_id": session_id, "message": message, **extra}
    return client.post("/chat/stream", json=body, headers=headers)


def test_stream_binds_new_conversation_to_project(client, alice_token, alice_project):
    r = _stream(client, _bearer(alice_token), "p1", "hi", project_id=alice_project.id)
    assert r.status_code == 200

    sessions = client.get("/chat/sessions", headers=_bearer(alice_token)).json()["sessions"]
    bound = [s for s in sessions if s["id"] == "p1"]
    assert len(bound) == 1
    assert bound[0]["project_id"] == alice_project.id


def test_stream_pipeline_receives_bound_project_id(client, alice_token, alice_project, chat_module):
    seen = {}
    original = chat_module._pipeline.process

    def spy(question, session_id, retriever_mode=None, filename=None, project_id=None, **kwargs):
        seen["project_id"] = project_id
        return original(
            question=question,
            session_id=session_id,
            retriever_mode=retriever_mode,
            filename=filename,
            project_id=project_id,
            **kwargs,
        )

    chat_module._pipeline.process = spy
    r = _stream(client, _bearer(alice_token), "p2", "hi", project_id=alice_project.id)
    assert r.status_code == 200
    assert seen["project_id"] == alice_project.id


def test_stream_foreign_project_404(client, alice_token, bob_project):
    r = _stream(client, _bearer(alice_token), "p3", "hi", project_id=bob_project.id)
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "project_not_found"


def test_stream_unknown_project_404(client, alice_token):
    r = _stream(client, _bearer(alice_token), "p4", "hi", project_id="no-such-project")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"


def test_existing_conversation_is_not_rebound_by_message(client, alice_token, alice_project):
    first = _stream(client, _bearer(alice_token), "p5", "hi")
    assert first.status_code == 200

    second = _stream(client, _bearer(alice_token), "p5", "hi again", project_id=alice_project.id)
    assert second.status_code == 200

    sessions = client.get("/chat/sessions", headers=_bearer(alice_token)).json()["sessions"]
    bound = [s for s in sessions if s["id"] == "p5"]
    assert len(bound) == 1
    assert bound[0]["project_id"] is None


def test_patch_rebinds_conversation_to_project(client, alice_token, alice_project):
    _stream(client, _bearer(alice_token), "p6", "hi")

    r = client.patch(
        "/chat/sessions/p6",
        json={"project_id": alice_project.id},
        headers=_bearer(alice_token),
    )
    assert r.status_code == 200

    sessions = client.get("/chat/sessions", headers=_bearer(alice_token)).json()["sessions"]
    bound = [s for s in sessions if s["id"] == "p6"]
    assert bound[0]["project_id"] == alice_project.id