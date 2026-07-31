"""brief-composer (components:12) — contracts:68/41/40, and the defects they carried.

Three of these tests exist because of defects found in the M5b pre-build audit rather than
because of anything the frozen plan says: F23 (split coverage had no denominator), F25
("supersedes in the graph" had no mechanism) and F26 (the audit's denominator moved).
"""

import pytest

from engine.briefs import (
    ALLOCATION,
    CLOSURE,
    BriefSelection,
    ClosureUnreadable,
    IncompleteAccounting,
    NothingToSplit,
    ObligationsNotOwned,
    OmissionNeedsReason,
    ObligationsNotCovered,
)
from engine.models import LinkSpec, RowSubmission
from engine.obligations import NotEnumerated
from engine.tasks import DONE, IN_PROGRESS, PENDING, TaskSuperseded

OBLIGATIONS = [
    {"key": "effect", "kind": "effect", "statement": "does the thing"},
    {"key": "NotFound", "kind": "error", "statement": "names the missing id"},
]


def _plan(rows, extra_rows=0, obligations=OBLIGATIONS):
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
            content={"title": "the contract", "behaviours": obligations},
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


# --- contracts:40 split_task, and DEFECTS.md F23 / F25 ---


def test_split_redistributes_the_obligations(briefs, tasks, rows, obligations):
    """decisions:63 — a split "divides along the contract's param/error surface". The
    obligation surface (D12) *is* that surface, enumerated at finalization rather than by
    the splitter at split time."""
    _plan(rows)
    tasks.finalize_plan()
    tasks.serve_brief(1)

    new = briefs.split_task(1, [("the happy path", [1]), ("the error path", [2])])
    assert len(new) == 2
    assert [o.key for o in obligations.for_task(new[0].id)] == ["behaviour"]
    assert [o.key for o in obligations.for_task(new[1].id)] == ["NotFound"]
    # And nothing is owed twice: the original owns nothing now.
    assert obligations.for_task(1) == ()


def test_a_split_that_drops_an_obligation_is_refused(briefs, tasks, rows):
    """contracts:40's coverage check — `PartsDontCover` in the frozen plan — with the
    denominator F23 found missing. Before D12 every task a split produced named the same
    single contract, so joint coverage was vacuous and requirements:37's "silent trimming is
    not a remedy" had no enforcement at all."""
    _plan(rows)
    tasks.finalize_plan()

    with pytest.raises(ObligationsNotCovered) as exc:
        briefs.split_task(1, [("task a", [1]), ("task b", [])])
    assert "contracts:1#NotFound" in str(exc.value)
    assert len(tasks._all()) == 1        # nothing written


def test_a_split_cannot_claim_obligations_the_original_never_owed(briefs, tasks, rows):
    """`ObligationsNotCovered`'s mirror: coverage alone would let a split satisfy its
    accounting by enlarging the denominator, which is F23's disease the other way round."""
    _plan(rows)
    tasks.finalize_plan()

    with pytest.raises(ObligationsNotOwned):
        briefs.split_task(1, [("task a", [1]), ("task b", [2, 99])])


def test_a_task_with_no_surface_cannot_be_split(briefs, tasks, rows):
    """D12's accepted cost, made loud. A split measured against an empty denominator
    passes vacuously — the tool refuses rather than permitting an unaccountable split."""
    _plan(rows, obligations=None)
    tasks.finalize_plan()

    with pytest.raises(NotEnumerated):
        briefs.split_task(1, [("task a", []), ("task b", [])])


def test_one_task_is_not_a_split(briefs, tasks, rows):
    _plan(rows)
    tasks.finalize_plan()
    with pytest.raises(NothingToSplit):
        briefs.split_task(1, [("the whole thing", [1, 2])])


def test_the_original_leaves_the_graph(briefs, tasks, rows):
    """DEFECTS.md F25 — `contracts:40` returns tasks "superseding the original in the
    graph" and never says what that does. Left in, the original sits in `in_flight`
    forever, trips the 24h staleness flag, and can be served again."""
    _plan(rows)
    tasks.finalize_plan()
    tasks.serve_brief(1)
    assert tasks.graph_status().in_flight == (1,)

    new = briefs.split_task(1, [("task a", [1]), ("task b", [2])])

    status = tasks.graph_status()
    assert status.in_flight == ()
    assert set(status.ready) == {n.id for n in new}
    assert tasks.next_task().task.id in {n.id for n in new}
    with pytest.raises(TaskSuperseded):
        tasks.serve_brief(1)


def test_dependants_are_rewired_to_the_new_tasks(briefs, tasks, rows):
    """The deadlock half of F25. `task_deps` edges point at the original's id, and a
    split original can never reach `done` — so every consumer would sit in `pending`
    behind a node that will never complete."""
    rows.submit_rows(
        [RowSubmission(table="contracts",
                       content={"title": "provider", "behaviours": OBLIGATIONS}, name="provider")],
        "provider",
    )
    rows.submit_rows(
        [RowSubmission(table="contracts",
                       content={"title": "consumer", "behaviours": OBLIGATIONS},
                       links=[LinkSpec(target="contracts:1", edge_type="depends_on")], name="consumer")],
        "consumer",
    )
    tasks.finalize_plan()
    provider, consumer = 1, 2
    tasks.serve_brief(provider)

    new = briefs.split_task(provider, [("task a", [1]), ("task b", [2])])

    assert set(tasks.get(consumer).deps) == {n.id for n in new}
    # And the consumer really does become ready once both of them are done.
    for task in new:
        tasks.serve_brief(task.id)
        tasks.verify_completion(
            task.id,
            {o.ref: "tests pass" for o in briefs.obligations.for_task(task.id)},
        )
        tasks.report_status(task.id, "complete", "built")
    assert tasks.graph_status().ready == (consumer,)


def test_new_tasks_inherit_the_originals_dependencies(briefs, tasks, rows):
    """Each is still downstream of whatever the whole was — otherwise a split is a way to
    escape the dependency order requirements:34 exists to preserve."""
    rows.submit_rows(
        [RowSubmission(table="contracts",
                       content={"title": "provider", "behaviours": OBLIGATIONS}, name="provider")],
        "provider",
    )
    rows.submit_rows(
        [RowSubmission(table="contracts",
                       content={"title": "consumer", "behaviours": OBLIGATIONS},
                       links=[LinkSpec(target="contracts:1", edge_type="depends_on")], name="consumer")],
        "consumer",
    )
    tasks.finalize_plan()

    new = briefs.split_task(2, [("task a", [3]), ("task b", [4])])
    for task in new:
        assert task.deps == (1,)
        assert tasks.readiness_of(task) == PENDING
