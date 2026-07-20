"""Session B done-when, part 1: every remaining submit tool validates at write
time and rejects pedagogically — rule + offending input + compliant example."""
import json

from engine import submits

from conftest import (valid_contract, valid_component, valid_crud, valid_dependency,
                      valid_entity, valid_machine, valid_use_case)


# --- use cases ----------------------------------------------------------------

def test_use_case_lands_with_steps_and_extensions(conn):
    result = submits.submit_use_cases(conn, [valid_use_case()])
    assert result["accepted"] == 1
    assert result["results"][0]["step_ids"] == [1, 2]
    steps = conn.execute("SELECT * FROM uc_steps ORDER BY step_no").fetchall()
    assert [s["step_no"] for s in steps] == [1, 2]
    assert steps[1]["no_extension_reason"].startswith("monotonic")
    assert steps[0]["provenance"] == "decided"  # inherited from the use case
    exts = conn.execute("SELECT * FROM uc_extensions").fetchall()
    assert len(exts) == 1 and exts[0]["step_id"] == steps[0]["id"]
    assert exts[0]["in_scope"] == 1


def test_use_case_child_provenance_overrides_parent(conn):
    uc = valid_use_case()
    uc["steps"][0]["provenance"] = "assumed"
    uc["steps"][0]["assumption_kind"] = "intent"
    assert submits.submit_use_cases(conn, [uc])["accepted"] == 1
    steps = conn.execute("SELECT * FROM uc_steps ORDER BY step_no").fetchall()
    assert steps[0]["provenance"] == "assumed"
    assert steps[0]["assumption_kind"] == "intent"
    assert steps[1]["provenance"] == "decided"
    # The extension inherits the *step's* effective provenance.
    ext = conn.execute("SELECT * FROM uc_extensions").fetchone()
    assert ext["provenance"] == "assumed" and ext["assumption_kind"] == "intent"


def test_use_case_rejections_are_pedagogic(conn):
    result = submits.submit_use_cases(conn, [
        valid_use_case(actor=None),
        valid_use_case(title="No steps", steps=[]),
        valid_use_case(title="Contradiction", steps=[
            {"text": "step", "no_extension_reason": "cannot fail",
             "extensions": [{"description": "it failed", "handling": "handle it"}]}]),
        valid_use_case(title="Unhandled", steps=[
            {"text": "step", "extensions": [{"description": "gateway times out"}]}]),
    ])
    assert result["accepted"] == 0
    errors = [v["error"] for v in result["results"]]
    assert "primary actor" in errors[0] and "Compliant example" in errors[0]
    assert "non-empty array" in errors[1]
    assert "never both" in errors[2]
    assert "handling" in errors[3] and "in_scope=false" in errors[3]
    for err in errors:
        assert err.startswith("Rule:") or "Rule:" in err
        assert "Offending" in err


def test_bad_child_rejects_whole_row_without_partial_insert(conn):
    good = valid_use_case()
    bad = valid_use_case(title="Broken", steps=[
        {"text": "fine step", "extensions": [{"description": "x", "handling": "y"}]},
        {"text": ""},  # empty text
    ])
    result = submits.submit_use_cases(conn, [good, bad])
    assert result["accepted"] == 1 and result["rejected"] == 1
    assert conn.execute("SELECT count(*) FROM use_cases").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM uc_steps").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM uc_extensions").fetchone()[0] == 1


def test_duplicate_use_case_title_rejected(conn):
    submits.submit_use_cases(conn, [valid_use_case()])
    result = submits.submit_use_cases(conn, [valid_use_case(title="PLACE AN ORDER")])
    assert result["rejected"] == 1
    assert "already exists" in result["results"][0]["error"]


def test_uc_extensions_added_to_existing_step(conn):
    submits.submit_use_cases(conn, [valid_use_case()])
    result = submits.submit_uc_extensions(conn, [
        {"step_id": 1, "description": "duplicate submission",
         "handling": "idempotency key; second submit is a no-op", "provenance": "decided"},
        {"step_id": 1, "description": "browser refresh mid-submit", "in_scope": False,
         "provenance": "decided"},
    ])
    assert result["accepted"] == 2
    assert conn.execute("SELECT count(*) FROM uc_extensions WHERE step_id = 1").fetchone()[0] == 3


def test_uc_extension_on_cannot_fail_step_rejected(conn):
    submits.submit_use_cases(conn, [valid_use_case()])
    result = submits.submit_uc_extensions(conn, [
        {"step_id": 2, "description": "counter overflows", "handling": "wrap",
         "provenance": "decided"},
        {"step_id": 99, "description": "x", "handling": "y", "provenance": "decided"},
    ])
    assert result["accepted"] == 0
    errors = [v["error"] for v in result["results"]]
    assert "no_extension_reason" in errors[0] and "supersede_row" in errors[0]
    assert "Known uc_steps" in errors[1]


# --- CRUD grid ----------------------------------------------------------------

def test_crud_cells_land(conn):
    submits.submit_entities(conn, [valid_entity()])
    result = submits.submit_crud(conn, [
        valid_crud(),
        valid_crud(op="r"),  # normalized to upper case
        valid_crud(op="U", actor=None, na=True,
                   na_reason="orders are immutable; corrections are new orders"),
        valid_crud(op="D", actor="OrderService",
                   children_on_delete="order lines cascade-deleted"),
    ])
    assert result["accepted"] == 4
    rows = {r["op"]: r for r in conn.execute("SELECT * FROM crud_grid")}
    assert set(rows) == {"C", "R", "U", "D"}
    assert rows["U"]["na"] == 1 and rows["U"]["actor"] is None
    assert rows["D"]["children_on_delete"] is not None


def test_crud_rejections_are_pedagogic(conn):
    submits.submit_entities(conn, [valid_entity()])
    result = submits.submit_crud(conn, [
        valid_crud(op="X"),
        valid_crud(actor=None),
        valid_crud(op="U", na=True, na_reason=None, actor=None),
        valid_crud(op="U", na=True, na_reason="reason", actor="Someone"),
        valid_crud(op="C", children_on_delete="cascade"),
        valid_crud(entity_id=42),
    ])
    assert result["accepted"] == 0
    errors = [v["error"] for v in result["results"]]
    assert "['C', 'R', 'U', 'D']" in errors[0]
    assert "responsible actor/component" in errors[1] and "n/a" in errors[1]
    assert "na_reason" in errors[2]
    assert "never both" in errors[3]
    assert "D cell only" in errors[4]
    assert "Known entities" in errors[5] and "Order" in errors[5]


def test_crud_duplicate_cell_rejected_in_batch_and_across_calls(conn):
    submits.submit_entities(conn, [valid_entity()])
    result = submits.submit_crud(conn, [valid_crud(), valid_crud()])
    assert result["accepted"] == 1 and "already recorded" in result["results"][1]["error"]
    again = submits.submit_crud(conn, [valid_crud(op="c")])
    assert again["rejected"] == 1


# --- state machines -----------------------------------------------------------

def test_state_machine_with_cells_lands(conn):
    submits.submit_entities(conn, [valid_entity()])
    result = submits.submit_states(conn, [valid_machine()])
    assert result["accepted"] == 1
    assert result["results"][0]["cells"] == 1
    machine = conn.execute("SELECT * FROM state_machines").fetchone()
    assert json.loads(machine["states"]) == ["draft", "placed"]
    cell = conn.execute("SELECT * FROM sm_cells").fetchone()
    assert cell["machine_id"] == machine["id"]
    assert cell["provenance"] == "decided"  # inherited


def test_state_machine_rejections_are_pedagogic(conn):
    submits.submit_entities(conn, [
        valid_entity(),
        valid_entity(name="AuditEntry", has_lifecycle=False,
                     lifecycle_reason="append-only; never mutated"),
        valid_entity(name="Shipment"),
    ])
    submits.submit_states(conn, [valid_machine()])
    result = submits.submit_states(conn, [
        valid_machine(entity_id=2),                       # no lifecycle
        valid_machine(),                                  # duplicate machine
        valid_machine(entity_id=3, states=[]),
        valid_machine(entity_id=3, cells=[{"state": "nowhere", "event": "place",
                                           "transition_to": "placed"}]),
        valid_machine(entity_id=3, cells=[{"state": "draft", "event": "place",
                                           "transition_to": "placed", "impossible": True,
                                           "impossible_reason": "x"}]),
        valid_machine(entity_id=3, cells=[{"state": "draft", "event": "place"}]),
    ])
    assert result["accepted"] == 0
    errors = [v["error"] for v in result["results"]]
    assert "lifecycle entities only" in errors[0] and "supersede_row" in errors[0]
    assert "already has one" in errors[1] and "submit_state_cells" in errors[1]
    assert "non-empty array" in errors[2]
    assert "machine's states" in errors[3]
    assert "never both" in errors[4]
    assert "transition" in errors[5] and "impossible" in errors[5]


def test_state_cells_added_to_existing_machine(conn):
    submits.submit_entities(conn, [valid_entity()])
    submits.submit_states(conn, [valid_machine()])
    result = submits.submit_state_cells(conn, [
        {"entity_id": 1, "state": "placed", "event": "cancel", "transition_to": "draft",
         "provenance": "decided"},
        {"entity_id": 1, "state": "draft", "event": "cancel", "impossible": True,
         "impossible_reason": "nothing to cancel yet", "provenance": "decided"},
        {"entity_id": 1, "state": "draft", "event": "place", "transition_to": "placed",
         "provenance": "decided"},  # duplicate of the machine's existing cell
    ])
    assert result["accepted"] == 2 and result["rejected"] == 1
    assert "already recorded" in result["results"][2]["error"]
    assert conn.execute("SELECT count(*) FROM sm_cells").fetchone()[0] == 3


def test_state_cells_need_a_machine_first(conn):
    submits.submit_entities(conn, [valid_entity()])
    result = submits.submit_state_cells(conn, [
        {"entity_id": 1, "state": "draft", "event": "place", "transition_to": "placed",
         "provenance": "decided"}])
    assert result["rejected"] == 1
    assert "submit_states" in result["results"][0]["error"]


# --- components & contracts ----------------------------------------------------

def test_component_requires_single_responsibility(conn):
    result = submits.submit_components(conn, [
        valid_component(),
        valid_component(name="Mystery", responsibility=None),
        valid_component(name="ORDERSERVICE"),
    ])
    assert result["accepted"] == 1
    assert "responsibility" in result["results"][1]["error"]
    assert "already exists" in result["results"][2]["error"]


def test_contract_lands_with_structured_signature(conn):
    submits.submit_components(conn, [valid_component()])
    result = submits.submit_contracts(conn, [
        valid_contract(),
        valid_contract(name="order_total", params=[], errors=None, cannot_fail=True,
                       cannot_fail_reason="pure computation over validated input"),
        valid_contract(name="orders_api", kind="api", is_external=True),
    ])
    assert result["accepted"] == 3
    rows = conn.execute("SELECT * FROM contracts ORDER BY id").fetchall()
    params = json.loads(rows[0]["params"])
    assert params == [{"name": "draft", "type_expr": "OrderDraft", "required": True}]
    assert json.loads(rows[0]["errors"])[0]["name"] == "ValidationError"
    assert rows[1]["cannot_fail"] == 1 and rows[1]["errors"] is None
    assert json.loads(rows[1]["params"]) == []
    assert rows[2]["is_external"] == 1


def test_contract_rejections_are_pedagogic(conn):
    submits.submit_components(conn, [valid_component()])
    submits.submit_contracts(conn, [valid_contract()])
    result = submits.submit_contracts(conn, [
        valid_contract(name="a", params=None),
        valid_contract(name="b", params=[{"name": "x"}]),
        valid_contract(name="c", returns=None),
        valid_contract(name="d", errors=None),
        valid_contract(name="e", cannot_fail=True,
                       cannot_fail_reason="it cannot"),  # errors AND cannot_fail
        valid_contract(name="f", kind="rpc"),
        valid_contract(name="g", component_id=9),
        valid_contract(name="PLACE_ORDER"),
    ])
    assert result["accepted"] == 0
    errors = [v["error"] for v in result["results"]]
    assert "pass []" in errors[0]
    assert "type_expr" in errors[1]
    assert "return type_expr" in errors[2]
    assert "named error" in errors[3] and "cannot_fail" in errors[3]
    assert "never both" in errors[4]
    assert "['api', 'function', 'schema', 'file', 'event']" in errors[5]
    assert "Known components" in errors[6]
    assert "already exists" in errors[7]


def test_contract_deps_edges(conn):
    submits.submit_components(conn, [valid_component(),
                                     valid_component(name="Notifier",
                                                     responsibility="sends notifications")])
    submits.submit_contracts(conn, [valid_contract(),
                                    valid_contract(name="notify", component_id=2)])
    result = submits.submit_contract_deps(conn, [
        {"consumer_component_id": 2, "provider_contract_id": 1, "provenance": "decided"},
        {"consumer_contract_id": 2, "provider_contract_id": 1, "provenance": "decided"},
        {"provider_contract_id": 1, "provenance": "decided"},           # no consumer
        {"consumer_contract_id": 1, "consumer_component_id": 2,
         "provider_contract_id": 1, "provenance": "decided"},           # two consumers
        {"consumer_contract_id": 1, "provider_contract_id": 1, "provenance": "decided"},
        {"consumer_component_id": 1, "provider_contract_id": 42, "provenance": "decided"},
    ])
    assert result["accepted"] == 2
    errors = [v["error"] for v in result["results"][2:]]
    assert "exactly one consumer" in errors[0].lower()
    assert "exactly one consumer" in errors[1].lower()
    assert "consume itself" in errors[2]
    assert "Known contracts" in errors[3]


# --- dependencies & failure modes -----------------------------------------------

def test_dependency_and_failure_modes(conn):
    result = submits.submit_dependencies(conn, [
        valid_dependency(),
        valid_dependency(name="Postgres", kind=None),
        valid_dependency(name="STRIPE API"),
    ])
    assert result["accepted"] == 1
    assert "kind" in result["results"][1]["error"]
    assert "already exists" in result["results"][2]["error"]

    fm = submits.submit_dep_failure_modes(conn, [
        {"dep_id": 1, "mode": "slow", "handling": "2s timeout; retry once",
         "provenance": "decided"},
        {"dep_id": 1, "mode": "down", "handling": "x", "provenance": "decided"},
        {"dep_id": 1, "mode": "slow", "handling": "dup", "provenance": "decided"},
        {"dep_id": 1, "mode": "auth", "provenance": "decided"},
        {"dep_id": 9, "mode": "auth", "handling": "x", "provenance": "decided"},
    ])
    assert fm["accepted"] == 1
    errors = [v["error"] for v in fm["results"][1:]]
    assert "all five" in errors[0] and "'malformed'" in errors[0]
    assert "already recorded" in errors[1]
    assert "handling" in errors[2]
    assert "Known dependencies" in errors[3]
