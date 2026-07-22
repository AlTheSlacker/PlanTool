"""The plan as a document a person reads.

The last planning package ends by rendering the plan and skimming it **with the owner**.
That skim is the last cheap moment for a "that is not what I meant" catch: everything after
it costs a revision. Reading the plan back one paginated call at a time is not the same act
— nobody catches a contradiction between package 2 and package 6 by paging.

**Why this exists when rendering was scoped out.** The charter cut plan extraction, and it
was right about the thing it cut: a round-trippable bundle you could edit outside the tool
and import back is a second write path into the plan, and every invariant this engine holds
— provenance, supersession, containment, naming — lives on the write path. So there is no
bundle and no import. What is built here is one direction only: live rows out, formatted,
into a file. The database stays the only source of truth, and the file is a photograph of it.

**Two properties follow from that, and both are deliberate.**

*The document is written to disk and never returned into a planner's context.*
`requirements:62` says a full-plan dump is never the rehydration path, and a tool that
handed back the whole plan as a string would be exactly that with a different name. The
receipt is small: where the file went and what went into it. The owner opens the file; the
planner keeps reading through `read_rows`.

*The document is derived, never authoritative.* It carries the plan's version and the moment
it was written for one reason — so that a reader holding an old copy can tell. Anything wrong
in it is fixed in the rows and re-rendered, never by editing the file, and the script says so
to the owner in those words.

**Addresses are annotated, not rewritten** — the same rule as the door (DEVIATIONS D19). A
row's stored prose citing `contracts:52` is the owner's text and is served as written; the
resolution goes in a *cites* line beneath it. That is also where F17 becomes something the
owner can see: a citation whose row was superseded resolves to a name and a state, and one
pointing at nothing at all says so, in the one artefact he actually reads end to end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.clock import now
from engine.door import Resolution, collect, label, resolver_from
from engine.errors import PlanToolError
from engine.models import PlanRow, RowRef, RowSelector

#: The rendered document's name in the workspace, beside `plan.db`. Fixed rather than a
#: parameter: the owner is told in the package script to open `plan.md`, and a name the
#: caller chooses is a name the script cannot state.
RENDER_FILENAME = "plan.md"

#: How many rows one read takes. The render is the one caller that legitimately wants every
#: live row, so it pages rather than asking for an unbounded set — `read_rows` is paginated
#: on purpose and a caller that works around that has re-introduced what it forbids.
PAGE = 200


class RenderFailed(PlanToolError):
    """The document could not be written.

    A render that half-wrote a file and reported success would be worse than one that
    refused: the owner would skim a truncated plan and certify it.
    """


@dataclass(frozen=True, slots=True)
class RenderReceipt:
    """What was written, and out of what.

    Not the document. A caller that wants the text opens the file; a caller that wants the
    rows calls `read_rows`. This says only enough to know the render happened and matched
    the plan the caller thought it was rendering.
    """

    path: str
    plan_name: str
    plan_state: str
    plan_version: int
    live_rows: int
    tables: dict[str, int] = field(default_factory=dict)
    written_at: str = ""
    #: Citations in stored prose that no longer reach a live row (F17). Surfaced on the
    #: receipt as well as in the document, because the planner reads one and the owner reads
    #: the other. Written in the door's display form — the tool composed this list, so it
    #: says what the address failed to reach rather than leaving a bare address to be
    #: resolved somewhere else in the payload.
    dead_citations: tuple[str, ...] = ()

    def present(self) -> str:
        """The one line the surface composes itself, so it is held to the strict door."""
        tables = f"{len(self.tables)} table" + ("" if len(self.tables) == 1 else "s")
        dead = (
            "" if not self.dead_citations
            else f"; {len(self.dead_citations)} citation(s) no longer reach a live row"
        )
        return (
            f"{RENDER_FILENAME} written from {self.live_rows} live rows across "
            f"{tables}{dead}. Read it with the owner; fix anything wrong in the rows and "
            f"render again."
        )


class PlanRender:
    """Renders the live plan into the workspace. Reads only."""

    def __init__(self, storage, rows, findings=None):
        self.storage = storage
        self.rows = rows
        #: So that a `findings:3` in the owner's prose resolves to the finding rather than
        #: reading as a dead citation. Findings live in their own store (D22); the address
        #: space is shared and the resolver is what shares it.
        self.findings = findings

    # --- the deviation's contract ---

    def render_plan(self) -> RenderReceipt:
        """Write `plan.md` from the live rows and report what went into it."""
        handle = self.storage.plan_handle()
        resolve = resolver_from(self.rows, self.findings)
        live = self._live_rows()

        cites: list[Resolution] = []
        body = self._document(handle, live, resolve, cites)

        path = Path(self.storage.workspace) / RENDER_FILENAME
        try:
            path.write_text(body, encoding="utf-8")
        except OSError as exc:
            raise RenderFailed(
                "the plan document could not be written",
                path=str(path), cause=str(exc),
            ) from exc

        tables: dict[str, int] = {}
        for row in live:
            tables[row.ref.table] = tables.get(row.ref.table, 0) + 1
        return RenderReceipt(
            path=str(path),
            plan_name=handle["name"],
            plan_state=handle["state"],
            plan_version=handle["version"],
            live_rows=len(live),
            tables=tables,
            written_at=now(),
            dead_citations=tuple(
                label(None, c["address"]) for c in cites if c["state"] == "absent"
            ),
        )

    # --- reading ---

    def _live_rows(self) -> list[PlanRow]:
        """Every live row, in creation order, paged.

        Creation order rather than alphabetical: it is the order the interview produced
        them, so the document reads in the order the decisions were actually made.
        """
        out: list[PlanRow] = []
        offset = 0
        while True:
            page = self.rows.read_rows(
                RowSelector(live_only=True, limit=PAGE, offset=offset)
            )
            out.extend(page.rows)
            if not page.has_more or not page.rows:
                return out
            offset += len(page.rows)

    # --- writing ---

    def _document(self, handle, live, resolve, cites) -> str:
        lines = [
            f"# {handle['name']}",
            "",
            f"Plan state: {handle['state']} · version {handle['version']} · "
            f"{len(live)} live rows · rendered {now()}",
            "",
            "This document is derived from the plan database and is not the plan. Anything "
            "wrong here is fixed in the rows and rendered again — never by editing this "
            "file, whose next render would discard the edit.",
            "",
        ]
        for table in self._tables_in_order(live):
            lines.append(f"## {table}")
            lines.append("")
            for row in live:
                if row.ref.table == table:
                    lines.extend(self._row(row, resolve, cites))
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _tables_in_order(live: list[PlanRow]) -> list[str]:
        seen: list[str] = []
        for row in live:
            if row.ref.table not in seen:
                seen.append(row.ref.table)
        return seen

    def _row(self, row: PlanRow, resolve, cites) -> list[str]:
        """One row: its name and address, what it says, and what it rests on."""
        lines = [f"### {label(row.name, row.ref)}", ""]

        facts = [str(row.provenance)]
        if row.assumption_kind:
            facts.append(f"assumption: {row.assumption_kind}")
        if row.package is not None:
            facts.append(f"package {row.package}")
        if row.supersedes is not None:
            facts.append(f"supersedes {self._display(row.supersedes, resolve)}")
        lines.append("*" + " · ".join(facts) + "*")
        lines.append("")

        mine: list[Resolution] = []
        for key, value in row.content.items():
            lines.append(f"- **{key}**: {self._value(value, resolve, mine)}")
        if row.links:
            targets = [
                f"{spec.edge_type} → {self._display(spec.target, resolve)}"
                for spec in row.links
                if not spec.is_intra_batch
            ]
            if targets:
                lines.append(f"- **links**: {', '.join(targets)}")

        if mine:
            lines.append("")
            lines.append(
                "*cites: "
                + "; ".join(f"{c['address']} — {c['name']} ({c['state']})" for c in mine)
                + "*"
            )
            cites.extend(mine)
        lines.append("")
        return lines

    @staticmethod
    def _display(target: Any, resolve) -> str:
        ref = target if isinstance(target, RowRef) else RowRef.coerce(str(target))
        name, _state = resolve(ref)
        return label(name, ref)

    def _value(self, value: Any, resolve, mine: list[Resolution]) -> str:
        """Stored content, flattened for reading and never reworded.

        `collect` is the door's own annotator: it notes every address the text cites and
        hands the text back byte-for-byte. The notes surface under the row; the prose the
        owner wrote reaches him exactly as he wrote it.
        """
        if isinstance(value, str):
            return str(collect(value, resolve, mine))
        if isinstance(value, dict):
            return "; ".join(
                f"{k}: {self._value(v, resolve, mine)}" for k, v in value.items()
            )
        if isinstance(value, (list, tuple)):
            return "; ".join(self._value(v, resolve, mine) for v in value)
        return str(value)
