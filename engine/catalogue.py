"""catalogue-service — every object, method and function the plan intends to exist (D10).

The defect it answers is measured in this repo's own history: three naming collisions landed
in a single sitting, and a helper was duplicated verbatim under a slightly longer name.
Neither was carelessness. The code that would have prevented them was not visible at the
moment of writing, because the codebase had outgrown the window — and that condition gets
worse, not better, as a project grows.

**The mechanism is a refusal, not a discipline.** D10's original rule was that near matches
already catalogued are *each* dismissed with a written reason, and the rule is right: "check
for duplicates" is an intention. Applied to every near match its cost is unaffordable, and
that is measured rather than feared — simulating the registration of v2's own 635 entries in
order, a page of five shows a mean of 3.90 candidates and the plan would owe **2,475 written
sentences**. `BUILD_SURFACE.md` §1 diagnoses v2's brief composition in exactly those terms —
*"a good rule with an unbudgeted cost, and it is why the execution half was never exercised:
the cheapest path was always to skip it"* — so requiring a dismissal per candidate would
rebuild that rule one level down, inside the change whose own design document diagnosed it.

So the registration runs the search itself and **refuses until the highest-ranked candidate
has been adjudicated**; the rest are shown and not required. That is 561 adjudications across
the whole plan rather than 2,475, and three things make it the right cut rather than a
compromise:

- **It is not a similarity threshold.** "The best candidate the ranking found" encodes no
  opinion about what similarity is worth acting on; it is the top of a list. No number
  decides whether something is a near match, so the standing ruling against thresholds is
  untouched.
- **The friction sits where the risk is.** If the ranking is any good the duplicate is at the
  top; if it is not, no adjudication count fixes that.
- **The mandatory answer is the one that stops the registration.** A planner cannot tick the
  box, because `same` and `contains` — the two verdicts anyone reaches for when the match is
  real — refuse the write.

**A comparison is recorded whether or not an entry follows**, and the refusing verdicts are
the ones that matter most: if only merges are written down, the next planner runs the same
search, sees the same candidate, and decides again — possibly the other way.

**Who adjudicates, and it is not the owner** (Al, 2026-07-31, after change 3 was built):
*"a word match provokes an investigation by you to check it is ok and only if you also agree
there is a similarity problem do you ask the user."* The refusal is addressed to the
**planning session**, which goes and looks at the candidate and answers. The owner hears
about it only when the session has looked and agrees there is a real duplicate or a real
naming collision.

That matters most at the moment this reads worst. **Every plan starts with an empty
catalogue**, and eligibility is any shared word — including `a` and `the` — so the first
handful of registrations in every project are matched against near-nonsense. The rarity
weight cannot help there: it is computed over the candidates, and with two entries in the
table there is no crowd for a common word to be diluted against. At v2's 635 entries the
noise is outranked and falls off a page of five; at three entries it *is* the page. Left to
reach the owner, the tool's first act on every new plan would be to ask him about fake
duplicates, and a meter that cries wolf stops being read (D7).

**This does not put judgment in the tool** (`decisions:12`), and the distinction is the whole
of it: the tool computes the ranking and refuses the write, and exercises no opinion about
what similarity is worth acting on. The session judges — as it already does for every gap
dismissal, every waiver and every other adjudication in v3. What is new is only that the
session's judgment is named as the filter in front of the owner rather than being passed
through to him.

**And the session is not trusted, it is recorded.** The guard against rubber-stamping is that
every verdict is stored with its reason and the owner can read the lot. That is the standard
`dismiss_gap` and the waiver log already set, and it is what the section below means by *the
remaining dishonesty is a lie in a record the owner can read*.

**The ranking is lexical and there is no alternative.** There is no model and there never
will be (`decisions:12`), and there are no embeddings. FTS5 was rejected on a measurement,
not a preference: `engine/schema.py` ships a `source_fts` virtual table and `references.py`
writes to it, and **nothing reads it** — `ReferenceService.search` claims FTS5/BM25 in its
docstring and its `_matches` helper is a plain lowercase substring scan. There is no working
FTS retrieval here to borrow, only a docstring saying there is.

**Where the tokeniser came from.** `TermService._tokens` was here first, and this module now
owns it — `terms.py` delegates. v3 change 4 settles the direction: with the glossary's own
near-match guard deleted there is exactly one caller of a shared tokeniser, so there is no
shared module and *"change 3 keeps `CatalogueService._rank` private and takes the tokeniser
with it"*. Extract on the second occurrence; there is no second occurrence. Change 4 then
deletes the delegation along with `violations()`, leaving this the only copy — which is why
the move happens here rather than a second tokeniser being written in the change whose own
subject is duplication.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

from engine.clock import now
from engine.errors import (
    PlanToolError,
    RetireNeedsReason,
    RowNotFound,
    UnresolvedReference,
)
from engine.models import (
    Candidate,
    CatalogueEntry,
    CatalogueResult,
    Cluster,
    Comparison,
    RowRef,
)
from engine.rows import RowService, stored_text, unresolved_refs
from engine.storage import FromOp, Op, Storage
from engine.tasks import TaskNotFound

#: A word, in prose or inside an identifier. `_` and case boundaries split identifiers, so
#: `planRowId` and `plan_row_id` tokenise the same way. Moved here from `terms.py` by v3
#: change 3; `TermService._tokens` delegates to `tokens()` below until change 4 deletes it.
WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+")

#: The component table. An object's owner must be a live row *in this table* — checked
#: rather than assumed, because `RowService.get` takes any ref and would happily accept
#: `requirements:4`, producing an object owned by a requirement.
COMPONENTS = "components"

OBJECT = "object"
FUNCTION = "function"
KINDS = (OBJECT, FUNCTION)

PUBLIC = "public"
PRIVATE = "private"
VISIBILITIES = (PUBLIC, PRIVATE)

SAME = "same"
CONTAINS = "contains"
CONTAINED_BY = "contained_by"
PARTIALLY_OVERLAPS = "partially_overlaps"
UNRELATED = "unrelated"

#: The five relationships, and what each instructs the planner to do. **The middle column is
#: an instruction to the planner and nothing in the engine performs it**, which is stated
#: because it would otherwise read as a promise: `contained_by` does not fold the old entry
#: in, and `partially_overlaps` does not extract anything. Both write the entry and record
#: the judgment, and the follow-through is the planner's next call — a retirement, or two
#: more registrations. Automating either would be the tool deciding that a function it has
#: never seen should be restructured, which is the line drawn everywhere else here: the tool
#: computes and shows, the planner decides.
RELATIONSHIPS = {
    SAME: "merge: use what exists",
    CONTAINS: "the existing entry contains the new one; use what exists",
    CONTAINED_BY: "the new one contains the existing; write it, and fold the old one in",
    PARTIALLY_OVERLAPS: "extract the shared middle as a third function",
    UNRELATED: "record the negative",
}

#: The two verdicts that refuse the write. See the module docstring: they are what makes the
#: adjudication load-bearing rather than a box a planner can tick past.
REFUSING = (SAME, CONTAINS)

#: The page size the search returns, and it is a page size and **not a threshold**: it bounds
#: what is displayed, never what counts as similar. `references.search` already carries
#: `limit: int = 10` for the same job. Five is chosen against the measurement — a page of
#: five shows a mean of 3.90 candidates over v2's own 635 entries.
PAGE = 5


class PurposeRequired(PlanToolError):
    """A catalogue entry with no purpose line is an entry the search cannot find.

    The purpose carries the whole weight of the search — inputs and outputs were rejected as
    a matching basis — so a blank one is not a missing nicety, it is an entry that will never
    match anything and will therefore never stop a duplicate.
    """


class ReasonRequired(PlanToolError):
    """A comparison records why, and blank is not why.

    Named rather than left to the database: `catalogue_comparisons.reason` is NOT NULL, so
    without this the honest answer "I have not written why" would surface as an
    `IntegrityError` naming a column, on this change's central write path.
    """


class NameTaken(PlanToolError):
    """A live entry already holds this name in this container.

    Reported as a refusal rather than as an `IntegrityError` so the message can name what
    already holds the name; `idx_catalogue_live_name` is what makes the check *true* rather
    than merely attempted. Both, deliberately — the same arrangement `submit_rows` has with
    `idx_rows_live_name`.

    **And the message carries a retired entry when it finds one**, with its retire reason.
    A dead function cannot be reused and offering it as a search candidate would be a
    confidently wrong answer — but the thing about to be written may have been removed on
    purpose, and the planner may be undoing somebody's decision without knowing it.
    """


class NearMatchesUnadjudicated(PlanToolError):
    """The search found candidates and the top-ranked ones have not been judged.

    The candidates travel in the refusal text, so the planner reads them and answers. There
    is no path to an entry that did not pass a search, because the tool runs the search
    inside the registration — which is the same guarantee a search receipt would have given,
    with no receipt to keep true and no staleness question to answer.
    """


class ContainerNotCatalogued(PlanToolError):
    """The named container is not a live object entry.

    Refused rather than created: creating it would be the tool deciding that a new object
    exists. This is why packet 3D.1 lands before this one — the message names a call, and
    `door.scan` raises `UnreachableCall` on outgoing text naming a call the registry cannot
    resolve, so written before the registry row exists the tool refuses its own refusal.
    """


class ComponentNotFound(PlanToolError):
    """`component_ref` does not address a live row in `components`.

    Three failures wear this one name and the message distinguishes them: no row at that
    address, a row that is not a component, and a component that is no longer live. All
    three matter — an object owned by a superseded component is an entry whose owner has
    moved, and the cross-container report groups by owner.
    """


class EntryPointExists(PlanToolError):
    """The task already has a live public function entry.

    D6 stated as a constraint: a task is one externally-callable function, so a second one
    means either the task is two tasks or the name is wrong, and both are worth stopping for.
    `idx_catalogue_task_entry` holds the invariant; this reports it.
    """


class EntryNotFound(PlanToolError):
    """No live entry holds this name and container."""


class ContainerNotEmpty(PlanToolError):
    """The object still holds live entries, and they are named.

    Retiring it would leave entries pointing at a dead container while the report groups by
    it. Naming the survivors is what makes the refusal actionable.
    """


class UnknownRelationship(PlanToolError):
    """A comparison's verdict is not one of the five.

    The database constrains the column too, and both are deliberate: the CHECK is what makes
    the rule true, and this is what names the five so a planner can pick one. A misspelling
    is worth its own refusal because it does not merely fail — it takes the permissive branch
    and writes the entry the planner had just said not to write.
    """


class UnknownVisibility(PlanToolError):
    """`visibility` is not `public` or `private`.

    Named rather than left to the CHECK for the same reason: `visibility` appears in
    `idx_catalogue_task_entry`'s predicate, where a typo does not fail — it drops the row out
    of the invariant and the task quietly acquires a second entry point.
    """


def tokens(text: str) -> set[str]:
    """The words in one string, lowercased, with plurals folded onto the singular.

    Plural folding is deliberately the crudest possible rule — a trailing `s` — because
    anything cleverer starts guessing, and a guess here spends the planner's attention on a
    word nobody wrote. The singular is *added* rather than substituted, so `tasks` matches
    both `tasks` and `task`.
    """
    words: set[str] = set()
    for token in WORD.findall(text or ""):
        token = token.lower()
        words.add(token)
        if token.endswith("s"):
            words.add(token[:-1])
    return words


def rank(
    name: str,
    purpose: str,
    entries: Iterable[CatalogueEntry],
    limit: int = PAGE,
) -> tuple[Candidate, ...]:
    """Rank entries against a proposed name and purpose, both directions in one pass.

    Pure, and separated from the service that reads the rows so it can be exercised without
    a store. **One function, called by both the search and the registration** — two rankings
    would let a planner be shown one candidate and be required to adjudicate another, and
    every individual test would still pass.

    **The search reads in both directions** because that is the design's own point: a close
    description under a different name is duplication, a close name with a different
    description is a naming collision, and one query answers both, so it costs nothing to
    look for both.

    **A shared word counts in inverse proportion to how many of the candidates contain it**,
    computed from the candidate set rather than from a maintained list of English. Measured
    over a real candidate set, the word `the` accounted for 46% of all matching and put noise
    at the top of the list — which is precisely where this change makes adjudication
    mandatory. This is not a threshold: no cut-off decides whether a word counts, and the
    weight only orders a list whose top is taken regardless. It changes eligibility not at
    all, so the measured 74-shown-nothing, 561 adjudications and mean of 3.90 all stand.

    **Ordering is total score, then the name half, then `id`.** The name half breaks ties
    because a name collision is the defect that bit this build three times in a sitting,
    while a description collision is what the catalogue is primarily aimed at; that is a
    preference and is stated as one, so a later change can argue with it. `id` breaks what
    is left because it is the only total order this schema guarantees — the draft said
    "older entry first" and meant `created_at`, which is not a stability guarantee at all:
    two entries written in the same clock tick share one, and their order is then whatever
    SQLite returns. An unstable ranking makes the required answer change between the call
    that showed the candidates and the call that answers them.
    """
    probe_name = tokens(name)
    probe_purpose = tokens(purpose)

    hits: list[tuple[CatalogueEntry, set[str], set[str]]] = []
    for entry in entries:
        name_hits = tokens(entry.name) & probe_name
        purpose_hits = tokens(entry.purpose) & probe_purpose
        if name_hits or purpose_hits:
            hits.append((entry, name_hits, purpose_hits))

    # The rarity weight's denominator is the candidate set, so it has to be counted after
    # eligibility and before scoring. A word every candidate shares weighs 1/n and decides
    # almost nothing; a word one candidate has weighs 1 and decides the order.
    frequency: dict[str, int] = {}
    for entry, _, _ in hits:
        for word in tokens(entry.name) | tokens(entry.purpose):
            frequency[word] = frequency.get(word, 0) + 1

    def weigh(words: set[str]) -> float:
        return sum(1.0 / frequency[w] for w in words)

    candidates = [
        Candidate(
            entry=entry,
            name_score=weigh(name_hits),
            purpose_score=weigh(purpose_hits),
            matched=tuple(sorted(name_hits | purpose_hits)),
        )
        for entry, name_hits, purpose_hits in hits
    ]
    candidates.sort(key=lambda c: (-c.score, -c.name_score, c.entry.id))
    return tuple(candidates[:limit])


def tied_at_top(candidates: Sequence[Candidate]) -> tuple[Candidate, ...]:
    """Every candidate sharing the top of the ranking, not merely the first.

    Behaviour 7's `id` tie-break makes the ranking *stable*, which is necessary and is not
    the same as making the top of it *meaningful*. When several candidates score identically
    the tie-break decides which one a planner is compelled to write a sentence about, and the
    equally-ranked alternatives are never adjudicated at all. Measured over fourteen probes
    against ten candidates, the top score is a tie in 4 of 14 unweighted and 2 of 14
    weighted, with a four-way tie in the worst case.

    So the tie is "equal under every ordering rule except `id`" — the ordering key with the
    id dropped. That is derived from the sort rather than restated beside it, which is what
    stops the two drifting.

    It is computed over the candidates that were **shown**. A planner can only adjudicate
    what they were given, and the refusal names exactly the page they saw.
    """
    if not candidates:
        return ()
    top = (candidates[0].score, candidates[0].name_score)
    return tuple(c for c in candidates if (c.score, c.name_score) == top)


class CatalogueService:
    """contracts: none — the frozen plan never anticipated a catalogue (v3 D10).

    **Neither collaborator is optional**, and that is written here rather than assumed
    because convention 11 makes an unpassed collaborator fail *silently*: its guard skipped,
    its effects omitted, the call proceeding. `rows` is what checks that a `component_ref`
    names a live component and what resolves the addresses inside stored prose, and a
    catalogue that skipped both would look identical to a working one.
    """

    def __init__(self, storage: Storage, rows: RowService):
        self.storage = storage
        self.rows = rows

    # --- the read path (task 3B.1) ---
    #
    # These are not three incidental helpers. The registrations need a lookup four times —
    # the name check, the container name-to-id resolution, the `(name, container)` finder
    # that retirement and restatement both start from, and "is this object still holding
    # live entries" — plus the entry every one of them returns has to be read back from
    # somewhere. Left unspecified, five tasks each invent their own query, which is this
    # change's own subject matter happening inside this change.

    def _find(
        self, name: str, container: str | None, include_retired: bool = False
    ) -> CatalogueEntry | None:
        """The one entry with this name and container, live unless asked otherwise.

        `include_retired` is the implementation site for *"a retired entry is still consulted
        for the name check"* — a property the design stated and nothing anywhere could
        perform, because the search excludes retired entries by definition and no call looked.
        """
        container_id = self._resolve_container(container) if container else None
        if container and container_id is None:
            return None
        sql = (
            "SELECT * FROM catalogue WHERE name = ? "
            "AND container_id IS ?"
        )
        if not include_retired:
            sql += " AND retired_at IS NULL"
        # Newest first so the name check sees the most recent retirement when several
        # generations of a reintroduced name exist.
        found = self.storage.query(sql + " ORDER BY id DESC", (name, container_id))
        return self._hydrate(found[0]) if found else None

    def _resolve_container(self, name: str) -> int | None:
        """The id of the live object entry with this name, or None when there is none."""
        found = self.storage.query(
            "SELECT id FROM catalogue WHERE name = ? AND kind = ? "
            "AND container_id IS NULL AND retired_at IS NULL",
            (name, OBJECT),
        )
        return found[0]["id"] if found else None

    def _live_within(self, container_id: int) -> tuple[CatalogueEntry, ...]:
        """The live entries this object holds. `idx_catalogue_container` serves this."""
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT * FROM catalogue WHERE container_id = ? AND retired_at IS NULL "
                "ORDER BY id",
                (container_id,),
            )
        )

    def _live(self) -> tuple[CatalogueEntry, ...]:
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT * FROM catalogue WHERE retired_at IS NULL ORDER BY id"
            )
        )

    def _rank(self, name: str, purpose: str, limit: int = PAGE) -> tuple[Candidate, ...]:
        """The live entries, ranked. A retired entry is never a candidate at any rank."""
        return rank(name, purpose, self._live(), limit)

    def _hydrate(self, row) -> CatalogueEntry:
        return CatalogueEntry(
            id=row["id"],
            name=row["name"],
            container=self._container_name(row["container_id"]),
            kind=row["kind"],
            visibility=row["visibility"],
            purpose=row["purpose"],
            owner=(
                row["task_id"]
                if row["task_id"] is not None
                else RowRef.parse(row["component_ref"])
            ),
            retired_at=row["retired_at"],
            retire_reason=row["retire_reason"],
        )

    def _container_name(self, container_id: int | None) -> str | None:
        if container_id is None:
            return None
        found = self.storage.query(
            "SELECT name FROM catalogue WHERE id = ?", (container_id,)
        )
        return found[0]["name"] if found else None

    # --- the registrations (tasks 3B.2 and 3B.3) ---

    def catalogue_object(
        self,
        name: str,
        purpose: str,
        visibility: str,
        component_ref: RowRef | str,
        idempotency_key: str,
        comparisons: tuple[Comparison, ...] = (),
    ) -> CatalogueResult:
        """Record an object the plan intends to exist, owned by a component.

        **Objects are the half that catches things.** Measured over v2's own engine: the
        identity `(name, container)` collides eleven times, six names over seventeen
        definitions — `PlanUnreadable` in four modules, `AlreadyResolved`, `InvalidTransition`
        and `RefNotFound` in three each, `Package` and `UnknownPackage` in two — and **zero**
        among the 431 function entries. Five of the six are error types, which are the names
        contracts cite, and a reader who imports the wrong `RefNotFound` writes an `except`
        clause that never fires. Leave objects out and eleven refusals become zero.
        """
        name = (stored_text(name) or "").strip()
        purpose = self._require_purpose(name, purpose)
        self._require_reasons(comparisons)
        self._refuse_unresolvable(purpose, comparisons)
        owner = self._live_component(component_ref)
        note = self._refuse_taken(name, container=None)
        return self._register(
            name=name,
            purpose=purpose,
            kind=OBJECT,
            visibility=self._require_visibility(visibility),
            container=None,
            container_id=None,
            task_id=None,
            component_ref=str(owner),
            comparisons=comparisons,
            idempotency_key=idempotency_key,
            note=note,
        )

    def catalogue_function(
        self,
        name: str,
        purpose: str,
        visibility: str,
        task_id: int,
        idempotency_key: str,
        container: str | None = None,
        comparisons: tuple[Comparison, ...] = (),
    ) -> CatalogueResult:
        """Record a function or method the plan intends to exist, owned by a task.

        `container` of `None` is module level and is not an error. **A module is not
        catalogued**: a module is a location, and location is never identity — if a row were
        identified by location, reorganising files would read as deletion plus addition and
        destroy the history the catalogue is accumulating.

        **A sequencing consequence that bites now and stops biting at change 5.** `task_id`
        references a row in `tasks`, and tasks are still derived at finalization from contract
        rows, so until change 5 moves task creation to stage 8 a function entry can only be
        catalogued for a plan that has been finalized. That is awkward and it is not a defect:
        the catalogue's real population happens at stage 8. Object entries have no such
        constraint, because a component is a plan row and exists from stage 6.
        """
        name = (stored_text(name) or "").strip()
        purpose = self._require_purpose(name, purpose)
        self._require_reasons(comparisons)
        self._refuse_unresolvable(purpose, comparisons)
        container = stored_text(container)
        container_id = None
        if container is not None:
            container_id = self._resolve_container(container)
            if container_id is None:
                raise ContainerNotCatalogued(
                    f"{container!r} is not a live object entry, so {name!r} has nothing to "
                    f"belong to. Catalogue the object first with catalogue_object(), then "
                    f"register this against it — an unknown container is refused rather "
                    f"than created, because creating it would be this tool deciding that a "
                    f"new object exists",
                    container=container, name=name,
                )
        self._require_task(task_id)
        visibility = self._require_visibility(visibility)
        # Checked against **this container**, not against module level. Inherited verbatim
        # from the object case, `catalogue_function("_hydrate", container="RowService")`
        # would be refused because a module-level `_hydrate` exists — the exact case the
        # whole table's identity is designed around.
        note = self._refuse_taken(name, container=container)
        if visibility == PUBLIC:
            self._refuse_second_entry_point(task_id, name)
        return self._register(
            name=name,
            purpose=purpose,
            kind=FUNCTION,
            visibility=visibility,
            container=container,
            container_id=container_id,
            task_id=task_id,
            component_ref=None,
            comparisons=comparisons,
            idempotency_key=idempotency_key,
            note=note,
        )

    def _register(
        self,
        *,
        name: str,
        purpose: str,
        kind: str,
        visibility: str,
        container: str | None,
        container_id: int | None,
        task_id: int | None,
        component_ref: str | None,
        comparisons: tuple[Comparison, ...],
        idempotency_key: str,
        note: str | None = None,
    ) -> CatalogueResult:
        """The half `catalogue_object` and `catalogue_function` share.

        **The refusal order is deliberate and it is the pseudocode's.** Cheap checks on the
        caller's own arguments run first, the lookups run next, and the search runs last
        because it is the expensive one. Get it the other way round and an exact name
        collision surfaces as `NearMatchesUnadjudicated` — because an exact match ranks first
        — so the planner is told to adjudicate a candidate when what they need to be told is
        that the name is taken.
        """
        comparisons = tuple(
            Comparison(
                matched=(stored_text(c.matched) or "").strip(),
                relationship=c.relationship,
                reason=c.reason,
                container=stored_text(c.container),
            )
            for c in comparisons
        )
        # Every comparison names a live entry, resolved here with the other lookups and
        # before the expensive search: a judgment recorded against nothing tells the next
        # planner nothing, and finding out after the ranking has run costs a scan for a
        # mistake in the caller's own argument.
        matched_ids: dict[tuple[str, str | None], int] = {}
        for comparison in comparisons:
            found = self._find(comparison.matched, comparison.container)
            if found is None:
                raise EntryNotFound(
                    f"the comparison judges {self._display_pair(comparison)}, which is not "
                    f"a live catalogue entry — a judgment recorded against nothing tells "
                    f"the next planner nothing",
                    matched=comparison.matched, container=comparison.container,
                )
            matched_ids[(comparison.matched, comparison.container)] = found.id

        candidates = self._rank(name=name, purpose=purpose)
        verdict = None
        if candidates:
            required = tied_at_top(candidates)
            judged = {
                (c.matched, c.container): c for c in comparisons
            }
            unjudged = [
                c for c in required
                if (c.entry.name, c.entry.container) not in judged
            ]
            if unjudged:
                raise NearMatchesUnadjudicated(
                    f"{name!r} was not written until you have looked at "
                    f"{'this' if len(unjudged) == 1 else 'these'} and said what you think. "
                    f"Go and read {'it' if len(unjudged) == 1 else 'them'} before answering: "
                    f"{self._unjudged_list(unjudged)}. "
                    # The rest of the page is shown only when there is a rest of the page.
                    # Repeating the same one line under two headings is noise in a message
                    # whose whole job is to be read.
                    + (
                        f"The others the search returned, best first: "
                        f"{self._candidate_list(c for c in candidates if c not in unjudged)}. "
                        if len(candidates) > len(unjudged) else ""
                    )
                    + f"**A shared word is not a duplicate.** The search matches on any word "
                    f"in common, including `a` and `the`, so a spurious match is expected "
                    f"and `unrelated` with a one-line reason is the right answer to it — "
                    f"look at what actually matched. What this asks is that somebody looked, "
                    f"not that they argued. Answer each with a relationship and a reason: "
                    f"{'; '.join(f'{k} — {v}' for k, v in RELATIONSHIPS.items())}",
                    name=name,
                    unjudged=[self._display(c.entry) for c in unjudged],
                )
            verdict = judged.get(
                (candidates[0].entry.name, candidates[0].entry.container)
            )

        stamp = now()
        ops: list[Op] = []
        entry_id_source: FromOp | None = None
        if verdict is not None and verdict.relationship in REFUSING:
            # `same` and `contains` are an **outcome, not an exception**. The call returns
            # "no entry written, use this one" and records the comparison. Raising would be
            # wrong twice over: the planner did exactly the right thing, and an exception
            # path that also commits a write is a shape nothing else in this engine has.
            written = None
        else:
            ops.append(Op("insert", "catalogue", {
                "name": name,
                "container_id": container_id,
                "kind": kind,
                "visibility": visibility,
                "purpose": purpose,
                "task_id": task_id,
                "component_ref": component_ref,
                "created_at": stamp,
                "updated_at": stamp,
            }))
            entry_id_source = FromOp(0)
            written = True

        for comparison in comparisons:
            ops.append(Op("insert", "catalogue_comparisons", {
                "proposed": name,
                "container_id": container_id,
                "matched_id": matched_ids[(comparison.matched, comparison.container)],
                "entry_id": entry_id_source,
                "relationship": comparison.relationship,
                "reason": stored_text(comparison.reason),
                "created_at": stamp,
            }))

        receipt = self.storage.write_atomic(ops, idempotency_key)
        if written is None:
            # The replay case that matters. No entry was written and no name is taken, so a
            # repeated call reaches `write_atomic` and the receipt suppresses a duplicate
            # comparison row. The other direction — replaying a call that *did* write an
            # entry — never reaches here: every guard above runs first and it is refused
            # with `NameTaken` naming the row the first call wrote, which is the correct
            # outcome rather than a gap.
            return CatalogueResult(
                entry=None,
                comparisons=comparisons,
                use_instead=candidates[0].entry,
                note=note,
            )
        entry_id = receipt["results"][0]["id"]
        return CatalogueResult(
            entry=self._by_id(entry_id),
            comparisons=comparisons,
            use_instead=None,
            note=note,
        )

    # --- retirement and restatement (tasks 3B.4 and 3B.5) ---

    def retire_catalogue_entry(
        self, name: str, reason: str, idempotency_key: str, container: str | None = None
    ) -> CatalogueEntry:
        """Withdraw an entry, with the reason on the record.

        `container` is last and defaulted, matching `catalogue_function` and the registry
        row, which marks it optional. A module-level entry is the ordinary case and a
        parameter the caller must pass `None` to is a parameter that gets passed wrongly.

        **Retirement is never undone.** The name is free for a new entry, and that entry is a
        new row. A function written, removed and written again is precisely the case that
        suggests something was wrong with the original design, and nulling the retirement
        would erase that history at the moment it becomes interesting. The lineage is a query
        — every entry with this name and container, oldest first — and no edge type is added,
        because the edge vocabulary is deliberately closed.
        """
        if not (reason or "").strip():
            raise RetireNeedsReason(
                f"retiring {name!r} records why it no longer applies, and blank is not why. "
                f"At planning time that is a design that changed; at build time it is an "
                f"absence discovered, and where it was discovered is what is actually known",
                name=name,
            )
        entry = self._require_live(name, container)
        if entry.kind == OBJECT:
            held = self._live_within(entry.id)
            if held:
                raise ContainerNotEmpty(
                    f"{name!r} still holds {len(held)} live "
                    f"{'entry' if len(held) == 1 else 'entries'}: "
                    f"{self._name_list(held)}. Retiring it would leave them pointing at a "
                    f"dead container, and the cross-container report groups by it — retire "
                    f"or move those first",
                    name=name, holds=[e.name for e in held],
                )
        self.storage.write_atomic(
            [Op("update", "catalogue",
                {"retired_at": now(), "retire_reason": stored_text(reason)},
                where={"id": entry.id})],
            idempotency_key,
        )
        return self._by_id(entry.id)

    def restate_purpose(
        self, name: str, purpose: str, idempotency_key: str, container: str | None = None
    ) -> CatalogueEntry:
        """Replace an entry's purpose line in place.

        **In place, and this is a deliberate departure from every other justification-bearing
        field in this store.** Change 2 made `grounds` write-once because an argument that can
        be rewritten is a place to revise history quietly. A purpose line is not an argument;
        it is an index entry, and nothing cites it. Forcing a retirement and a
        re-registration to fix a wrong verb would poison the one measurement the commit
        fields are carried for — churn is designed-and-dead-quickly, and it stops meaning
        anything if typos produce dead entries.

        **Recorded comparisons are untouched, and that is the honest cost.** A comparison
        judged against the old wording is not re-adjudicated, so a restatement can leave an
        `unrelated` verdict standing against an entry it no longer describes. Invalidating
        them would make restating expensive again and re-create the problem this call solves.
        The comparison records what was judged and when; the change feed records the
        restatement.
        """
        entry = self._require_live(name, container)
        purpose = self._require_purpose(name, purpose)
        self._refuse_unresolvable(purpose, ())
        self.storage.write_atomic(
            [Op("update", "catalogue",
                {"purpose": purpose, "updated_at": now()},
                where={"id": entry.id})],
            idempotency_key,
        )
        return self._by_id(entry.id)

    # --- the search and the report (packet 3C) ---

    def search_catalogue(self, query: str, limit: int = PAGE) -> tuple[Candidate, ...]:
        """Live entries ranked against a free-text query. No cut-off, no notification.

        The tool computes and shows; the planner decides. An empty result for a query that
        matches nothing is an answer and not an error.

        **The query goes into both arguments of the ranking, and that is right rather than
        double-counting.** An entry scores on words appearing in **its own** name and **its
        own** purpose; the probe is only the source of the words. So an entry matching the
        query in its name *and* in its purpose is a genuinely stronger match than one
        matching in either alone, and the name-outranks-purpose preference is a property of
        the entry side, untouched. A cold reader drew the opposite conclusion from the same
        fact, which is why this is written down rather than left to be re-derived.
        """
        return self._rank(name=query, purpose=query, limit=limit)

    def catalogue_clusters(self, limit: int = 20) -> tuple[Cluster, ...]:
        """Live entries grouped by shared purpose vocabulary, most shared first.

        **No cut-off and no notification**, which is `CATALOGUE.md` §5 and the owner's
        standing ruling: a threshold is a judgment written as arithmetic so that review
        cannot see it. "Three or more containers share a similar method" encodes an opinion
        about what similarity is worth acting on, as a number nobody will ever revisit.

        **Containers are reported and never filtered on** — see `Cluster`. Module-level
        entries participate on the same terms as any other, because excluding them would hide
        the case where a module-level helper and a method do the same job, which is one of the
        two shapes duplication actually takes here.

        **The cost is honest and unchanged from the design**: nobody is standing there when a
        duplication becomes true, so a ranked report only helps if someone reads it, and
        nothing in this change schedules that read. Change 5's stage-8 script owes the step.
        """
        entries = self._live()
        by_word: dict[str, list[CatalogueEntry]] = {}
        for entry in entries:
            for word in tokens(entry.purpose):
                by_word.setdefault(word, []).append(entry)

        # Group by the *set* of entries a word picks out, so words that travel together
        # produce one cluster naming all of them rather than one cluster each.
        grouped: dict[tuple[int, ...], set[str]] = {}
        for word, members in by_word.items():
            if len(members) < 2:
                continue  # a word one entry uses shares nothing with anybody
            grouped.setdefault(tuple(e.id for e in members), set()).add(word)

        by_id = {e.id: e for e in entries}
        clusters = [
            Cluster(
                shared=tuple(sorted(words)),
                members=tuple(by_id[i] for i in ids),
            )
            for ids, words in grouped.items()
        ]
        # Ordered by how much they share: the number of shared words first, then how many
        # entries share them, then the words themselves so the order is total and stable.
        clusters.sort(key=lambda c: (-len(c.shared), -len(c.members), c.shared))
        return tuple(clusters[:limit])

    # --- internals ---

    def _by_id(self, entry_id: int) -> CatalogueEntry:
        return self._hydrate(
            self.storage.query("SELECT * FROM catalogue WHERE id = ?", (entry_id,))[0]
        )

    def _require_purpose(self, name: str, purpose: str) -> str:
        clean = stored_text(purpose)
        if not clean:
            raise PurposeRequired(
                f"{name!r} needs a purpose line: verb, object, qualifier — what concept "
                f"this owns, in a phrase. It carries the whole weight of the search, so a "
                f"blank one is an entry nothing will ever match and which will therefore "
                f"never stop a duplicate",
                name=name,
            )
        return clean

    def _require_reasons(self, comparisons: Sequence[Comparison]) -> None:
        for comparison in comparisons:
            if comparison.relationship not in RELATIONSHIPS:
                raise UnknownRelationship(
                    f"{comparison.relationship!r} is not a relationship. One of: "
                    f"{'; '.join(f'{k} — {v}' for k, v in RELATIONSHIPS.items())}",
                    matched=comparison.matched,
                    relationship=comparison.relationship,
                )
            if not (comparison.reason or "").strip():
                raise ReasonRequired(
                    f"the comparison against {self._display_pair(comparison)} needs a "
                    f"reason: why it stands in that relationship to what you are about to "
                    f"write. The next planner runs this same search and sees this same "
                    f"candidate, and the reason is what stops them deciding it again",
                    matched=comparison.matched,
                )

    def _require_visibility(self, visibility: str) -> str:
        clean = (visibility or "").strip()
        if clean not in VISIBILITIES:
            raise UnknownVisibility(
                f"{visibility!r} is not a visibility. `public` is a task's entry point — "
                f"exactly one per task, and the only thing another task's pseudocode may "
                f"call; `private` is everything serving it",
                visibility=visibility,
            )
        return clean

    def _require_task(self, task_id: int) -> None:
        if not self.storage.query("SELECT id FROM tasks WHERE id = ?", (task_id,)):
            raise TaskNotFound(
                f"no task {task_id}, so there is nothing for this function to belong to",
                task_id=task_id,
            )

    def _live_component(self, component_ref: RowRef | str) -> RowRef:
        """The owner must be **both** in `components` and live, and the message says which.

        `RowService.get` takes any ref, so without the table check
        `catalogue_object(component_ref="requirements:4")` is accepted and produces an object
        owned by a requirement.
        """
        ref = RowRef.coerce(component_ref)
        try:
            row = self.rows.get(ref)
        except PlanToolError as exc:
            raise ComponentNotFound(
                f"{ref} names no row, so this object has no owner to belong to",
                ref=str(ref),
            ) from exc
        if ref.table != COMPONENTS:
            raise ComponentNotFound(
                f"{row.name} ({ref}) is a {ref.table} row, not a component. An object's "
                f"owner is the component that holds it — a service class carries the entry "
                f"points of twenty tasks, so no task owns it, and the report groups by owner",
                ref=str(ref), table=ref.table,
            )
        if not row.is_live:
            raise ComponentNotFound(
                f"{row.name} ({ref}) is {row.state.value}, not live. An object owned by a "
                f"superseded component is an entry whose owner has moved",
                ref=str(ref), state=row.state.value,
            )
        return ref

    def _refuse_taken(self, name: str, container: str | None) -> str | None:
        """Refuse a live collision, and report any retired namesake either way.

        A retired entry does **not** block the name — retirement frees it, and the new entry
        is a new row. But where one exists it is named in the refusal, because that is the
        strongest argument in the design: a dead function cannot be reused and offering it as
        a search candidate would be a confidently wrong answer, yet **the thing about to be
        written may have been removed on purpose, and the planner may be undoing somebody's
        decision without knowing it.** Delivered nowhere, that argument protects nobody, so
        it is delivered in all three places the name can be met: here on the refusal, here
        again on the *success* — as `CatalogueResult.note`, which is the case the argument
        was actually written for, since a freed name is refused by nothing — and in
        `_require_live`'s `EntryNotFound`.
        """
        live = self._find(name, container)
        retired = self._retired_namesakes(name, container)
        note = self._retirement_note(name, container, retired)
        if live is None:
            return note
        raise NameTaken(
            f"{name!r} is already catalogued "
            f"{f'in {container}' if container else 'at module level'}: "
            f"{live.purpose!r}, owned by {self._owner_of(live)}. Two things called one word "
            f"is the collision this table exists to refuse — rename one, or judge them the "
            f"same thing and use what exists"
            + (f". {note}" if note else ""),
            name=name, container=container,
        )

    @staticmethod
    def _retirement_note(
        name: str, container: str | None, retired: Sequence[CatalogueEntry]
    ) -> str | None:
        if not retired:
            return None
        where = f"in {container}" if container else "at module level"
        return (
            f"note: {name!r} has been catalogued {where} and retired before — "
            + "; ".join(f"{e.retire_reason!r}" for e in retired)
            + ". Retirement is a decision somebody made, and it may be the one you are "
              "about to undo"
        )

    def _retired_namesakes(
        self, name: str, container: str | None
    ) -> tuple[CatalogueEntry, ...]:
        """Every retired entry that has held this name and container, oldest first.

        This is the lineage `retire_catalogue_entry` promises instead of un-retirement: a
        function written, removed and written again is precisely the case that suggests
        something was wrong with the original design, and the query is the history.
        """
        container_id = self._resolve_container(container) if container else None
        if container and container_id is None:
            return ()
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT * FROM catalogue WHERE name = ? AND container_id IS ? "
                "AND retired_at IS NOT NULL ORDER BY id",
                (name, container_id),
            )
        )

    def _refuse_second_entry_point(self, task_id: int, name: str) -> None:
        found = self.storage.query(
            "SELECT * FROM catalogue WHERE task_id = ? AND kind = ? AND visibility = ? "
            "AND retired_at IS NULL",
            (task_id, FUNCTION, PUBLIC),
        )
        if found:
            held = self._hydrate(found[0])
            raise EntryPointExists(
                f"task {task_id} already has a public entry point, {held.name!r} — "
                f"{held.purpose!r}. A task is one externally-callable function, so a second "
                f"{name!r} means either this is two tasks or one of the names is wrong",
                task_id=task_id, name=name, existing=held.name,
            )

    def _refuse_unresolvable(
        self, purpose: str, comparisons: Sequence[Comparison]
    ) -> None:
        """Every `table:ordinal` in stored prose resolves, checked at the write.

        The convention change 2 reached for `grounds` and `alternatives`, and this is its
        third site. It matters more here: a comparison `reason` cannot be rewritten, so an
        unresolvable ref in one makes the row permanently unreadable through the door, and
        `restate_purpose` is the only repair available on the other field.

        Change 2's probe against realistic justification prose found one trap, a URL with a
        port, and its consequence is worse here — where change 2 left such a token rendering
        oddly, this **refuses the write** over it. So the refusal names the token, and the
        planner can see it is their `localhost:8080` and not a citation.
        """
        for label, text in (
            ("the purpose line", purpose),
            *(("the comparison against " + c.matched, c.reason) for c in comparisons),
        ):
            unresolved = unresolved_refs(text, self._row_exists)
            if unresolved:
                raise UnresolvedReference(
                    f"{label} cites {', '.join(unresolved)}, which names no row. Every "
                    f"address in stored prose is resolved for the reader on the way out, "
                    f"and one with nothing behind it would fail every read of this entry "
                    f"from here on. Note that a URL with a port reads as an address — "
                    f"write it without one",
                    field=label, unresolved=unresolved,
                )

    def _row_exists(self, ref: RowRef) -> bool:
        """Does any row live at this address? Superseded and retired rows count.

        The door renders them with their successor, and citing what a decision replaced is
        exactly what an argument does — so `unresolved_refs` asks "names no row at all",
        which is `RowService.get` raising rather than a liveness test.
        """
        try:
            self.rows.get(ref)
        except RowNotFound:
            return False
        return True

    def _require_live(self, name: str, container: str | None) -> CatalogueEntry:
        entry = self._find(name, container)
        if entry is not None:
            return entry
        retired = self._find(name, container, include_retired=True)
        where = f"in {container}" if container else "at module level"
        if retired is not None:
            raise EntryNotFound(
                f"{name!r} {where} was retired — {retired.retire_reason!r}. Retirement is "
                f"never undone; if it should exist again, catalogue it afresh and the two "
                f"rows are the history",
                name=name, container=container,
            )
        raise EntryNotFound(
            f"no live catalogue entry called {name!r} {where}",
            name=name, container=container,
        )

    def _owner_of(self, entry: CatalogueEntry) -> str:
        return (
            f"task {entry.owner}" if entry.kind == FUNCTION else f"component {entry.owner}"
        )

    @staticmethod
    def _display(entry: CatalogueEntry) -> str:
        return f"{entry.container}.{entry.name}" if entry.container else entry.name

    @staticmethod
    def _display_pair(comparison: Comparison) -> str:
        return (
            f"{comparison.container}.{comparison.matched}"
            if comparison.container
            else comparison.matched
        )

    @classmethod
    def _name_list(cls, entries: Iterable[CatalogueEntry]) -> str:
        return ", ".join(cls._display(e) for e in entries)

    @classmethod
    def _unjudged_list(cls, candidates: Iterable[Candidate]) -> str:
        """The ones that must be answered, each with the words that put it there.

        The matched words are the whole of what makes a spurious match cheap to dispose of:
        `matched on: a` is settled at a glance, and `matched on: supersession, lineage` is
        not. Without them the reader has to re-derive why the tool stopped them.
        """
        return "; ".join(
            f"{cls._display(c.entry)} — {c.entry.purpose!r} "
            f"(matched on: {', '.join(c.matched)})"
            for c in candidates
        )

    @classmethod
    def _candidate_list(cls, candidates: Iterable[Candidate]) -> str:
        return "; ".join(
            f"{cls._display(c.entry)} — {c.entry.purpose!r} "
            f"(matched on {', '.join(c.matched)})"
            for c in candidates
        )
