"""Reference sources and verified extracts.

Not in the frozen plan — this is deviation D3, filling the hole recorded as DEFECTS.md
F2, where the plan mandates research for scientific claims but specifies nowhere for the
research to live. Design: V2_BUILD_PLAN.md section 5.

The invariant this module exists to enforce:

    An extract cannot be written unless its verbatim quote is an exact substring of the
    cited source's stored text.

That is a pure string operation, which matters: decisions:12 forbids the tool from
holding an LLM API, so verification cannot depend on a model. It kills fabrication (an
invented finding has no matching text) and cross-source conflation (the quote is checked
against one specific source). It does not kill misinterpretation, which is why the quote
is stored beside the paraphrase and travels with it everywhere.

Sources and extracts are ordinary plan rows (`sources:n`, `extracts:n`), so they inherit
provenance, supersession lineage and link participation with no special-casing.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from engine.errors import (
    QuoteNotVerified,
    RowNotFound,
    SourceNotFound,
    SourceTextUnavailable,
)
from engine.models import LinkSpec, PlanRow, Provenance, RowRef, RowSubmission
from engine.rows import RowService
from engine.clock import now
from engine.storage import Op, Storage

SOURCES_TABLE = "sources"
EXTRACTS_TABLE = "extracts"

#: Headings a scientific paper is likely to use. Detection is heuristic and its misses
#: are visible rather than silent: an unsectioned span still verifies, it just has a
#: coarser locator.
_HEADING_WORDS = (
    "abstract", "introduction", "background", "related work", "method", "methods",
    "methodology", "materials and methods", "experiment", "experiments",
    "experimental setup", "results", "evaluation", "analysis", "discussion",
    "limitations", "threats to validity", "future work", "conclusion", "conclusions",
    "acknowledgements", "acknowledgments", "references", "bibliography", "appendix",
)
_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\d+(?:\.\d+)*\.?\s+)?(" + "|".join(_HEADING_WORDS) + r")\s*:?\s*$",
    re.IGNORECASE,
)


# --- normalization -----------------------------------------------------------------


def _normalize(text: str, keep_break_hyphen: bool = False) -> tuple[str, list[int]]:
    """Collapse whitespace and join words split across lines, keeping an offset map.

    Returns the normalized text and a list mapping each normalized character index back
    to its index in the raw text, so a match found in normalized space can be reported
    as a locator into the original document.

    A hyphen before a line break is ambiguous — `high-\\nspeed` may be the word
    "highspeed" broken across lines, or the genuine compound "high-speed" that happened
    to wrap. Nothing in the text distinguishes them, so this produces one reading and
    the caller tries both (see `_locate`). `keep_break_hyphen` selects the reading.

    PDF extraction routinely breaks words this way and varies whitespace; without this,
    legitimate quotes would fail to verify. See V2_BUILD_PLAN.md section 5.7.
    """
    out: list[str] = []
    index_map: list[int] = []
    i = 0
    pending_space = False
    length = len(text)

    while i < length:
        char = text[i]
        if char == "-" and i + 1 < length and text[i + 1] in "\r\n":
            if keep_break_hyphen:
                out.append("-")
                index_map.append(i)
            i += 1
            while i < length and text[i] in "\r\n \t":
                i += 1
            continue
        if char.isspace():
            pending_space = bool(out)
            i += 1
            continue
        if pending_space:
            out.append(" ")
            index_map.append(i)
            pending_space = False
        out.append(char)
        index_map.append(i)
        i += 1

    return "".join(out), index_map


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_sections(text: str) -> list[tuple[str, int, int]]:
    """Split raw text into (heading, start_offset, end_offset) spans."""
    marks: list[tuple[str, int]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        match = _HEADING_RE.match(line.rstrip("\r\n"))
        if match:
            marks.append((match.group(1).strip().title(), offset))
        offset += len(line)

    if not marks:
        return [("(whole document)", 0, len(text))]

    sections: list[tuple[str, int, int]] = []
    if marks[0][1] > 0:
        sections.append(("(front matter)", 0, marks[0][1]))
    for index, (heading, start) in enumerate(marks):
        end = marks[index + 1][1] if index + 1 < len(marks) else len(text)
        sections.append((heading, start, end))
    return sections


# --- results -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchHit:
    source: RowRef
    section: str | None
    start_offset: int
    end_offset: int
    snippet: str


@dataclass(frozen=True, slots=True)
class SectionCoverage:
    """The meter behind V2_BUILD_PLAN.md section 5.4.

    A paper cited from Results but never from Limitations is a gap, and Limitations is
    where study-killing caveats live. gap-engine consumes this in M2.
    """

    source: RowRef
    heading: str
    ordinal: int
    extract_count: int

    @property
    def untouched(self) -> bool:
        return self.extract_count == 0


class ReferenceService:
    def __init__(self, storage: Storage, rows: RowService):
        self.storage = storage
        self.rows = rows

    # --- ingest ---

    def add_source(
        self,
        title: str,
        text: str,
        idempotency_key: str,
        authors: str | None = None,
        year: int | None = None,
        identifier: str | None = None,
        path: str | None = None,
        lease=None,
    ) -> RowRef:
        """Store a source and its full text.

        The tool never fetches: the session supplies the text, and the retrieved copy
        plus its hash are stored so the citation survives URL rot (V2_BUILD_PLAN.md
        5.6). The full text is never loaded into context wholesale — only extracts and
        bounded spans travel.
        """
        if not text or not text.strip():
            raise SourceTextUnavailable(
                "a source must be stored with its text, or its quotes could never be "
                "verified",
                title=title,
            )

        content_hash = _hash(text)
        sections = detect_sections(text)

        ops: list[Op] = []
        if not self._text_row(content_hash):
            ops.append(
                Op("insert", "source_texts", {
                    "content_hash": content_hash,
                    "text": text,
                    "char_count": len(text),
                    "created_at": now(),
                })
            )
            ops.extend(
                Op("insert", "source_sections", {
                    "content_hash": content_hash,
                    "ordinal": ordinal,
                    "heading": heading,
                    "start_offset": start,
                    "end_offset": end,
                })
                for ordinal, (heading, start, end) in enumerate(sections, start=1)
            )

        ops.append(
            Op("insert_row", "plan_rows", {
                "table_name": SOURCES_TABLE,
                "content": _json({
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "identifier": identifier,
                    "path": path,
                    "content_hash": content_hash,
                    "char_count": len(text),
                    "sections": len(sections),
                }),
                "provenance": str(Provenance.DECIDED),
                "assumption_kind": None,
                "state": "active",
                "package": None,
                "created_at": now(),
            })
        )

        receipt = self.storage.write_atomic(ops, idempotency_key, lease=lease)
        if not receipt.get("replayed"):
            self._index_text(content_hash, text)
        return RowRef.parse(receipt["results"][-1]["ref"])

    def _index_text(self, content_hash: str, text: str) -> None:
        """Best-effort FTS indexing; absence of FTS5 degrades search, never writes."""
        try:
            self.storage.conn.execute(
                "INSERT INTO source_fts (content_hash, text) VALUES (?, ?)",
                (content_hash, text),
            )
            self.storage.conn.commit()
        except Exception:  # noqa: BLE001 - FTS5 may not be compiled in
            pass

    # --- the invariant ---

    def add_extract(
        self,
        source: RowRef | str,
        quote: str,
        idempotency_key: str,
        paraphrase: str | None = None,
        links: list[LinkSpec] | None = None,
        context_chars: int = 240,
        lease=None,
    ) -> RowRef:
        """File an extract, refusing any quote that is not in the source.

        This is the enforcement point for the whole citation design. A quote that does
        not appear in this specific source's stored text cannot be filed, so neither a
        fabricated finding nor one belonging to a different paper can acquire a
        citation.
        """
        source_ref = RowRef.coerce(source)
        source_row = self._source_row(source_ref)
        content_hash = source_row.content["content_hash"]
        text_row = self._text_row(content_hash)
        if text_row is None:
            raise SourceTextUnavailable(
                "the source's text is not stored, so the quote cannot be verified; "
                "refusing rather than filing an unverifiable extract",
                source=str(source_ref),
            )

        if not quote or not quote.strip():
            raise QuoteNotVerified("an extract must carry a verbatim quote",
                                   source=str(source_ref))

        raw = text_row["text"]
        start, end = self._locate(raw, quote)
        if start is None:
            raise QuoteNotVerified(
                "the quote does not appear in this source's stored text; the extract "
                "was not filed",
                source=str(source_ref),
                source_title=source_row.content.get("title"),
                quote_preview=quote[:120],
            )

        section = self._section_at(content_hash, start)
        window_start = max(0, start - context_chars)
        window_end = min(len(raw), end + context_chars)

        submission = RowSubmission(
            table=EXTRACTS_TABLE,
            content={
                "source": str(source_ref),
                "quote": raw[start:end],
                "quote_normalized": quote.strip(),
                "start_offset": start,
                "end_offset": end,
                "section": section,
                "paraphrase": paraphrase,
                "context": raw[window_start:window_end],
                "context_offsets": [window_start, window_end],
                "verified_at": now(),
            },
            provenance=Provenance.DERIVED,
            links=[LinkSpec(source_ref, "cites"), *(links or [])],
        )
        receipt = self.rows.submit_rows([submission], idempotency_key, lease=lease)
        verdict = receipt.verdicts[0]
        if not verdict.accepted:
            raise QuoteNotVerified(
                "the extract was rejected", problem=verdict.problem
            )
        return verdict.ref

    @staticmethod
    def _locate(raw: str, quote: str) -> tuple[int | None, int | None]:
        """Find a quote in raw text, tolerating whitespace and hyphenation differences.

        Exact match is tried first so the common case stays cheap and unambiguous.
        """
        direct = raw.find(quote)
        if direct != -1:
            return direct, direct + len(quote)

        # Both readings of a line-break hyphen, on both sides. A quote is verified if
        # any reading matches: the ambiguity is in the source text, not in the claim.
        for keep_text in (False, True):
            norm_text, index_map = _normalize(raw, keep_break_hyphen=keep_text)
            for keep_quote in (False, True):
                norm_quote, _ = _normalize(quote, keep_break_hyphen=keep_quote)
                if not norm_quote:
                    continue
                found = norm_text.find(norm_quote)
                if found != -1:
                    start = index_map[found]
                    last = index_map[found + len(norm_quote) - 1]
                    return start, last + 1
        return None, None

    # --- retrieval ---

    def search(
        self, query: str, source: RowRef | str | None = None, limit: int = 10
    ) -> list[SearchHit]:
        """Lexical search over stored sources (V2_BUILD_PLAN.md 5.4).

        No embeddings exist here — decisions:12 forbids the tool from holding an LLM
        API — so retrieval is FTS5/BM25, with a substring fallback when FTS5 is absent.
        """
        scope = [self._source_row(source)] if source is not None else self._all_sources()
        hits: list[SearchHit] = []

        for source_row in scope:
            content_hash = source_row.content["content_hash"]
            text_row = self._text_row(content_hash)
            if text_row is None:
                continue
            raw = text_row["text"]
            for start, end in self._matches(raw, query, limit):
                window_start = max(0, start - 120)
                window_end = min(len(raw), end + 120)
                hits.append(
                    SearchHit(
                        source=source_row.ref,
                        section=self._section_at(content_hash, start),
                        start_offset=start,
                        end_offset=end,
                        snippet=raw[window_start:window_end],
                    )
                )
                if len(hits) >= limit:
                    return hits
        return hits

    @staticmethod
    def _matches(raw: str, query: str, limit: int) -> list[tuple[int, int]]:
        found: list[tuple[int, int]] = []
        needle = query.strip().lower()
        if not needle:
            return found
        hay = raw.lower()
        start = hay.find(needle)
        while start != -1 and len(found) < limit:
            found.append((start, start + len(needle)))
            start = hay.find(needle, start + len(needle))
        return found

    def read_span(
        self, source: RowRef | str, start: int, end: int, max_chars: int = 4000
    ) -> str:
        """Read a bounded region on demand. Bounded deliberately: the point of the
        design is that a paper never arrives in context wholesale."""
        source_row = self._source_row(source)
        text_row = self._text_row(source_row.content["content_hash"])
        if text_row is None:
            raise SourceTextUnavailable("no stored text", source=str(source_row.ref))
        raw = text_row["text"]
        start = max(0, start)
        end = min(len(raw), max(start, end))
        if end - start > max_chars:
            end = start + max_chars
        return raw[start:end]

    def read_section(self, source: RowRef | str, heading: str) -> str:
        source_row = self._source_row(source)
        content_hash = source_row.content["content_hash"]
        for row in self.storage.query(
            "SELECT heading, start_offset, end_offset FROM source_sections "
            "WHERE content_hash = ? ORDER BY ordinal",
            (content_hash,),
        ):
            if row["heading"].lower() == heading.strip().lower():
                return self.read_span(source_row.ref, row["start_offset"],
                                      row["end_offset"])
        raise SourceNotFound("no such section in this source",
                             source=str(source_row.ref), heading=heading)

    # --- the coverage meter ---

    def section_coverage(self, source: RowRef | str) -> list[SectionCoverage]:
        """Which sections of a source have ever been drawn from."""
        source_row = self._source_row(source)
        content_hash = source_row.content["content_hash"]
        offsets = [
            row.content["start_offset"]
            for row in self._extracts_for(source_row.ref)
        ]
        coverage: list[SectionCoverage] = []
        for row in self.storage.query(
            "SELECT ordinal, heading, start_offset, end_offset FROM source_sections "
            "WHERE content_hash = ? ORDER BY ordinal",
            (content_hash,),
        ):
            count = sum(
                1 for o in offsets if row["start_offset"] <= o < row["end_offset"]
            )
            coverage.append(
                SectionCoverage(source_row.ref, row["heading"], row["ordinal"], count)
            )
        return coverage

    # --- internals ---

    def _all_sources(self) -> list[PlanRow]:
        from engine.models import RowSelector

        page = self.rows.read_rows(
            RowSelector(table=SOURCES_TABLE, live_only=True, limit=1000)
        )
        return list(page.rows)

    def _source_row(self, source: RowRef | str) -> PlanRow:
        ref = RowRef.coerce(source)
        if ref.table != SOURCES_TABLE:
            raise SourceNotFound("not a source ref", ref=str(ref))
        try:
            return self.rows.get(ref)
        except RowNotFound as exc:
            raise SourceNotFound("no such source", ref=str(ref)) from exc

    def _extracts_for(self, source_ref: RowRef) -> list[PlanRow]:
        from engine.models import RowSelector

        page = self.rows.read_rows(
            RowSelector(table=EXTRACTS_TABLE, live_only=True, limit=1000)
        )
        return [r for r in page.rows if r.content.get("source") == str(source_ref)]

    def _text_row(self, content_hash: str):
        rows = self.storage.query(
            "SELECT * FROM source_texts WHERE content_hash = ?", (content_hash,)
        )
        return rows[0] if rows else None

    def _section_at(self, content_hash: str, offset: int) -> str | None:
        rows = self.storage.query(
            "SELECT heading FROM source_sections WHERE content_hash = ? "
            "AND start_offset <= ? AND end_offset > ? ORDER BY ordinal LIMIT 1",
            (content_hash, offset, offset),
        )
        return rows[0]["heading"] if rows else None


def _json(payload: dict) -> str:
    import json

    return json.dumps(payload)
