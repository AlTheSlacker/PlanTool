"""Typed errors.

Every error here is named by a contract in the frozen plan (spec/v2/plan.md). The
contract's error name is the class name; its stated behaviour is the docstring. Errors
carry structured detail because the plan repeatedly requires that an error *names* the
offending thing rather than merely failing.

**One amendment to that convention, owner's decision 2026-07-21 (DEFECTS.md F27).** Where a
contract's error name uses retired vocabulary, `GLOSSARY.md` wins and the class is renamed.
The frozen plan's spelling is recorded in the class docstring so a reader grepping the plan
still lands here. Known instance: `contracts:40`'s `PartsDontCover` is
`engine.briefs.ObligationsNotCovered`.

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


class AlreadyRetired(PlanToolError):
    """contracts:13 — refused so the audit trail records exactly one retirement."""


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
