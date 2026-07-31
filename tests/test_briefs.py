"""brief-composer (components:12) — contracts:68/41, and the defects they carried.

The split (contracts:40) and its three tests went with the sub-task level in v3 change 1,
and F23's and F25's tests went with them: there is nothing left to divide, so there is no
coverage to check and no original to supersede. F26 stays, because it is about a
denominator that moves, and briefs still freeze one.
"""

import pytest

from engine.briefs import (
    ALLOCATION,
    CLOSURE,
    BriefSelection,
    ClosureUnreadable,
    IncompleteAccounting,
    OmissionNeedsReason,
)
from engine.models import LinkSpec, RowSubmission
from engine.tasks import DONE, IN_PROGRESS

BEHAVIOURS = [
    {"key": "effect", "kind": "effect", "statement": "does the thing"},
    {"key": "NotFound", "kind": "error", "statement": "names the missing id"},
]


def _plan(rows, extra_rows=0, behaviours=BEHAVIOURS):
    """One contract citing `extra_rows` decision rows, so the closure has something in
    it beyond the contract itself."""
    subs = [
        RowSubmission(table="decisions", content={"title": f"decision {i}"}, name=f"decision {i}")
        for i in range(extra_rows)
    ]
    receipt = rows.submit_rows(subs, "decisions") if subs else None
    links = (
        [LinkSpec(target=v.ref) for v in receipt.verdicts] if receipt else []
    )
    rows.submit_rows(
        [RowSubmission(
            table="contracts",
            content={"title": "the contract", "behaviours": behaviours},
            links=links,
         name="the contract")],
        "contract",
    )


def _account_for_all(briefs, task_id, omit_reason="not relevant to this task"):
    """A selection that includes everything. The tool computes the candidate set; the
    caller is the only party that may choose from it (decisions:52/60)."""
    candidates = briefs._candidates(briefs.tasks.get(task_id))
    return BriefSelection(included=tuple(ref for ref, _ in candidates))


# --- contracts:68 compose_brief ---


def test_compose_records_the_selection_and_freezes_the_closure(briefs, tasks, rows):
    _plan(rows, extra_rows=2)
    tasks.finalize_plan()
    tasks.serve_brief(1)

    brief = briefs.compose_brief(1, _account_for_all(briefs, 1))
    assert brief.task_id == 1
    assert brief.serve_epoch == 1
    assert len(brief.rows) == 3          # the contract and its two decisions
    assert len(brief.included) == 3
    assert all(r.origin == CLOSURE for r in brief.rows)


def test_incomplete_accounting_is_rejected(briefs, tasks, rows):
    """decisions:52 — the contract mechanically rejects any composition that fails 100%
    candidate accounting. Omission must be a visible recorded act, never a silent
    deprioritization (requirements:44)."""
    _plan(rows, extra_rows=2)
    tasks.finalize_plan()
    tasks.serve_brief(1)

    with pytest.raises(IncompleteAccounting) as exc:
        briefs.compose_brief(1, BriefSelection(included=("contracts:1",)))
    assert "decisions:1" in str(exc.value)
    assert briefs.live_brief(1) is None


def test_an_omission_without_a_reason_is_refused(briefs, tasks, rows):
    """requirements:79 — omitted candidates are "explicitly waived with a recorded
    reason". A blank reason is accounting theatre."""
    _plan(rows, extra_rows=1)
    tasks.finalize_plan()
    tasks.serve_brief(1)

    with pytest.raises(OmissionNeedsReason):
        briefs.compose_brief(1, BriefSelection(
            included=("contracts:1",), omitted={"decisions:1": "   "}
        ))


def test_waivers_of_decision_rows_are_surfaced_by_name(briefs, tasks, rows):
    """requirements:79 — waivers of decision, requirement and failure-mode rows go to the
    owner in the review summaries, by name rather than as a count."""
    _plan(rows, extra_rows=1)
    tasks.finalize_plan()
    tasks.serve_brief(1)
    briefs.compose_brief(1, BriefSelection(
        included=("contracts:1",),
        omitted={"decisions:1": "superseded by the architecture rewrite"},
    ))

    waived = briefs.waivers()
    assert len(waived) == 1
    assert "decisions:1" in waived[0]
    assert "architecture rewrite" in waived[0]


def test_regeneration_supersedes_and_the_old_brief_stays_frozen(briefs, tasks, rows):
    """entities:13 — no lifecycle; regeneration creates a new brief that supersedes the
    old by reference, and the old stays frozen for defect forensics."""
    _plan(rows, extra_rows=1)
    tasks.finalize_plan()
    tasks.serve_brief(1)
    first = briefs.compose_brief(1, BriefSelection(
        included=("contracts:1",), omitted={"decisions:1": "judged out of scope"}
    ))
    second = briefs.compose_brief(1, _account_for_all(briefs, 1))

    assert second.supersedes == first.id
    assert briefs.get(first.id).superseded_by == second.id
    assert briefs.live_brief(1).id == second.id
    # The old brief's content is untouched — forensics can still answer what was served.
    assert len(briefs.get(first.id).omitted) == 1
    assert [b.id for b in briefs.history(1)] == [first.id, second.id]


def test_allocated_rows_are_candidates_not_automatic_inclusions(
    briefs, tasks, rows, attachments
):
    """The plan-time allocation surface (D8). An allocated row is a candidate subject to
    the same 100% accounting: making the composer omit it *with a reason* is how D8 2.5's
    "too high" attachment becomes visible in a log the owner reads."""
    _plan(rows, extra_rows=0)
    rows.submit_rows(
        [RowSubmission(table="decisions", content={"title": "a plan-wide decision"}, name="a plan-wide decision")],
        "allocated",
    )
    attachments.attach("decisions:1", "plan", reason="governs the whole build")
    tasks.finalize_plan()
    tasks.serve_brief(1)

    candidates = dict(briefs._candidates(tasks.get(1)))
    assert candidates["decisions:1"] == ALLOCATION

    with pytest.raises(IncompleteAccounting) as exc:
        briefs.compose_brief(1, BriefSelection(included=("contracts:1",)))
    assert "decisions:1" in str(exc.value)


def test_composition_refuses_partial_state(briefs, tasks, rows, store):
    """contracts:68's ClosureUnreadable. The mechanism (`storage.integrity_check`) existed
    from M1 and had no consumer; a brief whose accounting is complete over the wrong set
    is the failure the accounting exists to prevent."""
    _plan(rows, extra_rows=1)
    tasks.finalize_plan()
    tasks.serve_brief(1)
    store.conn.execute(
        "UPDATE plan_rows SET content = ? WHERE table_name = 'decisions'", ("{not json",)
    )
    store.conn.commit()

    with pytest.raises(ClosureUnreadable) as exc:
        briefs.compose_brief(1, _account_for_all(briefs, 1))
    assert "decisions:1" in str(exc.value)


# --- contracts:41 audit_brief, and DEFECTS.md F26 ---


def test_audit_measures_the_frozen_closure_not_the_current_one(briefs, tasks, rows):
    """DEFECTS.md F26. The plan is a living source of truth (`decisions:3`), so a closure
    recomputed at audit time has moved on. Auditing against it would report a brief that
    passed 100% accounting as incomplete purely because the plan grew — requirements:44's
    meter degrading with plan age rather than with composition quality."""
    _plan(rows, extra_rows=1)
    tasks.finalize_plan()
    tasks.serve_brief(1)
    brief = briefs.compose_brief(1, _account_for_all(briefs, 1))

    # The plan moves on after composition.
    rows.submit_rows(
        [RowSubmission(table="decisions", content={"title": "decided later"}, name="decided later")], "later"
    )

    audit = briefs.audit_brief(brief.id)
    assert audit.accounted          # the brief is still perfectly accounted
    assert audit.candidates == 2    # against the set frozen with it
    assert audit.unaccounted == ()


def test_audit_reports_drift_separately_and_it_never_fails(
    briefs, tasks, rows, attachments
):
    """The other half of F26: "the plan changed under this brief" is a real and useful
    fact. It is reported as its own number because it is a different fact from "the
    composer skipped a row"."""
    _plan(rows, extra_rows=1)
    tasks.finalize_plan()
    tasks.serve_brief(1)
    brief = briefs.compose_brief(1, _account_for_all(briefs, 1))

    # The plan moves on: a row is allocated to plan scope after the brief was composed,
    # so it is a candidate now and was not one then.
    rows.submit_rows(
        [RowSubmission(table="decisions", content={"title": "decided later"}, name="decided later")], "later"
    )
    attachments.attach("decisions:2", "plan", reason="governs everything from now on")

    audit = briefs.audit_brief(brief.id)
    assert audit.drifted
    assert audit.drifted_in == ("decisions:2",)
    assert audit.accounted


def test_audit_names_the_loud_omissions(briefs, tasks, rows):
    _plan(rows, extra_rows=1)
    tasks.finalize_plan()
    tasks.serve_brief(1)
    brief = briefs.compose_brief(1, BriefSelection(
        included=("contracts:1",), omitted={"decisions:1": "already implemented"}
    ))

    assert briefs.audit_brief(brief.id).loud_omissions == ("decisions:1",)


