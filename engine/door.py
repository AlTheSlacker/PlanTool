"""The door — everything leaving the tool passes through here.

`mcp-surface` (`components:15`) is the only externally visible task, so every byte that
reaches any planner crosses one choke point. That makes it the one place where an
output-shaped rule can be a *mechanism* rather than an intention, which is why two
invariants that look unrelated live in the same module:

  **Never emit an address without the name of what it addresses** (M6_PLAN.md §6.7,
  clause 4 of the naming design). `requirements:61`'s addressing scheme is `table:ordinal`,
  and an address on its own forces the reader to go and look it up — which a person does
  not do, and which a model answers by inventing something plausible.

  **Never name a call the surface does not expose** (M6_PLAN.md §7.6). The resume digest
  closes by telling a cold planner what to fetch; before this module existed, five of the
  six calls it named could not be reached through any tool.

They are the same invariant said twice: **the tool never points a reader at something the
reader cannot get to.** So they are one pass over the payload, not two.

Two layers, and the second is the one that holds:

  1. `render` is the only path from an engine value to a payload, and it resolves every
     `RowRef` through a name lookup. There is no code path that emits a bare address,
     because a `RowRef` does not survive rendering.
  2. `scan` re-reads the finished payload and fails the call on any bare address or
     unreachable call name. This is the backstop for hand-assembled message strings —
     error text, digest lines — which the first layer cannot see, and hand-assembled
     strings are exactly where the digest's "1 engineer's mandate — get_mandate() to read
     them" nonsense came from.

`RowRef.__str__` is untouched and still produces `table:ordinal`: that is the correct
storage form for the `links`, `supersedes` and `superseded_by` columns. Storage form and
display form are different types, and only one of them may leave.

**Where the line between the two layers falls.** Every string that comes off stored data is
`Verbatim` and is annotated, never rewritten and never rejected. Every string the surface
assembles itself is plain, and must accompany any address it names. That split is not a
convenience: an address the owner typed into his own prose is *input*, and blocking a call
over it would be the tool editing the owner's words (M6_PLAN.md §6.10), while an address
the tool composed is the tool's own failure to name something. The rule needs no list of
exempt fields — the value's own type carries it, so nothing rots.
"""

from __future__ import annotations

import re
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Callable

from engine.errors import PlanToolError
from engine.models import RowRef

#: An address as it appears in text. Deliberately the same shape as `models.REF_PATTERN`
#: without the anchors, because the scan hunts occurrences inside prose rather than
#: validating a whole string. The leading lowercase letter is what keeps clock times
#: (`10:39`) and ratios out of the net.
ADDRESS = re.compile(r"\b[a-z][a-z0-9_]*:[1-9][0-9]*\b")

#: A call name as our output writes one: `next_gaps()`, `get_stage_script(1)`,
#: `get_stage_script(N)`. An identifier, an open bracket, and then either the close or an
#: argument position — never a letter. The letter is what keeps English out: prose is full
#: of `row(s)`, `hole(s)` and `assumed(intent)`, and an earlier version of this pattern
#: matched all of them. A false rejection here fails a call that was working, which is a
#: worse trade than letting a name through, so the pattern is the narrow one.
CALL = re.compile(r"\b([a-z_][a-z0-9_]*)\((?=\)|[0-9N])")

#: What `render` produces, and the only form `scan` accepts: something, a space, and the
#: address in brackets. Both layers read this one pattern, so they agree by construction
#: rather than by both having been written correctly.
ACCOMPANIED = re.compile(r"\S ?\([a-z][a-z0-9_]*:[1-9][0-9]*\)")

NO_LIVE_ROW = "no live row at this address"

#: Our own build documents. A planner using the tool has no copy of any of them, so citing
#: one in a message the tool hands out is the same failure as a bare address wearing a
#: different hat — it points the reader at something they cannot open (M6_PLAN.md §6.9a,
#: which was itself found by reading driver output that said "…the address rides alongside
#: it (M6_PLAN.md §6)" to a planner). They stay legal in comments and docstrings, which are
#: read by us.
INTERNAL_DOCUMENTS = (
    "M5_PLAN.md",
    "M6_PLAN.md",
    "DEFECTS.md",
    "DEVIATIONS.md",
    "GLOSSARY.md",
    "V2_BUILD_PLAN.md",
)

#: Names for the parts of a payload the surface assembles rather than reads. Used only in
#: error text, so a failure says *where* rather than making the reader diff two payloads.
ROOT = "result"


class BareAddress(PlanToolError):
    """An outgoing payload carried an address with nothing naming what it addresses.

    Not in the frozen plan — the naming design is a deviation (M6_PLAN.md §6.11, DEVIATIONS
    D18). It fails the call rather than warning, because a warning about unreadable output
    is itself output nobody reads.
    """


class UnreachableCall(PlanToolError):
    """An outgoing payload told the reader to make a call the surface does not expose.

    The failure the pre-build audit found in `plan_status`: a digest closing by naming six
    calls, of which one could be made.
    """


class Verbatim(str):
    """Stored prose, served as written.

    A brief serves the plan's own text and must not be rewritten — frozen content edited in
    flight is a far worse defect than a lookup (M6_PLAN.md §6.8). So verbatim strings are
    exempt from both invariants and the tool **annotates alongside** instead: `render`
    appends the resolution of every address the prose cites, which is also where F17 stops
    being silent. A citation of a superseded row is resolved to its live successor, one
    whose chain is closed says so, and an address that reaches nothing at all reads as "no
    live row at this address" — none of it by touching the frozen prose (owner, 2026-07-23).

    A `str` subclass rather than a wrapper, so the exemption travels with the value through
    every nested structure and the scan cannot miss it.
    """

    __slots__ = ()


class Resolution(dict):
    """One address the payload cited, and what it turned out to be.

    A plain dict so it serialises with no special casing; a named type so the scan can tell
    an annotation from ordinary content and leave it alone.
    """

    __slots__ = ()


def label(name: str | None, ref: RowRef | str) -> str:
    """The one display form for an address: `name (table:ordinal)`.

    The name leads, because the name is what the reader is being told; the address rides
    behind it so a caller that wants to fetch the row still can. Every message anywhere in
    the engine that mentions a row should be built with this — `scan` accepts this shape
    and no other, so the two agree by construction, and a second spelling of it somewhere
    else is how the rule quietly acquires an exception.
    """
    return f"{name or NO_LIVE_ROW} ({ref})"


def resolver_from(rows: Any, findings: Any = None) -> Callable[[RowRef], tuple[str | None, str]]:
    """Build the name lookup `render` needs.

    Returns `(name, state)`, where a missing row is `(None, 'absent')`. State comes back
    alongside the name because a *superseded* row still has a perfectly good name — the
    reader needs to know the citation moved on, and that is not the same failure as F17's
    address pointing at nothing at all.

    **Two stores, one address space, and that is the point** (D22, DEFECTS.md F38). A
    finding is addressed `findings:N` and lives in its own table, not in `plan_rows` —
    because its lifecycle is a state machine and a plan row's is supersession. Addressing
    never required a common table; it required somebody able to resolve it, which is this
    function. Without the second lookup every `findings:3` in the owner's own prose came
    back as *no live row at this address*, and the door would have been reporting the F17
    damage it exists to detect, where there was none.
    """

    def resolve(ref: RowRef) -> tuple[str | None, str]:
        if findings is not None and ref.table == findings.TABLE:
            found = findings.find(ref)
            return (found.name, found.state) if found is not None else (None, "absent")
        try:
            row = rows.get(ref)
        except Exception:
            return None, "absent"
        return row.name, row.state.value if isinstance(row.state, Enum) else str(row.state)

    return resolve


def display(ref: RowRef, resolve: Callable[[RowRef], tuple[str | None, str]]) -> str:
    name, _state = resolve(ref)
    return label(name, ref)


#: The two states a plan row is in when it has dropped out of live reads. A citation of
#: such a row is F17's whole subject: the prose is frozen and keeps pointing where it
#: pointed, and the row it points at has moved on or been struck out.
DEAD_STATES = ("superseded", "retired")


def successor_lookup(rows: Any, findings: Any = None) -> Callable[[RowRef], tuple[RowRef, str] | None]:
    """For a citation of a dead row, where its lineage stands now (owner, 2026-07-23).

    F17's read-time half made a dead citation *visible*; this is the owner's ruling on
    what to do once it is seen — **resolve it to the live successor, or say the chain is
    closed.** A brief is consumed by a code engine that cannot go and look, so telling it a
    row was superseded and stopping there strands it exactly where the wrong diagnosis of
    F15 stranded a person. Following `superseded_by` is not the tool exercising judgment: it
    is a write-once structural pointer, resolved the same mechanical way a name is.

    Returns `(head_ref, head_name)` when the supersession chain reaches a row that is still
    live, and `None` when it does not — either the chain ends at a row that was itself
    retired, or nothing superseded the cited row and it was simply struck out. `None` is the
    "no live successor" case the owner asked to be stated plainly rather than repaired.

    Only ever asked about plan rows. A finding has a state machine, not a supersession
    chain, so a `findings:` address never has a successor to follow — the guard makes that
    explicit rather than leaving it to `lineage_head` returning the ref unchanged.
    """

    def follow(ref: RowRef) -> tuple[RowRef, str] | None:
        if findings is not None and ref.table == findings.TABLE:
            return None
        try:
            head_ref = rows.lineage_head(ref)
        except Exception:
            return None
        if str(head_ref) == str(ref):
            return None  # nothing superseded it; the chain ends where it was cited
        try:
            head = rows.get(head_ref)
        except Exception:
            return None
        if not head.is_live:
            return None  # the chain is closed: its end is itself dead
        return head_ref, head.name

    return follow


def collect(
    text: str,
    resolve: Callable[[RowRef], tuple[str | None, str]],
    into: list[Resolution],
    follow: Callable[[RowRef], tuple[RowRef, str] | None] | None = None,
) -> Verbatim:
    """Note every address the text cites, and hand the text back untouched.

    **Untouched is the load-bearing word, and it was learned the hard way.** The first
    version returned `{"text": …, "cites": […]}` in place of the string, which read well
    and broke the tool: a gap key and a warning key are *identifiers* that happen to
    contain an address, and a caller who reads one and passes it back to `dismiss_gap` was
    suddenly handing over an object. Annotation must never change a value's shape. So the
    resolutions accumulate in one list that the surface attaches beside the payload, and
    the payload itself is exactly what it always was.

    When `follow` is given, a citation of a dead row is resolved through its supersession
    chain (`successor_lookup`, owner's F17 ruling): the resolution gains a `successor`
    address and a `successor_name` when the chain reaches a live row, or `successor: None`
    when it is closed. The successor's address and name go in *separate keys* for the same
    reason the payload's do — a bare address inside a value the reader must parse is the
    failure this module exists to stop. Callers without a row service (the door's own tests
    with a bare lambda resolver) omit `follow` and get the plain resolution as before.
    """
    for token in dict.fromkeys(ADDRESS.findall(text)):
        if any(r["address"] == token for r in into):
            continue
        ref = RowRef.parse(token)
        name, state = resolve(ref)
        cite = Resolution(address=token, name=name or NO_LIVE_ROW, state=state)
        if follow is not None and state in DEAD_STATES:
            successor = follow(ref)
            if successor is None:
                cite["successor"] = None  # chain closed: no live successor to point at
            else:
                succ_ref, succ_name = successor
                cite["successor"] = str(succ_ref)
                cite["successor_name"] = succ_name
        into.append(cite)
    return Verbatim(text)


def render(
    value: Any,
    resolve: Callable[[RowRef], tuple[str | None, str]],
    cites: list[Resolution] | None = None,
    follow: Callable[[RowRef], tuple[RowRef, str] | None] | None = None,
) -> Any:
    """Turn an engine value into a payload, resolving every address on the way out.

    This is layer 1. It is exhaustive on purpose: an unhandled type raises rather than
    falling back to `str(value)`, because `str()` on a dataclass holding a `RowRef` is
    precisely how a bare address would get out.

    Every string that comes off stored data leaves as `Verbatim` — the same string, marked.
    That marking is what tells layer 2 to annotate rather than reject: the addresses in it
    are the owner's, or an earlier caller's, and rejecting a call over the owner's own words
    would be the tool editing his prose.
    """
    if cites is None:
        cites = []
    if isinstance(value, RowRef):
        return display(value, resolve)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return collect(value, resolve, cites, follow)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: render(getattr(value, f.name), resolve, cites, follow)
            for f in fields(value)
        }
    if isinstance(value, dict):
        # **A `RowRef` key is displayed, not `str()`-ed**, and this is the one place a bare
        # address could still get out. Layer 2 walks a payload's *values* and never its
        # keys, so `{str(ref): ...}` would put `requirements:61` in front of a reader with
        # no name beside it and no check able to see it — D19's rule failing exactly where
        # nothing enforces it. Added by v3 change 4, whose `RowPage.labels` is the first
        # ref-keyed mapping to cross this boundary; it costs one lookup per key and closes
        # the hole for every mapping after it.
        return {
            display(k, resolve) if isinstance(k, RowRef) else str(k):
                render(v, resolve, cites, follow)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [render(v, resolve, cites, follow) for v in value]
    raise TypeError(
        f"{type(value).__name__} has no rendering; add one rather than letting "
        f"str() decide, which is how a bare address escapes"
    )


def _walk(payload: Any, path: str):
    """Yield every scannable string in the payload with the path that reached it.

    `Verbatim` values and their annotations are skipped — they are exempt by design, and
    skipping them here rather than at each call site is what keeps the exemption from
    being forgotten somewhere.
    """
    if isinstance(payload, Verbatim):
        return
    if isinstance(payload, Resolution):
        return
    if isinstance(payload, str):
        yield payload, path
    elif isinstance(payload, dict):
        for k, v in payload.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(payload, (list, tuple)):
        for i, v in enumerate(payload):
            yield from _walk(v, f"{path}[{i}]")


def scan(payload: Any, known_calls: set[str], path: str = ROOT) -> None:
    """Layer 2. One pass, both invariants; raises on the first violation.

    Both checks are pure lookups over a set fixed at the moment of dispatch (M6_PLAN.md
    §6.7): the set of address tokens comes from the payload being returned, the set of call
    names from the registry. Nothing is re-derived later against a target that has moved,
    which is the mistake F26 records.
    """
    for text, where in _walk(payload, path):
        covered = [m.span() for m in ACCOMPANIED.finditer(text)]
        for hit in ADDRESS.finditer(text):
            start, end = hit.span()
            if not any(a <= start and end <= b for a, b in covered):
                token = hit.group(0)
                raise BareAddress(
                    f"{where} says {token!r} without naming what it is; "
                    f"render the row so the reader gets 'name ({token})'"
                )
        for name in CALL.findall(text):
            if name not in known_calls:
                raise UnreachableCall(
                    f"{where} tells the reader to call {name}(), which no tool exposes; "
                    f"expose it or stop naming it"
                )
        for document in INTERNAL_DOCUMENTS:
            if document in text:
                raise BareAddress(
                    f"{where} cites {document}, which is ours and not the reader's; "
                    f"cite it in a comment or a docstring instead"
                )
