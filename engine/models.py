"""Value types crossing component boundaries.

Names follow the frozen plan's contract signatures (spec/v2/plan.md). Where the plan
names a type but does not specify its fields, the shape is invented here and the
insufficiency is logged in spec/v2/DEFECTS.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

REF_PATTERN = re.compile(r"^([a-z][a-z0-9_]*):([1-9][0-9]*)$")


class Provenance(StrEnum):
    """requirements:5 — every row persists its provenance."""

    DECIDED = "decided"
    DERIVED = "derived"
    ASSUMED = "assumed"


class RowState(StrEnum):
    """state_machines:2 — the PlanRow lifecycle."""

    ASSUMED = "assumed"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class PlanState(StrEnum):
    """state_machines:1 — the Plan lifecycle."""

    DRAFT = "draft"
    FINALIZED = "finalized"
    IMPLEMENTING = "implementing"
    REVISING = "revising"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class RowRef:
    """A stable reference of the form `table:ordinal`, e.g. `requirements:61`.

    Ordinals are per-table and 1-based, matching the frozen plan's own referencing
    scheme so a v2 plan reads the same way spec/v2/plan.md does.
    """

    table: str
    ordinal: int

    @classmethod
    def parse(cls, text: str) -> RowRef:
        match = REF_PATTERN.match(text.strip())
        if not match:
            raise ValueError(
                f"malformed ref {text!r}; expected 'table:ordinal', e.g. 'requirements:61'"
            )
        return cls(match.group(1), int(match.group(2)))

    @classmethod
    def coerce(cls, value: RowRef | str) -> RowRef:
        return value if isinstance(value, cls) else cls.parse(value)

    def __str__(self) -> str:
        return f"{self.table}:{self.ordinal}"


#: The closed set of edge types, with what each one asserts. `links` table's column
#: defaults to `links`, so an unknown edge type does not fail loudly — it silently
#: produces an edge no traversal looks for, which is F20 and F24's failure mode arriving
#: by typo instead of by omission.
#:
#: `belongs_to` is deliberately ONE name for every containment relation. v1 had seven
#: distinct parent foreign keys (`use_case_id`, `step_id`, `entity_id`, `machine_id`,
#: `dep_id`, `component_id`, …) that all asserted the same thing — *this row's owning
#: parent* — and seven names for one relation is the disease `GLOSSARY.md` exists to
#: prevent. The parent's row type disambiguates: `uc_steps:4 belongs_to use_cases:2`
#: needs no second edge name to be unambiguous.
EDGE_TYPES = {
    "links": "untyped association; the source row cites the target as related",
    "belongs_to": "the target is this row's owning parent (containment)",
    "depends_on": "D11 — consumer to provider; the target must be built first",
    "cites": "the source row's prose quotes or references the target",
    "contradicts": "the source row makes a claim incompatible with the target's",
}


@dataclass(frozen=True, slots=True)
class LinkSpec:
    """An outbound typed edge declared by a row at submission time.

    entities:15 — links are immutable and owned by their source row; they are created
    as part of row submission and never mutated.

    `target` may be a RowRef to an already-stored row, or an int index into the batch
    currently being submitted, for rows that link to their own siblings. The frozen
    plan says links are created "as part of row submission" (crud_grid:57) but never
    says how a row references a sibling whose ref does not exist yet — see DEFECTS.md
    F5.
    """

    target: RowRef | int
    edge_type: str = "links"

    @property
    def is_intra_batch(self) -> bool:
        return isinstance(self.target, int)


@dataclass(frozen=True, slots=True)
class SpikeSpec:
    """contracts:29 — question, hypothesis, method against the real dependency, budget.

    All four are mandatory. A spike with no hypothesis cannot be refuted, and one with
    no budget is the open-ended investigation the spike mechanism exists to bound.

    It lives here, beside RowSubmission, because D16 makes filing a world-assumption and
    registering its spike one act: a world-assumption submission carries its spike, so the
    two shapes cross the same boundary together. validation-service still owns the spike
    lifecycle and re-exports this name.
    """

    question: str
    hypothesis: str
    method: str
    budget: str


def content_fingerprint(content: dict[str, Any]) -> str:
    """The fingerprint a row's name was given for (M6_PLAN.md §6.6).

    Key-order-independent, so re-serialising an unchanged dict does not read as a change
    and demand a pointless re-naming — a check that fires when nothing happened is a check
    people learn to click through.
    """
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class RowSubmission:
    """One row offered to submit_rows (contracts:9).

    `name` is required and has no default. M6_PLAN.md §6: a row is addressed as
    `table:ordinal`, and an address on its own forces the reader to go and look it up —
    which a person does not do, and which a model answers by inventing something
    plausible. The name is what the tool says; the address is detail beside it.
    """

    table: str
    content: dict[str, Any]
    name: str
    provenance: Provenance = Provenance.DECIDED
    assumption_kind: str | None = None
    links: list[LinkSpec] = field(default_factory=list)
    package: int | None = None
    #: D16 — a world-assumption is filed WITH the spike that will attack it, in one
    #: atomic act, so unbacked becomes unrepresentable rather than caught five packages
    #: later. Required on a world-assumption, forbidden on anything else (a spike resolves
    #: world-assumptions only). row-service writes it into the spikes table in the same
    #: transaction, borrowing the just-assigned row ref.
    spike: SpikeSpec | None = None

    def initial_state(self) -> RowState:
        return (
            RowState.ASSUMED
            if self.provenance is Provenance.ASSUMED
            else RowState.ACTIVE
        )


@dataclass(frozen=True, slots=True)
class PlanRow:
    """A stored content row (entities:2)."""

    ref: RowRef
    content: dict[str, Any]
    name: str
    provenance: Provenance
    state: RowState
    created_at: str
    assumption_kind: str | None = None
    package: int | None = None
    supersedes: RowRef | None = None
    superseded_by: RowRef | None = None
    superseded_at: str | None = None
    retired_at: str | None = None
    retire_reason: str | None = None
    links: tuple[LinkSpec, ...] = ()

    @property
    def is_live(self) -> bool:
        """requirements:61 — liveness is the single check that superseded_by is null
        and the row is not retired."""
        return self.superseded_by is None and self.state is not RowState.RETIRED

    @property
    def updated_at(self) -> str:
        """When this row last changed — **derived, never stored** (owner, 2026-07-21).

        A planning row is immutable: `requirements:61` says content is never edited, and
        changing your mind writes a *new* row and stamps this one `superseded_at`. A stored
        `updated_at` here would therefore equal `created_at` forever — a column that promises
        change and cannot deliver it — and would be a second source of truth for something
        `superseded_at` already records. That is D10's argument for derived readiness, applied
        to time: the two copies drift precisely when the row is revised, which is the only
        moment either one matters.

        So the last change to *this row* is when it was superseded or retired, and if neither
        has happened, when it was created. For "what became of the thing I said yesterday",
        walk the lineage to its live head — `RowService.lineage_head` — and read that row's
        `created_at`. The question "when did I last touch this decision" is a question about a
        *lineage*, not about a row, and answering it from a column on one row is what would
        make it wrong.
        """
        return self.retired_at or self.superseded_at or self.created_at


@dataclass(frozen=True, slots=True)
class RowVerdict:
    """contracts:9 — per-row accept/reject naming the specific problem.

    requirements:14 — a failing row is rejected alone; accepted rows stand.
    """

    index: int
    accepted: bool
    ref: RowRef | None = None
    problem: str | None = None
    #: Advice the row was filed *with* — a retired word it used, and what to say instead.
    #: Separate from `problem` because the two have opposite consequences: a problem is why
    #: nothing was filed, and a note rides along with a row that stands. Warn-don't-block is
    #: the only tenable rule here, since a retired word inside a quotation is legitimate and
    #: refusing one would put the tool in the business of editing the owner's words.
    note: str | None = None


@dataclass(frozen=True, slots=True)
class BatchReceipt:
    """contracts:2 — replaying an idempotency_key returns the original receipt."""

    idempotency_key: str
    verdicts: tuple[RowVerdict, ...]
    written_at: str
    replayed: bool = False


@dataclass(slots=True)
class RowSelector:
    """contracts:10 — by ids | table | package | provenance | liveness | link-neighborhood.

    Paginated, because requirements:62 forbids a full-plan dump as the default read
    path. The plan names the selector's dimensions but not its field shapes; this
    structure is invented (DEFECTS.md F3).
    """

    ids: list[RowRef] | None = None
    table: str | None = None
    package: int | None = None
    provenance: Provenance | None = None
    live_only: bool = False
    neighbourhood_of: RowRef | None = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True, slots=True)
class RowPage:
    """contracts:10 — a page of full row contents plus its continuation state."""

    rows: tuple[PlanRow, ...]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.rows) < self.total


@dataclass(slots=True)
class TraversalSpec:
    """contracts:14 — edge types + direction + depth."""

    edge_types: list[str] | None = None
    direction: str = "both"  # out | in | both
    depth: int = -1  # -1 = unbounded

    def validate(self) -> None:
        if self.direction not in ("out", "in", "both"):
            raise ValueError(
                f"direction must be out|in|both, got {self.direction!r}"
            )


@dataclass(frozen=True, slots=True)
class Closure:
    """contracts:14 — every row reachable from roots via the defined traversal."""

    roots: tuple[RowRef, ...]
    reached: tuple[RowRef, ...]
    depth_of: dict[str, int]


# --- revision-service (components:13), state_machines:10 ---
#
# The frozen plan names these types in the revision contracts but does not give their fields;
# the shapes are settled here and in M7_PLAN.md. Two owner decisions (2026-07-23) shape them,
# both logged as deviations: changes apply live once conflict-checked rather than being held to
# a single deferred apply (D25), and abandon is a confirmed rewind to the opening snapshot (D26).


class Disposition(StrEnum):
    """contracts:57 — how the owner adjudicates a repercussion."""

    ACCEPT = "accept"
    MODIFY = "modify"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class ChangeRequest:
    """contracts:42 — what the owner wants changed and why.

    `targets` are the live rows the change touches; they seed the link-graph impact walk.
    `intent` is the owner's own words, recorded verbatim against the revision.
    """

    targets: tuple[RowRef, ...]
    intent: str


@dataclass(frozen=True, slots=True)
class OwnerDecision:
    """contracts:57 — accept | modify | defer, with the owner's words.

    A `modify` carries the full `replacement` row the owner wants the affected row superseded
    by (a real `RowSubmission`, so the existing supersession and validation machinery applies).
    The tool never writes the wording — it checks the affected row for an open conflict and, if
    none is shown, supersedes the row live (D25). `words` is the owner's rationale, recorded
    against the repercussion whatever the disposition.
    """

    disposition: Disposition
    words: str
    replacement: RowSubmission | None = None


@dataclass(frozen=True, slots=True)
class Repercussion:
    """contracts:43 — one ripple the owner must decide on.

    Enumerated once at open time and never recomputed (the frozen denominator, F26). `kind`
    distinguishes a directly-targeted row, a transitively-affected row, and a resurfaced
    accepted-risk or suppressed warning (requirements:55).
    """

    id: int
    position: int
    kind: str
    advice: str
    row: RowRef | None = None
    finding: RowRef | None = None
    warning_id: int | None = None
    disposition: Disposition | None = None


@dataclass(frozen=True, slots=True)
class WalkthroughComplete:
    """contracts:43 — the walkthrough has no more repercussions to present."""

    revision_id: int
    total: int


@dataclass(frozen=True, slots=True)
class Revision:
    """entities:10 — an owner-initiated change to a finalized plan.

    Born in `walkthrough` because impact analysis is synchronous (D27); `proposed`
    and `analyzing` are passed through inside `open_revision` and never persisted.
    """

    id: int
    intent: str
    from_version: int
    to_version: int
    state: str
    repercussion_count: int


@dataclass(frozen=True, slots=True)
class StagedChange:
    """contracts:57 — the recorded adjudication.

    Named `StagedChange` after the frozen contract, but under D25 an accepted `modify` is
    already live: `applied` names the superseding row it produced. A `modify` whose wording
    conflicts is not applied — `held_conflict` names the conflict blocking it, and the
    repercussion stays unadjudicated until the owner resolves it.
    """

    repercussion_id: int
    disposition: Disposition
    applied: RowRef | None = None
    held_conflict: int | None = None


@dataclass(frozen=True, slots=True)
class RevisionResult:
    """contracts:45 — revision applied and closed; the plan's new version is live."""

    revision_id: int
    version: int
    applied: tuple[RowRef, ...]


@dataclass(frozen=True, slots=True)
class RewindPreview:
    """abandon_revision, unconfirmed (D26) — what a confirmed rewind would revert.

    A pure read: it mutates nothing. The owner confirms to rewind or steps back to keep the
    revision open.
    """

    revision_id: int
    reverts: tuple[RowRef, ...]
    restores_version: int


@dataclass(frozen=True, slots=True)
class RollbackReport:
    """contracts:46 — plan rewound cleanly to its pre-change version.

    The analysis record (the revision and its repercussions) survives the rewind because it
    lives outside the plan-row snapshot (requirements:72).
    """

    revision_id: int
    restored_version: int
    reverted: tuple[RowRef, ...]

