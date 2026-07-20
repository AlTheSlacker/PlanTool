"""Supersede/retire/confirm (Session D, W1) — the correction path proven in
both directions, plus the dogfood F5 timeline (batch dangling refs) now
rejected, and lineage surviving the export round-trip."""
import json

import pytest

from engine import db, gaps, gates, lineage, render, submits

from conftest import (make_stage1_pass, make_stage2_pass, make_stage3_pass,
                      make_stage5_pass, populate_full_plan, valid_contract,
                      valid_component, valid_crud, valid_entity, valid_machine,
                      valid_requirement, valid_use_case)


def active(conn, table, rid):
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (rid,)).fetchone()
    return db.is_active(row)


# --- supersede_row: happy paths ------------------------------------------------

def test_supersede_decision_creates_bidirectional_lineage(conn):
    submits.record_decision(conn, "Stack: Python 3.11", "assumed",
                            assumption_kind="intent")
    out = lineage.supersede_row(conn, "decisions", 1,
                                {"text": "Stack: Python 3.12", "provenance": "decided"},
                                "user corrected the version")
    assert out["supersedes"] == "decisions:1" and out["ref"] == "decisions:2"
    old = conn.execute("SELECT * FROM decisions WHERE id = 1").fetchone()
    new = conn.execute("SELECT * FROM decisions WHERE id = 2").fetchone()
    assert old["superseded_by"] == 2 and old["superseded_reason"] == "user corrected the version"
    assert old["retired"] == 0
    assert new["supersedes"] == 1 and new["superseded_by"] is None
    assert new["text"] == "Stack: Python 3.12" and new["provenance"] == "decided"
    assert new["assumption_kind"] is None  # dropped with the provenance change


def test_supersede_successor_may_reuse_the_natural_key(conn):
    submits.submit_entities(conn, [valid_entity()])
    out = lineage.supersede_row(conn, "entities", 1,
                                {"description": "A customer purchase order"},
                                "sharper description")
    assert out["ref"] == "entities:2"
    new = conn.execute("SELECT * FROM entities WHERE id = 2").fetchone()
    assert new["name"] == "Order"  # same name, allowed because original is inactive


def test_supersede_repoints_children_and_rewrites_links(conn):
    make_stage2_pass(conn)
    make_stage3_pass(conn)
    out = lineage.supersede_row(conn, "use_cases", 1, {"actor": "Registered customer"},
                                "actor was too broad")
    assert out["children_repointed"] == {"uc_steps": 2}
    steps = conn.execute("SELECT use_case_id FROM uc_steps").fetchall()
    assert {s["use_case_id"] for s in steps} == {out["id"]}
    # The requirement linked "use_cases:1"; active rows follow the successor.
    req = conn.execute("SELECT links FROM requirements WHERE id = 1").fetchone()
    assert json.loads(req["links"]) == [f"use_cases:{out['id']}"]
    assert gates.gate_stage2(conn) == [] and gates.gate_stage3(conn) == []


def test_supersede_contract_links_is_the_stage6_remedy(conn):
    make_stage3_pass(conn)
    submits.submit_components(conn, [valid_component()])
    submits.submit_contracts(conn, [valid_contract(is_external=True)])  # untraced
    assert gates.gate_stage6(conn)
    out = lineage.supersede_row(conn, "contracts", 1,
                                {"links": ["requirements:1"]},
                                "gate hole: traced it to its requirement")
    assert not out.get("error")
    assert gates.gate_stage6(conn) == []


def test_supersede_null_clears_a_field(conn):
    make_stage2_pass(conn)
    # Step 2 carries a no_extension_reason; clearing it re-opens the step.
    out = lineage.supersede_row(conn, "uc_steps", 2, {"no_extension_reason": None},
                                "the counter can in fact overflow")
    assert not out.get("error")
    result = submits.submit_uc_extensions(conn, [
        {"step_id": out["id"], "description": "counter overflows",
         "handling": "wrap with epoch prefix", "provenance": "decided"}])
    assert result["accepted"] == 1


def test_supersede_files_staleness_conflict_on_resolved_question(conn):
    submits.submit_entities(conn, [valid_entity()])
    submits.file_question(conn, "Is Order immutable?", links=["entities:1"])
    submits.resolve_question(conn, 1, "yes, corrections are new orders")
    out = lineage.supersede_row(conn, "entities", 1,
                                {"description": "mutable until shipped"}, "user changed call")
    assert out["conflicts_filed"]
    assert "resolved" in out["conflicts_filed"][0]["description"]


# --- supersede_row: rejections leave everything intact --------------------------

def test_supersede_rejects_and_rolls_back_on_invalid_replacement(conn):
    submits.submit_requirements(conn, [valid_requirement()])
    out = lineage.supersede_row(conn, "requirements", 1, {"ears_type": "sometimes"},
                                "typo demo")
    assert "ears_type" in out["error"]
    assert active(conn, "requirements", 1)
    assert conn.execute("SELECT count(*) FROM requirements").fetchone()[0] == 1


def test_supersede_rejects_already_superseded_row(conn):
    submits.record_decision(conn, "Goal: ship", "decided", rationale="ships")
    lineage.supersede_row(conn, "decisions", 1, {"text": "Goal: ship weekly"}, "sharper")
    out = lineage.supersede_row(conn, "decisions", 1, {"text": "Goal: ship daily"}, "again")
    assert "already superseded by decisions:2" in out["error"]


def test_supersede_rejects_children_and_unknown_fields(conn):
    make_stage2_pass(conn)
    assert "supersede individually" in lineage.supersede_row(
        conn, "use_cases", 1, {"steps": []}, "r")["error"]
    assert "unknown replacement field" in lineage.supersede_row(
        conn, "use_cases", 1, {"titel": "typo"}, "r")["error"]


def test_supersede_rejects_bookkeeping_tables_and_missing_reason(conn):
    submits.file_question(conn, "who owns retries?")
    assert "claim tables" in lineage.supersede_row(
        conn, "open_questions", 1, {"text": "x"}, "r")["error"]
    submits.submit_entities(conn, [valid_entity()])
    assert "reason" in lineage.supersede_row(conn, "entities", 1, {"name": "X"}, "  ")["error"]


def test_supersede_verified_row_requires_fresh_provenance(conn, tmp_path):
    submits.submit_dependencies(conn, [
        {"name": "SMB share", "kind": "filesystem", "provenance": "assumed",
         "assumption_kind": "world"}])
    from engine import spikes
    spikes.register_spike(conn, tmp_path, "reachable?", "yes", "mount it", "1h",
                          links=["dependencies:1"])
    spikes.record_spike_result(conn, 1, "confirmed", "mounted and listed files")
    out = lineage.supersede_row(conn, "dependencies", 1, {"notes": "read-only"}, "r")
    assert "verified" in out["error"] and "provenance" in out["error"]
    ok = lineage.supersede_row(conn, "dependencies", 1,
                               {"notes": "read-only", "provenance": "decided"}, "r")
    assert not ok.get("error")


# --- retire_row -----------------------------------------------------------------

def test_retire_contract_is_the_stage6_cut(conn):
    make_stage3_pass(conn)
    submits.submit_components(conn, [valid_component()])
    submits.submit_contracts(conn, [
        valid_contract(links=["requirements:1"], is_external=True),
        valid_contract(name="mystery_helper", is_external=True)])  # invented scope
    assert gates.gate_stage6(conn)
    out = lineage.retire_row(conn, "contracts", 2, "invented scope — no requirement needs it")
    assert out["retired"] == "contracts:2"
    assert gates.gate_stage6(conn) == []


def test_retire_cascades_to_dependent_children(conn):
    make_stage2_pass(conn)
    out = lineage.retire_row(conn, "use_cases", 1, "descoped")
    assert set(out["cascaded"]) == {"uc_steps:1", "uc_steps:2", "uc_extensions:1"}
    assert not active(conn, "uc_steps", 1) and not active(conn, "uc_extensions", 1)
    assert holes_free_of(gates.gate_stage2(conn), "uc_steps")


def holes_free_of(holes, table):
    return not [h for h in holes if h["table"] == table]


def test_retire_rejects_double_retire(conn):
    submits.submit_entities(conn, [valid_entity()])
    lineage.retire_row(conn, "entities", 1, "wrong model")
    assert "retired" in lineage.retire_row(conn, "entities", 1, "again")["error"]


# --- confirm_assumption ----------------------------------------------------------

def test_confirm_assumption_upgrades_intent_in_place(conn):
    submits.submit_requirements(conn, [valid_requirement(
        provenance="assumed", assumption_kind="intent")])
    out = lineage.confirm_assumption(conn, "requirements", 1,
                                     "user: 'yes, exactly that behaviour'")
    assert out["provenance"] == "decided"
    row = conn.execute("SELECT * FROM requirements WHERE id = 1").fetchone()
    assert row["provenance"] == "decided" and row["assumption_kind"] is None
    assert "yes, exactly that behaviour" in row["provenance_note"]
    # The F4 nag is gone: no assumed_intent gap surfaces for this row.
    result = gaps.next_gap(conn)
    kinds = [g["kind"] for g in result.get("cluster", [])]
    assert "assumed_intent" not in kinds


def test_confirm_assumption_refuses_world_and_non_assumed(conn):
    submits.submit_dependencies(conn, [
        {"name": "SMB share", "kind": "filesystem", "provenance": "assumed",
         "assumption_kind": "world"}])
    out = lineage.confirm_assumption(conn, "dependencies", 1, "user says it's fine")
    assert "register_spike" in out["error"]
    submits.submit_entities(conn, [valid_entity()])
    out = lineage.confirm_assumption(conn, "entities", 1, "sure")
    assert "assumed rows only" in out["error"]


def test_confirm_assumption_requires_evidence(conn):
    submits.submit_requirements(conn, [valid_requirement(
        provenance="assumed", assumption_kind="intent")])
    assert "evidence" in lineage.confirm_assumption(conn, "requirements", 1, " ")["error"]


# --- the closed F5 hole (dangling batch refs) -------------------------------------

def test_f5_timeline_batch_contracts_with_forward_refs_rejected(conn):
    """The dogfood timeline: contracts submitted 15:59 referencing requirements
    created three minutes later. Batch submits now resolve every links field."""
    submits.submit_components(conn, [valid_component()])
    result = submits.submit_contracts(conn, [
        valid_contract(links=["requirements:63"]),
        valid_contract(name="acquire_writer_lock", links=["requirements:64"])])
    assert result["accepted"] == 0 and result["rejected"] == 2
    for verdict in result["results"]:
        assert "matches nothing" in verdict["error"]
        assert "supersede_row or retire_row" in verdict["error"]  # the sanctioned remedy


def test_nested_children_links_are_resolved_too(conn):
    result = submits.submit_use_cases(conn, [valid_use_case(steps=[
        {"text": "step one", "no_extension_reason": "trivial",
         "links": ["requirements:9"]}])])
    assert result["rejected"] == 1
    assert "requirements:9 matches nothing" in result["results"][0]["error"]


def test_links_to_superseded_row_rejected_with_successor_named(conn):
    submits.submit_entities(conn, [valid_entity()])
    lineage.supersede_row(conn, "entities", 1, {"description": "v2"}, "sharper")
    result = submits.submit_requirements(conn, [valid_requirement(links=["entities:1"])])
    assert result["rejected"] == 1
    assert "superseded — link its successor entities:2" in result["results"][0]["error"]


# --- inactive rows are invisible to the machinery ---------------------------------

def test_next_gap_stops_surfacing_superseded_assumed_rows(conn):
    submits.record_decision(conn, "Retries are capped at 3", "assumed",
                            assumption_kind="intent")
    kinds = [g["kind"] for g in gaps.next_gap(conn).get("cluster", [])]
    assert "assumed_intent" in kinds
    lineage.supersede_row(conn, "decisions", 1,
                          {"provenance": "decided"}, "user confirmed in review")
    kinds = [(g["kind"], g["table"], g["row_id"])
             for g in gaps.next_gap(conn).get("cluster", [])]
    assert ("assumed_intent", "decisions", 1) not in kinds


def test_duplicate_check_ignores_inactive_rows(conn):
    submits.submit_entities(conn, [valid_entity()])
    lineage.retire_row(conn, "entities", 1, "wrong cut")
    result = submits.submit_entities(conn, [valid_entity()])  # same name again
    assert result["accepted"] == 1


def test_fk_lookup_names_the_successor(conn):
    submits.submit_entities(conn, [valid_entity()])
    lineage.supersede_row(conn, "entities", 1, {"description": "v2"}, "r")
    result = submits.submit_crud(conn, [valid_crud(entity_id=1)])
    assert "superseded by entities:2" in result["results"][0]["error"]


def test_full_plan_still_passes_gates_after_a_supersede_storm(conn):
    populate_full_plan(conn)
    lineage.supersede_row(conn, "entities", 1, {"description": "v2"}, "r")
    lineage.supersede_row(conn, "contracts", 1,
                          {"returns": "OrderRef", "provenance": "decided"}, "r")
    lineage.supersede_row(conn, "decisions", 1, {"rationale": "99% self-serve"}, "r")
    for stage in range(1, 7):
        assert gates.GATES[stage](conn) == [], stage


# --- export round-trip carries lineage --------------------------------------------

def test_lineage_survives_export_drop_reimport(conn, tmp_path):
    populate_full_plan(conn)
    lineage.supersede_row(conn, "decisions", 1, {"rationale": "sharper"}, "why not")
    lineage.retire_row(conn, "contracts", 1, "descoped")
    data = render.export_data(conn)
    fresh = db.create_db(tmp_path / "fresh.db")
    render.import_data(fresh, data)
    old = fresh.execute("SELECT * FROM decisions WHERE id = 1").fetchone()
    assert old["superseded_by"] and old["superseded_reason"] == "why not"
    new = fresh.execute(
        "SELECT * FROM decisions WHERE id = ?", (old["superseded_by"],)).fetchone()
    assert new["supersedes"] == 1
    cut = fresh.execute("SELECT * FROM contracts WHERE id = 1").fetchone()
    assert cut["retired"] == 1 and cut["superseded_reason"] == "descoped"
    fresh.close()


# --- dismiss_gap (W6) --------------------------------------------------------------

def test_dismiss_gap_silences_next_gap_but_not_gates(conn):
    make_stage1_pass(conn)
    gates.run_gate(conn, 1)
    make_stage2_pass(conn)
    submits.submit_use_cases(conn, [valid_use_case(
        title="Browse catalogue", steps=[{"text": "Customer scrolls the list"}])])
    gap = next(g for g in gaps.next_gap(conn)["cluster"]
               if g["kind"] == "hole:step_without_extensions")
    out = gaps.dismiss_gap(conn, gap["kind"], gap["table"], gap["row_id"],
                           "user: browsing failure modes are out of scope for v1")
    assert out["dismissed"]["row_id"] == gap["row_id"]
    keys = [(g["kind"], g["row_id"]) for g in gaps.next_gap(conn).get("cluster", [])]
    assert (gap["kind"], gap["row_id"]) not in keys
    assert gates.gate_stage2(conn)  # the gate still sees the hole


def test_dismiss_gap_guards(conn):
    assert "resolve_conflict" in gaps.dismiss_gap(conn, "conflict", "conflicts", 1, "r")["error"]
    assert "reason" in gaps.dismiss_gap(conn, "hole:no_use_cases", "use_cases", None, "")["error"]
    assert "matches none" in gaps.dismiss_gap(
        conn, "hole:no_use_cases", "use_cases", 99, "r")["error"]
