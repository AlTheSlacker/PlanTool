"""Session A done-when: a killed-and-restarted session re-arms itself from
plan_status() + next_gap() alone — plan state *and* operating protocol."""
from server import main

from conftest import valid_entity, valid_requirement


def test_no_plan_status_still_arms_the_session(workspace):
    out = main.plan_status_impl()
    assert out["status"] == "no_plan"
    assert "plan_start" in out["instruction"]
    assert "own technical rigor" in out["mandate"]


def test_plan_start_returns_mandate_and_stage1_script(workspace):
    out = main.plan_start_impl("toy-plan")
    assert out["status"] == "created"
    assert "Proposal-first" in out["mandate"]
    assert "Non-goals" in out["stage_script"]
    assert "Target stack" in out["stage_script"]


def test_plan_start_refuses_second_plan(workspace):
    main.plan_start_impl("toy-plan")
    out = main.plan_start_impl("another")
    assert "already exists" in out["error"]
    assert "plan_status" in out["error"]


def test_cold_session_rehydrates_from_status_and_gap(workspace):
    # Session 1: create a plan, land some rows, then "die" (impls close per call).
    main.plan_start_impl("toy-plan")
    reqs = main.submit_requirements_impl([
        valid_requirement(),
        valid_requirement(provenance="assumed", assumption_kind="world",
                          system_response="rely on vendor batch upserts"),
    ])
    ents = main.submit_entities_impl([valid_entity()])
    assert reqs["accepted"] == 2 and ents["accepted"] == 1

    # Session 2, cold: plan_status carries state + protocol, next_gap carries work + context.
    status = main.plan_status_impl()
    assert status["status"] == "ok"
    assert status["plan"]["name"] == "toy-plan"
    assert status["counts"]["requirements"] == 2
    assert status["counts"]["entities"] == 1
    assert "own technical rigor" in status["mandate"]      # operating protocol
    assert "Coverage checklist" in status["stage_script"]     # current-stage instructions

    gap = main.next_gap_impl()
    assert gap["status"] == "gaps"
    assert 1 <= len(gap["cluster"]) <= 5
    world = [g for g in gap["cluster"] if g["kind"] == "assumed_world"]
    assert world and world[0]["context"]["row"]["system_response"] == "rely on vendor batch upserts"


def test_full_v1_write_surface_is_registered():
    """Guard against an engine function existing without its MCP tool."""
    import asyncio
    names = {t.name for t in asyncio.run(main.mcp.list_tools())}
    assert names >= {
        "plan_start", "plan_status", "next_gap",
        "submit_use_cases", "submit_uc_extensions", "submit_requirements",
        "submit_entities", "submit_crud", "submit_states", "submit_state_cells",
        "submit_components", "submit_contracts", "submit_contract_deps",
        "submit_dependencies", "submit_dep_failure_modes",
        "file_question", "resolve_question", "file_conflict", "resolve_conflict",
        "record_decision",
    }


def test_singular_tools_no_plan_guard(workspace):
    assert main.file_question_impl("q?")["status"] == "no_plan"
    assert main.record_decision_impl("x", "decided")["status"] == "no_plan"


def test_server_nested_submit_and_decision_roundtrip(workspace):
    """Nested rows and the significance heuristic through the impl layer."""
    from conftest import valid_component, valid_contract, valid_use_case
    main.plan_start_impl("toy-plan")
    ucs = main.submit_use_cases_impl([valid_use_case()])
    assert ucs["accepted"] == 1

    main.submit_components_impl([valid_component()])
    main.submit_contracts_impl([valid_contract()])
    blocked = main.record_decision_impl(
        "contract place_order is synchronous", "decided", links=["contracts:1"])
    assert "significance" in blocked["error"]
    ok = main.record_decision_impl(
        "contract place_order is synchronous", "decided", links=["contracts:1"],
        alternatives=[{"alternative": "async job", "rejected_because": "overkill for v1"}])
    assert ok == {"id": 1, "significant": True}


def test_server_batch_partial_acceptance(workspace):
    main.plan_start_impl("toy-plan")
    out = main.submit_requirements_impl([
        valid_requirement(),
        {"ears_type": "event", "provenance": "decided"},  # missing both slots
    ])
    assert out["accepted"] == 1 and out["rejected"] == 1
    assert "guidance" in out
