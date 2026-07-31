"""revision-service (components:13), reduced — contracts:42/43/45/46/57, plus F21's
affected-only freeze on task-graph and the two owner deviations (D25 live application,
D26 confirmed rewind)."""

import pytest

from engine.errors import (
    NotFinalized,
    RepercussionOutOfStep,
    RevisionAlreadyApplied,
    RevisionInProgress,
    RevisionNotFound,
    UnadjudicatedItems,
)
from engine.models import (
    ChangeRequest,
    Disposition,
    LinkSpec,
    OwnerDecision,
    RevisionResult,
    RewindPreview,
    RollbackReport,
    RowSubmission,
    WalkthroughComplete,
)
from engine.revision import RevisionService


@pytest.fixture
def rev(store, graph, rows, findings, warns, conflicts):
    return RevisionService(store, graph, rows, findings, warns, conflicts)


def _contracts(rows, n, deps=None):
    deps = deps or []
    subs = [
        RowSubmission(
            table="contracts",
            content={
                "title": f"c{i}",
                "behaviours": [
                    {"key": "effect", "kind": "effect", "statement": f"c{i} works"},
                    {"key": "NotFound", "kind": "error", "statement": f"c{i} missing id"},
                ],
            },
            name=f"contract {i}",
            links=[LinkSpec(target=p, edge_type="depends_on") for c, p in deps if c == i],
        )
        for i in range(n)
    ]
    return [v.ref for v in rows.submit_rows(subs, f"c:{n}:{deps}").verdicts]


def _replacement(name="contract 0", title="c0 tightened"):
    return RowSubmission(
        table="contracts",
        content={"title": title, "behaviours": [
            {"key": "effect", "kind": "effect", "statement": "narrower"}]},
        name=name,
    )


# --- contracts:42 open_revision ---


def test_open_revision_refuses_a_draft_plan(rev, rows):
    refs = _contracts(rows, 2)  # a plan that never finalized is still draft
    with pytest.raises(NotFinalized):
        rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))


def test_open_revision_snapshots_bumps_and_enumerates(rev, rows, tasks, store):
    refs = _contracts(rows, 3, deps=[(1, 0)])
    tasks.finalize_plan()
    before = store.plan_handle()["version"]
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="tighten"))
    assert r.state == "walkthrough"
    assert r.from_version == before and r.to_version == before + 1
    # the targeted row and its one dependent
    assert r.repercussion_count == 2
    h = store.plan_handle()
    assert h["state"] == "revising" and h["version"] == before + 1


def test_open_revision_refuses_a_second_concurrent_revision(rev, rows, tasks):
    refs = _contracts(rows, 2)
    tasks.finalize_plan()
    rev.open_revision(ChangeRequest(targets=(refs[0],), intent="one"))
    with pytest.raises(RevisionInProgress):
        rev.open_revision(ChangeRequest(targets=(refs[1],), intent="two"))


def test_open_revision_refuses_a_superseded_target(rev, rows, tasks):
    refs = _contracts(rows, 2)
    tasks.finalize_plan()
    rows.supersede_row(refs[0], _replacement(name="contract 0"), "sup")
    with pytest.raises(Exception):
        rev.open_revision(ChangeRequest(targets=(refs[0],), intent="stale"))


# --- contracts:43 next_repercussion ---


def test_walkthrough_presents_in_order_and_completes(rev, rows, tasks):
    refs = _contracts(rows, 3, deps=[(1, 0)])
    tasks.finalize_plan()
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    first = rev.next_repercussion(r.id)
    assert first.kind == "target" and first.position == 0
    # a pure read: calling again returns the same item until it is adjudicated
    assert rev.next_repercussion(r.id).id == first.id
    rev.adjudicate_repercussion(r.id, first.id, OwnerDecision(Disposition.ACCEPT, "ok"))
    second = rev.next_repercussion(r.id)
    assert second.kind == "affected" and second.position == 1
    rev.adjudicate_repercussion(r.id, second.id, OwnerDecision(Disposition.ACCEPT, "ok"))
    done = rev.next_repercussion(r.id)
    assert isinstance(done, WalkthroughComplete) and done.total == 2


def test_next_repercussion_names_a_missing_revision(rev):
    with pytest.raises(RevisionNotFound):
        rev.next_repercussion(999)


# --- contracts:57 adjudicate_repercussion ---


def test_modify_supersedes_the_row_live(rev, rows, tasks, store):
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="tighten"))
    item = rev.next_repercussion(r.id)
    staged = rev.adjudicate_repercussion(
        r.id, item.id, OwnerDecision(Disposition.MODIFY, "narrow", replacement=_replacement())
    )
    assert staged.applied is not None and staged.held_conflict is None
    # the original is superseded now, before any apply
    old = rows.get(refs[0])
    assert old.state == "superseded"


def test_accept_changes_no_rows(rev, rows, tasks):
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    item = rev.next_repercussion(r.id)
    rev.adjudicate_repercussion(r.id, item.id, OwnerDecision(Disposition.ACCEPT, "fine"))
    assert rows.get(refs[0]).state == "active"


def test_modify_is_held_while_an_open_conflict_touches_the_row(rev, rows, tasks, conflicts):
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    conflicts.raise_conflict([refs[0]], "c0 contradicts itself", "pick one")
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="reword"))
    item = rev.next_repercussion(r.id)
    staged = rev.adjudicate_repercussion(
        r.id, item.id, OwnerDecision(Disposition.MODIFY, "try", replacement=_replacement())
    )
    assert staged.applied is None and staged.held_conflict is not None
    # the row is untouched and the walkthrough has not advanced past it
    assert rows.get(refs[0]).state == "active"
    assert rev.next_repercussion(r.id).id == item.id


def test_adjudicating_out_of_step_is_refused(rev, rows, tasks):
    refs = _contracts(rows, 2, deps=[(1, 0)])
    tasks.finalize_plan()
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    reps = rev.storage.query(
        "SELECT id FROM repercussions WHERE revision_id=? ORDER BY position", (r.id,)
    )
    later = reps[1]["id"]
    with pytest.raises(RepercussionOutOfStep):
        rev.adjudicate_repercussion(r.id, later, OwnerDecision(Disposition.ACCEPT, "no"))


def test_modify_on_a_resurfaced_item_is_refused(rev, rows, tasks, findings, warns):
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    f = findings.file_finding([refs[0]], "a risk on c0", "medium", "c0 risk", resolve_by=7)
    findings.resolve_finding(f.id, "accepted_risk", "owner accepts")
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    # position 0 is the target; position 1 is the resurfaced accepted risk
    rev.adjudicate_repercussion(
        r.id, rev.next_repercussion(r.id).id, OwnerDecision(Disposition.ACCEPT, "ok")
    )
    risk_item = rev.next_repercussion(r.id)
    assert risk_item.kind == "accepted_risk"
    with pytest.raises(RepercussionOutOfStep):
        rev.adjudicate_repercussion(
            r.id, risk_item.id,
            OwnerDecision(Disposition.MODIFY, "x", replacement=_replacement()),
        )


# --- contracts:45 apply_revision ---


def test_apply_refuses_while_items_are_undecided(rev, rows, tasks):
    refs = _contracts(rows, 2, deps=[(1, 0)])
    tasks.finalize_plan()
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    with pytest.raises(UnadjudicatedItems):
        rev.apply_revision(r.id)


def test_apply_closes_the_revision_and_is_idempotent(rev, rows, tasks, store):
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    item = rev.next_repercussion(r.id)
    rev.adjudicate_repercussion(
        r.id, item.id, OwnerDecision(Disposition.MODIFY, "n", replacement=_replacement())
    )
    result = rev.apply_revision(r.id)
    assert isinstance(result, RevisionResult) and result.version == 2
    assert store.plan_handle()["state"] == "finalized"
    assert rev.apply_revision(r.id).applied == result.applied  # idempotent


# --- contracts:46 abandon_revision ---


def test_abandon_preview_mutates_nothing(rev, rows, tasks, store):
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    item = rev.next_repercussion(r.id)
    rev.adjudicate_repercussion(
        r.id, item.id, OwnerDecision(Disposition.MODIFY, "n", replacement=_replacement())
    )
    preview = rev.abandon_revision(r.id)
    assert isinstance(preview, RewindPreview) and len(preview.reverts) == 1
    # still revising; the reworded row is still live
    assert store.plan_handle()["state"] == "revising"
    assert rows.get(refs[0]).state == "superseded"


def test_confirmed_abandon_rewinds_and_preserves_the_record(rev, rows, tasks, store):
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    v_before = store.plan_handle()["version"]
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    item = rev.next_repercussion(r.id)
    rev.adjudicate_repercussion(
        r.id, item.id, OwnerDecision(Disposition.MODIFY, "n", replacement=_replacement())
    )
    report = rev.abandon_revision(r.id, confirm=True)
    assert isinstance(report, RollbackReport)
    h = store.plan_handle()
    assert h["state"] == "finalized" and h["version"] == v_before
    # the reworded row is live again, exactly as it was
    assert rows.get(refs[0]).state == "active"
    # the analysis record survives the rewind (requirements:72)
    assert store.query("SELECT state FROM revisions WHERE id=?", (r.id,))[0]["state"] == "abandoned"
    assert len(store.query("SELECT 1 FROM repercussions WHERE revision_id=?", (r.id,))) == 1


def test_reopening_an_identical_change_after_abandon_is_a_new_revision(rev, rows, tasks):
    # F29 family: after a rewind the version is back to what it was, so a content-keyed
    # open_revision would replay the abandoned revision. The second open must be a new id.
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    change = ChangeRequest(targets=(refs[0],), intent="same change")
    first = rev.open_revision(change)
    rev.abandon_revision(first.id, confirm=True)
    second = rev.open_revision(change)
    assert second.id != first.id
    assert second.state == "walkthrough"


def test_abandon_refuses_an_applied_revision(rev, rows, tasks):
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    item = rev.next_repercussion(r.id)
    rev.adjudicate_repercussion(r.id, item.id, OwnerDecision(Disposition.ACCEPT, "ok"))
    rev.apply_revision(r.id)
    with pytest.raises(RevisionAlreadyApplied):
        rev.abandon_revision(r.id, confirm=True)


# --- F21 / decisions:62 the affected-only freeze on task-graph ---


def test_unaffected_subtasks_flow_during_a_revision(rev, rows, tasks):
    refs = _contracts(rows, 2)  # independent
    tasks.finalize_plan()
    rev.open_revision(ChangeRequest(targets=(refs[0],), intent="touch c0"))
    served = tasks.next_subtask()
    assert served.subtask.contract_ref == refs[1] and served.is_draft is False


def test_a_fully_frozen_revision_serves_nothing_without_consent(rev, rows, tasks):
    refs = _contracts(rows, 2)
    tasks.finalize_plan()
    rev.open_revision(ChangeRequest(targets=(refs[0], refs[1]), intent="both"))
    assert tasks.next_subtask() == tasks.next_subtask()  # AllBlockedReport, falsy
    assert not tasks.next_subtask()


def test_allow_draft_serves_a_frozen_subtask_watermarked(rev, rows, tasks):
    refs = _contracts(rows, 2)
    tasks.finalize_plan()
    rev.open_revision(ChangeRequest(targets=(refs[0], refs[1]), intent="both"))
    served = tasks.next_subtask(allow_draft=True, consent="owner ok")
    assert served.is_draft is True


# --- requirements:55 resurfacing ---


def test_accepted_risk_touching_the_change_resurfaces(rev, rows, tasks, findings):
    refs = _contracts(rows, 1)
    tasks.finalize_plan()
    f = findings.file_finding([refs[0]], "known risk on c0", "high", "c0 risk", resolve_by=7)
    findings.resolve_finding(f.id, "accepted_risk", "owner accepts")
    r = rev.open_revision(ChangeRequest(targets=(refs[0],), intent="x"))
    kinds = [
        row["kind"]
        for row in rev.storage.query(
            "SELECT kind FROM repercussions WHERE revision_id=? ORDER BY position", (r.id,)
        )
    ]
    assert "accepted_risk" in kinds
