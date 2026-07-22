"""The plan as a document a person reads (DEVIATIONS D21).

What these tests are actually guarding is the reason the render exists: the last planning
package ends by skimming the plan **with the owner**, and a render that quietly dropped
rows, or that reworded the owner's prose, would make that skim worse than no skim — it
would certify a plan nobody read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.render import RENDER_FILENAME
from engine.storage import Storage
from engine.surface import Surface, ToolCall


@pytest.fixture
def surface(tmp_path):
    storage = Storage(tmp_path)
    storage.init_plan("the widget plan", "standard")
    made = Surface(storage)
    yield made
    storage.close()


def submit(surface, batch, key):
    result = surface.dispatch(
        ToolCall("submit_rows", {"batch": batch, "idempotency_key": key})
    )
    assert result.ok, result.problem
    return result


def rendered(surface) -> str:
    result = surface.dispatch(ToolCall("render_plan", {}))
    assert result.ok, result.problem
    return Path(result.payload["detail"]["path"]).read_text(encoding="utf-8")


class TestWhatReachesTheOwner:
    def test_every_live_row_is_in_the_document(self, surface):
        submit(surface, [
            {"table": "decisions", "name": "ship on SQLite",
             "content": {"text": "Goal: one file, no server."}},
            {"table": "requirements", "name": "the widget settles in 40 ms",
             "content": {"text": "The widget shall settle within 40 ms."}},
        ], "two-rows")
        body = rendered(surface)
        assert "ship on SQLite" in body
        assert "the widget settles in 40 ms" in body
        assert "one file, no server" in body

    def test_a_row_is_named_before_it_is_addressed(self, surface):
        """D19 in the one artefact the owner actually reads end to end. A heading of
        `requirements:1` alone tells him nothing and sends him back to the tool."""
        submit(surface, [
            {"table": "requirements", "name": "the widget settles in 40 ms",
             "content": {"text": "The widget shall settle within 40 ms."}},
        ], "named")
        body = rendered(surface)
        assert "### the widget settles in 40 ms (requirements:1)" in body

    def test_a_retired_row_is_not_in_the_document(self, surface):
        submit(surface, [
            {"table": "decisions", "name": "use a queue",
             "content": {"text": "A queue absorbs the burst."}},
        ], "retire-me")
        result = surface.dispatch(ToolCall("retire_row", {
            "ref": "decisions:1", "reason": "there is no burst",
            "idempotency_key": "r1",
        }))
        assert result.ok, result.problem
        assert "use a queue" not in rendered(surface)

    def test_the_owners_prose_is_served_word_for_word(self, surface):
        """The render annotates and never rewrites. A document that tidied the owner's
        wording would be a document he cannot check his own intent against."""
        said = "Goal: cut the 3am pages. NOT a dashboard — see decisions:1."
        submit(surface, [
            {"table": "decisions", "name": "cut the 3am pages",
             "content": {"text": said}},
        ], "verbatim")
        assert said in rendered(surface)


class TestCitations:
    def test_an_address_in_prose_is_resolved_beneath_the_row(self, surface):
        submit(surface, [
            {"table": "decisions", "name": "cut the 3am pages",
             "content": {"text": "Goal: cut the 3am pages."}},
            {"table": "requirements", "name": "the pager stays quiet below warning",
             "content": {"text": "Follows from decisions:1."}},
        ], "cite")
        body = rendered(surface)
        assert "cites: decisions:1 — cut the 3am pages (active)" in body

    def test_a_citation_that_reaches_nothing_says_so(self, surface):
        """F17 stops being silent. The row's prose is frozen and keeps pointing where it
        pointed; the render is where the owner finds out that it points nowhere."""
        submit(surface, [
            {"table": "requirements", "name": "the pager stays quiet below warning",
             "content": {"text": "Follows from decisions:9."}},
        ], "dead")
        body = rendered(surface)
        assert "decisions:9" in body
        assert "no live row at this address" in body

    def test_the_receipt_counts_the_dead_citations(self, surface):
        """The owner reads the document; the planner reads the receipt. A defect visible
        in only one of them is a defect one of the two will act on."""
        submit(surface, [
            {"table": "requirements", "name": "the pager stays quiet below warning",
             "content": {"text": "Follows from decisions:9."}},
        ], "dead-receipt")
        result = surface.dispatch(ToolCall("render_plan", {}))
        assert result.ok, result.problem
        assert result.payload["detail"]["dead_citations"] == [
            "no live row at this address (decisions:9)"
        ]


class TestTheDocumentIsDerived:
    def test_the_receipt_carries_the_path_and_not_the_document(self, surface):
        """`requirements:62` — a full-plan dump is never how a session rehydrates. A tool
        that returned the whole rendered plan would be exactly that under another name, so
        the document goes to disk and the receipt says where."""
        submit(surface, [
            {"table": "decisions", "name": "ship on SQLite",
             "content": {"text": "Goal: one file, no server."}},
        ], "receipt")
        result = surface.dispatch(ToolCall("render_plan", {}))
        detail = result.payload["detail"]
        assert detail["path"].endswith(RENDER_FILENAME)
        assert "one file, no server" not in str(detail)

    def test_it_says_it_is_derived_where_the_owner_will_read_it(self, surface):
        submit(surface, [
            {"table": "decisions", "name": "ship on SQLite",
             "content": {"text": "Goal: one file, no server."}},
        ], "derived")
        body = rendered(surface)
        assert "not the plan" in body
        assert "never by editing this file" in body

    def test_rendering_again_replaces_the_document(self, surface):
        submit(surface, [
            {"table": "decisions", "name": "use a queue",
             "content": {"text": "A queue absorbs the burst."}},
        ], "first")
        assert "use a queue" in rendered(surface)
        result = surface.dispatch(ToolCall("retire_row", {
            "ref": "decisions:1", "reason": "there is no burst",
            "idempotency_key": "r2",
        }))
        assert result.ok, result.problem
        assert "use a queue" not in rendered(surface)

    def test_the_summary_survives_the_strict_door(self, surface):
        """The one string on this path the surface composes itself, so it is held to the
        rule that a composed string may not name an address or an unreachable call."""
        submit(surface, [
            {"table": "decisions", "name": "ship on SQLite",
             "content": {"text": "Goal: one file, no server."}},
        ], "summary")
        result = surface.dispatch(ToolCall("render_plan", {}))
        assert result.ok, result.problem
        assert RENDER_FILENAME in result.payload["summary"]


class TestPaging:
    def test_more_rows_than_one_page_all_arrive(self, surface, monkeypatch):
        """The render is the one caller entitled to every live row, and it gets there by
        paging. A render that stopped at the first page would drop the end of the plan and
        report success — the silent-success shape this build keeps finding."""
        monkeypatch.setattr("engine.render.PAGE", 3)
        submit(surface, [
            {"table": "decisions", "name": f"decision number {i}",
             "content": {"text": f"Goal: number {i}."}}
            for i in range(7)
        ], "many")
        body = rendered(surface)
        for i in range(7):
            assert f"decision number {i}" in body
