"""session-service (components:14) — contracts:48, contracts:49, contracts:64.

Tests assert on what a resuming planner can *see*, not on the columns the write set. That
distinction is F22's lesson: a test written alongside the code inherits the implementation's
blind spot, and the way out is to ask what the next reader actually receives.
"""

from __future__ import annotations

import json

import pytest

from engine.clock import now
from engine.conflicts import ConflictService
from engine.fingerprint import capture, compare
from engine.gaps import GapEngine
from engine.gates import GateEngine
from engine.guidance import Guidance
from engine.idempotency import key
from engine.models import RowSubmission
from engine.resume import Fetch, NoPlanFound, PlanCorrupt, ResumeService
from engine.rows import RowService
from engine.storage import Op, Storage
from engine.warnings import WarningService


@pytest.fixture
def services(tmp_path):
    storage = Storage(tmp_path)
    storage.init_plan("resume test", "standard")
    rows = RowService(storage)
    warnings = WarningService(storage)
    gaps = GapEngine(storage, rows)
    conflicts = ConflictService(storage, rows)
    gates = GateEngine(storage, rows, conflicts, warnings, gaps)
    resume = ResumeService(storage, gaps, warnings, Guidance())
    return storage, gates, resume


# --- contracts:48 journal_note ---


def test_a_note_is_readable_the_moment_it_is_written(services):
    """requirements:56/60 — durable at the moment the entry completes, never batched."""
    _, _, resume = services
    resume.journal_note("coupling, not size")
    assert [n.note for n in resume.journal()] == ["coupling, not size"]


def test_the_same_note_twice_is_one_note(services):
    """The key names the act, not the attempt (DEFECTS.md F29).

    The first version of `journal_note` keyed on how many notes already existed, so every
    call was a new operation and a retry duplicated silently. This test fails against that.
    """
    _, _, resume = services
    first = resume.journal_note("the same learning")
    again = resume.journal_note("the same learning")
    assert first.id == again.id
    assert len(resume.journal()) == 1


def test_a_note_against_a_different_task_is_a_different_note(services):
    _, _, resume = services
    a = resume.journal_note("same words", task="contracts:1")
    b = resume.journal_note("same words", task="contracts:2")
    assert a.id != b.id
    assert len(resume.journal()) == 2


def test_an_empty_note_records_nothing(services):
    _, _, resume = services
    with pytest.raises(Exception):
        resume.journal_note("   ")
    assert resume.journal() == []


# --- contracts:49 set_next_action ---


def test_the_recorded_intent_becomes_the_digest_next_action(services):
    _, _, resume = services
    resume.set_next_action("ask about the two missing use cases")
    status = resume.plan_status()
    assert status.next_action == "ask about the two missing use cases"
    assert status.next_action_source == "recorded"


def test_checkpoints_are_append_only(services):
    """Successive intents are the only evidence of a plan going round in circles."""
    _, _, resume = services
    resume.set_next_action("first intent")
    resume.set_next_action("second intent")
    assert [c.intent for c in resume.checkpoints()] == ["first intent", "second intent"]
    assert resume.plan_status().next_action == "second intent"


def test_without_an_intent_the_digest_still_names_a_next_step(services):
    """uc_extensions:48 — absent a recorded action, resume falls back rather than going
    silent. An honest 'nobody said' must still end in an instruction, or the next planner
    invents one."""
    _, _, resume = services
    status = resume.plan_status()
    assert status.next_action_source == "derived"
    assert "next_gaps()" in status.next_action


# --- contracts:64 plan_status ---


def test_no_plan_is_said_plainly(tmp_path):
    """uc_extensions:5 — so the caller can offer to start one."""
    storage = Storage(tmp_path)
    rows = RowService(storage)
    service = ResumeService(
        storage, GapEngine(storage, rows), WarningService(storage), Guidance()
    )
    with pytest.raises(NoPlanFound):
        service.plan_status()


def test_a_corrupt_plan_never_answers_from_partial_state(services, monkeypatch):
    """requirements:11 — a digest built from half a plan is worse than no digest."""
    storage, _, resume = services

    class Broken:
        unreadable = ["plan_rows:7"]

    monkeypatch.setattr(storage, "integrity_check", lambda: Broken())
    with pytest.raises(PlanCorrupt):
        resume.plan_status()


def test_the_digest_carries_no_document_text(services):
    """DEVIATIONS.md D17 — the mandate and script are named, never included."""
    storage, _, resume = services
    status = resume.plan_status()
    mandate = Guidance().get_mandate()
    rendered = status.present()
    assert mandate not in rendered
    assert "get_mandate()" in rendered
    assert f"get_package_script({status.package})" in rendered


def test_every_count_names_the_call_that_fetches_it(services):
    """D17's other half. A bare number invites a reader to reason about it instead of
    reading what it stands for."""
    _, _, resume = services
    status = resume.plan_status()
    counts = [
        f for f in (status.gaps, status.earlier_journal, status.earlier_gate_runs)
    ]
    for fetch in counts:
        assert isinstance(fetch, Fetch)
        assert fetch.call.endswith(")"), fetch
        assert fetch.call in fetch.present()


def test_the_digest_marks_quoted_prose_verbatim_and_composed_lines_plain(services):
    """DEFECTS.md F49 — provenance by type through the digest. A journal note is the
    planner's own words, so its line is `Verbatim` (the door annotates any address in it
    rather than failing the call); the tool's own composed lines stay plain and strictly
    scanned. Before F49 `present()` was one flat string that erased the distinction, so an
    address the owner wrote crashed the resume call."""
    from engine.door import Verbatim

    _, _, resume = services
    resume.journal_note("reuse the resolver in contracts:12")
    segments = resume.plan_status().present_lines()

    journal_line = next(p for p in segments if "contracts:12" in p)
    assert isinstance(journal_line, Verbatim), "owner prose must be exempt"
    plan_line = next(p for p in segments if p.startswith("Plan '"))
    assert not isinstance(plan_line, Verbatim), "the tool's own line must stay strict"
    # present() still joins to the same readable string a human or plain caller reads.
    assert "contracts:12" in resume.plan_status().present()


def test_the_gap_count_matches_what_its_named_call_returns(services):
    """DEFECTS.md F47 — the count must equal what the call it names actually serves, not
    just name a call. plan_status counted every package's gaps and labelled it next_gaps(),
    which reports only the current package: on this part-built plan the digest headlined a
    number the reader could not reach by following the pointer.

    F47's own root is F22's: the pre-existing pairing test asserted a call was *named*, never
    that the number matched it. This asserts the observable consequence."""
    storage, _, resume = services
    # A row in package 4 (entities) so the current package is 1 but later packages carry
    # their own not-started gaps: all-package and current-package counts genuinely differ.
    rows = RowService(storage)
    rows.submit_rows(
        [RowSubmission("entities", {"title": "Widget"}, name="Widget")], "k"
    )
    status = resume.plan_status()
    assert status.package == 1
    assert status.gaps.count == resume.gaps.next_gaps().total_open
    # And it is genuinely the scoped number, not an accident of an empty later plan.
    assert status.gaps.count < len(resume.gaps.open_gaps())


def test_the_digest_ends_by_naming_the_next_action(services):
    _, _, resume = services
    assert resume.plan_status().present().splitlines()[-1].startswith("Next action")


def test_the_journal_in_the_digest_is_bounded_to_the_current_package(services):
    """requirements:62 — resume cost scales with the working set, not the whole plan.

    The older notes do not vanish; they become a count and the call that reads them.
    """
    storage, _, resume = services
    resume.journal_note("belongs to an earlier package")
    storage.conn.execute("UPDATE journal_notes SET package = 0")
    storage.conn.commit()
    resume.journal_note("belongs to the current package")

    status = resume.plan_status()
    assert [n.note for n in status.journal] == ["belongs to the current package"]
    assert status.earlier_journal.count == 1
    assert "journal()" in status.earlier_journal.present()
    assert len(resume.journal()) == 2


# --- gate history (DEFECTS.md F30) ---


def test_a_gate_run_survives_the_call_that_produced_it(services):
    """requirements:10 and uc_steps:5 both promise gate history on resume; nothing stored
    one until M6. The verdict was computed, returned and forgotten."""
    _, gates, resume = services
    result = gates.run_gate(1)
    history = resume.gate_runs()
    assert len(history) == 1
    assert history[0].package == 1
    assert history[0].passed is result.passed
    assert history[0].hole_count == len(result.holes)


def test_re_running_a_gate_records_a_second_verdict(services):
    """History that collapsed re-runs would show a package passing without ever showing
    that it failed first."""
    _, gates, resume = services
    gates.run_gate(1)
    gates.run_gate(1)
    assert len(resume.gate_runs()) == 2


def test_the_digest_shows_the_latest_verdict_per_package_and_counts_the_rest(services):
    _, gates, resume = services
    gates.run_gate(1)
    gates.run_gate(1)
    gates.run_gate(2)
    status = resume.plan_status()
    assert [g.package for g in status.gate_history] == [1, 2]
    assert status.earlier_gate_runs.count == 1


# --- drift (requirements:59 / requirements:73) ---


def test_no_baseline_is_reported_as_absent_not_as_no_drift(services):
    """The whole planning phase runs before any fingerprint exists. An empty flag list
    there is a check that ran, found nothing and meant nothing — F14's shape."""
    _, _, resume = services
    drift = resume.plan_status().drift
    assert drift.state == "no_baseline"
    assert "no baseline yet" in drift.present()
    assert drift.flags == ()


def test_a_moved_workspace_is_flagged_against_its_baseline(services):
    storage, _, resume = services
    baseline = capture(storage)
    baseline["workspace"] = "D:/somewhere/else"
    _store_baseline(storage, baseline)

    drift = resume.plan_status().drift
    assert drift.state == "drifted"
    assert [f.field for f in drift.flags] == ["workspace"]
    assert "D:/somewhere/else" in drift.present()


def test_an_unchanged_workspace_reports_unchanged(services):
    storage, _, resume = services
    _store_baseline(storage, capture(storage))
    drift = resume.plan_status().drift
    assert drift.state == "unchanged"
    assert drift.flags == ()


def test_a_field_the_baseline_never_carried_is_not_drift(services):
    """Otherwise every old baseline looks drifted the moment a new field is added, which
    trains a reader to ignore the flags."""
    storage, _, resume = services
    baseline = capture(storage)
    del baseline["journal_mode"]
    _store_baseline(storage, baseline)
    assert resume.plan_status().drift.state == "unchanged"


def test_capture_and_compare_agree_on_the_field_list(services):
    """One owner for what the workspace *is*. If capture grows a field that compare cannot
    see, the baseline records a fact nobody checks and drift reports clean."""
    storage, _, _ = services
    current = capture(storage)
    moved = {**current, "backend": "postgres"}
    assert [f.field for f in compare(moved, current)] == ["backend"]


# --- requirements:69 ---


def test_a_network_workspace_is_warned_about_durability(services, monkeypatch):
    """Lexical detection only: the tool never touches the network to decide whether to
    warn about the network."""
    storage, _, resume = services
    # A string, never a connection. Pointing the test at a real share would be both slow
    # and a network write, which this project does not do (no-network-experiments).
    monkeypatch.setattr(storage, "workspace", r"\\DISKSTATION\plans\x")
    advisories = resume.plan_status().advisories
    assert advisories and "network mount" in advisories[0]


def test_a_local_workspace_is_not_warned(services):
    _, _, resume = services
    assert resume.plan_status().advisories == ()


def _store_baseline(storage, fingerprint: dict) -> None:
    storage.write_atomic(
        [Op("insert", "workspace_fingerprints", {
            "occasion": "finalization",
            "plan_version": 1,
            "subtask_id": None,
            "fingerprint": json.dumps(fingerprint, sort_keys=True),
            "created_at": now(),
        })],
        key("fingerprint", "test", len(storage.query(
            "SELECT id FROM workspace_fingerprints"
        ))),
    )


# --- the glossary in the digest (D23) ---


def test_a_cold_planner_is_told_the_glossary_exists(services):
    """The chicken and egg the packaging defect taught: a line that appears only once
    there are terms can never be the line that produces the first one."""
    _, _, resume = services
    assert "define_term()" in resume.plan_status().present()


def test_the_digest_counts_the_agreed_terms(services):
    from engine.terms import TermService

    storage, _, resume = services
    TermService(storage).define_term("package", "a declared grouping of tasks")
    digest = resume.plan_status()
    assert digest.glossary.count == 1
    assert "1 agreed term — glossary()" in digest.present()
