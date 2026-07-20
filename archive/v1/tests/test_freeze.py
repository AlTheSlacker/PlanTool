"""Session E done-when, part 1: freeze_plan is allowed only when all gates
pass, bumps the version, and actually freezes — every write surface refuses
afterwards while status, reads, packs, gates, and exports keep working.
"""
from engine import db, findings, gaps, gates, lineage, render, spikes, status, submits

from conftest import populate_freezable_plan, valid_requirement


def frozen_plan(conn):
    populate_freezable_plan(conn)
    result = gates.freeze_plan(conn)
    assert result.get("state") == "frozen", result
    return result


def test_freeze_refused_while_gates_fail(conn):
    result = gates.freeze_plan(conn)
    assert "only when all gates pass" in result["error"]
    assert result["holes"]
    plan = db.get_plan(conn)
    assert plan["state"] == "open" and plan["version"] == 1
    # The refusal itself is a recorded gate-8 run.
    row = conn.execute("SELECT stage, passed FROM gate_results ORDER BY id DESC").fetchone()
    assert (row["stage"], row["passed"]) == (8, 0)


def test_freeze_bumps_version_and_records_the_pass(conn):
    result = frozen_plan(conn)
    assert result["version"] == 2
    plan = db.get_plan(conn)
    assert plan["state"] == "frozen" and plan["version"] == 2
    assert plan["current_stage"] == 8
    row = conn.execute("SELECT stage, passed FROM gate_results ORDER BY id DESC").fetchone()
    assert (row["stage"], row["passed"]) == (8, 1)


def test_second_freeze_refused(conn):
    frozen_plan(conn)
    assert "already frozen" in gates.freeze_plan(conn)["error"]


def test_frozen_plan_rejects_every_write_surface(conn, tmp_path):
    frozen_plan(conn)
    attempts = {
        "submit": submits.submit_requirements(conn, [valid_requirement()]),
        "decision": submits.record_decision(conn, "late idea", "decided"),
        "question": submits.file_question(conn, "too late?"),
        "resolve_question": submits.resolve_question(conn, 1, "answer"),
        "conflict": submits.file_conflict(conn, "late conflict", ["use_cases:1"]),
        "resolve_conflict": submits.resolve_conflict(conn, 1, "resolution"),
        "supersede": lineage.supersede_row(
            conn, "requirements", 1, {"system_response": "changed"}, "late edit"),
        "retire": lineage.retire_row(conn, "requirements", 1, "late cut"),
        "confirm": lineage.confirm_assumption(conn, "requirements", 1, "user said yes"),
        "spike": spikes.register_spike(
            conn, tmp_path / "spikes", "q?", "h", "real probe", "1h"),
        "spike_result": spikes.record_spike_result(conn, 1, "confirmed", "saw it"),
        "dismiss": gaps.dismiss_gap(conn, "hole:awaiting_freeze", "plans", None, "done"),
        "finding": findings.file_finding(conn, "redteam", "late finding"),
        "disposition": findings.disposition_finding(conn, 1, "accepted", "fine"),
    }
    for surface, result in attempts.items():
        assert "frozen" in result.get("error", ""), (surface, result)
    # Nothing landed.
    assert conn.execute(
        "SELECT count(*) FROM requirements WHERE superseded_by IS NOT NULL "
        "OR retired = 1").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM open_questions").fetchone()[0] == 0


def test_frozen_plan_reads_still_work(conn, tmp_path):
    frozen_plan(conn)
    gap = gaps.next_gap(conn)
    assert gap["status"] == "frozen" and "read-only" in gap["message"]
    digest = status.digest(conn)
    assert digest["plan"]["state"] == "frozen"
    assert status.get_rows(conn, "contracts")["count"] == 1
    assert gates.run_gate(conn, 6)["passed"] is True
    assert "place_order" in render.plan_pack(conn, "full")["markdown"]
    out = render.export_plan(conn, tmp_path)
    assert (tmp_path / "plan.md").exists() and (tmp_path / "plan.yaml").exists()
    assert out["plan_yaml"]["rows"]["plans"] == 1
