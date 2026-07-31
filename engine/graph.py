"""link-graph (components:3).

Owns the typed-edge substrate: closure traversal, impact enumeration, and cycle
detection. Edges are never mutated here — conflicts:4 requires impact to be a pure read.

Contracts: contracts:14 closure, contracts:15 impact, contracts:58 find_cycles.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from engine.errors import DanglingRef
from engine.models import Closure, RowRef, TraversalSpec
from engine.storage import Storage


@dataclass(frozen=True, slots=True)
class ImpactReport:
    """contracts:15 — every row transitively affected by a change.

    The plan also requires briefs and built tasks to be enumerated
    (requirements:50). Those belong to the deferred execution module (DEVIATIONS.md
    D1), so this report carries rows only and says so.
    """

    changed: tuple[RowRef, ...]
    affected: tuple[RowRef, ...]
    execution_layer_omitted: bool = True


@dataclass(frozen=True, slots=True)
class GraphScope:
    """contracts:58 — the scope a cycle search runs over."""

    edge_types: list[str] | None = None
    tables: list[str] | None = None


class LinkGraph:
    def __init__(self, storage: Storage):
        self.storage = storage

    # --- internals ---

    def _all_refs(self) -> set[str]:
        return {
            f"{r['table_name']}:{r['ordinal']}"
            for r in self.storage.query("SELECT table_name, ordinal FROM plan_rows")
        }

    def _edges(self, edge_types: list[str] | None = None) -> list[tuple[str, str, str]]:
        rows = self.storage.query(
            "SELECT source_ref, target_ref, edge_type FROM links ORDER BY id"
        )
        return [
            (r["source_ref"], r["target_ref"], r["edge_type"])
            for r in rows
            if edge_types is None or r["edge_type"] in edge_types
        ]

    def _adjacency(
        self, spec_types: list[str] | None, direction: str
    ) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = {}
        for source, target, _ in self._edges(spec_types):
            if direction in ("out", "both"):
                adj.setdefault(source, set()).add(target)
            if direction in ("in", "both"):
                adj.setdefault(target, set()).add(source)
        return adj

    def _guard_dangling(self, refs: set[str] | None = None) -> None:
        """A traversed edge pointing at a missing row signals store inconsistency and
        routes to the integrity check."""
        known = self._all_refs()
        for source, target, _ in self._edges():
            if refs is not None and source not in refs and target not in refs:
                continue
            for ref in (source, target):
                if ref not in known:
                    raise DanglingRef(
                        "an edge references a missing row; the store is inconsistent "
                        "— run integrity_check",
                        ref=ref,
                        edge=f"{source} -> {target}",
                    )

    # --- contracts:14 ---

    def closure(
        self, roots: list[RowRef | str], spec: TraversalSpec | None = None
    ) -> Closure:
        """Every row reachable from roots via the defined traversal.

        This is the brief-candidate set of requirements:36. The brief composer that
        consumes it is deferred (DEVIATIONS.md D1), but the closure itself is needed
        now: gates and impact analysis both walk it.
        """
        spec = spec or TraversalSpec()
        spec.validate()

        known = self._all_refs()
        root_refs = [str(RowRef.coerce(r)) for r in roots]
        for ref in root_refs:
            if ref not in known:
                raise DanglingRef("a root references a missing row", ref=ref)
        self._guard_dangling()

        adj = self._adjacency(spec.edge_types, spec.direction)
        depth_of: dict[str, int] = {ref: 0 for ref in root_refs}
        queue: deque[str] = deque(root_refs)
        reached: list[str] = []

        while queue:
            current = queue.popleft()
            reached.append(current)
            depth = depth_of[current]
            if spec.depth >= 0 and depth >= spec.depth:
                continue
            for neighbour in sorted(adj.get(current, ())):
                if neighbour not in depth_of:
                    depth_of[neighbour] = depth + 1
                    queue.append(neighbour)

        return Closure(
            tuple(RowRef.parse(r) for r in root_refs),
            tuple(RowRef.parse(r) for r in reached),
            depth_of,
        )

    # --- contracts:15 ---

    def impact(self, changed: list[RowRef | str]) -> ImpactReport:
        """Enumerate every row transitively affected by a change. A pure read."""
        changed_refs = [RowRef.coerce(r) for r in changed]
        # Impact flows to whatever depends on the changed rows: follow inbound edges,
        # since a link means "this row rests on that one".
        closure = self.closure(changed_refs, TraversalSpec(direction="in"))
        roots = {str(r) for r in changed_refs}
        affected = tuple(r for r in closure.reached if str(r) not in roots)
        return ImpactReport(tuple(changed_refs), affected)

    # --- contracts:58 ---

    def find_cycles(self, scope: GraphScope | None = None) -> list[list[RowRef]]:
        """Each cycle as an ordered list of refs.

        requirements:35 — a dependency cycle is surfaced to the owner as a design
        conflict before implementation starts.
        """
        scope = scope or GraphScope()
        self._guard_dangling()

        adj = self._adjacency(scope.edge_types, "out")
        if scope.tables is not None:
            allowed = set(scope.tables)
            adj = {
                s: {t for t in targets if t.split(":")[0] in allowed}
                for s, targets in adj.items()
                if s.split(":")[0] in allowed
            }

        cycles: list[list[str]] = []
        seen_cycles: set[frozenset[str]] = set()
        colour: dict[str, int] = {}  # 0 unvisited, 1 in-stack, 2 done
        stack: list[str] = []

        def walk(node: str) -> None:
            colour[node] = 1
            stack.append(node)
            for neighbour in sorted(adj.get(node, ())):
                state = colour.get(neighbour, 0)
                if state == 0:
                    walk(neighbour)
                elif state == 1:
                    cycle = stack[stack.index(neighbour):]
                    key = frozenset(cycle)
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        cycles.append([*cycle, neighbour])
            stack.pop()
            colour[node] = 2

        for node in sorted(adj):
            if colour.get(node, 0) == 0:
                walk(node)

        return [[RowRef.parse(r) for r in cycle] for cycle in cycles]
