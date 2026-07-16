"""Engine-side conflict detection: the n/a-CRUD-vs-use-case-step sweep, its
dedupe guarantee, and its automatic hookup to the submit surface."""
import json

from engine import conflicts, submits

from conftest import valid_crud, valid_entity, valid_use_case


DELETE_STEP_UC = valid_use_case(
    title="Cancel an order", steps=[
        {"text": "Customer deletes the order from their history",
         "no_extension_reason": "soft delete; nothing downstream can fail"}])

NA_DELETE_CELL = valid_crud(
    op="D", actor=None, na=True, na_reason="orders are immutable audit records")


def test_sweep_files_conflict_for_contradicted_na_cell(conn):
    submits.submit_entities(conn, [valid_entity()])
    submits.submit_use_cases(conn, [DELETE_STEP_UC])
    submits.submit_crud(conn, [NA_DELETE_CELL])

    row = conn.execute("SELECT * FROM conflicts").fetchone()
    assert row is not None and row["source"] == "engine" and row["state"] == "open"
    assert json.loads(row["refs"]) == ["crud_grid:1", "uc_steps:1"]
    assert "immutable audit records" in row["description"]
    assert "appears to delete" in row["description"]


def test_sweep_is_idempotent(conn):
    test_sweep_files_conflict_for_contradicted_na_cell(conn)
    assert conflicts.sweep_crud_contradictions(conn) == []
    assert conn.execute("SELECT count(*) FROM conflicts").fetchone()[0] == 1


def test_engine_dedupe_survives_resolution(conn):
    test_sweep_files_conflict_for_contradicted_na_cell(conn)
    submits.resolve_conflict(conn, 1, "user: the n/a cell was wrong; D is CustomerPortal")
    assert conflicts.sweep_crud_contradictions(conn) == []


def test_sweep_needs_entity_and_op_verb_together(conn):
    submits.submit_entities(conn, [valid_entity()])
    submits.submit_use_cases(conn, [valid_use_case(
        title="Browse orders", steps=[
            {"text": "Customer deletes an old saved filter",  # delete-verb, no entity
             "no_extension_reason": "local preference only"},
            {"text": "Customer views the order",              # entity, no delete-verb
             "no_extension_reason": "read only"}])])
    submits.submit_crud(conn, [NA_DELETE_CELL])
    assert conn.execute("SELECT count(*) FROM conflicts").fetchone()[0] == 0


def test_submit_crud_surfaces_filed_conflicts(conn):
    submits.submit_entities(conn, [valid_entity()])
    submits.submit_use_cases(conn, [DELETE_STEP_UC])
    result = submits.submit_crud(conn, [NA_DELETE_CELL])
    assert result["conflicts_filed"][0]["refs"] == ["crud_grid:1", "uc_steps:1"]
    assert "next_gap" in result["guidance"]


def test_submit_use_cases_surfaces_filed_conflicts(conn):
    submits.submit_entities(conn, [valid_entity()])
    submits.submit_crud(conn, [NA_DELETE_CELL])
    result = submits.submit_use_cases(conn, [DELETE_STEP_UC])
    assert result["conflicts_filed"][0]["refs"] == ["crud_grid:1", "uc_steps:1"]


def test_dedupe_is_engine_only_model_can_still_file_same_refs(conn):
    test_sweep_files_conflict_for_contradicted_na_cell(conn)
    out = submits.file_conflict(conn, "the na_reason also contradicts requirement 1",
                                ["crud_grid:1", "uc_steps:1"])
    assert "error" not in out
    sources = [r["source"] for r in conn.execute("SELECT source FROM conflicts ORDER BY id")]
    assert sources == ["engine", "model"]
