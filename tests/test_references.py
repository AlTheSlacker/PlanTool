"""Verified references (DEVIATIONS.md D3).

The invariant under test: an extract cannot be written unless its verbatim quote is an
exact substring of the cited source's stored text. These are the tests that make the
citation system trustworthy, so they are the ones to read first if this design is ever
questioned.
"""

import pytest

from engine.errors import QuoteNotVerified, SourceNotFound, SourceTextUnavailable
from engine.models import RowSelector
from engine.references import detect_sections

from .conftest import PAPER


def test_source_stores_text_and_sections(refs, store):
    ref = refs.add_source("Widget Settling", PAPER, "k", authors="Ohm", year=2024)
    row = refs.rows.get(ref)
    assert row.content["title"] == "Widget Settling"
    assert row.content["sections"] > 3
    assert store.query("SELECT * FROM source_texts")[0]["char_count"] == len(PAPER)


def test_a_source_without_text_is_refused(refs):
    """An unverifiable source could only ever produce unverifiable extracts."""
    with pytest.raises(SourceTextUnavailable):
        refs.add_source("Empty", "   ", "k")


def test_real_quote_is_filed_with_a_locator(refs):
    source = refs.add_source("Widget Settling", PAPER, "k1")
    extract = refs.add_extract(
        source, "The measured settling time was 40 ms under nominal load.", "k2",
        paraphrase="Settling is 40ms.",
    )
    row = refs.rows.get(extract)
    assert row.content["section"] == "Results"
    assert row.content["paraphrase"] == "Settling is 40ms."
    assert PAPER[row.content["start_offset"]:row.content["end_offset"]] == (
        "The measured settling time was 40 ms under nominal load."
    )


def test_fabricated_quote_cannot_be_filed(refs):
    """Kills hallucination: invented text has no match, so it gets no citation."""
    source = refs.add_source("Widget Settling", PAPER, "k1")
    with pytest.raises(QuoteNotVerified) as exc:
        refs.add_extract(
            source, "The measured settling time was 5 microseconds.", "k2"
        )
    assert exc.value.detail["source_title"] == "Widget Settling"
    assert refs.rows.read_rows(RowSelector(table="extracts")).total == 0


def test_quote_from_a_different_paper_cannot_be_filed(refs):
    """Kills conflation: the quote is checked against one specific source."""
    paper_a = refs.add_source("Paper A", PAPER, "k1")
    refs.add_source(
        "Paper B", "Abstract\nGadgets settle in 900 ms under all conditions.\n", "k2"
    )
    with pytest.raises(QuoteNotVerified):
        refs.add_extract(paper_a, "Gadgets settle in 900 ms", "k3")


def test_quote_survives_line_break_hyphenation(refs):
    """PDF extraction breaks words across lines; a real quote must still verify."""
    source = refs.add_source("Widget Settling", PAPER, "k1")
    extract = refs.add_extract(
        source, "recorded the response with a high-speed camera at 10 kHz", "k2"
    )
    assert refs.rows.get(extract).content["section"] == "Methods"


def test_quote_survives_whitespace_differences(refs):
    source = refs.add_source("Widget Settling", PAPER, "k1")
    extract = refs.add_extract(
        source, "Peak   overshoot\n   reached 12 percent.", "k2"
    )
    assert refs.rows.get(extract).content["start_offset"] > 0


def test_empty_quote_is_refused(refs):
    source = refs.add_source("Widget Settling", PAPER, "k1")
    with pytest.raises(QuoteNotVerified):
        refs.add_extract(source, "  ", "k2")


def test_extract_links_to_its_source(refs):
    source = refs.add_source("Widget Settling", PAPER, "k1")
    extract = refs.add_extract(source, "Widgets settle in 40 ms.", "k2")
    row = refs.rows.get(extract)
    assert any(link.target == source and link.edge_type == "cites"
               for link in row.links)


def test_extract_carries_surrounding_context(refs):
    """Selective quoting is reduced by keeping a window around the quote."""
    source = refs.add_source("Widget Settling", PAPER, "k1")
    extract = refs.add_extract(source, "Widgets settle in 40 ms.", "k2",
                               context_chars=100)
    context = refs.rows.get(extract).content["context"]
    assert "Conclusion" in context


def test_unknown_source_is_named(refs):
    with pytest.raises(SourceNotFound):
        refs.add_extract("sources:99", "anything", "k")


def test_search_returns_locators(refs):
    source = refs.add_source("Widget Settling", PAPER, "k1")
    hits = refs.search("settling time")
    assert hits
    assert hits[0].source == source
    assert hits[0].section == "Results"
    assert "40 ms" in hits[0].snippet


def test_search_can_scope_to_one_source(refs):
    refs.add_source("Paper A", PAPER, "k1")
    b = refs.add_source("Paper B", "Results\nGadgets settle in 900 ms.\n", "k2")
    hits = refs.search("settle", source=b)
    assert {h.source for h in hits} == {b}


def test_read_span_is_bounded(refs):
    """A paper never arrives in context wholesale."""
    source = refs.add_source("Widget Settling", PAPER, "k1")
    assert len(refs.read_span(source, 0, 10_000, max_chars=50)) == 50


def test_read_section_by_heading(refs):
    source = refs.add_source("Widget Settling", PAPER, "k1")
    text = refs.read_section(source, "limitations")
    assert "60 C was not characterised" in text


def test_section_coverage_flags_what_was_never_read(refs):
    """The meter behind the omission problem: cited from Results, never from
    Limitations — and Limitations is where the study-killing caveat lives."""
    source = refs.add_source("Widget Settling", PAPER, "k1")
    refs.add_extract(
        source, "The measured settling time was 40 ms under nominal load.", "k2"
    )
    coverage = {c.heading: c for c in refs.section_coverage(source)}
    assert coverage["Results"].extract_count == 1
    assert coverage["Limitations"].untouched is True
    assert coverage["Methods"].untouched is True


def test_detect_sections_finds_paper_structure():
    headings = [h for h, _, _ in detect_sections(PAPER)]
    assert "Abstract" in headings
    assert "Methods" in headings
    assert "Limitations" in headings


def test_detect_sections_handles_unstructured_text():
    sections = detect_sections("just a blob of prose with no headings at all")
    assert len(sections) == 1
    assert sections[0][0] == "(whole document)"


def test_identical_texts_deduplicate(refs, store):
    refs.add_source("Copy A", PAPER, "k1")
    refs.add_source("Copy B", PAPER, "k2")
    assert len(store.query("SELECT * FROM source_texts")) == 1
    assert refs.rows.read_rows(RowSelector(table="sources")).total == 2
