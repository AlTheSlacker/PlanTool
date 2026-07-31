"""revision-service (components:13), reduced form (V2_BUILD_PLAN.md 4.1, M7_PLAN.md).

Drives an owner-initiated change to a finalized plan: snapshot and version bump, a link-graph
impact walkthrough with per-item owner adjudication, and either a clean close (`apply_revision`)
or a rewind to the opening snapshot (`abandon_revision`).

Two owner decisions (2026-07-23) depart from the frozen contract text and are logged as
deviations:

  * **D25 — changes apply live, conflict-checked.** The frozen `contracts:57` staged every
    adjudication and mutated nothing until a single deferred `apply_revision`. The owner chose
    instead that a `modify`'s new wording is run through the conflict check and, the moment it
    clears, the row is superseded on the live plan. This is consistent with the write-once
    history rule because abandon does not un-supersede anything — it rewinds.

  * **D26 — abandon is a confirmed rewind.** Because changes are live, `abandon_revision` first
    previews what a rewind would revert; only a confirmed call restores the opening snapshot.

The Revision is born in `walkthrough` (not `proposed`/`analyzing`): impact analysis is a
synchronous read that finishes inside `open_revision`, so those states are passed through and
never persisted. The revision and its repercussions live outside the plan-row snapshot, so a
rewind preserves the analysis record (requirements:72).
"""

from __future__ import annotations

from typing import Any

from engine.clock import now
from engine.conflicts import OPEN as CONFLICT_OPEN
from engine.errors import (
    DanglingRef,
    NotFinalized,
    RepercussionOutOfStep,
    RevisionAlreadyApplied,
    RevisionInProgress,
    RevisionNotFound,
    UnadjudicatedItems,
)
from engine.findings import ACCEPTED_RISK
from engine.idempotency import key
from engine.models import (
    ChangeRequest,
    Disposition,
    OwnerDecision,
    PlanState,
    Repercussion,
    Revision,
    RevisionResult,
    RewindPreview,
    RollbackReport,
    RowRef,
    StagedChange,
    WalkthroughComplete,
    content_fingerprint,
)
from engine.storage import FromOp, Op, Storage
from engine.warnings import CriticalPoint

#: state_machines:1 — the plan states a revision may be opened from (request_revision:
#: sm_cells:9/15/27). `draft` is refused (sm_cells:8) and `revising` is caught earlier by the
#: one-revision-at-a-time rule.
REVISABLE_FROM = (PlanState.FINALIZED, PlanState.IMPLEMENTING, PlanState.COMPLETE)

WALKTHROUGH = "walkthrough"
APPLIED = "applied"
ABANDONED = "abandoned"


class RevisionService:
    def __init__(self, storage: Storage, graph, rows, findings, warns, conflicts):
        self.storage = storage
        self.graph = graph
        self.rows = rows
        self.findings = findings
        self.warns = warns
        self.conflicts = conflicts

    # --- reads ---

    def _open_revision_row(self) -> dict[str, Any] | None:
        rows = self.storage.query(
            "SELECT * FROM revisions WHERE state = ? LIMIT 1", (WALKTHROUGH,)
        )
        return dict(rows[0]) if rows else None

    def _revision_row(self, revision_id: int) -> dict[str, Any]:
        rows = self.storage.query(
            "SELECT * FROM revisions WHERE id = ?", (revision_id,)
        )
        if not rows:
            raise RevisionNotFound("no such revision", revision=revision_id)
        return dict(rows[0])

    def _repercussion_rows(self, revision_id: int) -> list[dict[str, Any]]:
        return [dict(r) for r in self.storage.query(
            "SELECT * FROM repercussions WHERE revision_id = ? ORDER BY position",
            (revision_id,),
        )]

    def _to_repercussion(self, row: dict[str, Any]) -> Repercussion:
        return Repercussion(
            id=row["id"],
            position=row["position"],
            kind=row["kind"],
            advice=row["advice"],
            row=RowRef.coerce(row["row_ref"]) if row["row_ref"] else None,
            finding=RowRef.coerce(row["finding_ref"]) if row["finding_ref"] else None,
            warning_id=row["warning_id"],
            disposition=Disposition(row["disposition"]) if row["disposition"] else None,
        )

    # --- contracts:42 — open_revision ---

    def open_revision(self, change: ChangeRequest) -> Revision:
        """Snapshot, bump the version, run impact analysis, and open the walkthrough.

        Refuses a draft plan (NotFinalized) and a second concurrent revision
        (RevisionInProgress). Everything else is enumeration: the repercussion list is fixed
        here, at open time, and never recomputed (the frozen denominator, F26).
        """
        handle = self.storage.plan_handle()
        state = handle["state"]

        # The open-revision check comes first: while a revision is open the plan sits in
        # `revising`, so the state check below would otherwise fire with a vaguer message
        # than the contract's `RevisionInProgress`, which names the open revision.
        open_rev = self._open_revision_row()
        if open_rev is not None:
            raise RevisionInProgress(
                "a revision is already open; apply or abandon it before starting another",
                revision=open_rev["id"],
            )

        if state == PlanState.DRAFT:
            raise NotFinalized(
                "draft plans are edited directly through the interview; revisions exist "
                "for finalized plans"
            )
        if state not in REVISABLE_FROM:
            # Only reachable if a future state is added to state_machines:1 without a rule
            # here — fail loudly rather than open a revision from an unmodelled state.
            raise NotFinalized(f"a plan in state {state!r} cannot be revised")

        targets = tuple(RowRef.coerce(t) for t in change.targets)
        if not targets:
            raise DanglingRef(
                "a revision must name at least one row to change; none were given"
            )
        self._guard_targets_live(targets)

        # Snapshot BEFORE the version bump so the rewind target is the plan exactly as it
        # stood when the revision opened (entities:11). The analysis record is written after,
        # into tables the snapshot does not cover, so a rewind never destroys it.
        snapshot_id = self.storage.snapshot_version(
            f"pre-revision v{handle['version']}: {change.intent[:80]}"
        )
        from_version = handle["version"]
        to_version = from_version + 1

        report = self.graph.impact(list(targets))
        specs = self._enumerate_repercussions(targets, report.affected)

        ops: list[Op] = [
            Op("insert", "revisions", {
                "intent": change.intent,
                "snapshot_id": snapshot_id,
                "from_version": from_version,
                "to_version": to_version,
                "state": WALKTHROUGH,
                "cursor": 0,
                "created_at": now(),
                "resolved_at": None,
            }),
            # request_revision (sm_cells:9/15/27): the plan leaves finalized for revising and
            # its version bumps now, so briefs already issued read as a stale version.
            Op("update", "plan",
               {"state": PlanState.REVISING.value, "version": to_version},
               where={"guard": 1}),
        ]
        for position, spec in enumerate(specs):
            ops.append(Op("insert", "repercussions", {
                "revision_id": FromOp(0, "id"),
                "position": position,
                "kind": spec["kind"],
                "row_ref": spec.get("row_ref"),
                "finding_ref": spec.get("finding_ref"),
                "warning_id": spec.get("warning_id"),
                "advice": spec["advice"],
                "disposition": None,
                "owner_words": None,
                "applied_ref": None,
                "created_at": now(),
                "resolved_at": None,
            }))

        # Keyed on the snapshot id, which `snapshot_version` mints fresh on every call — NOT on
        # the change's content. A content key (intent + targets + version) would collide after
        # an abandon: the rewind restores the pre-change version, so an identical re-open would
        # replay the abandoned revision's receipt and hand back the dead id. The one-revision-
        # at-a-time guard above already stops a genuine duplicate, so the key needs only to be
        # unique per attempt. The mirror of F29/F44 — a key answering the wrong question.
        receipt = self.storage.write_atomic(
            ops, key("open_revision", str(snapshot_id))
        )
        revision_id = receipt["results"][0]["id"]

        return Revision(
            id=revision_id,
            intent=change.intent,
            from_version=from_version,
            to_version=to_version,
            state=WALKTHROUGH,
            repercussion_count=len(specs),
        )

    # --- open_revision internals ---

    def _guard_targets_live(self, targets: tuple[RowRef, ...]) -> None:
        for ref in targets:
            row = self.storage.query(
                "SELECT superseded_by, state FROM plan_rows "
                "WHERE table_name = ? AND ordinal = ?",
                (ref.table, ref.ordinal),
            )
            if not row:
                raise DanglingRef("no such row to change", ref=str(ref))
            if row[0]["superseded_by"]:
                raise DanglingRef(
                    "that row is superseded history; change its live replacement instead",
                    ref=str(ref),
                )

    def _enumerate_repercussions(
        self, targets: tuple[RowRef, ...], affected: tuple[RowRef, ...]
    ) -> list[dict[str, Any]]:
        """The frozen repercussion list: the targeted rows, then everything transitively
        affected, then any accepted risk or suppressed warning the change touches
        (requirements:55). Deterministically ordered so the walkthrough resumes identically.
        """
        specs: list[dict[str, Any]] = []
        for ref in sorted(targets, key=str):
            specs.append({
                "kind": "target",
                "row_ref": str(ref),
                "advice": "you asked to change this row; supply its new wording, "
                          "accept it as-is, or defer it.",
            })
        for ref in sorted(affected, key=str):
            specs.append({
                "kind": "affected",
                "row_ref": str(ref),
                "advice": "this row rests on one you are changing; decide whether it needs "
                          "to change too.",
            })

        impact_set = {str(r) for r in targets} | {str(r) for r in affected}

        for finding in self._resurfaced_findings(impact_set):
            specs.append({
                "kind": "accepted_risk",
                "finding_ref": str(finding.ref),
                "advice": f"a risk you accepted touches this change and must be "
                          f"re-adjudicated: {finding.name}",
            })

        for warning in self._resurfaced_warnings(impact_set):
            specs.append({
                "kind": "suppressed_warning",
                "warning_id": warning.id,
                "advice": warning.present(),
            })
        return specs

    def _resurfaced_findings(self, impact_set: set[str]):
        for finding in self.findings.all_findings():
            if finding.state != ACCEPTED_RISK:
                continue
            if any(str(r) in impact_set for r in finding.refs):
                yield finding

    def _resurfaced_warnings(self, impact_set: set[str]):
        for warning in self.warns.active_warnings(context=CriticalPoint.REVISION):
            if warning.resurfaced and warning.source_ref is not None \
                    and str(warning.source_ref) in impact_set:
                yield warning

    # --- contracts:43 — next_repercussion ---

    def next_repercussion(
        self, revision_id: int
    ) -> Repercussion | WalkthroughComplete:
        """Present the repercussion at the current checkpoint, or `WalkthroughComplete`.

        The `cursor` is the checkpoint (uc_extensions:44): the walk resumes losslessly
        because this is a pure read of the row at `cursor`, and only `adjudicate_repercussion`
        advances it. Calling twice returns the same item until it is adjudicated — a `modify`
        held on a conflict keeps surfacing here until the owner resolves it.
        """
        rev = self._revision_row(revision_id)
        reps = self._repercussion_rows(revision_id)
        cursor = rev["cursor"]
        if rev["state"] != WALKTHROUGH or cursor >= len(reps):
            return WalkthroughComplete(revision_id=revision_id, total=len(reps))
        return self._to_repercussion(reps[cursor])

    # --- contracts:57 — adjudicate_repercussion ---

    def adjudicate_repercussion(
        self, revision_id: int, item_id: int, decision: OwnerDecision
    ) -> StagedChange:
        """Record the owner's decision on the current repercussion, applying it live.

        The walkthrough is strictly in order: only the item `next_repercussion` is currently
        presenting may be adjudicated (RepercussionOutOfStep otherwise). accept and defer
        record the owner's words and change no rows. A modify carries a replacement row; the
        affected row is checked for an open conflict, and only if none is shown is the row
        superseded on the live plan (D25) and the cursor advanced. A held conflict leaves the
        repercussion current so `next_repercussion` keeps surfacing it until it is resolved.
        """
        rev = self._revision_row(revision_id)
        if rev["state"] != WALKTHROUGH:
            raise RepercussionOutOfStep(
                "the revision is not in walkthrough; nothing to adjudicate",
                revision=revision_id, state=rev["state"],
            )
        reps = self._repercussion_rows(revision_id)
        cursor = rev["cursor"]
        if cursor >= len(reps):
            raise RepercussionOutOfStep(
                "the walkthrough is complete; call apply_revision to close the revision",
                revision=revision_id,
            )
        current = reps[cursor]
        if current["id"] != item_id:
            raise RepercussionOutOfStep(
                "adjudicate the repercussion the walkthrough is presenting, not a later one",
                expected=current["id"], got=item_id,
            )

        if decision.disposition == Disposition.MODIFY:
            return self._adjudicate_modify(rev, current, decision)

        # accept / defer: a recorded judgment that changes no rows.
        self._record_and_advance(
            rev, current, decision.disposition, decision.words, applied_ref=None
        )
        return StagedChange(
            repercussion_id=current["id"], disposition=decision.disposition
        )

    def _adjudicate_modify(
        self, rev: dict[str, Any], current: dict[str, Any], decision: OwnerDecision
    ) -> StagedChange:
        if not current["row_ref"]:
            raise RepercussionOutOfStep(
                "this repercussion is a resurfaced risk or warning — there is no row here "
                "to reword; accept it to keep it, or defer to handle it later",
                repercussion=current["id"], kind=current["kind"],
            )
        if decision.replacement is None:
            raise RepercussionOutOfStep(
                "a modify supplies the replacement row the affected row is superseded by",
                repercussion=current["id"],
            )
        ref = RowRef.coerce(current["row_ref"])

        # The conflict gate (owner's decision): a row under an open conflict is not quietly
        # reworded. The conflict is "shown" and the change held until the owner resolves it —
        # possibly with new wording, but that resolution is theirs to make, not the tool's.
        open_conflicts = [
            c for c in self.conflicts.conflicts_for(ref) if c.state == CONFLICT_OPEN
        ]
        if open_conflicts:
            return StagedChange(
                repercussion_id=current["id"],
                disposition=Disposition.MODIFY,
                held_conflict=open_conflicts[0].id,
            )

        # The owner's own words are why this row is being abandoned — recorded verbatim
        # against the repercussion already, and now on the row itself. Composing a reason
        # here would be the tool writing the wording, which D25 keeps it out of.
        result = self.rows.supersede_row(
            ref,
            decision.replacement,
            decision.words,
            key("revision_modify", content_fingerprint({
                "revision": rev["id"],
                "position": current["position"],
                "content": decision.replacement.content,
            })),
        )
        new_ref = result["new"]
        self._record_and_advance(
            rev, current, Disposition.MODIFY, decision.words, applied_ref=str(new_ref)
        )
        return StagedChange(
            repercussion_id=current["id"],
            disposition=Disposition.MODIFY,
            applied=new_ref,
        )

    def _record_and_advance(
        self, rev: dict[str, Any], current: dict[str, Any],
        disposition: Disposition, words: str, applied_ref: str | None,
    ) -> None:
        """Stamp the adjudication and step the checkpoint in one write, so the cursor never
        points at an item already decided."""
        self.storage.write_atomic(
            [
                Op("update", "repercussions", {
                    "disposition": disposition.value,
                    "owner_words": words,
                    "applied_ref": applied_ref,
                    "resolved_at": now(),
                }, where={"id": current["id"]}),
                Op("update", "revisions", {"cursor": rev["cursor"] + 1},
                   where={"id": rev["id"]}),
            ],
            key("adjudicate", f"{rev['id']}:{current['position']}:"
                f"{content_fingerprint({'d': disposition.value, 'w': words, 'a': applied_ref})}"),
        )

    def _applied_refs(self, revision_id: int) -> tuple[RowRef, ...]:
        """The superseding rows a revision's modifies produced — the changes a rewind undoes."""
        return tuple(
            RowRef.coerce(r["applied_ref"])
            for r in self.storage.query(
                "SELECT applied_ref FROM repercussions WHERE revision_id = ? "
                "AND applied_ref IS NOT NULL ORDER BY position",
                (revision_id,),
            )
        )

    # --- contracts:45 — apply_revision ---

    def apply_revision(self, revision_id: int) -> RevisionResult:
        """Close a fully-adjudicated revision; the plan's new version goes live.

        Under live application (D25) the row changes already landed as they were adjudicated,
        so apply is the closing act: it verifies every repercussion was decided (a held
        conflict leaves one undecided → UnadjudicatedItems) and fires apply_revision on the
        plan (revising → finalized, sm_cells:22).
        """
        rev = self._revision_row(revision_id)
        if rev["state"] == APPLIED:
            return self._result(rev)
        if rev["state"] == ABANDONED:
            raise RevisionAlreadyApplied(
                "this revision was abandoned; start a new one to change the plan",
                revision=revision_id,
            )

        reps = self._repercussion_rows(revision_id)
        undecided = [r for r in reps if r["disposition"] is None]
        if undecided:
            raise UnadjudicatedItems(
                "every repercussion must be adjudicated before the revision can be applied; "
                "these remain (a modify held on an open conflict counts as undecided): "
                + ", ".join(self._name_repercussion(r) for r in undecided),
                remaining=[r["id"] for r in undecided],
            )

        self.storage.write_atomic(
            [
                Op("update", "revisions",
                   {"state": APPLIED, "resolved_at": now()}, where={"id": revision_id}),
                Op("update", "plan",
                   {"state": PlanState.FINALIZED.value}, where={"guard": 1}),
            ],
            key("apply_revision", str(revision_id)),
        )
        return self._result(self._revision_row(revision_id))

    def _result(self, rev: dict[str, Any]) -> RevisionResult:
        return RevisionResult(
            revision_id=rev["id"],
            version=rev["to_version"],
            applied=self._applied_refs(rev["id"]),
        )

    def _name_repercussion(self, r: dict[str, Any]) -> str:
        target = r["row_ref"] or r["finding_ref"] or f"warning {r['warning_id']}"
        return f"[{r['position']}] {r['kind']} {target}"

    # --- contracts:46 — abandon_revision ---

    def abandon_revision(
        self, revision_id: int, confirm: bool = False
    ) -> RewindPreview | RollbackReport:
        """Preview or perform a rewind of the plan to the revision's opening snapshot (D26).

        Unconfirmed, this is a pure read that reports exactly which applied changes a rewind
        would revert, so the owner can decide with the consequences in front of them. A
        confirmed call restores the opening snapshot (abandon_revision, revising → finalized,
        sm_cells:23) and marks the revision abandoned; its analysis record survives because it
        lives outside the snapshot (requirements:72).
        """
        rev = self._revision_row(revision_id)
        if rev["state"] == APPLIED:
            raise RevisionAlreadyApplied(
                "applied revisions roll forward via a new revision, never backward",
                revision=revision_id,
            )
        if rev["state"] == ABANDONED:
            raise RevisionAlreadyApplied(
                "this revision was already abandoned; the plan is at its pre-change version",
                revision=revision_id,
            )

        reverts = self._applied_refs(revision_id)
        if not confirm:
            return RewindPreview(
                revision_id=revision_id,
                reverts=reverts,
                restores_version=rev["from_version"],
            )

        # Restore first, then mark abandoned. A crash between leaves the plan rewound with the
        # revision still open — safe, and a re-run of the confirmed call completes it (the
        # restore is idempotent: it re-applies the same snapshot).
        restored_version = self.storage.restore_snapshot(rev["snapshot_id"])
        self.storage.write_atomic(
            [Op("update", "revisions",
                {"state": ABANDONED, "resolved_at": now()}, where={"id": revision_id})],
            key("abandon_revision", str(revision_id)),
        )
        return RollbackReport(
            revision_id=revision_id,
            restored_version=restored_version,
            reverted=reverts,
        )
