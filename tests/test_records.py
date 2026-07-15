"""Session B done-when, part 2: questions/conflicts bookkeeping and the
code-enforced significance heuristic on record_decision — a decision whose
links touch a component or contract is significant, and an empty-alternatives
significant decision is blocked."""
from engine import gaps, submits

from conftest import valid_component, valid_contract, valid_entity, valid_requirement


# --- open questions -------------------------------------------------------------

def test_question_lifecycle(conn):
    out = submits.file_question(conn, "Which currency rounding rule applies?", owner="user")
    assert out == {"id": 1, "state": "open"}
    q = conn.execute("SELECT * FROM open_questions").fetchone()
    assert q["state"] == "open" and q["owner"] == "user"

    missing = submits.resolve_question(conn, 1, resolution=None)
    assert "records its resolution" in missing["error"] and "defer" in missing["error"]

    resolved = submits.resolve_question(conn, 1, "banker's rounding, per user 2026-07-15")
    assert resolved["state"] == "resolved"
    again = submits.resolve_question(conn, 1, "changed my mind")
    assert "already resolved" in again["error"]


def test_question_defer_and_unknown_id(conn):
    submits.file_question(conn, "Park me")
    deferred = submits.resolve_question(conn, 1, defer=True)
    assert deferred["state"] == "deferred"
    # A deferred question can still be resolved later.
    resolved = submits.resolve_question(conn, 1, "answered at stage 6")
    assert resolved["state"] == "resolved"

    unknown = submits.resolve_question(conn, 99, "x")
    assert "Open questions" in unknown["error"]


def test_question_rejects_empty_text_and_dangling_links(conn):
    assert "non-empty text" in submits.file_question(conn, "  ")["error"]
    out = submits.file_question(conn, "Linked?", links=["requirements:5"])
    assert "match nothing" in out["error"]


# --- conflicts -------------------------------------------------------------------

def test_conflict_lifecycle_and_gap_priority(conn):
    submits.submit_requirements(conn, [valid_requirement()])
    out = submits.file_conflict(
        conn, "Requirement contradicts the recorded retention decision",
        refs=["requirements:1"])
    assert out["id"] == 1 and out["state"] == "open"
    row = conn.execute("SELECT * FROM conflicts").fetchone()
    assert row["source"] == "model"

    # Open conflicts outrank everything in next_gap (priority 1).
    gap = gaps.next_gap(conn)
    assert gap["cluster"][0]["kind"] == "conflict"

    resolved = submits.resolve_conflict(conn, 1, "user kept the requirement; decision revised")
    assert resolved["state"] == "resolved"
    after = gaps.next_gap(conn)
    assert after["status"] == "stage_clear" or all(
        g["kind"] != "conflict" for g in after["cluster"])
    assert "already resolved" in submits.resolve_conflict(conn, 1, "again")["error"]


def test_conflict_requires_existing_refs(conn):
    assert "non-empty array" in submits.file_conflict(conn, "vague unease", refs=[])["error"]
    assert "match nothing" in submits.file_conflict(
        conn, "points at ghosts", refs=["decisions:7"])["error"]
    assert "table:id" in submits.file_conflict(
        conn, "bad shape", refs=["decision 7"])["error"]


# --- record_decision & the significance heuristic --------------------------------

def _link_a_contract(conn):
    submits.submit_components(conn, [valid_component()])
    submits.submit_contracts(conn, [valid_contract()])


def test_heuristic_blocks_empty_alternatives_on_contract_linked_decision(conn):
    _link_a_contract(conn)
    out = submits.record_decision(
        conn, "place_order is synchronous", "decided",
        rationale="user prefers simple flow", links=["contracts:1"])
    assert "significance" in out["error"] and "alternatives" in out["error"]
    assert conn.execute("SELECT count(*) FROM decisions").fetchone()[0] == 0


def test_heuristic_marks_component_and_contract_links_significant(conn):
    _link_a_contract(conn)
    out = submits.record_decision(
        conn, "place_order is synchronous", "decided",
        rationale="user: \"keep it simple until volume demands otherwise\"",
        links=["contracts:1"],
        alternatives=[{"alternative": "async with job queue",
                       "rejected_because": "no volume to justify the moving parts"}])
    assert out == {"id": 1, "significant": True}
    row = conn.execute("SELECT * FROM decisions").fetchone()
    assert row["significant"] == 1
    assert "job queue" in row["alternatives"]

    comp = submits.record_decision(
        conn, "OrderService owns all order writes", "decided", links=["components:1"],
        alternatives=[{"alternative": "shared repository layer",
                       "rejected_because": "splits the invariant across components"}])
    assert comp["significant"] is True


def test_non_architectural_decision_needs_no_alternatives(conn):
    submits.submit_requirements(conn, [valid_requirement()])
    out = submits.record_decision(
        conn, "Target stack is Rust + SQLite", "decided",
        rationale="user's call", links=["requirements:1"])
    assert out == {"id": 1, "significant": False}
    assert conn.execute("SELECT significant FROM decisions").fetchone()[0] == 0


def test_decision_validation_is_pedagogic(conn):
    _link_a_contract(conn)
    assert "non-empty text" in submits.record_decision(conn, " ", "decided")["error"]
    assert "provenance" in submits.record_decision(conn, "x", "chosen")["error"]
    assert "spike" in submits.record_decision(conn, "x", "verified")["error"]
    assert "assumption_kind" in submits.record_decision(conn, "x", "assumed")["error"]
    ok = submits.record_decision(conn, "retry twice then dead-letter", "assumed",
                                 assumption_kind="intent")
    assert ok["significant"] is False

    dangling = submits.record_decision(conn, "x", "decided", links=["contracts:99"])
    assert "match nothing" in dangling["error"]

    bad_alt = submits.record_decision(
        conn, "x", "decided", links=["contracts:1"],
        alternatives=[{"alternative": "other way"}])
    assert "rejected_because" in bad_alt["error"]

    bad_challenge = submits.record_decision(
        conn, "x", "decided",
        challenge={"text": "this couples billing to orders", "outcome": "ignored"})
    assert "overridden" in bad_challenge["error"] and "revised" in bad_challenge["error"]

    good = submits.record_decision(
        conn, "billing stays inside OrderService for v1", "decided",
        rationale="user overrode: \"one deployable for now\"",
        links=["components:1"],
        alternatives=[{"alternative": "separate billing component",
                       "rejected_because": "second deployable the team can't run yet"}],
        challenge={"text": "this couples billing to orders", "outcome": "overridden"})
    assert good["significant"] is True
    row = conn.execute("SELECT challenge FROM decisions WHERE id = ?", (good["id"],)).fetchone()
    assert "overridden" in row["challenge"]
