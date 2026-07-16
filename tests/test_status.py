"""plan_status digest + get_rows (Session D, W3) and the gate_results.holes
persistence regression (W4 — the column already existed; keep it working)."""
import json

from engine import db, gates, lineage, status, submits

from conftest import populate_full_plan, valid_entity, valid_requirement


def test_digest_carries_the_cold_resume_essentials(conn):
    populate_full_plan(conn)
    gates.run_gate(conn, 1)
    submits.file_question(conn, "who owns retries?", owner="Al")
    submits.file_conflict(conn, "req 1 vs decision 2", refs=["requirements:1"])
    d = status.digest(conn)
    assert d["plan"]["current_stage"] == 2
    assert d["counts"]["use_cases"] == 1
    assert d["gates"][0]["stage"] == 1 and d["gates"][0]["passed"] is True
    assert d["open_questions"][0]["text"] == "who owns retries?"
    assert d["open_conflicts"][0]["id"] == 1
    assert d["open_gap_total"] >= 1
    # All fixture rows share one created_at second; just prove the working set
    # is present and well-formed.
    assert d["recent_rows"] and all(":" in r["ref"] and r["label"] for r in d["recent_rows"])
    assert "get_rows" in d["reading"]


def test_digest_stays_small_no_db_dump(conn):
    """F2 acceptance: the digest of a populated plan is well under ~1k tokens
    (~4k chars) — cold resume must never need a full-DB dump."""
    populate_full_plan(conn)
    for stage in range(1, 7):
        gates.run_gate(conn, stage)
    size = len(json.dumps(status.digest(conn), default=str))
    assert size < 4000, size


def test_digest_surfaces_latest_gate_holes(conn):
    gates.run_gate(conn, 1)  # fails: nothing recorded
    d = status.digest(conn)
    run = d["gates"][0]
    assert run["passed"] is False
    assert any("no goals" in h["problem"] for h in run["holes"])


def test_gate_results_holes_persist_per_run(conn):
    """W4 regression (dogfood F6 was wrong — verify the column keeps working):
    each run stores its own row-level holes JSON."""
    gates.run_gate(conn, 4)
    submits.submit_entities(conn, [valid_entity(has_lifecycle=False,
                                                lifecycle_reason="append-only")])
    gates.run_gate(conn, 4)
    rows = conn.execute(
        "SELECT holes FROM gate_results WHERE stage = 4 ORDER BY id").fetchall()
    assert len(rows) == 2
    first, second = (json.loads(r["holes"]) for r in rows)
    assert any(h["problem"] == "no domain entities recorded" for h in first)
    assert any("CRUD cell" in h["problem"] for h in second)


def test_get_rows_by_ids_and_filters(conn):
    populate_full_plan(conn)
    out = status.get_rows(conn, "decisions", ids=[1, 3])
    assert [r["id"] for r in out["rows"]] == [1, 3]
    out = status.get_rows(conn, "requirements", filters={"is_nfr": 0})
    assert out["count"] == 1
    out = status.get_rows(conn, "requirements", filters={"is_nfr": 1})
    assert out["count"] == 0


def test_get_rows_hides_inactive_unless_asked(conn):
    submits.submit_requirements(conn, [valid_requirement()])
    lineage.supersede_row(conn, "requirements", 1,
                          {"system_response": "persist and emit OrderPlaced v2"}, "r")
    assert [r["id"] for r in status.get_rows(conn, "requirements")["rows"]] == [2]
    both = status.get_rows(conn, "requirements", include_inactive=True)["rows"]
    assert [r["id"] for r in both] == [1, 2]
    assert both[0]["superseded_by"] == 2 and both[1]["supersedes"] == 1


def test_get_rows_guards(conn):
    assert "table is one of" in status.get_rows(conn, "sqlite_master")["error"]
    assert "unknown filter column" in status.get_rows(
        conn, "decisions", filters={"drop table": 1})["error"]
    assert "non-empty array of integers" in status.get_rows(
        conn, "decisions", ids=["1"])["error"]


def test_get_rows_truncation_note(conn):
    submits.record_decision(conn, "Goal: a", "decided", rationale="a")
    submits.record_decision(conn, "Goal: b", "decided", rationale="b")
    submits.record_decision(conn, "Goal: c", "decided", rationale="c")
    out = status.get_rows(conn, "decisions", limit=2)
    assert out["truncated"] is True and out["count"] == 2


def test_table_counts_count_active_claim_rows_only(conn):
    submits.submit_entities(conn, [valid_entity()])
    lineage.retire_row(conn, "entities", 1, "wrong cut")
    assert db.table_counts(conn)["entities"] == 0
