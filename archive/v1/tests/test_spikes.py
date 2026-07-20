"""Spike tools: registration gatekeeping + quarantine, and the verdict paths —
'verified' is reachable only through a confirmed spike; refuted files conflicts;
inconclusive escalates. Plus the third mechanical conflict detector: resolved
questions whose linked row a spike just changed."""
import json

import pytest

from engine import spikes, submits

from conftest import valid_requirement


@pytest.fixture
def spikes_root(tmp_path):
    return tmp_path / "spikes"


def world_assumed_requirement(**overrides):
    return valid_requirement(provenance="assumed", assumption_kind="world", **overrides)


def register(conn, spikes_root, **overrides):
    args = {"question": "does the vendor API accept batch upserts?",
            "hypothesis": "it accepts arrays of up to 100 records",
            "method": "POST 2 records to the vendor sandbox with real credentials",
            "budget": "2h"}
    args.update(overrides)
    return spikes.register_spike(conn, spikes_root, **args)


# --- register_spike ------------------------------------------------------------

def test_register_requires_all_four_fields(conn, spikes_root):
    for field in ("question", "hypothesis", "method", "budget"):
        out = register(conn, spikes_root, **{field: "  "})
        assert f"requires {field}" in out["error"]
    assert conn.execute("SELECT count(*) FROM spikes").fetchone()[0] == 0


def test_register_creates_numbered_quarantine_dir(conn, spikes_root):
    out = register(conn, spikes_root)
    assert out["id"] == 1
    assert out["quarantine_path"].endswith("001_does_the_vendor_api_accept_batch_upserts")
    assert (spikes_root / "001_does_the_vendor_api_accept_batch_upserts").is_dir()
    assert "REAL dependency" in out["next"]


def test_register_rejects_dangling_links(conn, spikes_root):
    out = register(conn, spikes_root, links=["requirements:99"])
    assert "error" in out


# --- record_spike_result: gatekeeping -------------------------------------------

def test_record_unknown_spike_lists_open_ones(conn, spikes_root):
    register(conn, spikes_root)
    out = spikes.record_spike_result(conn, 99, "confirmed", "saw it work")
    assert "awaiting a result" in out["error"] and "batch upserts" in out["error"]


def test_record_rejects_bad_verdict(conn, spikes_root):
    register(conn, spikes_root)
    out = spikes.record_spike_result(conn, 1, "proven", "saw it work")
    assert "'confirmed', 'refuted', 'inconclusive'" in out["error"].replace('"', "'")


def test_record_requires_evidence_summary(conn, spikes_root):
    register(conn, spikes_root)
    out = spikes.record_spike_result(conn, 1, "confirmed", "  ")
    assert "evidence_summary" in out["error"]


def test_spike_records_only_one_verdict(conn, spikes_root):
    register(conn, spikes_root)
    spikes.record_spike_result(conn, 1, "confirmed", "2-record batch accepted")
    out = spikes.record_spike_result(conn, 1, "refuted", "changed my mind")
    assert "already has verdict 'confirmed'" in out["error"]


# --- confirmed: the only path to 'verified' --------------------------------------

def test_confirmed_upgrades_linked_world_assumption(conn, spikes_root):
    submits.submit_requirements(conn, [world_assumed_requirement()])
    register(conn, spikes_root, links=["requirements:1"])
    out = spikes.record_spike_result(
        conn, 1, "confirmed", "sandbox accepted a 2-record batch, returned both ids",
        evidence_path="spikes/001_batch/probe.py")
    assert out["upgraded_to_verified"] == ["requirements:1"]
    row = conn.execute("SELECT * FROM requirements WHERE id = 1").fetchone()
    assert (row["provenance"], row["spike_id"], row["assumption_kind"]) == ("verified", 1, None)


def test_confirmed_skips_non_world_rows_with_reason(conn, spikes_root):
    submits.submit_requirements(conn, [
        world_assumed_requirement(),
        valid_requirement(provenance="decided",
                          trigger="the nightly export runs",
                          system_response="write the batch file")])
    register(conn, spikes_root, links=["requirements:1", "requirements:2"])
    out = spikes.record_spike_result(conn, 1, "confirmed", "batch accepted")
    assert out["upgraded_to_verified"] == ["requirements:1"]
    assert out["skipped"] == [{"ref": "requirements:2",
                               "reason": "provenance 'decided' — only assumed(world) rows "
                                         "upgrade to verified"}]


def test_confirmed_flags_stale_resolved_questions(conn, spikes_root):
    submits.submit_requirements(conn, [world_assumed_requirement()])
    submits.file_question(conn, "Is the batch limit 100 or 1000?", links=["requirements:1"])
    submits.resolve_question(conn, 1, "user says 100")
    register(conn, spikes_root, links=["requirements:1"])
    out = spikes.record_spike_result(conn, 1, "confirmed", "limit header says 100")
    filed = out["conflicts_filed"]
    assert len(filed) == 1
    assert filed[0]["refs"] == ["open_questions:1", "requirements:1"]
    assert "has since changed" in filed[0]["description"]


# --- refuted and inconclusive -----------------------------------------------------

def test_refuted_files_conflicts_on_linked_assumed_rows(conn, spikes_root):
    submits.submit_requirements(conn, [world_assumed_requirement()])
    register(conn, spikes_root, links=["requirements:1"])
    out = spikes.record_spike_result(
        conn, 1, "refuted", "sandbox 400s on any array payload")
    assert out["conflicts_filed"][0]["refs"] == ["requirements:1", "spikes:1"]
    assert "spike success" in out["note"]
    row = conn.execute("SELECT * FROM requirements WHERE id = 1").fetchone()
    assert row["provenance"] == "assumed"  # never silently corrected


def test_inconclusive_changes_nothing_and_escalates(conn, spikes_root):
    submits.submit_requirements(conn, [world_assumed_requirement()])
    register(conn, spikes_root, links=["requirements:1"])
    out = spikes.record_spike_result(conn, 1, "inconclusive", "budget expired")
    assert "risk decision" in out["note"]
    assert conn.execute("SELECT count(*) FROM conflicts").fetchone()[0] == 0
    assert conn.execute("SELECT provenance FROM requirements").fetchone()[0] == "assumed"
