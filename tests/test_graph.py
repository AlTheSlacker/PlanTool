"""link-graph (components:3)."""

import pytest

from engine.errors import DanglingRef
from engine.graph import GraphScope, LinkGraph
from engine.models import LinkSpec, RowRef, RowSubmission, TraversalSpec


@pytest.fixture
def graph(store):
    return LinkGraph(store)


def _chain(rows):
    """use_cases:1 <- requirements:1 <- contracts:1"""
    rows.submit_rows([RowSubmission("use_cases", {"text": "uc"})], "k1")
    rows.submit_rows(
        [RowSubmission("requirements", {"text": "req"},
                       links=[LinkSpec(RowRef("use_cases", 1))])],
        "k2",
    )
    rows.submit_rows(
        [RowSubmission("contracts", {"text": "con"},
                       links=[LinkSpec(RowRef("requirements", 1))])],
        "k3",
    )


def test_closure_reaches_transitively(rows, graph):
    _chain(rows)
    closure = graph.closure([RowRef("contracts", 1)], TraversalSpec(direction="out"))
    assert {str(r) for r in closure.reached} == {
        "contracts:1", "requirements:1", "use_cases:1",
    }


def test_closure_respects_depth(rows, graph):
    _chain(rows)
    closure = graph.closure(
        [RowRef("contracts", 1)], TraversalSpec(direction="out", depth=1)
    )
    assert {str(r) for r in closure.reached} == {"contracts:1", "requirements:1"}


def test_closure_respects_edge_types(rows, graph):
    rows.submit_rows([RowSubmission("use_cases", {"text": "uc"})], "k1")
    rows.submit_rows(
        [RowSubmission("requirements", {"text": "r"},
                       links=[LinkSpec(RowRef("use_cases", 1), "cites")])],
        "k2",
    )
    closure = graph.closure(
        [RowRef("requirements", 1)],
        TraversalSpec(edge_types=["links"], direction="out"),
    )
    assert {str(r) for r in closure.reached} == {"requirements:1"}


def test_closure_rejects_a_missing_root(rows, graph):
    _chain(rows)
    with pytest.raises(DanglingRef) as exc:
        graph.closure([RowRef("use_cases", 99)])
    assert exc.value.detail["ref"] == "use_cases:99"


def test_dangling_edge_is_named(store, rows, graph):
    _chain(rows)
    store.conn.execute(
        "INSERT INTO links (source_ref, target_ref, edge_type, created_at) "
        "VALUES ('contracts:1', 'ghost:7', 'links', 'now')"
    )
    store.conn.commit()
    with pytest.raises(DanglingRef) as exc:
        graph.closure([RowRef("contracts", 1)])
    assert exc.value.detail["ref"] == "ghost:7"


def test_impact_enumerates_dependents(rows, graph):
    """Changing the use case affects everything resting on it."""
    _chain(rows)
    report = graph.impact([RowRef("use_cases", 1)])
    assert {str(r) for r in report.affected} == {"requirements:1", "contracts:1"}
    assert report.execution_layer_omitted is True


def test_impact_does_not_mutate_edges(store, rows, graph):
    """conflicts:4 — impact is a pure read."""
    _chain(rows)
    before = store.query("SELECT * FROM links")
    graph.impact([RowRef("use_cases", 1)])
    assert len(store.query("SELECT * FROM links")) == len(before)


def test_find_cycles_detects_a_loop(store, rows, graph):
    rows.submit_rows([RowSubmission("contracts", {"text": "a"})], "k1")
    rows.submit_rows([RowSubmission("contracts", {"text": "b"})], "k2")
    for source, target in (("contracts:1", "contracts:2"),
                           ("contracts:2", "contracts:1")):
        store.conn.execute(
            "INSERT INTO links (source_ref, target_ref, edge_type, created_at) "
            "VALUES (?, ?, 'links', 'now')",
            (source, target),
        )
    store.conn.commit()

    cycles = graph.find_cycles()
    assert len(cycles) == 1
    assert {str(r) for r in cycles[0]} == {"contracts:1", "contracts:2"}


def test_find_cycles_is_quiet_on_a_dag(rows, graph):
    _chain(rows)
    assert graph.find_cycles() == []


def test_find_cycles_can_scope_by_table(store, rows, graph):
    _chain(rows)
    assert graph.find_cycles(GraphScope(tables=["contracts"])) == []
