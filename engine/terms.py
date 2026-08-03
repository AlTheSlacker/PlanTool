"""The plan's glossary — what the words mean, in the owner's terms.

Not in the frozen plan (DEVIATIONS.md D23). The eight planning stages interview for use
cases, entities, contracts, decisions and failure modes, and never once ask *what do you
call things, and what do those words mean?* — DEFECTS.md F40.

**F27 is why this exists.** A binding vocabulary was written down and broken the next build
stage. Not through carelessness: naming happens at the point of *least* attention — the
thinking goes into the algorithm and the name is incidental typing — and the one document
where retired words legitimately survive is also the document read immediately before
writing each function.

**No scan can catch the failure this is for, and that finding shapes everything else.** The
failure is one word for two things, or two words for one — calling something a `part` one
day and a `component` the next, or the owner saying `part` and the tool assuming instead of
asking. `part` and `component` share no letters. Every mechanism tried against that was
lexical — a banned-word list, an allowlist over row names, near-match ranking — and none of
them can see a synonym that shares no vocabulary. This module admitted as much in its own
words from the day it was written:

    it matches words, so a *new* name invented for an existing concept, sharing no letters
    with it, goes unseen. Nothing without judgment can catch that.

**So the glossary's job is not to be scanned. It is to be in front of the writer at the
moment of naming.** That is what loading it into a planning session at its start is for, and
it is why the owner accepted a mechanism he himself called not robust: the alternative is
not a better mechanism, it is a mechanism that cannot work. It is read at session start and
**never written out at session end** — N stale copies with nothing keeping them true, and
consulted in preference to the live table, is the exact defect the glossary exists to
prevent, committed by the thing meant to prevent it.

**One mechanical use, and this is the whole of it: a label must be a live term.**
`attach_label` looks the word up here and refuses if nothing holds it (`engine/labels.py`).
Nothing else scans this table, counts it, gates on it or warns from it.

**A real table, not a plan-row type** (owner's decision). D12 settled that an accounting
denominator may never be inferred from `plan_rows.content`, which is free-form JSON with no
per-table schema — and `label_attachments` keys on the *word*, so the word has to be
something a query can resolve. It is looked up the way a person looks a word up: by the word
you were about to type, never by an ordinal.

**What was here until v3 change 4**, so a reader of an older plan knows what those columns
meant. A definition was *proposed* by the planner and *approved* by the owner, and a rewrite
superseded the proposal rather than overwriting it. Words could be *retired* — banned in
prose, in identifiers, or both, with a reason and a word to say instead — and a retired word
stayed in live reads carrying its ban, because dropping it out would have emptied the
denominator every downstream check counted against. A `violations()` scan read submitted
rows against that list, and the glossary was published as a JSON manifest for external CI.
All of it goes: the approval step, because the owner writes the contents and there is
nothing to settle; the banned list, because §2.2 above says no scan can work; the manifest,
because nothing ever read it.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.clock import now
from engine.errors import PlanToolError
from engine.idempotency import key
from engine.storage import Op, Storage

#: `WORD` and the tokeniser that read it are `engine.catalogue`'s, moved there by v3 change
#: 3 and left there by change 4: the catalogue ranks names and purpose lines against each
#: other and is now the only caller. Nothing here needs a regex — `_word` is strip and
#: lowercase.


class TermNotFound(PlanToolError):
    """No term for this word."""


class TermExists(PlanToolError):
    """A term already defines this word; changing it is a redefinition."""


class DefinitionRequired(PlanToolError):
    """A word with no meaning recorded beside it is not a glossary entry."""


class TermInUse(PlanToolError):
    """The word is carried as a label, and removing it would strip that label from every
    row and task using it. The owner ruled that out in as many words: *"do not arbitrarily
    remove the label from all the references"*."""


class AmbiguousRemoval(PlanToolError):
    """A replacement word and "take it off everything" are two answers to one question, and
    supplying both is the caller not having decided. This engine refuses rather than
    picking."""


@dataclass(frozen=True, slots=True)
class Term:
    """One word the plan has agreed the meaning of.

    Identified by the word itself rather than by an address. That is not an oversight: a
    term is *looked up by the word you were about to type*, and an ordinal would put a
    lookup between the writer and the answer at the exact moment attention is lowest.
    """

    id: int
    term: str
    definition: str
    created_at: str = ""
    updated_at: str = ""


class TermService:
    #: Reserved as a plan-row table name for the reason F38 records: deciding which store
    #: owns a word is half a fix, and `plan_rows.table` is open by design.
    TABLE = "terms"

    def __init__(self, storage: Storage, labels=None):
        self.storage = storage
        #: `remove_term` counts, moves and detaches attachments, and every one of those is
        #: label-service work. Optional here and required at the one call that needs it, so
        #: that `TermService(storage)` — which five modules and most of the tests construct
        #: — does not have to build a label service to define a word.
        self.labels = labels

    # --- writing ---

    def define_term(self, term: str, definition: str) -> Term:
        """Record what a word means in this plan.

        There is no approval step and no proposal state. The owner defines the contents, so
        whatever is written was authorised at the moment it was written — a queue of
        unsettled definitions would be the tool asking him to confirm what he had just said.
        """
        word = self._word(term)
        definition = self._definition(word, definition)
        if self.find(word) is not None:
            raise TermExists(
                f"'{word}' is already defined; changing what it means is redefine_term",
                term=word,
            )
        stamp = now()
        receipt = self.storage.write_atomic(
            [Op("insert", "terms", {
                "term": word,
                "definition": definition,
                "created_at": stamp,
                "updated_at": stamp,
            })],
            key("define_term", word),
        )
        return self.get(receipt["results"][0]["id"])

    def redefine_term(self, term: str, definition: str) -> Term:
        """Change what a word means, **in place**.

        It was a supersession until v3 change 4: stamp the old row, write a new one, one
        transaction, ordered so the partial live index never saw two live rows for one word.
        All of that existed to keep a definition's history, and the history goes on change
        3's settled ground — *a purpose line is not an argument; it is an index entry, and
        nothing cites it*. Nothing cites a definition either, so there is no argument
        resting on the wording it had last week. In place is now literally an `UPDATE`, and
        the ordering hazard disappears with the partial index.

        Kept as a separate call from `define_term` rather than merged into an upsert, on the
        owner's ruling of 2026-07-30: *"there should be a tool to create terms and a tool to
        edit (redefine) them"*. Creating a word and editing one are different acts, so
        `define_term`'s refusal on an existing word is kept **by decision** — which matters,
        because the argument for merging them is otherwise good and would be made again.
        """
        word = self._word(term)
        definition = self._definition(word, definition)
        current = self._require(word)
        self.storage.write_atomic(
            [Op("update", "terms",
                {"definition": definition, "updated_at": now()},
                where={"id": current.id})],
            key("redefine_term", word, definition),
        )
        return self.get(current.id)

    def remove_term(
        self, term: str, replacement: str | None = None, detach_all: bool = False
    ) -> None:
        """Take a word out of the glossary.

        **With anything carrying it as a label, this refuses first**, and the refusal *is*
        the prompt — this engine has no other way to ask a question. The owner's
        instruction: *"if the user tries to delete a glossary item that is a label then
        prompt for a replacement label, do not arbitrarily remove the label from all the
        references."* So the message carries what he needs in order to answer: not that the
        word is in use, but how widely, **split by population and never summed**. A word on
        three rows and a word on four hundred are different decisions.

        Two answers resolve it, and he chooses; nothing is automatic. A `replacement` moves
        every live attachment to another live term. `detach_all` takes the label off
        everything — his ruling of 2026-07-30, *"yes to take it off everything"* — because
        the alternative, blocking deletion until he has detached by hand, means a filter he
        has decided is wrong must be peeled off forty rows before he is allowed to say so.

        **One call with a parameter rather than three calls**, because the three outcomes
        share the whole of their work — normalise, look up, count, transact, delete — and
        differ only in what happens to the attachments. Three tools would be three copies of
        the refusal and three registry rows for one act.
        """
        word = self._word(term)
        current = self._require(word)
        if replacement is not None and detach_all:
            raise AmbiguousRemoval(
                f"removing '{word}' takes a replacement word or detach_all, not both: "
                "moving the label to another word and taking it off everything are two "
                "different answers, and this is not the tool's to choose between",
                term=word,
            )
        service = self._label_service()
        rows, tasks = service.usage_of(word)
        replacement_word = None
        if replacement is not None:
            replacement_word = self._word(replacement)
            if replacement_word == word:
                raise AmbiguousRemoval(
                    f"'{word}' cannot replace itself; name the word its labels move to, "
                    "or pass detach_all to take the label off everything",
                    term=word,
                )
            # Validated even when nothing is attached, and then ignored. A replacement that
            # names no term is a mistake whether or not this particular word happens to be
            # carried, and accepting it silently would teach the caller it was fine.
            if self.find(replacement_word) is None:
                raise TermNotFound(
                    f"'{replacement_word}' is not defined, so the labels would move to "
                    "nothing. define_term records what it means first",
                    term=replacement_word,
                )
        if (rows or tasks) and replacement_word is None and not detach_all:
            raise TermInUse(
                f"'{word}' is carried as a label by {rows} plan row(s) and {tasks} "
                f"task(s), so removing it would take the label off all of them. Pass a "
                f"replacement word — it must itself be defined — to move them, or "
                f"detach_all to take it off everything",
                term=word, rows=rows, tasks=tasks,
            )
        stamp = now()
        ops: list[Op] = []
        if replacement_word is not None:
            ops.extend(service.move_ops(word, replacement_word, stamp))
        elif detach_all:
            ops.extend(service.detach_ops(word, stamp))
        # The move and the removal are one act, in one transaction: F33 was a supersession
        # that ran as two, so an interruption left the plan holding both halves of a change
        # nobody made.
        ops.append(Op("delete", "terms", {}, where={"id": current.id}))
        self.storage.write_atomic(
            ops, key("remove_term", word, current.id, replacement_word, detach_all)
        )

    # --- reading ---

    def get(self, term_id: int) -> Term:
        found = self.storage.query("SELECT * FROM terms WHERE id = ?", (term_id,))
        if not found:
            raise TermNotFound("no such term", term_id=term_id)
        return self._hydrate(found[0])

    def find(self, term: str) -> Term | None:
        """The entry for a word, or None."""
        found = self.storage.query(
            "SELECT * FROM terms WHERE term = ?", (self._word(term),)
        )
        return self._hydrate(found[0]) if found else None

    def glossary(self) -> tuple[Term, ...]:
        """Every term, alphabetically."""
        return tuple(
            self._hydrate(r)
            for r in self.storage.query("SELECT * FROM terms ORDER BY term")
        )

    # --- internals ---

    def _label_service(self):
        """The label service, built here if it was not passed.

        Built rather than skipped, deliberately overriding convention 11: an unpassed
        collaborator normally means the guard is skipped and the call proceeds, and here
        that would make `remove_term` delete a word while leaving its attachments pointing
        at nothing — the refusal this call exists for, silently absent.
        """
        if self.labels is None:
            from engine.labels import LabelService
            from engine.rows import RowService

            self.labels = LabelService(self.storage, RowService(self.storage), self)
        return self.labels

    @staticmethod
    def _word(term: str) -> str:
        word = (term or "").strip().lower()
        if not word:
            raise TermNotFound("a term is a word; this one is empty")
        return word

    @staticmethod
    def _definition(word: str, definition: str) -> str:
        """The last mechanical opinion the glossary holds, and it earns its place.

        A word listed with no meaning beside it is a word two readers read two ways, which
        is the failure this table exists to prevent arriving through the table itself.
        """
        if not (definition or "").strip():
            raise DefinitionRequired(
                f"'{word}' needs a definition: what it means here, in a sentence. A word "
                "listed with no meaning beside it is a word two readers will read two ways",
                term=word,
            )
        return definition.strip()

    def _require(self, word: str) -> Term:
        current = self.find(word)
        if current is None:
            raise TermNotFound(
                f"'{word}' is not defined, so there is nothing to change; define_term "
                "records what a word means for the first time",
                term=word,
            )
        return current

    @staticmethod
    def _hydrate(r) -> Term:
        return Term(
            id=r["id"],
            term=r["term"],
            definition=r["definition"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
