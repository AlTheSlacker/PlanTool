import pytest

from engine import db


@pytest.fixture
def conn(tmp_path):
    c = db.create_plan_db(tmp_path / "plan.db", "test-plan")
    yield c
    c.close()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Point the server at an isolated workspace, as .mcp.json's cwd would."""
    monkeypatch.setenv("PLANTOOL_WORKSPACE", str(tmp_path))
    return tmp_path


def valid_requirement(**overrides):
    row = {
        "ears_type": "event",
        "trigger": "the user submits a valid order",
        "system_response": "persist the order and emit OrderPlaced",
        "provenance": "decided",
    }
    row.update(overrides)
    return row


def valid_entity(**overrides):
    row = {
        "name": "Order",
        "description": "A customer purchase",
        "has_lifecycle": True,
        "provenance": "decided",
    }
    row.update(overrides)
    return row
