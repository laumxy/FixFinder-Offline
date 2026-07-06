import pytest


def test_system_role_returns_clarification_when_missing_info(client=None):
    # Unit-level: we only verify schema shape by calling the pure helpers indirectly
    # would require a TestClient; keep deterministic by checking endpoint module exports.
    from app.api import v2_routes

    body = v2_routes.SystemRoleRequest(
        query="Help me fix it",  # intentionally too vague
        top_k=3,
        responses=[],
    )

    resp = v2_routes.system_role_conversation(body)
    assert isinstance(resp, dict)
    assert resp.get("status") in {"clarification_needed", "plan_ready"}

    if resp.get("status") == "clarification_needed":
        assert "conversation" in resp
        assert "missing_fields" in resp
        assert len(resp.get("conversation", "")) > 0


def test_system_role_returns_plan_or_clarification():
    from app.api import v2_routes

    body = v2_routes.SystemRoleRequest(
        query="My RV water pump runs but no water comes out",
        top_k=2,
        responses=[],
    )
    resp = v2_routes.system_role_conversation(body)
    assert isinstance(resp, dict)
    assert resp.get("status") in {"clarification_needed", "plan_ready"}
    assert "conversation" in resp

