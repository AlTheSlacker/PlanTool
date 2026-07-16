import pytest

from engine import db, submits


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


# --- gate-passing stage builders (drive the real submit surface) ------------
# Shared by the gate tests (pass direction) and the export round-trip test.

FULL_MACHINE_CELLS = [
    {"state": "draft", "event": "place", "transition_to": "placed"},
    {"state": "draft", "event": "cancel", "impossible": True,
     "impossible_reason": "nothing exists to cancel before placement"},
    {"state": "placed", "event": "place", "impossible": True,
     "impossible_reason": "an order is placed at most once"},
    {"state": "placed", "event": "cancel", "transition_to": "draft"},
]


def _ok(result):
    assert not result.get("error") and not result.get("rejected"), result
    return result


def make_stage1_pass(conn):
    _ok(submits.record_decision(
        conn, "Goal: customers place orders online", "decided",
        rationale="95% of orders complete without a support contact"))
    _ok(submits.record_decision(conn, "Non-goal: multi-currency pricing", "decided"))
    _ok(submits.record_decision(conn, "Stack: Python 3.12 service on AWS", "decided"))


def make_stage2_pass(conn):
    _ok(submits.submit_use_cases(conn, [valid_use_case()]))


def make_stage3_pass(conn):
    # The requirement links use_cases:1, and dangling refs are rejected since
    # Session D — make sure the use case exists for standalone callers.
    if not conn.execute("SELECT 1 FROM use_cases LIMIT 1").fetchone():
        make_stage2_pass(conn)
    _ok(submits.submit_requirements(conn, [valid_requirement(links=["use_cases:1"])]))


def make_stage4_pass(conn):
    _ok(submits.submit_entities(conn, [valid_entity()]))
    _ok(submits.submit_crud(conn, [valid_crud(op=op) for op in "CRUD"]))
    _ok(submits.submit_states(conn, [valid_machine(cells=FULL_MACHINE_CELLS)]))


def make_stage5_pass(conn):
    _ok(submits.submit_dependencies(conn, [valid_dependency()]))
    _ok(submits.submit_dep_failure_modes(conn, [
        {"dep_id": 1, "mode": mode, "handling": f"handle {mode} sensibly",
         "provenance": "decided"}
        for mode in ("unavailable", "slow", "malformed", "auth", "partial")]))


def make_stage6_pass(conn):
    _ok(submits.submit_components(conn, [valid_component()]))
    _ok(submits.submit_contracts(
        conn, [valid_contract(links=["requirements:1"], is_external=True)]))


def populate_full_plan(conn):
    """Drive the submit surface to a state where gates 1-6 all pass."""
    for build in (make_stage1_pass, make_stage2_pass, make_stage3_pass,
                  make_stage4_pass, make_stage5_pass, make_stage6_pass):
        build(conn)
