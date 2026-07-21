"""row-service (components:2).

Owns the PlanRow lifecycle: provenance-checked batched submission with per-row verdicts,
full and targeted readback, in-place assumption upgrade, supersession lineage, and
retirement.

Contracts: contracts:9 submit_rows, contracts:10 read_rows, contracts:11
resolve_assumption, contracts:12 supersede_row, contracts:13 retire_row.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from engine.errors import (
    AlreadyRetired,
    AlreadySuperseded,
    ConflictRequired,
    InvalidSelector,
    NotAssumed,
    RowNotFound,
    UpgradeFailed,
)
from engine.models import (
    BatchReceipt,
    LinkSpec,
    PlanRow,
    Provenance,
    RowPage,
    RowRef,
    RowSelector,
    RowState,
    RowSubmission,
    RowVerdict,
)
from engine.clock import now
from engine.storage import Op, Storage

#: A contradiction detector: given a candidate submission and the store, return a
#: human-readable description of what stored row it contradicts, or None.
#:
#: contracts:9 mandates a ConflictRequired error but the frozen plan never specifies how
#: contradiction is *determined* (DEFECTS.md F4). conflict-service supplies a real
#: detector in M3; until then no contradiction is detected and the error is unreachable.
ContradictionDetector = Callable[[RowSubmission, "RowService"], str | None]


def _no_contradictions(submission: RowSubmission, service: RowService) -> str | None:
    return None


class RowService:
    def __init__(
        self,
        storage: Storage,
        detector: ContradictionDetector = _no_contradictions,
    ):
        self.storage = storage
        self.detect_contradiction = detector

    # --- contracts:9 ---

    def submit_rows(
        self, batch: list[RowSubmission], idempotency_key: str, lease=None
    ) -> BatchReceipt:
        """Submit a batch of rows.

        requirements:14 — a row failing validation is rejected alone, with a verdict
        naming the specific problem; accepted rows stand.
        requirements:6 — the batch is atomic: no partial rows.
        requirements:27 — a row contradicting a stored row files nothing until a
        conflict is raised.
        """
        replay = self.storage.replay(idempotency_key)
        if replay is not None and "verdicts" in replay["meta"]:
            # decisions:43 — a replayed key returns the ORIGINAL receipt. The batch
            # presented now is not re-evaluated; it may not even be the same batch.
            return BatchReceipt(
                idempotency_key,
                tuple(
                    RowVerdict(
                        v["index"],
                        v["accepted"],
                        RowRef.parse(v["ref"]) if v["ref"] else None,
                        v["problem"],
                    )
                    for v in replay["meta"]["verdicts"]
                ),
                replay["written_at"],
                replayed=True,
            )

        problems: dict[int, str] = {}
        for index, submission in enumerate(batch):
            problem = self._validate(submission, index, len(batch))
            if problem is not None:
                problems[index] = problem
                continue
            contradiction = self.detect_contradiction(submission, self)
            if contradiction is not None:
                raise ConflictRequired(
                    "a submitted row contradicts a stored row; nothing is filed until "
                    "a conflict is raised and presented (requirements:27)",
                    index=index,
                    contradiction=contradiction,
                )

        # A row whose sibling target was rejected cannot be filed either: dropping the
        # link silently would file a row with less provenance than it declared. Iterate
        # to a fixed point, since a rejection can cascade along a chain of siblings.
        changed = True
        while changed:
            changed = False
            for index, submission in enumerate(batch):
                if index in problems:
                    continue
                for link in submission.links:
                    if link.is_intra_batch and link.target in problems:
                        problems[index] = (
                            f"link target (batch index {link.target}) was rejected: "
                            f"{problems[link.target]}"
                        )
                        changed = True
                        break

        verdicts: list[RowVerdict] = []
        ops: list[Op] = []
        op_index: list[int] = []

        for index, submission in enumerate(batch):
            if index in problems:
                verdicts.append(RowVerdict(index, False, problem=problems[index]))
                continue

            ops.append(
                Op(
                    "insert_row",
                    "plan_rows",
                    {
                        "table_name": submission.table,
                        "content": json.dumps(submission.content),
                        "provenance": str(submission.provenance),
                        "assumption_kind": submission.assumption_kind,
                        "state": str(submission.initial_state()),
                        "package": submission.package,
                        "created_at": now(),
                    },
                )
            )
            op_index.append(index)
            verdicts.append(RowVerdict(index, True))

        receipt = self.storage.write_atomic(ops, idempotency_key, lease=lease)

        # Read assignments from the receipt, not from the ops: on an idempotent replay
        # the ops were never executed and carry no results, but the stored receipt has
        # the original refs (decisions:43).
        assigned: dict[int, RowRef] = {}
        for result, index in zip(receipt["results"], op_index, strict=True):
            assigned[index] = RowRef.parse(result["ref"])

        # Links are declared with their rows but can only be written once the rows have
        # refs. entities:15 keeps them immutable thereafter.
        link_ops = [
            Op(
                "insert",
                "links",
                {
                    "source_ref": str(assigned[index]),
                    "target_ref": str(
                        assigned[link.target] if link.is_intra_batch else link.target
                    ),
                    "edge_type": link.edge_type,
                    "created_at": now(),
                },
            )
            for index in op_index
            for link in batch[index].links
        ]
        if link_ops:
            self.storage.write_atomic(
                link_ops, f"{idempotency_key}:links", lease=lease
            )

        final = tuple(
            RowVerdict(v.index, v.accepted, assigned.get(v.index), v.problem)
            for v in verdicts
        )
        # Record the verdicts against the key so a replay can return them verbatim.
        self.storage.annotate(
            idempotency_key,
            {
                "verdicts": [
                    {
                        "index": v.index,
                        "accepted": v.accepted,
                        "ref": str(v.ref) if v.ref else None,
                        "problem": v.problem,
                    }
                    for v in final
                ]
            },
        )
        return BatchReceipt(
            idempotency_key,
            final,
            receipt["written_at"],
            replayed=receipt.get("replayed", False),
        )

    def _validate(
        self, submission: RowSubmission, index: int = 0, batch_size: int = 1
    ) -> str | None:
        """requirements:5 — provenance is mandatory, and an assumed row must say what
        kind of assumption it is."""
        if not submission.table or not submission.table.isidentifier():
            return f"table name {submission.table!r} is not a valid identifier"
        if not isinstance(submission.content, dict) or not submission.content:
            return "content must be a non-empty object"
        if submission.provenance is Provenance.ASSUMED and not submission.assumption_kind:
            return (
                "an assumed row must carry an assumption_kind (requirements:5); "
                "world assumptions go to spikes, intent assumptions go to the owner"
            )
        for link in submission.links:
            if link.is_intra_batch:
                if not 0 <= link.target < batch_size:
                    return (
                        f"link target index {link.target} is outside this batch "
                        f"(0..{batch_size - 1})"
                    )
                if link.target == index:
                    return "a row cannot link to itself"
            elif self._row(link.target) is None:
                return f"link target {link.target} does not exist"
        return None

    # --- contracts:10 ---

    def read_rows(self, selector: RowSelector) -> RowPage:
        """Targeted reads, so resume cost scales with the working set rather than total
        plan size (requirements:62, decisions:49)."""
        if selector.limit <= 0:
            raise InvalidSelector("limit must be positive", field="limit",
                                  value=selector.limit)
        if selector.offset < 0:
            raise InvalidSelector("offset cannot be negative", field="offset",
                                  value=selector.offset)

        where: list[str] = []
        params: list[Any] = []

        if selector.ids is not None:
            if not selector.ids:
                raise InvalidSelector("ids selector is empty", field="ids")
            marks = ", ".join("?" for _ in selector.ids)
            where.append(f"(table_name || ':' || ordinal) IN ({marks})")
            params.extend(str(RowRef.coerce(r)) for r in selector.ids)
        if selector.table is not None:
            where.append("table_name = ?")
            params.append(selector.table)
        if selector.package is not None:
            where.append("package = ?")
            params.append(selector.package)
        if selector.provenance is not None:
            where.append("provenance = ?")
            params.append(str(selector.provenance))
        if selector.live_only:
            # requirements:61 — liveness is this single check.
            where.append("superseded_by IS NULL AND state != 'retired'")
        if selector.neighbourhood_of is not None:
            ref = str(RowRef.coerce(selector.neighbourhood_of))
            where.append(
                "(table_name || ':' || ordinal) IN ("
                " SELECT target_ref FROM links WHERE source_ref = ?"
                " UNION SELECT source_ref FROM links WHERE target_ref = ?)"
            )
            params.extend([ref, ref])

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        total = self.storage.query(
            f"SELECT COUNT(*) AS n FROM plan_rows {clause}", tuple(params)  # noqa: S608
        )[0]["n"]
        rows = self.storage.query(
            f"SELECT * FROM plan_rows {clause} ORDER BY id LIMIT ? OFFSET ?",  # noqa: S608
            (*params, selector.limit, selector.offset),
        )
        return RowPage(
            tuple(self._hydrate(r) for r in rows), total, selector.offset,
            selector.limit,
        )

    def get(self, ref: RowRef | str) -> PlanRow:
        ref = RowRef.coerce(ref)
        row = self._row(ref)
        if row is None:
            raise RowNotFound("no such row", ref=str(ref))
        return self._hydrate(row)

    def lineage_root(self, ref: RowRef | str) -> RowRef:
        """The earliest ancestor in a row's supersession chain.

        The supersession-stable identity primitive. A record keyed on a row ref detaches
        silently the moment that row is superseded (findings:16); keyed on the lineage
        root it does not, because the root never changes. requirements:78 established
        this for gap dismissals; scope attachments take the same keying (M5_PLAN.md 2.4),
        which makes this the second application and the reason it lives here rather than
        on either caller.
        """
        current = RowRef.coerce(ref)
        seen: set[str] = set()
        while True:
            if str(current) in seen:  # defensive: a cycle in lineage is corruption
                return current
            seen.add(str(current))
            found = self.storage.query(
                "SELECT supersedes FROM plan_rows WHERE table_name = ? AND ordinal = ?",
                (current.table, current.ordinal),
            )
            if not found or not found[0]["supersedes"]:
                return current
            current = RowRef.parse(found[0]["supersedes"])

    def lineage_head(self, ref: RowRef | str) -> RowRef:
        """The live end of a row's supersession chain — `lineage_root`'s mirror.

        The root is the stable *identity* of a thing; the head is its current *state*. Both
        are needed and for opposite reasons: key on the root so a reference never detaches,
        read the head to answer "and where does that stand now".

        This is what serves "I decided something yesterday — what became of it" without a
        stored `updated_at` on an immutable row (see `PlanRow.updated_at`). The question is
        about a lineage, so it is answered by walking one.
        """
        current = RowRef.coerce(ref)
        seen: set[str] = set()
        while True:
            if str(current) in seen:  # defensive: a cycle in lineage is corruption
                return current
            seen.add(str(current))
            found = self.storage.query(
                "SELECT superseded_by FROM plan_rows WHERE table_name = ? AND ordinal = ?",
                (current.table, current.ordinal),
            )
            if not found or not found[0]["superseded_by"]:
                return current
            current = RowRef.parse(found[0]["superseded_by"])

    def history(self, ref: RowRef | str) -> list:
        """Every version of a thing, oldest first, from lineage root to live head.

        `requirements:61`'s lineage made readable. Each row carries its own `created_at`, so
        this answers both halves of the owner's question at once: *when* each version was
        written, and *what it said at the time*.
        """
        rows, current = [], self.lineage_root(ref)
        while True:
            row = self.get(current)
            rows.append(row)
            if row.superseded_by is None:
                return rows
            current = row.superseded_by

    def _row(self, ref: RowRef | str):
        ref = RowRef.coerce(ref)
        rows = self.storage.query(
            "SELECT * FROM plan_rows WHERE table_name = ? AND ordinal = ?",
            (ref.table, ref.ordinal),
        )
        return rows[0] if rows else None

    def _hydrate(self, row) -> PlanRow:
        ref = RowRef(row["table_name"], row["ordinal"])
        links = tuple(
            LinkSpec(RowRef.parse(r["target_ref"]), r["edge_type"])
            for r in self.storage.query(
                "SELECT target_ref, edge_type FROM links WHERE source_ref = ? "
                "ORDER BY id",
                (str(ref),),
            )
        )
        return PlanRow(
            ref=ref,
            content=json.loads(row["content"]),
            provenance=Provenance(row["provenance"]),
            state=RowState(row["state"]),
            created_at=row["created_at"],
            assumption_kind=row["assumption_kind"],
            package=row["package"],
            supersedes=RowRef.parse(row["supersedes"]) if row["supersedes"] else None,
            superseded_by=(
                RowRef.parse(row["superseded_by"]) if row["superseded_by"] else None
            ),
            superseded_at=row["superseded_at"],
            retired_at=row["retired_at"],
            retire_reason=row["retire_reason"],
            links=links,
        )

    # --- contracts:11 ---

    def resolve_assumption(
        self,
        ref: RowRef | str,
        quote: str,
        resolution: str,
        idempotency_key: str,
        lease=None,
        retire_reason: str | None = None,
    ) -> PlanRow:
        """Upgrade the SAME row in place to decided, with the owner's answer quoted.

        requirements:18/19 — the gap clears immediately and no duplicate row appears.
        This fixes the friction recorded in decisions:28(a), where an assumption could
        only be resolved by creating a second row.

        `retire_reason` overrides the default for a rejection. The owner is not the only
        thing that can settle an assumption: validation-service closes world-assumptions
        from spike evidence (requirements:25), and recording those as "rejected by the
        owner" would put a falsehood in the audit trail. See DEFECTS.md F14.
        """
        ref = RowRef.coerce(ref)
        row = self._row(ref)
        if row is None:
            raise RowNotFound("no such row; nothing written", ref=str(ref))
        if row["state"] != RowState.ASSUMED or row["provenance"] != Provenance.ASSUMED:
            raise NotAssumed(
                "row is not an open assumption; no write occurred",
                ref=str(ref),
                state=row["state"],
                provenance=row["provenance"],
            )
        if resolution not in ("confirm", "revise", "reject"):
            raise UpgradeFailed(
                "resolution must be confirm|revise|reject",
                ref=str(ref),
                resolution=resolution,
            )
        if not quote or not quote.strip():
            raise UpgradeFailed(
                "the owner's answer must be quoted verbatim (requirements:18)",
                ref=str(ref),
            )

        content = json.loads(row["content"])
        content["owner_answer"] = {"quote": quote, "resolution": resolution,
                                   "resolved_at": now()}
        target_state = RowState.RETIRED if resolution == "reject" else RowState.ACTIVE
        values: dict[str, Any] = {
            "content": json.dumps(content),
            "provenance": str(Provenance.DECIDED),
            "state": str(target_state),
            "assumption_kind": None,
        }
        if resolution == "reject":
            values["retired_at"] = now()
            values["retire_reason"] = retire_reason or "assumption rejected by the owner"

        op = Op("update", "plan_rows", values,
                where={"table_name": ref.table, "ordinal": ref.ordinal})
        receipt = self.storage.write_atomic([op], idempotency_key, lease=lease)
        result = receipt["results"][0]
        if result is not None and result.get("rows") == 0:
            raise UpgradeFailed("upgrade could not be applied", ref=str(ref))
        return self.get(ref)

    # --- contracts:12 ---

    def supersede_row(
        self,
        old: RowRef | str,
        replacement: RowSubmission,
        idempotency_key: str,
        lease=None,
    ) -> dict[str, Any]:
        """requirements:61 — the replacement is created with a supersedes pointer, the
        old row is stamped once with superseded_by and a timestamp, and content is
        never edited."""
        old = RowRef.coerce(old)
        row = self._row(old)
        if row is None:
            raise RowNotFound("no such row", ref=str(old))
        if row["superseded_by"]:
            raise AlreadySuperseded(
                "lineage is write-once; supersede the live replacement instead",
                ref=str(old),
                superseded_by=row["superseded_by"],
            )

        stamp = now()
        insert = Op(
            "insert_row",
            "plan_rows",
            {
                "table_name": replacement.table,
                "content": json.dumps(replacement.content),
                "provenance": str(replacement.provenance),
                "assumption_kind": replacement.assumption_kind,
                "state": str(replacement.initial_state()),
                "package": replacement.package,
                "supersedes": str(old),
                "created_at": stamp,
            },
        )
        receipt = self.storage.write_atomic([insert], idempotency_key, lease=lease)
        new_ref = RowRef.parse(receipt["results"][0]["ref"])

        stamp_old = Op(
            "update",
            "plan_rows",
            {"superseded_by": str(new_ref), "superseded_at": stamp,
             "state": str(RowState.SUPERSEDED)},
            where={"table_name": old.table, "ordinal": old.ordinal},
        )
        self.storage.write_atomic(
            [stamp_old], f"{idempotency_key}:stamp", lease=lease
        )
        return {"old": old, "new": new_ref, "superseded_at": stamp}

    # --- contracts:13 ---

    def retire_row(
        self, ref: RowRef | str, reason: str, idempotency_key: str, lease=None
    ) -> PlanRow:
        ref = RowRef.coerce(ref)
        row = self._row(ref)
        if row is None:
            raise RowNotFound("no such row", ref=str(ref))
        if row["state"] == RowState.RETIRED:
            raise AlreadyRetired(
                "refused so the audit trail records exactly one retirement",
                ref=str(ref),
                retired_at=row["retired_at"],
            )
        op = Op(
            "update",
            "plan_rows",
            {"state": str(RowState.RETIRED), "retired_at": now(),
             "retire_reason": reason},
            where={"table_name": ref.table, "ordinal": ref.ordinal},
        )
        self.storage.write_atomic([op], idempotency_key, lease=lease)
        return self.get(ref)
