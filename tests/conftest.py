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


def valid_use_case(**overrides):
    row = {
        "title": "Place an order",
        "actor": "Customer",
        "steps": [
            {"text": "Customer submits the completed order form",
             "extensions": [{"description": "form fails validation",
                             "handling": "field-level errors; order not created"}]},
            {"text": "System assigns the next order number",
             "no_extension_reason": "monotonic counter inside one transaction"},
        ],
        "provenance": "decided",
    }
    row.update(overrides)
    return row


def valid_crud(**overrides):
    row = {"entity_id": 1, "op": "C", "actor": "OrderService", "provenance": "decided"}
    row.update(overrides)
    return row


def valid_machine(**overrides):
    row = {
        "entity_id": 1,
        "states": ["draft", "placed"],
        "events": ["place", "cancel"],
        "cells": [{"state": "draft", "event": "place", "transition_to": "placed"}],
        "provenance": "decided",
    }
    row.update(overrides)
    return row


def valid_component(**overrides):
    row = {
        "name": "OrderService",
        "responsibility": "owns order lifecycle and enforces order invariants",
        "provenance": "decided",
    }
    row.update(overrides)
    return row


def valid_contract(**overrides):
    row = {
        "component_id": 1,
        "name": "place_order",
        "kind": "function",
        "params": [{"name": "draft", "type_expr": "OrderDraft"}],
        "returns": "OrderId",
        "errors": [{"name": "ValidationError",
                    "semantics": "invariant violated; nothing persisted"}],
        "provenance": "decided",
    }
    row.update(overrides)
    return row


def valid_dependency(**overrides):
    row = {"name": "Stripe API", "kind": "api", "provenance": "decided"}
    row.update(overrides)
    return row
