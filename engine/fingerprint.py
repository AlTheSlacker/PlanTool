"""The workspace fingerprint: one owner for taking it, and for comparing two of them.

`requirements:73` — when the plan is finalized and at each brief issue, capture a minimal
fingerprint of the workspace and store it as the baseline that resume-time drift detection
(`requirements:59`, `contracts:64`) compares the current workspace against. `findings:10` is
the red-team finding that put it there: drift flags were advertised by a contract with no
entity storing anything to compare against.

**Why this is its own module rather than a method on task-graph.** Capture and comparison are
one piece of knowledge — what counts as the workspace — and splitting them puts the two halves
in different files with nothing holding them to the same field list. Add a field to the capture
and the comparison silently ignores it: the baseline grows a fact nobody checks, and drift
detection reports clean because it never looked. That is the missing-denominator shape
(DEFECTS.md F23/F26) with a two-file gap instead of a two-name one. `compare` derives its
field list from the stored fingerprint itself, so a field added here is compared from the next
capture onward without a second edit.

**Nothing here reads a clock to decide anything.** The fingerprint is a set of facts about the
workspace; the timestamp on the stored row is written by the caller as a record.
"""

from __future__ import annotations

import platform
import sqlite3
from dataclasses import dataclass

from engine.methodology import MethodologyUnavailable, load

#: The storage backend, spelled once. `requirements:73` asks for it by name, and a future
#: backend swap is exactly the drift a resuming planner must be told about.
BACKEND = "sqlite"


def capture(storage) -> dict:
    """The current workspace, as `requirements:73`'s five facts.

    The methodology revision is read here rather than passed in, so that no caller can take a
    baseline that omits it. Journal mode is read from the live connection rather than assumed,
    because it is a property of the file: a database copied off a network share can come back
    in a different mode than it left in, and that changes durability without changing a single
    row.
    """
    handle = storage.plan_handle()
    return {
        "workspace": str(storage.workspace),
        "backend": BACKEND,
        "journal_mode": _journal_mode(storage),
        "methodology_revision": _methodology_revision(),
        "plan_version": handle.get("version"),
        "schema_version": handle.get("schema_version"),
        "toolchain": {
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
        },
    }


def _methodology_revision() -> str | None:
    """The content-revision stamp of the methodology in force.

    `requirements:71` makes the revision a shipped property of the assets, and a plan whose
    methodology changed under it has drifted in a way no file timestamp would show.
    """
    try:
        return load().revision_stamp
    except MethodologyUnavailable:  # pragma: no cover — assets missing is its own error
        return None


def _journal_mode(storage) -> str | None:
    try:
        row = storage.conn.execute("PRAGMA journal_mode").fetchone()
    except sqlite3.Error:  # pragma: no cover — an unreadable pragma is a dead store
        return None
    return row[0] if row else None


@dataclass(frozen=True, slots=True)
class DriftFlag:
    """One fact that changed between the baseline and now."""

    field: str
    was: object
    now: object

    def present(self) -> str:
        return f"{self.field}: was {self.was!r}, now {self.now!r}"


def compare(baseline: dict, current: dict) -> list[DriftFlag]:
    """Every field of the baseline whose value has moved.

    Iterating the *baseline* rather than the current fingerprint is deliberate: a field the
    baseline never carried cannot have drifted, because there is nothing to have drifted from.
    Reporting it as a change would make every old baseline look drifted the moment a new field
    is added here, which trains a reader to ignore the flags.
    """
    return [
        DriftFlag(field=field, was=was, now=current.get(field))
        for field, was in sorted(baseline.items())
        if current.get(field) != was
    ]
