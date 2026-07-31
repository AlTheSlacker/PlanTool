"""Typed errors.

Every error here is named by a contract in the frozen plan (spec/v2/plan.md). The
contract's error name is the class name; its stated behaviour is the docstring. Errors
carry structured detail because the plan repeatedly requires that an error *names* the
offending thing rather than merely failing.

**One amendment to that convention, owner's decision 2026-07-21 (DEFECTS.md F27).** Where a
contract's error name uses retired vocabulary, the retirement wins and the class is renamed.
The frozen plan's spelling is recorded in the class docstring so a reader grepping the plan
still lands here. There is no live instance today: the one there was — `contracts:40`'s
`PartsDontCover`, renamed once already — went with the split in v3 change 1, and
`engine/surface.py`'s `EXCLUDED` records where that contract went.

The reasoning is worth keeping, because the first instinct was to treat this as a standoff
between two rules and preserve the plan's spelling as a quotation. It is not a standoff. This
convention is internal — no protocol, no consumer outside the repo, and the plan's own name
stays findable in one docstring. A rule kept alive at the cost of a live retired word in the
codebase is the carve-out the glossary already rejected once.
"""


class PlanToolError(Exception):
    """Base for every error the engine raises deliberately."""

    def __init__(self, message: str, **detail):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if not self.detail:
            return self.message
        bits = ", ".join(f"{k}={v!r}" for k, v in sorted(self.detail.items()))
        return f"{self.message} ({bits})"


# --- storage-engine (components:1) ---


class StorageUnavailable(PlanToolError):
    """The store cannot be opened or a write exceeded its budget. Fail fast, visibly.

    dep_failure_modes:2 — writes exceeding 30s are treated as unavailable.
    """


class PlanAlreadyExists(PlanToolError):
    """contracts:1 — refuses to overwrite; caller offers resume."""


class NoGoodVersion(PlanToolError):
    """contracts:6 — restore requested but no readable PlanVersion snapshot exists."""


class MigrationFailed(PlanToolError):
    """contracts:8 — pre-migration snapshot restored; silent migration is forbidden."""


# The writer-lock errors (LockHeld, LeaseLost, WriterLockLost) were removed on
# 2026-07-22 with the writer lock itself. See engine/storage.py's module docstring for
# why the lock is gone and why it should not come back.


# --- row-service (components:2) ---


class RowNotFound(PlanToolError):
    """Names the missing ref; nothing written."""


class NotAssumed(PlanToolError):
    """contracts:11 — row is not an open assumption; no write occurs."""


class UpgradeFailed(PlanToolError):
    """contracts:11 — upgrade could not be applied; never a silent duplicate row."""


class AlreadySuperseded(PlanToolError):
    """contracts:12 — lineage is write-once; supersede the live replacement instead."""


class SpikeRequired(PlanToolError):
    """contracts:9 / contracts:12 (D16) — a world-assumption is filed with the spike that
    will attack it, atomically. Raised when a replacement mints a world-assumption with no
    spike, or attaches a spike to a row that is not one; nothing is written."""


class AlreadyRetired(PlanToolError):
    """contracts:13 — refused so the audit trail records exactly one retirement."""


class SupersedeNeedsReason(PlanToolError):
    """contracts:12 — superseding is an act, and an act records why it was performed.

    Added by v3 change 2. Retiring a row already cost a reason and superseding one cost
    nothing, which meant the two exits from "this row is no longer live" were treated
    differently for no recorded reason. The replacement's own `grounds` say why the new
    content is right; they do not say what was wrong with the old, and that is the sentence
    a cold session needs in order not to re-propose the original.
    """


class RetireNeedsReason(PlanToolError):
    """contracts:13 / contracts:11 — a retirement records why, and blank is not why.

    Added by v3 change 2, which settled what a justification is and found the two sites
    that were not checking: `retire_row` accepted a blank reason outright, and
    `resolve_assumption` wrote whitespace into `retire_reason` on a rejection. Six of the
    eight sibling sites already refused a blank; these are now the same.
    """


class RowNotLive(PlanToolError):
    """The row is superseded or retired, and the act attempted needs a live one.

    Names the state as well as the ref: "not live" is two different situations with two
    different repairs, and the caller cannot pick one from a refusal that hides which.
    """


class GroundsAlreadyRecorded(PlanToolError):
    """contracts:9 (v3 D11) — decision context is write-once per field.

    Filling a field that was never recorded is not editing the row's claim; *re-writing*
    one is revising history quietly, which is the one thing this store permits nowhere
    else. Changing an argument therefore goes through supersession, with the audit trail
    that already exists. Same shape as `AlreadySuperseded` — lineage is write-once — and
    it names the field and the alternative, because a refusal that says only "no" is how a
    planner invents a workaround.
    """


class GroundsNeedBoth(PlanToolError):
    """v3 D11 — a row's grounds and its alternatives both end up recorded.

    There is no exemption flag: a row with no alternative writes so, in the field. Allowing
    `alternatives` to stay blank would restore the exemption in the one spelling nobody can
    read — an empty string.
    """


class UnresolvedReference(PlanToolError):
    """A stored text carried a `table:ordinal` that names no row; nothing written.

    Refused at the write because of a mechanism, not a preference: `door.scan` raises
    `BareAddress` on any address in an outgoing payload that is not accompanied by a name,
    and an address naming no row cannot be accompanied by one. Combined with write-once,
    an unresolvable ref inside `grounds` would make that row permanently unreadable through
    the surface, repairable only by superseding a row whose content is fine. The write is
    the one moment when it is still cheap.
    """


class ConflictRequired(PlanToolError):
    """contracts:9 / requirements:27 — a submitted row contradicts a stored row.

    Nothing is filed until a conflict is raised and presented.
    """


class UnreadableRows(PlanToolError):
    """contracts:10 — integrity failure; names unreadable vs surviving rows."""


class InvalidSelector(PlanToolError):
    """contracts:10 — pedagogical error naming the invalid field; nothing read."""


# --- link-graph (components:3) ---


class DanglingRef(PlanToolError):
    """A root or traversed edge references a missing row; signals store inconsistency."""


# --- references (v2 addition, DEVIATIONS.md D3) ---


class SourceNotFound(PlanToolError):
    """Names the missing source."""


class QuoteNotVerified(PlanToolError):
    """The extract's quote is not present in the cited source's stored text.

    This is the invariant that makes the citation system non-hallucinable: an extract
    cannot be written unless its quote is an exact substring of that source's stored
    text. See V2_BUILD_PLAN.md section 5.3.
    """


class SourceTextUnavailable(PlanToolError):
    """The source's full text is not stored, so quotes cannot be verified.

    Refusing is deliberate: an unverifiable extract is exactly the thing the design
    exists to prevent.
    """


# --- revision-service (components:13) ---


class NotFinalized(PlanToolError):
    """contracts:42 — draft plans are edited through the interview; revisions are for
    finalized plans. Distinct from `PlanNotFinalized` (contracts:55, next_task): same
    condition, different contract and different caller advice."""


class RevisionInProgress(PlanToolError):
    """contracts:42 — one revision at a time; names the open revision."""


class RevisionNotFound(PlanToolError):
    """contracts:43 / 45 / 46 / 57 — names the missing revision id."""


class UnadjudicatedItems(PlanToolError):
    """contracts:45 — every repercussion must be adjudicated before apply; names the
    remainder."""


class RevisionAlreadyApplied(PlanToolError):
    """contracts:46 — the frozen spelling is `AlreadyApplied`. Applied revisions roll forward
    via a new revision, never backward."""


class RepercussionOutOfStep(PlanToolError):
    """contracts:57 — the frozen spelling is `InvalidState`. The revision is not in
    walkthrough, or the item is not the current step; state unchanged. Renamed from the
    generic frozen name so it says which invalid state (GLOSSARY policy, DEFECTS.md F27)."""
