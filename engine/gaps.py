"""gap-engine (components:5).

Derives prioritized gap clusters with surrounding row context from plan state, and owns
the dismiss/reopen overlay.

Contracts: contracts:19 next_gaps, contracts:66 dismiss_gap, contracts:67 reopen_gap.

Gaps are *computed* from plan state (crud_grid:9) — they are never stored as rows. Only
the dismissed/resolved overlay is persisted, which is what makes requirements:78's
stable identity necessary: the gap itself is re-derived every call, so its identity must
survive re-derivation and survive the target row being superseded.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from engine.errors import PlanToolError
from engine.methodology import Methodology, Rule, load
from engine.models import PlanRow, RowRef, RowSelector
from engine.references import EXTRACTS_TABLE, SOURCES_TABLE, ReferenceService
from engine.rows import RowService
from engine.clock import now
from engine.idempotency import key
from engine.storage import Op, Storage

#: Vendored from v1 (archive/v1/engine/gaps.py): return a coherent batch per call so the
#: session asks the owner one joined-up set of questions, not a drip feed.
CLUSTER_MIN = 3
CLUSTER_MAX = 5

#: Gap kinds with their own resolution flow are never dismissible (v1 UNDISMISSABLE).
UNDISMISSABLE: dict[str, str] = {
    "conflict": "a conflict is resolved through conflict-service, not dismissed",
}


def title_of(row: PlanRow) -> str:
    """A row's human-readable handle, for gap asks and gate holes alike.

    The store is schema-free by design (DEVIATIONS.md D3), so there is no title column
    to read — this is the agreed order of preference across every table.
    """
    for key in ("title", "name", "text", "quote", "description"):
        value = row.content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:120]
    return str(row.ref)


class GapNotFound(PlanToolError):
    """contracts:66/67 — names the missing gap."""


class AlreadyResolved(PlanToolError):
    """contracts:66 — resolved gaps cannot be dismissed; nothing written."""


class NotDismissed(PlanToolError):
    """contracts:67 — only dismissed gaps can be reopened."""


class Undismissable(PlanToolError):
    """This gap kind has its own resolution flow."""


class PlanUnreadable(PlanToolError):
    """contracts:19 — underlying rows failed integrity; routes to recovery."""


@dataclass(frozen=True, slots=True)
class Gap:
    key: str
    rule_key: str
    priority: int
    package: int | None
    ask: str
    target: RowRef | None
    root: RowRef | None
    state: str = "open"
    reason: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GapCluster:
    """contracts:19 — prioritized related gaps, each with surrounding row context."""

    gaps: tuple[Gap, ...]
    total_open: int
    package: int
    grouped_by: str | None = None
    recommend_gate: bool = False
    guidance: str = ""


class GapEngine:
    def __init__(
        self,
        storage: Storage,
        rows: RowService,
        references: ReferenceService | None = None,
        methodology: Methodology | None = None,
    ):
        self.storage = storage
        self.rows = rows
        self.references = references
        self.methodology = methodology or load()

    # --- identity (requirements:78) ---

    def lineage_root(self, ref: RowRef | str) -> RowRef:
        """The earliest ancestor in a row's supersession chain.

        A dismissal recorded against a row must survive that row being superseded — the
        deficiency is the same deficiency even though the row carrying it is new. Keying
        on the lineage root gives exactly that, without the dismissal silently detaching
        and re-surfacing (findings:16).

        Canonical implementation is `RowService.lineage_root`: scope attachments key the
        same way (M5_PLAN.md 2.4), so it belongs to neither caller alone.
        """
        return self.rows.lineage_root(ref)

    def _key(self, rule_key: str, root: RowRef | None, extra: str = "") -> str:
        segments = [rule_key, str(root) if root else "-"]
        if extra:
            segments.append(extra)
        return "|".join(segments)

    # --- derivation ---

    def _live(self, table: str) -> list[PlanRow]:
        page = self.rows.read_rows(
            RowSelector(table=table, live_only=True, limit=1000)
        )
        return list(page.rows)

    _title = staticmethod(title_of)

    def _linked(self, table: str, direction: str) -> set[str]:
        """Refs in `table` that participate in at least one link in `direction`."""
        column = "target_ref" if direction == "in" else "source_ref"
        other = "source_ref" if direction == "in" else "target_ref"
        return {
            r[column]
            for r in self.storage.query(
                f"SELECT {column}, {other} FROM links"  # noqa: S608
            )
            if r[column].split(":")[0] == table
        }

    def _linked_to(self, table: str, to_table: str, direction: str) -> set[str]:
        column = "target_ref" if direction == "in" else "source_ref"
        other = "source_ref" if direction == "in" else "target_ref"
        return {
            r[column]
            for r in self.storage.query(
                f"SELECT source_ref, target_ref FROM links"  # noqa: S608
            )
            if r[column].split(":")[0] == table
            and r[other].split(":")[0] == to_table
        }

    def _derive(self, rule: Rule) -> list[Gap]:
        handler = {
            "empty_table": self._rule_empty_table,
            "missing_field": self._rule_missing_field,
            "untraced": self._rule_untraced,
            "open_assumption": self._rule_open_assumption,
            "uncited_section": self._rule_uncited_section,
        }.get(rule.type)
        if handler is None:
            raise PlanUnreadable(f"unknown gap rule type {rule.type!r}", rule=rule.id)
        return handler(rule)

    def _make(
        self,
        rule: Rule,
        row: PlanRow | None = None,
        extra_key: str = "",
        **fmt: Any,
    ) -> Gap:
        root = self.lineage_root(row.ref) if row is not None else None
        return Gap(
            key=self._key(rule.id, root, extra_key),
            rule_key=rule.id,
            priority=rule.priority,
            package=rule.package,
            ask=rule.ask.format(title=self._title(row) if row else "", **fmt),
            target=row.ref if row else None,
            root=root,
            context={"row": row.content} if row is not None else {},
        )

    def _rule_empty_table(self, rule: Rule) -> list[Gap]:
        if self._live(rule.spec["table"]):
            return []
        return [self._make(rule)]

    def _rule_missing_field(self, rule: Rule) -> list[Gap]:
        when = rule.spec.get("when_field")
        gaps = []
        for row in self._live(rule.spec["table"]):
            if when and not row.content.get(when):
                continue
            missing = [f for f in rule.spec["fields"] if not row.content.get(f)]
            if missing:
                gaps.append(self._make(rule, row, extra_key=",".join(sorted(missing))))
        return gaps

    def _rule_untraced(self, rule: Rule) -> list[Gap]:
        table = rule.spec["table"]
        direction = rule.spec.get("direction", "in")
        linked = self._linked_to(table, rule.spec["to_table"], direction)
        unless = rule.spec.get("unless_field")
        when = rule.spec.get("when_field")
        gaps = []
        for row in self._live(table):
            if when and not row.content.get(when):
                continue
            if unless and row.content.get(unless):
                continue
            if str(row.ref) in linked:
                continue
            gaps.append(self._make(rule, row))
        return gaps

    def _rule_open_assumption(self, rule: Rule) -> list[Gap]:
        wanted = rule.spec.get("assumption_kind")
        page = self.rows.read_rows(RowSelector(live_only=True, limit=1000))
        return [
            self._make(rule, row)
            for row in page.rows
            if row.state == "assumed" and row.assumption_kind == wanted
        ]

    def _rule_uncited_section(self, rule: Rule) -> list[Gap]:
        """The coverage meter as a gap (V2_BUILD_PLAN.md 5.4).

        A paper cited only from its Results is a paper half read, and the caveat that
        derails a technical study lives in Limitations.
        """
        if self.references is None:
            return []
        ignore = {h.lower() for h in rule.spec.get("ignore_headings", [])}
        gaps: list[Gap] = []
        for source in self._live(SOURCES_TABLE):
            for coverage in self.references.section_coverage(source.ref):
                if not coverage.untouched:
                    continue
                if coverage.heading.lower() in ignore:
                    continue
                gaps.append(
                    self._make(
                        rule,
                        source,
                        extra_key=coverage.heading,
                        heading=coverage.heading,
                    )
                )
        return gaps

    # --- overlay ---

    def _overlay(self) -> dict[str, dict[str, Any]]:
        return {
            r["gap_key"]: dict(r)
            for r in self.storage.query("SELECT * FROM gap_overlay")
        }

    def open_gaps(self, package: int | None = None) -> list[Gap]:
        """Every open gap, prioritized — the whole list, not a cluster.

        next_gaps returns a cluster sized for one exchange; gate-engine needs the
        unabridged set to raise a warning per gap (requirements:21), because a gate
        reporting only the first five would be passing the rest over silently.

        `package=None` means every package rather than the current one. Passing a package
        keeps that package's rules plus the package-agnostic ones (open assumptions,
        reference coverage), which are never scoped out.
        """
        overlay = self._overlay()
        gaps: list[Gap] = []
        for rule in self.methodology.rules:
            if package is not None and rule.package is not None and rule.package != package:
                continue
            for gap in self._derive(rule):
                entry = overlay.get(gap.key)
                if entry is not None and entry["state"] in ("dismissed", "resolved"):
                    continue
                gaps.append(gap)
        gaps.sort(key=lambda g: (g.priority, g.rule_key, str(g.target or "")))
        return gaps

    # --- contracts:19 ---

    def next_gaps(self, limit: int = CLUSTER_MAX, package: int | None = None) -> GapCluster:
        """A prioritized cluster of related gaps, each with surrounding row context.

        requirements:13 — related, with context, so a cold session needs no other
        warm-up. requirements:12 — when the package has no open gaps, recommend running
        the gate.
        """
        integrity = self.storage.integrity_check()
        if integrity.unreadable:
            raise PlanUnreadable(
                "underlying rows failed integrity; recover before interviewing",
                unreadable=list(integrity.unreadable),
            )

        current = package if package is not None else self.current_package()
        derived = self.open_gaps(package=current)
        clustered = self._cluster(derived, limit)

        return GapCluster(
            gaps=tuple(clustered),
            total_open=len(derived),
            package=current,
            grouped_by=self._grouping(clustered),
            recommend_gate=not derived,
            guidance=self._guidance(current, bool(derived)),
        )

    def _cluster(self, gaps: list[Gap], limit: int) -> list[Gap]:
        """Group by same target table, then same rule, so the batch is coherent.

        v1's grouping key was entity -> table -> package. v2 keeps the spirit: a cluster
        the owner can answer as one conversation, not a scattering.
        """
        if not gaps:
            return []
        lead = gaps[0]
        lead_table = lead.target.table if lead.target else None

        def affinity(gap: Gap) -> tuple[int, int, str]:
            same_table = gap.target is not None and lead_table is not None and (
                gap.target.table == lead_table
            )
            return (
                0 if gap.rule_key == lead.rule_key else 1,
                0 if same_table else 1,
                str(gap.target or ""),
            )

        rest = sorted(gaps[1:], key=affinity)
        return [lead, *rest][:limit]

    @staticmethod
    def _grouping(gaps: list[Gap]) -> str | None:
        if not gaps:
            return None
        tables = {g.target.table for g in gaps if g.target}
        if len(tables) == 1:
            return tables.pop()
        rules = {g.rule_key for g in gaps}
        return rules.pop() if len(rules) == 1 else None

    def _guidance(self, package: int, has_gaps: bool) -> str:
        """The per-cluster nudge.

        v1's guidance was proposal-first only. decisions:36 recorded that this
        under-pushed the owner — the agent authored every use case and the owner "did
        not feel pushed that hard to add any". So on elicit packages the divergence round
        comes first, and proposal-first applies only after it.
        """
        if not has_gaps:
            return (
                "No open gaps in this package. Run the package gate — and before you do, "
                "work the package script's self-review checklist: gates verify "
                "completeness, self-review is where quality lives."
            )
        try:
            entry = self.methodology.package(package)
        except KeyError:
            entry = None

        if entry is not None and entry.is_elicit:
            return (
                "Elicit package: the owner is the source of truth. Run the divergence "
                "round BEFORE drafting — ask what scenarios are already in their head, "
                "then probe the negative space (which actor has no scenario? what must "
                "the system refuse to do?). Only once their candidates are on the table "
                "do you propose your own, marked assumed/intent. After the divergence "
                "round, prefer proposals-with-rationale over blank questions. Address "
                "this cluster as one coherent exchange and submit the accepted facts as "
                "one batch with provenance."
            )
        return (
            "Synthesize package: you are the source — the owner cannot answer 'what are "
            "the contracts?'. Design it, present it with rationale, and let them "
            "adjudicate. Form proposals and ask for objection rather than asking open "
            "questions. Address this cluster as one coherent exchange and submit as one "
            "batch with provenance."
        )

    def current_package(self) -> int:
        """The lowest package that still has open gaps, else the highest package.

        The plan never states how the current package is determined (DEFECTS.md F6).
        """
        for entry in self.methodology.packages:
            for rule in self.methodology.rules:
                if rule.package != entry.number:
                    continue
                if self._derive(rule):
                    return entry.number
        return self.methodology.package_range[1]

    # --- contracts:66 ---

    def dismiss_gap(self, gap_key: str, reason: str) -> Gap:
        """Record the dismissal reason, stop surfacing the gap, keep it reversible
        (requirements:15)."""
        if not reason or not reason.strip():
            raise GapNotFound("a dismissal must record why", gap_key=gap_key)

        gap = self._find(gap_key)
        kind = gap_key.split("|")[0]
        if kind in UNDISMISSABLE:
            raise Undismissable(UNDISMISSABLE[kind], gap_key=gap_key)

        existing = self._overlay().get(gap_key)
        if existing and existing["state"] == "resolved":
            raise AlreadyResolved(
                "resolved gaps cannot be dismissed; nothing written", gap_key=gap_key
            )

        self._write_overlay(gap, "dismissed", reason)
        return replace(gap, state="dismissed", reason=reason)

    # --- contracts:67 ---

    def reopen_gap(self, gap_key: str, reason: str) -> Gap:
        entry = self._overlay().get(gap_key)
        if entry is None:
            raise GapNotFound("no overlay recorded for this gap", gap_key=gap_key)
        if entry["state"] != "dismissed":
            raise NotDismissed(
                "only dismissed gaps can be reopened",
                gap_key=gap_key,
                state=entry["state"],
            )
        self.storage.write_atomic(
            [Op("update", "gap_overlay",
                {"state": "open", "reason": reason, "updated_at": now()},
                where={"gap_key": gap_key})],
            key("reopen", gap_key),
        )
        gap = self._find(gap_key, allow_missing=True)
        return replace(gap, state="open", reason=reason)

    def _write_overlay(self, gap: Gap, state: str, reason: str) -> None:
        existing = self._overlay().get(gap.key)
        op = (
            Op("update", "gap_overlay",
               {"state": state, "reason": reason, "updated_at": now()},
               where={"gap_key": gap.key})
            if existing
            else Op("insert", "gap_overlay", {
                "gap_key": gap.key,
                "rule_key": gap.rule_key,
                "root_ref": str(gap.root) if gap.root else None,
                "state": state,
                "reason": reason,
                "created_at": now(),
                "updated_at": now(),
            })
        )
        self.storage.write_atomic([op], key(state, gap.key))

    def _find(self, gap_key: str, allow_missing: bool = False) -> Gap:
        rule_key = gap_key.split("|")[0]
        for rule in self.methodology.rules:
            if rule.id != rule_key:
                continue
            for gap in self._derive(rule):
                if gap.key == gap_key:
                    return gap
        if allow_missing:
            root = gap_key.split("|")[1]
            return Gap(
                key=gap_key, rule_key=rule_key, priority=9, package=None,
                ask="(gap no longer derived from current plan state)",
                target=None,
                root=RowRef.parse(root) if root and root != "-" else None,
            )
        raise GapNotFound(
            "no such gap in the current plan state", gap_key=gap_key
        )
