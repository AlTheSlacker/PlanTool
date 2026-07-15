import json

from engine import db, gaps, submits

from conftest import valid_entity, valid_requirement


def _set_stage(conn, stage):
    conn.execute("UPDATE plans SET current_stage = ?", (stage,))
    conn.commit()


def test_empty_plan_yields_stage1_kickoff(conn):
    out = gaps.next_gap(conn)
    assert out["status"] == "gaps"
    assert out["cluster"][0]["kind"] == "hole:stage1_not_started"


def test_open_conflict_outranks_everything(conn):
    plan = db.get_plan(conn)
    conn.execute(
        "INSERT INTO conflicts (plan_id, plan_version_added, description, source) "
        "VALUES (?, 1, 'duplicate transition', 'engine')", (plan["id"],))
    conn.commit()
    out = gaps.next_gap(conn)
    assert out["cluster"][0]["kind"] == "conflict"
    assert out["cluster"][0]["priority"] == 1
    assert out["cluster"][0]["context"]["conflict"]["description"] == "duplicate transition"


def test_world_assumption_outranks_intent(conn):
    submits.submit_requirements(conn, [
        valid_requirement(provenance="assumed", assumption_kind="intent"),
        valid_requirement(system_response="handle vendor batch upserts",
                          provenance="assumed", assumption_kind="world"),
    ])
    _set_stage(conn, 2)  # keep stage-3 hole detectors quiet; use cases empty is a stage-2 hole
    out = gaps.next_gap(conn)
    kinds = [g["kind"] for g in out["cluster"]]
    world_pos = next(i for i, g in enumerate(out["cluster"]) if g["kind"] == "assumed_world")
    intent = [g for g in out["cluster"] if g["kind"] == "assumed_intent"]
    if intent:
        assert world_pos < out["cluster"].index(intent[0])
    world = out["cluster"][world_pos]
    assert "spike" in world["ask"].lower() or "experiment" in world["ask"].lower()
    assert world["context"]["row"]["system_response"] == "handle vendor batch upserts"


def test_cluster_groups_by_entity_first(conn):
    _set_stage(conn, 4)
    submits.submit_entities(conn, [
        valid_entity(name="Order"),
        valid_entity(name="Invoice"),
        valid_entity(name="Customer"),
    ])
    plan = db.get_plan(conn)
    order_id = conn.execute("SELECT id FROM entities WHERE name = 'Order'").fetchone()[0]
    # Give Order a state machine with undefined cells so it has two gap kinds.
    conn.execute(
        "INSERT INTO state_machines (plan_id, plan_version_added, entity_id, states, events, provenance)"
        " VALUES (?, 1, ?, ?, ?, 'decided')",
        (plan["id"], order_id, json.dumps(["new", "paid"]), json.dumps(["pay"])))
    conn.commit()
    out = gaps.next_gap(conn)
    cluster = out["cluster"]
    assert 3 <= len(cluster) <= 5
    # Anchor's entity dominates the cluster: every gap sharing its entity, then table/stage fill.
    anchor = cluster[0]
    assert anchor["entity"] is not None
    same_entity = [g for g in cluster if g["entity"] == anchor["entity"]]
    assert len(same_entity) >= 2  # Order has crud + sm_cells gaps grouped together


def test_cluster_capped_at_five(conn):
    _set_stage(conn, 4)
    submits.submit_entities(
        conn, [valid_entity(name=f"E{i}") for i in range(8)])
    out = gaps.next_gap(conn)
    assert len(out["cluster"]) <= 5
    assert out["open_gap_total"] >= 8


def test_open_question_is_priority_five(conn):
    plan = db.get_plan(conn)
    submits.submit_requirements(conn, [valid_requirement()])  # silence stage-1 kickoff
    conn.execute(
        "INSERT INTO open_questions (plan_id, plan_version_added, text, owner) "
        "VALUES (?, 1, 'Which auth provider?', 'Al')", (plan["id"],))
    conn.commit()
    out = gaps.next_gap(conn)
    assert out["cluster"][0]["kind"] == "open_question"
    assert out["cluster"][0]["priority"] == 5


def test_stage_clear_when_nothing_open(conn):
    submits.submit_requirements(conn, [valid_requirement()])  # stage 1 kickoff satisfied
    out = gaps.next_gap(conn)
    assert out["status"] == "stage_clear"
    assert "run_gate(1)" in out["message"]


def test_stage5_missing_failure_modes(conn):
    _set_stage(conn, 5)
    plan = db.get_plan(conn)
    conn.execute(
        "INSERT INTO dependencies (plan_id, plan_version_added, name, kind, provenance) "
        "VALUES (?, 1, 'vendor API', 'api', 'decided')", (plan["id"],))
    dep_id = conn.execute("SELECT id FROM dependencies").fetchone()[0]
    conn.execute(
        "INSERT INTO dep_failure_modes (plan_id, plan_version_added, dep_id, mode, handling, provenance)"
        " VALUES (?, 1, ?, 'slow', 'timeout at 5s, retry twice', 'decided')",
        (plan["id"], dep_id))
    conn.commit()
    out = gaps.next_gap(conn)
    gap = out["cluster"][0]
    assert gap["kind"] == "hole:failure_modes_missing"
    assert set(gap["context"]["missing_modes"]) == {"unavailable", "malformed", "auth", "partial"}
