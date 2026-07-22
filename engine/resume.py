"""session-service (`components:14`) — the resume surface.

Contracts: `contracts:48` journal_note, `contracts:49` set_next_action, `contracts:64`
plan_status.

**The module is `resume`, not `sessions`.** `GLOSSARY.md` retires `session` as an identifier
outright — it names no entity, has no table and no lifecycle, and its last occurrence in the
data went out with the writer lock. The frozen plan's `session-service` is the read-only
spelling, recorded here so a reader grepping the plan lands in the right file. This is the
same call as `contracts:40`'s `PartsDontCover` becoming `ObligationsNotCovered`: the
retirement beats the quotation for identifiers, and the quotation survives in prose.

**What this component is for.** A planner's context is disposable and dies without warning;
the database is the source of truth. `plan_status` is the one call a cold planner makes to
find out where the work got to, and `journal_note` / `set_next_action` are what an outgoing
planner leaves behind so that call has something true to say.

Three rules shape the digest, and each of them is a defect countermeasure rather than a
preference:

  **It carries no document text.** The mandate and the current package script are named,
  never included (DEVIATIONS.md **D17**). They need to reach a planner once, and only the
  caller knows whether they already have. `requirements:62` is the row that agrees: a full
  dump is never the default rehydration path.

  **Every count names the call that fetches what it counts, and the digest closes by naming
  the next action** (D17 again). A bare number invites a reader to reason about it — *only
  three warnings, that's fine* — instead of reading what it stands for, and a tidy summary
  with no instruction invites an invented next step. Both end the same way: a planner reads
  the digest, feels informed, fetches nothing, and proceeds on a summary. That is F14's shape.

  **An absent baseline is reported as absent, never as "no drift".** The workspace fingerprint
  is captured at finalization and at each brief issue (`requirements:73`), so for the whole
  planning phase there is nothing to compare against. Returning an empty flag list there would
  be a check that ran, found nothing and meant nothing, and a reader could not tell "the
  workspace has not changed" from "nothing ever recorded what it looked like".
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from engine.clock import now
from engine.errors import PlanToolError
from engine.fingerprint import DriftFlag, capture, compare
from engine.idempotency import key
from engine.models import RowRef
from engine.storage import Op, Storage

#: `requirements:69` — the workspace path shapes that mean a network mount. Purely lexical:
#: a UNC path, or a drive letter Windows maps to a share. The tool never probes the network
#: to find out, both because a probe is slow at exactly the wrong moment and because a
#: warning about durability must not itself depend on the storage being reachable.
UNC_PREFIXES = ("\\\\", "//")


class NoPlanFound(PlanToolError):
    """contracts:64 — no plan in this workspace, said plainly so the caller can offer to
    start one (uc_extensions:5)."""


class PlanCorrupt(PlanToolError):
    """contracts:64 — integrity failed on open; carries the report and routes to recovery.
    Never answers from partial state (requirements:11)."""


@dataclass(frozen=True, slots=True)
class Fetch:
    """A count and the call that turns it into content.

    The pairing is the point (D17). `Fetch` exists as a type rather than as a convention so
    that a count with no fetching call cannot be added to the digest by accident — there is
    nowhere to put it.
    """

    label: str
    call: str
    #: `None` means this is a reference to one named thing rather than a count of many —
    #: the mandate and the current package script, which are pointed at rather than counted.
    count: int | None = None

    def present(self) -> str:
        if self.count is None:
            return f"{self.label} — {self.call}"
        noun = self.label if self.count == 1 else f"{self.label}s"
        return f"{self.count} {noun} — {self.call}"


@dataclass(frozen=True, slots=True)
class JournalNote:
    """contracts:48 — a timestamped informal learning that is not a formal plan row."""

    id: int
    package: int
    note: str
    created_at: str
    task_ref: RowRef | None = None

    def present(self) -> str:
        where = f" [{self.task_ref}]" if self.task_ref else ""
        return f"{self.created_at}{where} {self.note}"


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """contracts:49 — the next intended action, which is the resume point."""

    id: int
    intent: str
    created_at: str


@dataclass(frozen=True, slots=True)
class GateRun:
    """One recorded gate verdict (DEFECTS.md F30)."""

    package: int
    passed: bool
    hole_count: int
    warning_count: int
    created_at: str

    def present(self) -> str:
        verdict = "passed" if self.passed else f"failed on {self.hole_count} holes"
        return f"package {self.package} {verdict} at {self.created_at}"


@dataclass(frozen=True, slots=True)
class Drift:
    """`requirements:59` — what the workspace looks like against its recorded baseline.

    `baseline_occasion` is `None` when no fingerprint has ever been captured, which is the
    normal state throughout planning and is reported as its own answer rather than as an empty
    list of flags.
    """

    baseline_occasion: str | None
    baseline_at: str | None
    flags: tuple[DriftFlag, ...] = ()

    @property
    def state(self) -> str:
        if self.baseline_occasion is None:
            return "no_baseline"
        return "drifted" if self.flags else "unchanged"

    def present(self) -> str:
        if self.baseline_occasion is None:
            return (
                "workspace drift: no baseline yet — one is captured at finalization and at "
                "each brief issue, so nothing has been recorded to compare against"
            )
        if not self.flags:
            return (
                f"workspace drift: none against the {self.baseline_occasion} baseline of "
                f"{self.baseline_at}"
            )
        changes = "; ".join(f.present() for f in self.flags)
        return (
            f"workspace drift against the {self.baseline_occasion} baseline of "
            f"{self.baseline_at}: {changes}"
        )


@dataclass(frozen=True, slots=True)
class PlanStatus:
    """contracts:64 — the compact digest a cold planner resumes from."""

    name: str
    tier: str
    state: str
    version: int
    package: int
    package_name: str
    methodology_revision: str
    mandate: Fetch
    script: Fetch
    gate_history: tuple[GateRun, ...]
    earlier_gate_runs: Fetch
    warnings: tuple[str, ...]
    gaps: Fetch
    journal: tuple[JournalNote, ...]
    earlier_journal: Fetch
    next_action: str
    next_action_source: str
    drift: Drift
    advisories: tuple[str, ...] = ()

    def present(self) -> str:
        """The digest as text, which is what an agent surface actually serves.

        Rendering lives with the data rather than in the caller so that the closing
        next-action line cannot be dropped by a surface that renders its own view — it is
        part of the digest, not decoration around it.
        """
        lines = [
            f"Plan '{self.name}' ({self.tier}), {self.state}, version {self.version}",
            f"Package {self.package} — {self.package_name} "
            f"(methodology {self.methodology_revision})",
            self.mandate.present(),
            self.script.present(),
        ]
        if self.gate_history:
            lines.append(
                "Gate history, latest per package: "
                + "; ".join(g.present() for g in self.gate_history)
            )
        else:
            lines.append("Gate history: no gate has been run yet")
        if self.earlier_gate_runs.count:
            lines.append(self.earlier_gate_runs.present())
        if self.warnings:
            noun = "warning" if len(self.warnings) == 1 else "warnings"
            lines.append(f"{len(self.warnings)} active {noun}:")
            lines.extend(f"  - {w}" for w in self.warnings)
        else:
            lines.append("No active warnings")
        lines.append(self.gaps.present())
        if self.journal:
            lines.append(f"Journal, this package ({len(self.journal)}):")
            lines.extend(f"  - {n.present()}" for n in self.journal)
        if self.earlier_journal.count:
            lines.append(self.earlier_journal.present())
        lines.append(self.drift.present())
        lines.extend(self.advisories)
        lines.append(f"Next action ({self.next_action_source}): {self.next_action}")
        return "\n".join(lines)


class ResumeService:
    """session-service (`components:14`)."""

    def __init__(self, storage: Storage, gaps, warnings, guidance):
        self.storage = storage
        self.gaps = gaps
        self.warnings = warnings
        self.guidance = guidance

    # --- contracts:48 ---

    def journal_note(self, note: str, task: RowRef | str | None = None) -> JournalNote:
        """Record an informal learning, durably, at the moment it arises.

        `requirements:56`/`60` — never batched to the end of a planner's life, because the
        whole premise is that the planner's life ends without warning. One row, one write.

        The note is stamped with the package current when it was written, and that is what
        later bounds the digest to the working set (`requirements:62`) instead of to the
        whole history of the plan.

        **The key is the note itself, not a counter.** The first version of this method keyed
        on the number of notes already written, which made every call a new operation and the
        key incapable of ever detecting a repeat — F29 exactly, reproduced in the module
        written the same afternoon as its defect entry, and caught by the driver rather than
        by the author. The question a key answers is *is this the same act?*, and the same
        learning filed twice against the same package and task is one act reported twice, not
        two learnings. A planner who genuinely wants the same sentence recorded again has
        learned something at a different moment, which means a different package, a different
        task, or different words.
        """
        text = note.strip()
        if not text:
            raise PlanToolError("a journal note with no text records nothing")
        package = self.gaps.current_package()
        task_ref = RowRef.coerce(task) if task is not None else None
        receipt = self.storage.write_atomic(
            [Op("insert", "journal_notes", {
                "package": package,
                "note": text,
                "task_ref": str(task_ref) if task_ref else None,
                "created_at": now(),
            })],
            key("journal_note", package, task_ref, text),
        )
        return self._note_from(receipt)

    # --- contracts:49 ---

    def set_next_action(self, intent: str) -> Checkpoint:
        """Record what the planner means to do next — the resume point (`requirements:58`).

        Append-only. Overwriting would lose the record of what successive planners intended,
        which is the only evidence of a plan going round in circles.
        """
        text = intent.strip()
        if not text:
            raise PlanToolError(
                "a next action with no text leaves the next planner nothing to resume from"
            )
        receipt = self.storage.write_atomic(
            [Op("insert", "checkpoints", {"intent": text, "created_at": now()})],
            key("set_next_action", text),
        )
        return self._checkpoint_by_id(receipt["results"][0]["id"])

    # --- contracts:64 ---

    def plan_status(self) -> PlanStatus:
        """The compact digest a cold planner resumes from."""
        if not self.storage.exists():
            raise NoPlanFound(
                "no plan in this workspace; start one with init_plan",
                workspace=str(self.storage.workspace),
            )
        try:
            handle = self.storage.plan_handle()
        except PlanToolError as exc:
            raise NoPlanFound(
                "no plan in this workspace; start one with init_plan",
                workspace=str(self.storage.workspace),
            ) from exc

        integrity = self.storage.integrity_check()
        if integrity.unreadable:
            raise PlanCorrupt(
                "integrity check failed on open; recover before resuming — a digest built "
                "from partial state is worse than no digest (requirements:11)",
                unreadable=list(integrity.unreadable),
            )

        package = self.gaps.current_package()
        script = self.guidance.get_package_script(package)
        open_gaps = self.gaps.open_gaps()
        notes, earlier = self._journal(package)
        latest_gates, earlier_gates = self._gate_history()
        next_action, source = self._next_action(open_gaps)

        return PlanStatus(
            name=handle["name"],
            tier=handle["tier"],
            state=handle["state"],
            version=handle["version"],
            package=package,
            package_name=script.name,
            methodology_revision=script.revision_stamp,
            mandate=Fetch("the engineer's mandate", "get_mandate()"),
            script=Fetch(
                f"the script for package {package}", f"get_package_script({package})"
            ),
            gate_history=latest_gates,
            earlier_gate_runs=earlier_gates,
            warnings=tuple(w.present() for w in self.warnings.active_warnings()),
            gaps=Fetch("open gap", "next_gaps()", len(open_gaps)),
            journal=notes,
            earlier_journal=earlier,
            next_action=next_action,
            next_action_source=source,
            drift=self.drift(),
            advisories=self._advisories(),
        )

    # --- requirements:59 / requirements:73 ---

    def drift(self) -> Drift:
        """The current workspace against its most recent recorded baseline."""
        found = self.storage.query(
            "SELECT * FROM workspace_fingerprints ORDER BY id DESC LIMIT 1"
        )
        if not found:
            return Drift(baseline_occasion=None, baseline_at=None)
        record = dict(found[0])
        flags = compare(json.loads(record["fingerprint"]), capture(self.storage))
        return Drift(
            baseline_occasion=record["occasion"],
            baseline_at=record["created_at"],
            flags=tuple(flags),
        )

    # --- reads ---

    def journal(self, package: int | None = None) -> list[JournalNote]:
        """Journal notes, newest last. `package=None` is the whole journal — the call the
        digest's earlier-notes count points at."""
        sql = "SELECT * FROM journal_notes"
        params: tuple = ()
        if package is not None:
            sql += " WHERE package = ?"
            params = (package,)
        return [self._build_note(dict(r)) for r in self.storage.query(sql + " ORDER BY id", params)]

    def checkpoints(self) -> list[Checkpoint]:
        return [
            Checkpoint(id=r["id"], intent=r["intent"], created_at=r["created_at"])
            for r in self.storage.query("SELECT * FROM checkpoints ORDER BY id")
        ]

    # --- internals ---

    def _journal(self, package: int) -> tuple[tuple[JournalNote, ...], Fetch]:
        """This package's notes by value; everything older as a count and a call.

        The denominator, stated because check 3 of the pre-build audit demands it: the set is
        *notes stamped with the current package*, it comes from `journal_notes.package`
        written at the moment each note was recorded, and it is fixed at read time. Read-time
        is correct here and wrong in a brief (F26): a status view reports where the plan *is*,
        while a brief's accounting must not move under the work it measures.
        """
        current = tuple(self.journal(package))
        total = self._count("journal_notes")
        return current, Fetch(
            "earlier journal note", "journal()", total - len(current)
        )

    def _next_action(self, open_gaps) -> tuple[str, str]:
        """The digest's closing sentence.

        `uc_extensions:48` names the fallback: absent a recorded intent, resume falls back to
        the last completed journal entry plus open gaps. The fallback still produces a
        sentence naming a call — an honest "nobody said" must not become no instruction, or
        the next planner invents one.
        """
        checkpoint = self._live_checkpoint()
        if checkpoint is not None:
            return checkpoint.intent, "recorded"
        last = self.journal()
        if open_gaps:
            tail = f" Last recorded: {last[-1].note}" if last else ""
            return (
                f"No next action was recorded. {len(open_gaps)} gaps are open — call "
                f"next_gaps() and work the first cluster.{tail}"
            ), "derived"
        if last:
            return (
                f"No next action was recorded and no gaps are open. Last journal entry: "
                f"{last[-1].note}. Call run_gate() for the current package."
            ), "derived"
        return (
            "Nothing has been recorded in this plan yet. Call get_package_script() and "
            "begin the interview."
        ), "derived"

    def _advisories(self) -> tuple[str, ...]:
        """`requirements:69` — the network-mount durability warning.

        Lexical detection only: the tool never touches the network to decide whether to warn
        about the network.
        """
        path = str(self.storage.workspace)
        if path.startswith(UNC_PREFIXES):
            return (
                "advisory: this workspace is on a network mount. Machine-crash durability "
                "is untested there — spike 1 found synchronous=FULL absorbed by client and "
                "NAS caching, with commit p50 near 0 ms (requirements:69).",
            )
        return ()

    def _gate_history(self) -> tuple[tuple[GateRun, ...], Fetch]:
        """The newest verdict for each package, and a count of every earlier run.

        The denominator again: a gate can be re-run any number of times, so the full history
        grows without bound and putting all of it in the digest would break the compactness
        `requirements:62` requires — the same problem as the journal, and it only became
        visible when the driver printed one package's verdict twice. What a resuming planner
        needs is *where each package stands*; what happened on the way there is history, and
        history is fetched.
        """
        runs = self.gate_runs()
        latest: dict[int, GateRun] = {}
        for run in runs:
            latest[run.package] = run
        newest = tuple(latest[p] for p in sorted(latest))
        return newest, Fetch(
            "earlier gate run", "gate_runs()", len(runs) - len(newest)
        )

    def gate_runs(self) -> list[GateRun]:
        """Every recorded gate verdict, oldest first (DEFECTS.md F30)."""
        return [
            GateRun(
                package=r["package"],
                passed=bool(r["passed"]),
                hole_count=r["hole_count"],
                warning_count=r["warning_count"],
                created_at=r["created_at"],
            )
            for r in self.storage.query("SELECT * FROM gate_runs ORDER BY id")
        ]

    def _count(self, table: str) -> int:
        return self.storage.query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]

    def _live_checkpoint(self) -> Checkpoint | None:
        """The newest recorded intent, or None if no planner ever left one."""
        found = self.storage.query("SELECT * FROM checkpoints ORDER BY id DESC LIMIT 1")
        return self._as_checkpoint(dict(found[0])) if found else None

    def _checkpoint_by_id(self, checkpoint_id: int) -> Checkpoint:
        found = self.storage.query(
            "SELECT * FROM checkpoints WHERE id = ?", (checkpoint_id,)
        )
        if not found:  # pragma: no cover — the write just landed
            raise PlanToolError("checkpoint vanished after write", id=checkpoint_id)
        return self._as_checkpoint(dict(found[0]))

    @staticmethod
    def _as_checkpoint(record: dict) -> Checkpoint:
        return Checkpoint(
            id=record["id"], intent=record["intent"], created_at=record["created_at"]
        )

    def _note_from(self, receipt: dict) -> JournalNote:
        """The note this write created, read by id off the receipt.

        Not "the newest row": on a replay no op runs, and the newest row would be whatever
        happened to be written since. Reading the id from the receipt is the fix F29 applied
        to `compose_brief` and `attach`, where exactly that shortcut had never once run
        because no key had ever repeated.
        """
        note_id = receipt["results"][0]["id"]
        found = self.storage.query(
            "SELECT * FROM journal_notes WHERE id = ?", (note_id,)
        )
        if not found:  # pragma: no cover — the write just landed
            raise PlanToolError("journal note vanished after write", id=note_id)
        return self._build_note(dict(found[0]))

    @staticmethod
    def _build_note(record: dict) -> JournalNote:
        return JournalNote(
            id=record["id"],
            package=record["package"],
            note=record["note"],
            created_at=record["created_at"],
            task_ref=RowRef.parse(record["task_ref"]) if record["task_ref"] else None,
        )
