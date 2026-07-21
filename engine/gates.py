"""gate-engine (components:6).

Evaluates deterministic, mechanical-only package gates, reporting row-level holes and
raising warnings, including elicit-package coverage cross-checks.

Contract: contracts:22 run_gate.

Three rules shape this module, and every design choice below follows from one of them:

  requirements:20 — a gate evaluates ONLY mechanical criteria. There is no judgment
    anywhere in here, and there cannot be: the criteria live in a methodology content
    asset (engine/methodology/rev2/gate_criteria.yaml) as declarative data, and this
    module is nothing but their interpreter. If a criterion type ever needs to ask
    "is this *good*?", it does not belong in a gate.

  requirements:46 — results are deterministic. Criteria evaluate in file order, holes
    emit in row order, and nothing here reads a clock or a random source. Running the
    same gate twice against an unchanged plan returns the same result.

  decisions:31 — gates warn, they do not block, on open gaps and unresolved
    assumptions. The one thing that *does* block is an open conflict contesting a row
    the gate depends on (requirements:28), because a gate evaluating contested rows
    would be certifying a plan that contradicts itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

from engine.conflicts import Conflict, ConflictService, GateScope
from engine.errors import PlanToolError
from engine.gaps import GapEngine, title_of
from engine.methodology import Criterion, Methodology, load
from engine.models import PlanRow, RowRef, RowSelector, RowState
from engine.rows import RowService
from engine.warnings import Warning, WarningService


class UnknownPackage(PlanToolError):
    """contracts:22 — names the valid range."""


class BlockedByConflict(PlanToolError):
    """contracts:22 / requirements:28 — an open conflict contests rows this gate
    depends on; names the conflicts and the contested rows."""


class PlanUnreadable(PlanToolError):
    """contracts:22 — a gate never evaluates partial state."""


@dataclass(frozen=True, slots=True)
class Hole:
    """requirements:20 — each hole names table, row, problem, and fix."""

    criterion_id: str
    table: str
    problem: str
    fix: str
    ref: RowRef | None = None
    cross_check: bool = False

    def __str__(self) -> str:
        where = f"{self.table}" + (f" {self.ref}" if self.ref else "")
        return f"[{where}] {self.problem} -> {self.fix}"


@dataclass(frozen=True, slots=True)
class GateResult:
    """contracts:22 — deterministic pass/fail with row-level holes and explicit
    warnings."""

    package: int
    passed: bool
    holes: tuple[Hole, ...]
    warnings: tuple[Warning, ...]
    #: requirements:17 — which coverage cross-checks ran, so their absence is visible.
    cross_checks_run: tuple[str, ...] = ()
    next_package: int | None = None

    @property
    def clean(self) -> bool:
        """Passed *and* nothing outstanding. A pass with warnings is still a pass
        (decisions:31), but it is not a clean one, and the difference matters at
        finalization."""
        return self.passed and not self.warnings


class GateEngine:
    def __init__(
        self,
        storage,
        rows: RowService,
        conflicts: ConflictService,
        warnings: WarningService,
        gaps: GapEngine | None = None,
        methodology: Methodology | None = None,
    ):
        self.storage = storage
        self.rows = rows
        self.conflicts = conflicts
        self.warnings = warnings
        self.methodology = methodology or load()
        self.gaps = gaps or GapEngine(storage, rows, methodology=self.methodology)

    # --- contracts:22 ---

    def run_gate(self, package: int, lease=None) -> GateResult:
        low, high = self.methodology.package_range
        if isinstance(package, bool) or not isinstance(package, int) or not low <= package <= high:
            raise UnknownPackage(
                f"package must be an integer in {low}-{high}", package=repr(package)
            )

        integrity = self.storage.integrity_check()
        if integrity.unreadable:
            raise PlanUnreadable(
                "a gate never evaluates partial state; recover first",
                package=package,
                unreadable=list(integrity.unreadable),
            )

        blocking = self.conflicts.blocking_conflicts(self.scope(package))
        if blocking:
            raise BlockedByConflict(
                "open conflicts contest rows this gate depends on",
                package=package,
                conflicts=[c.id for c in blocking],
                contested=sorted({str(r) for c in blocking for r in c.refs}),
                reasons=[c.blockage_reason() for c in blocking],
            )

        criteria = self.methodology.criteria_for(package)
        holes: list[Hole] = []
        for criterion in criteria:
            holes.extend(self._evaluate(criterion))

        warnings = self._raise_warnings(package, lease=lease)
        passed = not holes
        return GateResult(
            package=package,
            passed=passed,
            holes=tuple(holes),
            warnings=tuple(warnings),
            cross_checks_run=tuple(c.id for c in criteria if c.cross_check),
            next_package=package + 1 if passed and package < high else None,
        )

    def scope(self, package: int) -> GateScope:
        """The rows this gate depends on (contracts:28's GateScope).

        Every table the package's criteria read, plus the tables the manifest assigns to
        the package. Package 8 folds in every earlier package, because it re-runs them.
        """
        packages = (
            [s.number for s in self.methodology.packages]
            if self._is_terminal(package)
            else [package]
        )
        tables: set[str] = set()
        for number in packages:
            try:
                tables.update(self.methodology.package(number).tables)
            except KeyError:
                pass
            for criterion in self.methodology.criteria_for(number):
                tables.update(self._tables_of(criterion))
        return GateScope(tables=tuple(sorted(tables)))

    @staticmethod
    def _tables_of(criterion: Criterion) -> set[str]:
        spec = criterion.spec
        tables = set()
        for key in ("table", "child_table", "escape_table"):
            if spec.get(key):
                tables.add(spec[key])
        for key in ("to_tables", "backing_tables"):
            tables.update(spec.get(key) or ())
        return tables

    def _is_terminal(self, package: int) -> bool:
        return package == self.methodology.package_range[1]

    # --- warnings (requirements:21, decisions:31) ---

    def _raise_warnings(self, package: int, lease=None) -> list[Warning]:
        """Every open gap and unresolved assumption, raised as an explicit warning.

        Raising is idempotent on the warning key, so a deficiency that survives three
        gates is one warning re-presented three times — which is precisely what
        requirements:22's "re-present until resolved or suppressed" means. A warning the
        owner suppressed stays suppressed and does not come back here; it comes back at
        the critical points instead (requirements:23).

        Scoped to the package being gated (plus the package-agnostic rules, which
        open_gaps includes at any package). The unscoped reading of requirements:21 —
        every open gap in the plan — was built first and driven end to end, and it
        reported "no components yet" as a warning on the package-1 gate of a plan that
        had not reached package 6. Ten of twelve warnings were of that kind. A warning
        list that says "the plan is not finished yet" to someone who is three packages
        from finishing is noise, and gap_rules.yaml already records why that matters:
        "a meter that cries wolf stops being read". Warnings raised at their own package
        persist in the ledger and keep re-presenting, so nothing is passed over
        silently — see DEFECTS.md F10.
        """
        # An open assumption reaches this method twice: once as a gap (gap_rules.yaml
        # derives one per open assumption, for the interview) and once from the row
        # scan below. Raised under both keys it becomes two warnings for one fact, and
        # the drive showed the consequence — the owner suppressed the assumption
        # warning and the gap-derived twin carried on nagging, so suppression did not
        # stick. The row scan wins: contracts:22 names "unresolved assumption" as a
        # warning category in its own right, and that vocabulary should survive.
        assumption_rules = {
            rule.id for rule in self.methodology.rules if rule.type == "open_assumption"
        }
        for gap in self.gaps.open_gaps(package=package):
            if gap.rule_id in assumption_rules:
                continue
            self.warnings.raise_warning(
                warning_key=f"gap:{gap.key}",
                kind="open_gap",
                message=f"open gap ({gap.rule_id}): {gap.ask}",
                source_ref=gap.target,
                lease=lease,
            )
        for row in self._open_assumptions():
            root = self.gaps.lineage_root(row.ref)
            kind = row.assumption_kind or "unclassified"
            self.warnings.raise_warning(
                warning_key=f"assumption:{root}",
                kind="unresolved_assumption",
                message=(
                    f"unresolved {kind}-assumption {row.ref}: "
                    f"{title_of(row)}"
                ),
                source_ref=row.ref,
                lease=lease,
            )
        self._clear_settled_warnings(lease=lease)
        return self.warnings.active_warnings()

    def _clear_settled_warnings(self, lease=None) -> None:
        """Retire warnings whose underlying condition no longer holds.

        Without this, the ledger only ever grows: the first drive showed a
        "nothing recorded yet" warning still active on a package-1 gate that passed.
        A warning that outlives its cause trains the reader to ignore warnings, which
        is the exact failure decisions:31's keep-pushing policy is trying to avoid.

        A gap-derived warning is settled when the gap is no longer derived from plan
        state; an assumption warning when the row is no longer a live assumption. Both
        are recomputed, never remembered, so this cannot drift out of step with the
        conditions it mirrors.
        """
        live_keys = {f"gap:{gap.key}" for gap in self.gaps.open_gaps()}
        live_keys |= {
            f"assumption:{self.gaps.lineage_root(row.ref)}"
            for row in self._open_assumptions()
        }
        for warning in self.warnings.all_warnings():
            if warning.state == "resolved" or warning.warning_key in live_keys:
                continue
            if warning.kind not in ("open_gap", "unresolved_assumption"):
                continue  # not ours to settle; another component owns its lifecycle
            self.warnings.settle_warning(
                warning.id,
                "the condition that raised this warning no longer holds",
                lease=lease,
            )

    def _open_assumptions(self) -> list[PlanRow]:
        page = self.rows.read_rows(RowSelector(live_only=True, limit=1000))
        return [r for r in page.rows if r.state == RowState.ASSUMED]

    # --- criterion evaluation ---

    def _evaluate(self, criterion: Criterion) -> list[Hole]:
        handler = {
            "non_empty": self._c_non_empty,
            "required_fields": self._c_required_fields,
            "conditional_fields": self._c_conditional_fields,
            "traced": self._c_traced,
            "covers_all": self._c_covers_all,
            "matrix_complete": self._c_matrix_complete,
            "unbacked_assumption": self._c_unbacked_assumption,
            "prior_gates_green": self._c_prior_gates_green,
            "no_open_conflicts": self._c_no_open_conflicts,
        }.get(criterion.type)
        if handler is None:
            raise PlanUnreadable(
                f"unknown gate criterion type {criterion.type!r}",
                criterion=criterion.id,
            )
        return handler(criterion)

    def _hole(
        self, criterion: Criterion, row: PlanRow | None = None, **fmt: Any
    ) -> Hole:
        context = {
            "title": title_of(row) if row is not None else "",
            "ref": str(row.ref) if row is not None else "",
            **fmt,
        }
        return Hole(
            criterion_id=criterion.id,
            table=criterion.spec.get("table", "-"),
            problem=criterion.problem.format(**context),
            fix=criterion.fix,
            ref=row.ref if row is not None else None,
            cross_check=criterion.cross_check,
        )

    def _live(self, table: str) -> list[PlanRow]:
        page = self.rows.read_rows(
            RowSelector(table=table, live_only=True, limit=1000)
        )
        # requirements:46 — a stable order in, a stable order out.
        return sorted(page.rows, key=lambda r: r.ref.ordinal)

    def _c_non_empty(self, criterion: Criterion) -> list[Hole]:
        if self._live(criterion.spec["table"]):
            return []
        escape = criterion.spec.get("escape_table")
        if escape and self._live(escape):
            # An explicit "there are none, and here is why" row is a real answer, not a
            # missing one. Package 5's no-dependencies decision is the vendored case.
            return []
        return [self._hole(criterion)]

    def _c_required_fields(self, criterion: Criterion) -> list[Hole]:
        spec = criterion.spec
        when, unless = spec.get("when_field"), spec.get("unless_field")
        holes = []
        for row in self._live(spec["table"]):
            if when and not row.content.get(when):
                continue
            if unless and row.content.get(unless):
                continue
            missing = [f for f in spec["fields"] if not row.content.get(f)]
            if missing:
                holes.append(
                    self._hole(criterion, row, missing=", ".join(missing))
                )
        return holes

    def _c_conditional_fields(self, criterion: Criterion) -> list[Hole]:
        """Fields required by another field's value — EARS slots are the vendored
        case."""
        holes = []
        for row in self._live(criterion.spec["table"]):
            missing: list[str] = []
            for case in criterion.spec["cases"]:
                value = row.content.get(case["when_field"])
                if value not in case["when_values"]:
                    continue
                missing.extend(f for f in case["require"] if not row.content.get(f))
            if missing:
                holes.append(
                    self._hole(criterion, row, missing=", ".join(missing))
                )
        return holes

    def _c_traced(self, criterion: Criterion) -> list[Hole]:
        spec = criterion.spec
        table = spec["table"]
        direction = spec.get("direction", "in")
        when, unless = spec.get("when_field"), spec.get("unless_field")
        linked = self._linked_refs(table, tuple(spec["to_tables"]), direction)
        holes = []
        for row in self._live(table):
            if when and not row.content.get(when):
                continue
            if unless and row.content.get(unless):
                continue
            if str(row.ref) in linked:
                continue
            holes.append(self._hole(criterion, row))
        return holes

    def _linked_refs(
        self, table: str, to_tables: tuple[str, ...], direction: str
    ) -> set[str]:
        """Refs in `table` participating in a link to/from any of `to_tables`.

        direction 'in': the row is the *target* of an edge whose source lives in
        to_tables (a use case is traced when a requirement points at it). 'out': the
        row is the source (a contract traces to a requirement it points at).
        """
        mine, theirs = (
            ("target_ref", "source_ref") if direction == "in"
            else ("source_ref", "target_ref")
        )
        return {
            r[mine]
            for r in self.storage.query("SELECT source_ref, target_ref FROM links")
            if r[mine].split(":")[0] == table
            and r[theirs].split(":")[0] in to_tables
        }

    def _children(self, parent: PlanRow, child_table: str) -> list[PlanRow]:
        """Live rows in child_table linking to this parent."""
        sources = {
            r["source_ref"]
            for r in self.storage.query(
                "SELECT source_ref FROM links WHERE target_ref = ?", (str(parent.ref),)
            )
            if r["source_ref"].split(":")[0] == child_table
        }
        return [row for row in self._live(child_table) if str(row.ref) in sources]

    def _c_covers_all(self, criterion: Criterion) -> list[Hole]:
        spec = criterion.spec
        required = list(spec["values"])
        holes = []
        for parent in self._live(spec["table"]):
            covered = {
                child.content.get(spec["field"])
                for child in self._children(parent, spec["child_table"])
            }
            missing = [v for v in required if v not in covered]
            if missing:
                holes.append(
                    self._hole(criterion, parent, missing=", ".join(missing))
                )
        return holes

    def _c_matrix_complete(self, criterion: Criterion) -> list[Hole]:
        """The state x event grid: every cell is a transition or an explicit
        impossible."""
        spec = criterion.spec
        row_axis, col_axis = spec["axes"]
        row_field, col_field = spec["child_fields"]
        holes = []
        for parent in self._live(spec["table"]):
            rows_ = parent.content.get(row_axis) or []
            cols = parent.content.get(col_axis) or []
            if not rows_ or not cols:
                continue  # the parent's own completeness is another criterion's job
            covered = {
                (child.content.get(row_field), child.content.get(col_field))
                for child in self._children(parent, spec["child_table"])
            }
            missing = [
                f"{a} x {b}" for a, b in product(rows_, cols) if (a, b) not in covered
            ]
            if missing:
                holes.append(self._hole(
                    criterion, parent,
                    count=len(missing),
                    missing=", ".join(missing[:12])
                    + (" ..." if len(missing) > 12 else ""),
                ))
        return holes

    def _c_unbacked_assumption(self, criterion: Criterion) -> list[Hole]:
        """A world-assumption with no spike and no accepted risk behind it."""
        spec = criterion.spec
        backing = tuple(spec["backing_tables"])
        holes = []
        for row in self._open_assumptions():
            if row.assumption_kind != spec["assumption_kind"]:
                continue
            backed = any(
                r["source_ref"].split(":")[0] in backing
                for r in self.storage.query(
                    "SELECT source_ref FROM links WHERE target_ref = ?", (str(row.ref),)
                )
            )
            if not backed:
                holes.append(self._hole(criterion, row))
        return sorted(holes, key=lambda h: (h.ref.table, h.ref.ordinal))

    def _c_prior_gates_green(self, criterion: Criterion) -> list[Hole]:
        """Package 8 folds in every earlier gate.

        It re-runs their *criteria* rather than calling run_gate, deliberately: run_gate
        would re-raise warnings and re-check conflicts eight times over, and a
        BlockedByConflict from an inner gate would surface as the wrong package's error.
        """
        holes = []
        for entry in self.methodology.packages:
            if entry.number >= criterion.package:
                continue
            inner = [
                hole
                for inner_criterion in self.methodology.criteria_for(entry.number)
                for hole in self._evaluate(inner_criterion)
            ]
            if inner:
                holes.append(Hole(
                    criterion_id=criterion.id,
                    table="gates",
                    problem=criterion.problem.format(
                        package=entry.number, count=len(inner)
                    ),
                    fix=criterion.fix,
                ))
        return holes

    def _c_no_open_conflicts(self, criterion: Criterion) -> list[Hole]:
        """Plan-wide, not scope-limited: a frozen plan cannot contradict itself
        anywhere.

        This criterion is reachable — an open conflict contesting rows *outside* this
        gate's scope does not block it, so freeze must still refuse.
        """
        return [
            Hole(
                criterion_id=criterion.id,
                table="conflicts",
                problem=criterion.problem.format(
                    id=conflict.id, description=conflict.description
                ),
                fix=criterion.fix,
                ref=conflict.refs[0] if conflict.refs else None,
            )
            for conflict in self._sorted_open(self.conflicts.open_conflicts())
        ]

    @staticmethod
    def _sorted_open(conflicts: list[Conflict]) -> list[Conflict]:
        return sorted(conflicts, key=lambda c: c.id)
