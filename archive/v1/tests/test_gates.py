"""Gates 1-8, both directions: a fixture that fails with the specific hole,
and a fixture that passes. Fail fixtures go through the submit surface where
write-time validation permits the hole; where it doesn't, they use direct
inserts — exactly the plan.yaml-reimport path the gates exist to re-check.
"""
import json

from engine import db, findings, gates, submits

from conftest import (FULL_MACHINE_CELLS, make_stage1_pass, make_stage2_pass,
                      make_stage3_pass, make_stage4_pass, make_stage5_pass,
                      make_stage6_pass, make_stage7_pass, populate_freezable_plan,
                      populate_full_plan, valid_contract,
                      valid_component, valid_crud, valid_dependency, valid_entity,
                      valid_machine, valid_requirement, valid_use_case)


def holes_for(result_or_holes, table=None):
    holes = result_or_holes["holes"] if isinstance(result_or_holes, dict) else result_or_holes
    return [h for h in holes if table is None or h["table"] == table]


def _envelope(conn):
    plan = db.get_plan(conn)
    return {"plan_id": plan["id"], "plan_version_added": plan["version"]}


# --- stage 1 -----------------------------------------------------------------

def test_gate1_empty_plan_fails_with_all_three_holes(conn):
    problems = " | ".join(h["problem"] for h in gates.gate_stage1(conn))
    assert "no goals" in problems
    assert "no non-goals" in problems
    assert "target stack" in problems


def test_gate1_goal_without_success_criterion_fails(conn):
    make_stage1_pass(conn)
    submits.record_decision(conn, "Goal: be vaguely better", "decided")
    holes = gates.gate_stage1(conn)
    assert len(holes) == 1
    assert "success criterion" in holes[0]["problem"]
    assert holes[0]["row_id"] is not None


def test_gate1_passes(conn):
    make_stage1_pass(conn)
    assert gates.gate_stage1(conn) == []


# --- stage 2 -----------------------------------------------------------------

def test_gate2_no_use_cases_fails(conn):
    assert holes_for(gates.gate_stage2(conn), "use_cases")


def test_gate2_bare_step_fails_and_names_it(conn):
    submits.submit_use_cases(conn, [valid_use_case(steps=[
        {"text": "Customer submits the completed order form"}])])
    holes = holes_for(gates.gate_stage2(conn), "uc_steps")
    assert len(holes) == 1
    assert "no extensions and no no_extension_reason" in holes[0]["problem"]


def test_gate2_passes(conn):
    make_stage2_pass(conn)
    assert gates.gate_stage2(conn) == []


# --- stage 3 -----------------------------------------------------------------

def test_gate3_no_requirements_fails(conn):
    assert holes_for(gates.gate_stage3(conn), "requirements")


def test_gate3_slot_hole_on_reimported_row_fails(conn):
    # An event requirement without its trigger can only arrive via reimport —
    # write-time validation rejects it; the gate must re-check in SQL.
    db.insert_row(conn, "requirements", {
        **_envelope(conn), "ears_type": "event",
        "system_response": "do the thing", "provenance": "decided"})
    conn.commit()
    holes = holes_for(gates.gate_stage3(conn), "requirements")
    assert any("does not satisfy its ears_type 'event'" in h["problem"] for h in holes)


def test_gate3_unquantified_nfr_fails(conn):
    db.insert_row(conn, "requirements", {
        **_envelope(conn), "ears_type": "ubiquitous",
        "system_response": "be fast", "is_nfr": 1, "provenance": "decided"})
    conn.commit()
    holes = holes_for(gates.gate_stage3(conn), "requirements")
    assert any("Planguage triad" in h["problem"] for h in holes)


def test_gate3_untraced_use_case_fails(conn):
    make_stage2_pass(conn)
    submits.submit_requirements(conn, [valid_requirement()])  # no links
    holes = holes_for(gates.gate_stage3(conn), "use_cases")
    assert len(holes) == 1
    assert "traces to no requirement" in holes[0]["problem"]


def test_gate3_passes(conn):
    make_stage2_pass(conn)
    make_stage3_pass(conn)
    assert gates.gate_stage3(conn) == []


# --- stage 4 -----------------------------------------------------------------

def test_gate4_no_entities_fails(conn):
    assert holes_for(gates.gate_stage4(conn), "entities")


def test_gate4_missing_crud_cells_fail(conn):
    submits.submit_entities(conn, [valid_entity()])
    submits.submit_crud(conn, [valid_crud(op="C")])
    holes = holes_for(gates.gate_stage4(conn), "crud_grid")
    assert len(holes) == 1
    assert "['R', 'U', 'D']" in holes[0]["problem"]


def test_gate4_blank_lifecycle_reason_fails(conn):
    # The schema CHECK forces *a* reason on has_lifecycle=0; a whitespace one
    # (reimport artifact) must still be caught.
    db.insert_row(conn, "entities", {
        **_envelope(conn), "name": "AuditLine", "has_lifecycle": 0,
        "lifecycle_reason": "   ", "provenance": "decided"})
    conn.commit()
    submits.submit_crud(conn, [valid_crud(op=op) for op in "CRUD"])
    holes = holes_for(gates.gate_stage4(conn), "entities")
    assert any("without a recorded justification" in h["problem"] for h in holes)


def test_gate4_lifecycle_entity_without_machine_fails(conn):
    submits.submit_entities(conn, [valid_entity()])
    submits.submit_crud(conn, [valid_crud(op=op) for op in "CRUD"])
    assert holes_for(gates.gate_stage4(conn), "state_machines")


def test_gate4_undefined_state_cells_fail(conn):
    submits.submit_entities(conn, [valid_entity()])
    submits.submit_crud(conn, [valid_crud(op=op) for op in "CRUD"])
    submits.submit_states(conn, [valid_machine(cells=FULL_MACHINE_CELLS[:1])])
    holes = holes_for(gates.gate_stage4(conn), "sm_cells")
    assert len(holes) == 1
    assert "3 undefined state x event cell(s)" in holes[0]["problem"]


def test_gate4_passes(conn):
    make_stage4_pass(conn)
    assert gates.gate_stage4(conn) == []


# --- stage 5 -----------------------------------------------------------------

def test_gate5_nothing_recorded_fails(conn):
    holes = gates.gate_stage5(conn)
    assert len(holes) == 1
    assert "no external dependencies" in holes[0]["problem"]


def test_gate5_missing_failure_modes_fail(conn):
    submits.submit_dependencies(conn, [valid_dependency()])
    submits.submit_dep_failure_modes(conn, [
        {"dep_id": 1, "mode": "unavailable", "handling": "queue and retry",
         "provenance": "decided"}])
    holes = holes_for(gates.gate_stage5(conn), "dep_failure_modes")
    assert len(holes) == 1
    assert "'slow', 'malformed', 'auth', 'partial'" in holes[0]["problem"]


def test_gate5_passes_with_dependency(conn):
    make_stage5_pass(conn)
    assert gates.gate_stage5(conn) == []


def test_gate5_passes_with_explicit_no_deps_decision(conn):
    submits.record_decision(
        conn, "The system has no external dependencies", "decided",
        rationale="pure in-process library; the filesystem is the caller's")
    assert gates.gate_stage5(conn) == []


# --- stage 6 -----------------------------------------------------------------

def test_gate6_no_components_fails(conn):
    assert holes_for(gates.gate_stage6(conn), "components")


def test_gate6_component_without_contract_fails(conn):
    submits.submit_components(conn, [valid_component()])
    holes = holes_for(gates.gate_stage6(conn), "components")
    assert any("has no contract" in h["problem"] for h in holes)


def test_gate6_structurally_incomplete_reimported_contract_fails(conn):
    submits.submit_components(conn, [valid_component()])
    db.insert_row(conn, "contracts", {
        **_envelope(conn), "component_id": 1, "name": "mystery", "kind": "function",
        "provenance": "decided"})  # no params/returns/errors — reimport artifact
    conn.commit()
    holes = holes_for(gates.gate_stage6(conn), "contracts")
    assert any("structurally incomplete" in h["problem"] for h in holes)


def test_gate6_contract_without_consumer_fails(conn):
    make_stage3_pass(conn)
    submits.submit_components(conn, [valid_component()])
    submits.submit_contracts(conn, [valid_contract(links=["requirements:1"])])
    holes = holes_for(gates.gate_stage6(conn), "contracts")
    assert len(holes) == 1
    assert "no consumer" in holes[0]["problem"]


def test_gate6_unspiked_world_assumed_contract_fails(conn):
    make_stage3_pass(conn)
    submits.submit_components(conn, [valid_component()])
    submits.submit_contracts(conn, [valid_contract(
        links=["requirements:1"], is_external=True,
        provenance="assumed", assumption_kind="world")])
    holes = holes_for(gates.gate_stage6(conn), "contracts")
    assert len(holes) == 1
    assert "unverified world-assumption" in holes[0]["problem"]


def test_gate6_accepted_risk_decision_clears_world_assumption(conn):
    test_gate6_unspiked_world_assumed_contract_fails(conn)
    submits.record_decision(
        conn, "Accept the risk that the vendor schema matches the docs", "decided",
        rationale="user accepted after seeing the spike cost", links=["contracts:1"],
        alternatives=[{"alternative": "spike it now",
                       "rejected_because": "vendor sandbox access takes weeks"}])
    assert gates.gate_stage6(conn) == []


def test_gate6_untraced_requirement_fails(conn):
    make_stage3_pass(conn)
    submits.submit_components(conn, [valid_component()])
    submits.submit_contracts(conn, [valid_contract(is_external=True)])  # no links
    problems = " | ".join(h["problem"] for h in gates.gate_stage6(conn))
    assert "traces to no contract" in problems           # the requirement's hole
    assert "traces to no requirement" in problems        # the contract's hole


def test_gate6_deferral_decision_clears_untraced_requirement(conn):
    make_stage3_pass(conn)
    submits.submit_components(conn, [valid_component()])
    submits.submit_contracts(conn, [valid_contract(
        links=["requirements:1"], is_external=True)])
    submits.submit_requirements(conn, [valid_requirement(
        trigger="the user requests an export", links=["use_cases:1"])])
    assert holes_for(gates.gate_stage6(conn), "requirements")
    submits.record_decision(
        conn, "Defer export to phase 2", "decided",
        rationale="user chose to descope", links=["requirements:2"])
    assert gates.gate_stage6(conn) == []


def test_gate6_passes(conn):
    make_stage3_pass(conn)
    make_stage6_pass(conn)
    assert gates.gate_stage6(conn) == []


# --- stage 7 -----------------------------------------------------------------

def test_gate7_no_findings_fails(conn):
    # A stage-7 gate that passes on an empty findings table passes vacuously —
    # a red team that finds nothing means the script is broken (spec section 11).
    holes = gates.gate_stage7(conn)
    assert len(holes) == 1
    assert "no adversarial findings" in holes[0]["problem"]


def test_gate7_undispositioned_finding_fails(conn):
    findings.file_finding(conn, "premortem", "cold resume was never exercised")
    holes = gates.gate_stage7(conn)
    assert len(holes) == 1
    assert "undispositioned" in holes[0]["problem"]
    assert holes[0]["row_id"] == 1


def test_gate7_blank_disposition_rationale_fails(conn):
    # A disposition without rationale can only arrive via reimport — the write
    # surface requires it; the gate must re-check.
    plan = db.get_plan(conn)
    db.insert_row(conn, "findings", {
        "plan_id": plan["id"], "plan_version_added": plan["version"],
        "source": "redteam", "text": "x", "disposition": "fixed"})
    conn.commit()
    holes = gates.gate_stage7(conn)
    assert any("no rationale" in h["problem"] for h in holes)


def test_gate7_passes(conn):
    make_stage5_pass(conn)  # the finding links dependencies:1
    make_stage7_pass(conn)
    assert gates.gate_stage7(conn) == []


# --- stage 8 -----------------------------------------------------------------

def test_gate8_reports_every_failing_stage_gate(conn):
    problems = " | ".join(h["problem"] for h in gates.gate_stage8(conn))
    for stage in range(1, 8):
        assert f"stage-{stage} gate" in problems


def test_gate8_open_conflict_blocks(conn):
    populate_freezable_plan(conn)
    submits.file_conflict(conn, "step 2 contradicts the immutability decision",
                          ["use_cases:1"])
    holes = holes_for(gates.gate_stage8(conn), "conflicts")
    assert len(holes) == 1 and "still open" in holes[0]["problem"]


def test_gate8_lossy_roundtrip_blocks(conn, tmp_path, monkeypatch):
    # Simulate schema churn: the reimport target lacks a column the export
    # carries, so the round-trip drops data — gate 8 must refuse to freeze on it.
    populate_freezable_plan(conn)
    churned = db.SCHEMA_PATH.read_text(encoding="utf-8").replace(
        "    planguage_target   TEXT,\n", "")
    schema = tmp_path / "churned_schema.sql"
    schema.write_text(churned, encoding="utf-8")
    monkeypatch.setattr(db, "SCHEMA_PATH", schema)
    problems = " | ".join(h["problem"] for h in gates.gate_stage8(conn))
    assert "round-trip is not lossless" in problems
    assert "planguage_target" in problems


def test_gate8_passes(conn):
    populate_freezable_plan(conn)
    assert gates.gate_stage8(conn) == []


# --- run_gate ----------------------------------------------------------------

def test_run_gate_rejects_bad_stage(conn):
    for stage in (0, 9, "3", True, None):
        assert "integer 1-8" in gates.run_gate(conn, stage)["error"]


def test_run_gate_records_result_and_reports_holes(conn):
    result = gates.run_gate(conn, 1)
    assert result["passed"] is False and result["holes"]
    row = conn.execute("SELECT * FROM gate_results").fetchone()
    assert (row["stage"], row["passed"]) == (1, 0)
    assert json.loads(row["holes"]) == result["holes"]


def test_run_gate_fail_does_not_advance(conn):
    gates.run_gate(conn, 1)
    assert db.get_plan(conn)["current_stage"] == 1


def test_run_gate_pass_at_current_stage_advances(conn):
    make_stage1_pass(conn)
    result = gates.run_gate(conn, 1)
    assert result["passed"] is True
    assert result["advanced_to"] == 2 == result["current_stage"]
    assert db.get_plan(conn)["current_stage"] == 2


def test_run_gate_pass_at_other_stage_does_not_advance(conn):
    make_stage1_pass(conn)
    gates.run_gate(conn, 1)  # now at stage 2
    rerun = gates.run_gate(conn, 1)
    assert rerun["passed"] is True and "advanced_to" not in rerun
    assert db.get_plan(conn)["current_stage"] == 2


def test_full_plan_advances_through_all_six_gates(conn):
    populate_full_plan(conn)
    for stage in range(1, 7):
        result = gates.run_gate(conn, stage)
        assert result["passed"] is True, (stage, result["holes"])
        assert result["advanced_to"] == stage + 1
    assert db.get_plan(conn)["current_stage"] == 7


def test_full_plan_advances_through_all_eight_gates(conn):
    populate_freezable_plan(conn)
    for stage in range(1, 8):
        result = gates.run_gate(conn, stage)
        assert result["passed"] is True, (stage, result["holes"])
        assert result["advanced_to"] == stage + 1
    final = gates.run_gate(conn, 8)
    assert final["passed"] is True and "advanced_to" not in final
    assert "freeze_plan" in final["next"]
    assert db.get_plan(conn)["current_stage"] == 8
