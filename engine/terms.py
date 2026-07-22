"""The plan's glossary — what the words mean, and which ones are out.

Not in the frozen plan (DEVIATIONS.md D23). The eight planning packages interview for use
cases, entities, contracts, decisions and failure modes, and never once ask *what do you
call things, and what do those words mean?* — DEFECTS.md F40.

**F27 is why this exists, and its cause shapes the design.** A binding vocabulary was
written down and broken the next build package. Not through carelessness: the one document
where retired words legitimately survive is also the document read immediately before
writing each function, so ranked by proximity to the moment of typing the exception beats
the rule. And naming happens at the point of *least* attention — the thinking goes into the
algorithm and the name is incidental typing. A word in a document cannot fix that. Something
that runs can.

**A real table, not a plan-row type** (owner's decision, and he was right on two counts we
had both missed):

1. **A term needs two relations that the generic layer collapses into one.** *Redefinition*
   — same word, sharpened meaning — and *replacement* — this word is out, use that one — are
   both `superseded_by` in `plan_rows`. One mechanism serving two relations is the disease
   this module exists to prevent, inverted.
2. **D12's own reasoning forbids the row type.** An accounting denominator may never be
   inferred from `plan_rows.content`, which is free-form JSON with no per-table schema. The
   banned-word list *is* a denominator, so `ban_scope` has to be a queryable column.

**The trap, stated because a naive reading walks straight into it.** A retired word must
stay in **live reads**. Everywhere else in v2, retiring drops a row out of live reads; apply
that here and the banned list goes empty, so the check runs, finds nothing to ban, and
reports success — F23's missing denominator, reappearing inside the mechanism built to
prevent F27. So a retired word is `ban_scope IS NOT NULL`, never a row that disappears.

**Scope is plan-level, deliberately.** A word meaning two things in two packages is the
failure being prevented, so there is no package-level override.

**Un-banning is a redefinition, and needs no call of its own.** A word that comes back comes
back with a meaning, which is exactly what `redefine_term` records; the banned row keeps its
ban and its reason forever in the lineage behind it. A `restore` that cleared the columns in
place would throw away the record of a decision, and would be a second mechanism for
something one already covers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from engine.clock import now
from engine.errors import PlanToolError
from engine.idempotency import key
from engine.models import RowRef
from engine.storage import Op, Storage

#: The manifest the codebase's own CI consumes (M6_PLAN.md §3.3, delivery point 1). Beside
#: `plan.md`, and named rather than parameterised for the same reason: a name the caller
#: chooses is a name no script and no CI config can state up front.
EXPORT_FILENAME = "glossary.json"

PROSE = "prose"
IDENTIFIER = "identifier"
BOTH = "both"

#: Where a retired word may no longer appear. The distinction our own vocabulary needed and
#: would otherwise have hidden inside JSON: one word was banned from new prose while
#: remaining pervasive as an address, and another was banned as an identifier only.
BAN_SCOPES = (PROSE, IDENTIFIER, BOTH)

#: An address in prose — `requirements:61`. Stripped before tokenising, because an address
#: is not a use of the word: a plan whose row tables are named for a retired word would
#: otherwise warn on every citation of one, and a meter that cries wolf stops being read.
ADDRESS = re.compile(r"\b[a-z][a-z0-9_]*:[1-9][0-9]*\b")

#: A word, in prose or inside an identifier. `_` and case boundaries split identifiers, so
#: `subTaskId` and `sub_task_id` tokenise the same way.
WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+")


class TermNotFound(PlanToolError):
    """No live term for this word."""


class TermExists(PlanToolError):
    """A live term already defines this word; sharpening it is a redefinition."""


class DefinitionRequired(PlanToolError):
    """A word with no meaning recorded beside it is not a glossary entry."""


class BanNeedsReason(PlanToolError):
    """Retiring a word is the act this whole mechanism exists to make visible, so it
    records why and what to say instead. The same friction shape as requirements:79's
    waiver log."""


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
    names_ref: RowRef | None = None
    ban_scope: str | None = None
    ban_reason: str | None = None
    #: The word to say instead, stored as the word and not as a row id. A retirement
    #: outlives the entry it points at — the replacement will itself be redefined one day —
    #: and the word is the identity that survives that, which is the same reason this table
    #: is looked up by word everywhere else.
    use_instead: str | None = None
    superseded_at: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_banned(self) -> bool:
        """A banned word is still live, and that is the whole point — see the module
        docstring's trap."""
        return self.ban_scope is not None

    @property
    def is_live(self) -> bool:
        return self.superseded_at is None

    def bans(self, scope: str) -> bool:
        return self.is_banned and self.ban_scope in (scope, BOTH)


@dataclass(frozen=True, slots=True)
class Usage:
    """One retired word found in submitted content, and what to say instead."""

    term: str
    scope: str
    where: str
    reason: str
    use_instead: str | None = None

    def __str__(self) -> str:
        """Said to whoever is submitting the row, who has it in front of them."""
        return f"'{self.term}' is retired in {self.where} — {self.reason}{self._instead}"

    def about(self, subject: str) -> str:
        """The same fact said about a row somebody wrote days ago, which needs naming the
        row first. One owner for both wordings, because two would drift into two rules."""
        return (
            f"{subject} uses '{self.term}', retired in {self.where} — "
            f"{self.reason}{self._instead}"
        )

    @property
    def _instead(self) -> str:
        return f"; say '{self.use_instead}'" if self.use_instead else ""


@dataclass(frozen=True, slots=True)
class GlossaryExport:
    """What was written, and out of what. Not the glossary itself: a caller that wants the
    terms calls `glossary`, and CI reads the file."""

    path: str
    terms: int
    banned: int
    written_at: str = ""

    def present(self) -> str:
        return (
            f"{EXPORT_FILENAME} written with {self.terms} term(s), {self.banned} of them "
            f"retired. Point the codebase's own vocabulary check at it: the tool publishes "
            f"the words, the codebase polices itself."
        )


class TermService:
    #: Reserved as a plan-row table name for the reason F38 records: deciding which store
    #: owns a word is half a fix, and `plan_rows.table` is open by design.
    TABLE = "terms"

    def __init__(self, storage: Storage, rows=None):
        self.storage = storage
        #: Only to resolve `names_ref` to the name of the row it names, in the export. A
        #: manifest that carried bare addresses would hand its reader the lookup this
        #: whole design exists to remove.
        self.rows = rows

    # --- writing ---

    def define_term(
        self, term: str, definition: str, names_ref: RowRef | str | None = None
    ) -> Term:
        """Record what a word means in this plan."""
        word = self._word(term)
        if not definition.strip():
            raise DefinitionRequired(
                f"'{word}' needs a definition: what it means here, in a sentence. A word "
                "listed with no meaning beside it is a word two readers will read two ways",
                term=word,
            )
        if self.find(word) is not None:
            raise TermExists(
                f"'{word}' is already defined; sharpening what it means is a redefinition, "
                "which keeps the old wording as history — redefine_term does that",
                term=word,
            )
        stamp = now()
        receipt = self.storage.write_atomic(
            [Op("insert", "terms", {
                "term": word,
                "definition": definition.strip(),
                "names_ref": str(names_ref) if names_ref else None,
                "created_at": stamp,
                "updated_at": stamp,
            })],
            key("define_term", word),
        )
        return self.get(receipt["results"][0]["id"])

    def redefine_term(
        self, term: str, definition: str, names_ref: RowRef | str | None = None
    ) -> Term:
        """Same word, sharpened meaning. The old wording stays as history.

        This is also how a retired word comes back: the successor carries no ban, and the
        banned row keeps its scope and its reason behind it. A word returning to use is a
        word being given a meaning again, which is this act and not a separate one.

        One transaction, not two — F33 was a supersession that ran as two, so an
        interruption left the plan holding both halves of a change nobody made. The old
        entry is stamped *before* the new one is written, because the live-word index would
        otherwise see two live entries for one word for the length of one statement and
        reject the redefinition outright.
        """
        word = self._word(term)
        if not definition.strip():
            raise DefinitionRequired(
                f"redefining '{word}' records the new meaning, not just that it changed",
                term=word,
            )
        current = self._require(word)
        stamp = now()
        receipt = self.storage.write_atomic(
            [
                Op("update", "terms",
                   {"superseded_at": stamp, "updated_at": stamp},
                   where={"id": current.id}),
                Op("insert", "terms", {
                    "term": word,
                    "definition": definition.strip(),
                    "names_ref": (
                        str(names_ref) if names_ref
                        else (str(current.names_ref) if current.names_ref else None)
                    ),
                    "created_at": stamp,
                    "updated_at": stamp,
                }),
            ],
            key("redefine_term", word, current.id),
        )
        return self.get(receipt["results"][1]["id"])

    def retire_term(
        self,
        term: str,
        ban_scope: str,
        ban_reason: str,
        use_instead: str | None = None,
    ) -> Term:
        """Take a word out of use, on the record, saying what to say instead.

        The word stays in live reads carrying its ban — see the module docstring. Dropping
        it out, as retirement does everywhere else in v2, would empty the very list every
        check downstream counts against.
        """
        word = self._word(term)
        if ban_scope not in BAN_SCOPES:
            raise BanNeedsReason(
                f"ban_scope must be one of {', '.join(BAN_SCOPES)}: a word can be out of "
                "new prose while surviving in identifiers, or the other way round, and a "
                "ban that does not say which warns on the wrong things",
                term=word,
                ban_scope=ban_scope,
            )
        if not ban_reason.strip():
            raise BanNeedsReason(
                f"retiring '{word}' records why. A retired word with no reason is a rule "
                "the next writer has no way to agree with, and the one after that reverses",
                term=word,
            )
        current = self._require(word)
        replacement = None
        if use_instead:
            replacement = self._word(use_instead)
            if self.find(replacement) is None:
                raise TermNotFound(
                    f"'{replacement}' is not defined, so the retirement would point at "
                    "nothing. Define the word that replaces this one first",
                    term=replacement,
                )
        self.storage.write_atomic(
            [Op("update", "terms", {
                "ban_scope": ban_scope,
                "ban_reason": ban_reason.strip(),
                "use_instead": replacement,
                "updated_at": now(),
            }, where={"id": current.id})],
            key("retire_term", word, current.id),
        )
        return self.get(current.id)

    # --- reading ---

    def get(self, term_id: int) -> Term:
        found = self.storage.query("SELECT * FROM terms WHERE id = ?", (term_id,))
        if not found:
            raise TermNotFound("no such term", term_id=term_id)
        return self._hydrate(found[0])

    def find(self, term: str) -> Term | None:
        """The live entry for a word, banned or not."""
        found = self.storage.query(
            "SELECT * FROM terms WHERE term = ? AND superseded_at IS NULL",
            (self._word(term),),
        )
        return self._hydrate(found[0]) if found else None

    def glossary(self) -> tuple[Term, ...]:
        """Every live term, alphabetically. **Banned words are included** — a glossary that
        listed only the words still in use could not tell a writer which one to stop
        using, which is the half of it that actually changes behaviour."""
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT * FROM terms WHERE superseded_at IS NULL ORDER BY term"
            )
        )

    def banned(self) -> tuple[Term, ...]:
        """The retired words — the denominator every check downstream counts against.

        Defined independently of the thing being measured (`ban_scope` is a column, not an
        inference from row content), which is what F23 asks of any coverage check, and it
        can only be empty when nothing has been retired.
        """
        return tuple(t for t in self.glossary() if t.is_banned)

    def history(self, term: str) -> tuple[Term, ...]:
        """Every entry this word has ever had, oldest first — including the retirement it
        may have come back from."""
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                "SELECT * FROM terms WHERE term = ? ORDER BY id", (self._word(term),)
            )
        )

    # --- the lexical scan (M6_PLAN.md §3.3, delivery point 3) ---

    def violations(self, content: dict) -> tuple[Usage, ...]:
        """Retired words in one row's content: keys read as identifiers, values as prose.

        **Warn, never block.** A retired word inside a quotation is legitimate — the owner's
        own words are quoted verbatim all over a plan — and blocking on one would resurrect
        the cry-wolf failure D7 fixed. The submitter is told; the row stands.

        What it cannot do, stated so it is not oversold: it matches words, so a *new* name
        invented for an existing concept, sharing no letters with it, goes unseen. Nothing
        without judgment can catch that.
        """
        retired = self.banned()
        if not retired:
            return ()
        found: dict[tuple[str, str], Usage] = {}
        for scope, text in self._segments(content):
            words = self._tokens(text, scope)
            for entry in retired:
                if not entry.bans(scope) or entry.term not in words:
                    continue
                found.setdefault((entry.term, scope), Usage(
                    term=entry.term,
                    scope=scope,
                    where="prose" if scope == PROSE else "identifiers",
                    reason=entry.ban_reason or "",
                    use_instead=entry.use_instead,
                ))
        return tuple(found[k] for k in sorted(found))

    def _segments(self, content, prefix: str = "") -> list[tuple[str, str]]:
        """Every string in a row's content, labelled by which scope reads it.

        The two scopes map onto something real rather than onto a preference: a content
        *key* is an identifier — it becomes a field name every reader types — and a content
        *value* is prose.
        """
        out: list[tuple[str, str]] = []
        if isinstance(content, dict):
            for k, v in content.items():
                out.append((IDENTIFIER, str(k)))
                out.extend(self._segments(v))
        elif isinstance(content, (list, tuple)):
            for v in content:
                out.extend(self._segments(v))
        elif isinstance(content, str):
            out.append((PROSE, content))
        return out

    @staticmethod
    def _tokens(text: str, scope: str) -> set[str]:
        """The words in one string, lowercased, with plurals folded onto the singular.

        Addresses come out first: `components:15` cites a row, it does not use the word.
        Plural folding is deliberately the crudest possible rule — a trailing `s` — because
        anything cleverer starts guessing, and a guess here spends the owner's attention on
        a word nobody wrote.
        """
        if scope == PROSE:
            text = ADDRESS.sub(" ", text)
        words = set()
        for token in WORD.findall(text):
            token = token.lower()
            words.add(token)
            if token.endswith("s"):
                words.add(token[:-1])
        return words

    # --- the export (M6_PLAN.md §3.3, delivery point 1) ---

    def export_glossary(self) -> GlossaryExport:
        """Publish the vocabulary as a manifest the codebase's own CI consumes.

        This is the delivery point that achieves the most, and it is worth being clear why:
        it respects `decisions:12` completely — the tool publishes the words and exercises
        no judgment about anyone's code — it works in any language, and it is the mechanism
        already proven on ourselves, where a ten-line check found twenty violations that a
        careful reading had declared clean.
        """
        entries = self.glossary()
        payload = {
            "written_at": now(),
            "terms": [self._entry(t) for t in entries],
            "banned": [
                {
                    "term": t.term,
                    "scope": t.ban_scope,
                    "reason": t.ban_reason,
                    "use_instead": t.use_instead,
                }
                for t in entries
                if t.is_banned
            ],
        }
        path = Path(self.storage.workspace) / EXPORT_FILENAME
        try:
            path.write_text(
                json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            raise DefinitionRequired(
                "the glossary manifest could not be written",
                path=str(path), cause=str(exc),
            ) from exc
        return GlossaryExport(
            path=str(path),
            terms=len(entries),
            banned=sum(1 for t in entries if t.is_banned),
            written_at=payload["written_at"],
        )

    def _entry(self, term: Term) -> dict:
        entry: dict = {"term": term.term, "definition": term.definition}
        if term.names_ref is not None:
            entry["names"] = {
                "ref": str(term.names_ref),
                "name": self._name_of(term.names_ref),
            }
        return entry

    def _name_of(self, ref: RowRef) -> str | None:
        if self.rows is None:
            return None
        try:
            return self.rows.get(ref).name
        except Exception:  # noqa: BLE001 — a manifest never fails over a missing name
            return None

    # --- internals ---

    @staticmethod
    def _word(term: str) -> str:
        word = (term or "").strip().lower()
        if not word:
            raise TermNotFound("a term is a word; this one is empty")
        return word

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
            names_ref=RowRef.parse(r["names_ref"]) if r["names_ref"] else None,
            ban_scope=r["ban_scope"],
            ban_reason=r["ban_reason"],
            use_instead=r["use_instead"],
            superseded_at=r["superseded_at"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
