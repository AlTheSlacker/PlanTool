"""file_finding / disposition_finding — the stage-7 bookkeeping (spec
section 5): pedagogic rejections, disposition rules, and the spiked-needs-a-
spike link rule."""
import json

from engine import findings, spikes

from conftest import make_stage5_pass


def test_file_and_disposition_happy_path(conn):
    out = findings.file_finding(conn, "redteam", "no idempotency key on submits")
    assert out["id"] == 1 and "disposition_finding" in out["note"]
    out = findings.disposition_finding(
        conn, 1, "accepted", "user accepted: single-writer workspaces for v1")
    assert out == {"id": 1, "disposition": "accepted"}
    row = conn.execute("SELECT * FROM findings").fetchone()
    assert row["disposition"] == "accepted"
    assert "single-writer" in row["disposition_rationale"]


def test_file_finding_rejections_are_pedagogic(conn):
    bad_source = findings.file_finding(conn, "hunch", "x")
    assert "redteam" in bad_source["error"] and "premortem" in bad_source["error"]
    no_text = findings.file_finding(conn, "redteam", "   ")
    assert "states the specific issue" in no_text["error"]
    dangling = findings.file_finding(conn, "redteam", "x", links=["contracts:99"])
    assert "matches nothing" in dangling["error"]
    for result in (bad_source, no_text, dangling):
        assert "Rule:" in result["error"] and "Offending" in result["error"]


def test_disposition_rejections(conn):
    findings.file_finding(conn, "redteam", "finding under test")
    unknown = findings.disposition_finding(conn, 99, "fixed", "r")
    assert "must match a filed finding" in unknown["error"]
    assert "finding under test" in unknown["error"]  # lists the open ones
    bad_disp = findings.disposition_finding(conn, 1, "ignored", "r")
    assert "'fixed'" in bad_disp["error"]
    no_rationale = findings.disposition_finding(conn, 1, "fixed", "  ")
    assert "rationale" in no_rationale["error"]
    findings.disposition_finding(conn, 1, "fixed", "rows corrected")
    again = findings.disposition_finding(conn, 1, "accepted", "changed my mind")
    assert "already dispositioned" in again["error"]


def test_spiked_disposition_requires_a_spike_link(conn, tmp_path):
    make_stage5_pass(conn)
    findings.file_finding(conn, "redteam", "SMB locking is assumed, never probed",
                          links=["dependencies:1"])
    bare = findings.disposition_finding(conn, 1, "spiked", "a spike will settle it")
    assert "links the spike" in bare["error"]
    spikes.register_spike(conn, tmp_path / "spikes", "does SMB honour the lock?",
                          "it does", "probe the real share", "1h")
    out = findings.disposition_finding(conn, 1, "spiked", "spike #1 settles it",
                                       links=["spikes:1"])
    assert out["disposition"] == "spiked"
    # New links merge with the finding's own.
    row = conn.execute("SELECT links FROM findings").fetchone()
    assert json.loads(row["links"]) == ["dependencies:1", "spikes:1"]
