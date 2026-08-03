"""label-service — a glossary term attached to plan rows and tasks (v3 D12, as amended).

**A label is a term.** There is no `labels` table and no label lifecycle: the word lives in
`terms`, and this module owns only the attachment of a word to a target. That is what makes
the glossary's one mechanical use mechanical — `attach_label` looks the word up and refuses
if nothing holds it, which is the whole of what the glossary is scanned for.

**Why labels exist at all.** They replace the declared build grouping (v3 D7) as the way a
review list is filtered. The grouping was a *level*, so everything under it inherited it and
a row could belong to one thing; a label is an attachment, so a row carries as many as make
sense and none of them claims to be its home.

**Attachments key on the target's lineage root**, never on its ref. A record keyed on a ref
detaches silently the moment the row is superseded (findings:16) — so a label put on
`requirements:1` would vanish the first time that requirement was reworded, which is exactly
when the person who filed it would want it. requirements:78 established the keying for gap
dismissals and scope attachments took it second; this is its third application.

**Nothing here counts, warns, or gates.** `labels()` reports, with both denominators beside
the numerators so a count cannot be read alone, and there is deliberately no threshold above
which a label is "too broad": a rule saying five is fine and six is not is a judgment written
as arithmetic so review cannot see it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from engine.clock import now
from engine.errors import PlanToolError
from engine.idempotency import key
from engine.models import (
    LabelAttachment,
    LabelReport,
    LabelTarget,
    LabelUsage,
    RowRef,
)
from engine.rows import RowService
from engine.storage import Op, Storage
from engine.terms import Term, TermNotFound, TermService

#: Every live label on each of a page's rows, in one statement.
#:
#: The attachments key on lineage roots and a page is a set of *refs*, so the join has to
#: walk each row back to its root — and doing that in Python first would be one query per
#: supersession hop per row, which is the very thing this exists to avoid. The recursive CTE
#: walks `supersedes` backward from every ref at once, then joins the attachments to the
#: root it lands on. Probed at SQLite 3.49.1 against a page mixing a thrice-superseded row
#: with two never-superseded ones.
#:
#: `ORDER BY ... la.word` is where the alphabetical ordering actually comes from, rather
#: than being left to whatever order the grouping happens to produce.
LABELS_FOR_PAGE = """
WITH RECURSIVE walk(ref, cur) AS (
    SELECT value, value FROM json_each(?)
    UNION ALL
    SELECT w.ref, p.supersedes
      FROM walk w
      JOIN plan_rows p ON p.table_name || ':' || p.ordinal = w.cur
     WHERE p.supersedes IS NOT NULL
)
SELECT w.ref AS ref, la.word AS word FROM walk w
  JOIN label_attachments la
    ON la.target_root = w.cur AND la.detached_at IS NULL
 ORDER BY w.ref, la.word
"""


class InvalidTarget(PlanToolError):
    """A label goes on a plan row or a task, and this is neither."""


# `TermInUse` and `AmbiguousRemoval` belong to `terms.py`, which raises them: they are
# refusals of `remove_term`, not of anything here. Defining a second copy beside the first
# is the eleven-times-over collision this engine's catalogue exists to catch.


class LabelService:
    """Attaching, detaching, and reporting.

    **All three collaborators are required, none optional**, which overrides convention 11
    with the reason the register asks for. Entry 11 says a collaborator that was not passed
    has "its guard skipped and its effects omitted" and the call proceeds — so
    `LabelService(storage)` would construct cleanly and quietly stop resolving lineage
    roots, which is the one thing the whole keying design exists to do. A service that
    silently attaches to refs instead of roots is indistinguishable from a working one until
    the first supersession, months later.
    """

    def __init__(self, storage: Storage, rows: RowService, terms: TermService):
        self.storage = storage
        self.rows = rows
        self.terms = terms

    # --- writing ---

    def attach_label(
        self, word: str, targets: Sequence[RowRef | str | int]
    ) -> tuple[LabelAttachment, ...]:
        """Put a live glossary term on plan rows and tasks.

        Re-attaching something already carrying the word is a **no-op**, not an error, and
        duplicate targets inside one call are collapsed before the write. Both are guards on
        this side rather than jobs for the unique index, because an index does not produce a
        no-op: it raises and aborts the batch, so one already-labelled row in a batch of ten
        would take the other nine with it.
        """
        term = self._live_term(word)
        keys = self._resolve(targets)
        live = {self._key_of(a) for a in self._attachments(term.term)}
        stamp = now()
        ops = [
            Op("insert", "label_attachments", {
                "word": term.term,
                "target_root": root,
                "task_id": task_id,
                "created_at": stamp,
            })
            for root, task_id in keys
            if (root, task_id) not in live
        ]
        if ops:
            self.storage.write_atomic(ops, self._key("attach_label", term.term, keys))
        return self._attachments(term.term)

    def detach_label(
        self, word: str, targets: Sequence[RowRef | str | int]
    ) -> tuple[LabelAttachment, ...]:
        """Take the word off these targets, stamping rather than deleting.

        A detached attachment is the record that the label was once there, which is also why
        `label_attachments.word` carries no foreign key to `terms`: it must go on naming a
        word the owner has since removed.
        """
        term = self._live_term(word)
        keys = set(self._resolve(targets))
        stamp = now()
        current = self._attachments(term.term)
        ops = [
            Op("update", "label_attachments", {"detached_at": stamp},
               where={"id": attachment.id})
            for attachment in current
            if self._key_of(attachment) in keys
        ]
        if ops:
            self.storage.write_atomic(
                ops, self._key("detach_label", term.term, sorted(keys))
            )
        return self._attachments(term.term)

    # --- reading ---

    def labels(self, word: str | None = None) -> LabelReport:
        """Which words are carried, how widely, and — for one word — by what.

        The counts are split into rows and tasks and **never summed**: a word on three rows
        and a word on four hundred are different decisions, and a total hides which one this
        is. Both denominators travel inside the report rather than beside it, because a count
        whose denominator is one call away is a count that gets rendered alone.
        """
        definitions = {t.term: t.definition for t in self.terms.glossary()}
        counts = self._counts(None if word is None else self._word(word))
        if word is not None:
            # A word with no live attachment reports zero rather than going missing.
            # Reporting it as absent would tell the planner the word is free, which is the
            # moment they define it again — and `define_term` would then refuse it as a
            # duplicate, so the report would have walked them into a refusal.
            settled = self._word(word)
            counts.setdefault(settled, (0, 0))
        usages = tuple(
            LabelUsage(
                word=w,
                definition=definitions.get(w, ""),
                row_count=rows,
                task_count=tasks,
            )
            for w, (rows, tasks) in sorted(counts.items())
        )
        return LabelReport(
            usages=usages,
            live_rows=self._live_lineages(),
            live_tasks=self._live_tasks(),
            unattached_terms=sum(
                1 for term in definitions if term not in self._attached_words()
            ),
            targets=() if word is None else self._targets(self._word(word)),
        )

    def labels_for_page(self, refs: Sequence[RowRef]) -> dict[RowRef, tuple[str, ...]]:
        """Every live label on each ref, in **one** query however long the page.

        A row with none appears with an empty tuple rather than being absent: a caller that
        cannot tell "no labels" from "this page did not fetch them" writes
        `labels.get(ref, ())` and restores the ambiguity the mapping exists to remove.
        """
        out: dict[RowRef, tuple[str, ...]] = {RowRef.coerce(r): () for r in refs}
        if not out:
            return out
        found: dict[str, list[str]] = {}
        for record in self.storage.query(
            LABELS_FOR_PAGE, (json.dumps([str(r) for r in out]),)
        ):
            found.setdefault(record["ref"], []).append(record["word"])
        for ref in out:
            if str(ref) in found:
                out[ref] = tuple(found[str(ref)])
        return out

    # --- what `remove_term` needs, so it does not reach into the table itself ---

    def usage_of(self, word: str) -> tuple[int, int]:
        """(plan rows, tasks) carrying this word live — two counts, never their sum."""
        return self._counts(self._word(word)).get(self._word(word), (0, 0))

    def move_ops(self, word: str, replacement: str, stamp: str) -> list[Op]:
        """The ops that move every live attachment from one word to another.

        Returned rather than written, so `remove_term` can put them in the same transaction
        as the delete of the `terms` row: the move and the removal are one act, and a crash
        between them would leave the plan holding half a change nobody made (F33's shape).

        **A target already carrying the replacement collapses to one rather than raising.**
        Two live attachments for one (word, target) pair is what the unique index refuses,
        aborting the whole transaction — so a single already-tagged row would make the entire
        replacement fail. It is the same dedupe `attach_label` performs, and it belongs on
        the write path in both places rather than being left to the index.
        """
        held = {self._key_of(a) for a in self._attachments(replacement)}
        ops: list[Op] = []
        for attachment in self._attachments(word):
            if self._key_of(attachment) in held:
                ops.append(Op("update", "label_attachments", {"detached_at": stamp},
                              where={"id": attachment.id}))
            else:
                ops.append(Op("update", "label_attachments", {"word": replacement},
                              where={"id": attachment.id}))
        return ops

    def detach_ops(self, word: str, stamp: str) -> list[Op]:
        """The ops that detach every live attachment of a word, for the same reason."""
        return [
            Op("update", "label_attachments", {"detached_at": stamp},
               where={"id": attachment.id})
            for attachment in self._attachments(word)
        ]

    # --- internals ---

    def _live_term(self, word: str) -> Term:
        """The glossary's whole mechanical role: a label must be a word the plan has
        defined. There is no ban branch and no `TermBanned` — neither state exists."""
        found = self.terms.find(self._word(word))
        if found is None:
            raise TermNotFound(
                f"'{self._word(word)}' is not a term in this plan, so it cannot be a "
                "label: a label is a glossary word, which is what stops the plan being "
                "filtered by words nobody has agreed the meaning of. define_term records "
                "what it means",
                term=self._word(word),
            )
        return found

    def _target_key(self, target: RowRef | str | int) -> tuple[str | None, int | None]:
        """`(lineage root, None)` for a plan row, `(None, task id)` for a task.

        **`isinstance(x, int)` is not how the two id spaces are told apart**, because `bool`
        subclasses `int`: `isinstance(True, int)` is `True`, so `attach_label(word, (True,))`
        would read as task 1 and write an attachment to whatever task holds that id. The
        test is `type(x) is int`.

        **Existence is checked here and not left to `lineage_root`**, which refuses nothing:
        its body returns the input ref both for a row with no parent and for a row that does
        not exist. Without this check `attach_label('engine', ('nosuch:99',))` would succeed,
        writing an attachment to a target that has never existed and that nothing would ever
        clean up, since neither target column carries a foreign key.
        """
        if type(target) is int:
            if target <= 0:
                raise InvalidTarget(
                    "a task id is a positive whole number", target=repr(target)
                )
            found = self.storage.query(
                "SELECT id FROM tasks WHERE id = ?", (target,)
            )
            if not found:
                raise InvalidTarget("no such task", task_id=target)
            return (None, target)
        if isinstance(target, (RowRef, str)):
            try:
                ref = RowRef.coerce(target)
            except ValueError as exc:
                raise InvalidTarget(str(exc), target=repr(target)) from exc
            self.rows.get(ref)  # raises RowNotFound, naming the ref
            return (str(self.rows.lineage_root(ref)), None)
        raise InvalidTarget(
            "a label goes on a plan row, addressed like 'requirements:61', or on a task, "
            "given as its id",
            target=repr(target),
        )

    def _resolve(
        self, targets: Sequence[RowRef | str | int]
    ) -> list[tuple[str | None, int | None]]:
        """Every target's key, with duplicates **within the call** collapsed.

        Collapsing here rather than at the index: two inserts for one pair reach the unique
        index as one batch and the raise takes every other row in the batch with them.
        """
        seen: list[tuple[str | None, int | None]] = []
        for target in targets:
            resolved = self._target_key(target)
            if resolved not in seen:
                seen.append(resolved)
        return seen

    def _attachments(
        self, word: str, live_only: bool = True
    ) -> tuple[LabelAttachment, ...]:
        clause = " AND detached_at IS NULL" if live_only else ""
        return tuple(
            self._hydrate(r)
            for r in self.storage.query(
                f"SELECT * FROM label_attachments WHERE word = ?{clause} "  # noqa: S608
                "ORDER BY id",
                (self._word(word),),
            )
        )

    def _counts(self, word: str | None) -> dict[str, tuple[int, int]]:
        clause = "" if word is None else " AND word = ?"
        params = () if word is None else (word,)
        return {
            r["word"]: (r["rows"], r["tasks"])
            for r in self.storage.query(
                "SELECT word, "
                "  COUNT(target_root) AS rows, "
                "  COUNT(task_id) AS tasks "
                "FROM label_attachments "
                f"WHERE detached_at IS NULL{clause} "  # noqa: S608
                "GROUP BY word ORDER BY word",
                params,
            )
        }

    def _attached_words(self) -> set[str]:
        return {
            r["word"] for r in self.storage.query(
                "SELECT DISTINCT word FROM label_attachments WHERE detached_at IS NULL"
            )
        }

    def _live_lineages(self) -> int:
        """The denominator for `row_count`, counting the same population its numerator does.

        A live *lineage*, not a live row: attachments key on lineage roots, and the two sets
        coincide only for lineages that have never been superseded — so on a plan with any
        revision history a ratio against live rows drifts. One row per lineage, the one with
        no successor, which is also what a person means by "how much of the plan carries
        this label".
        """
        return self.storage.query(
            "SELECT COUNT(*) AS n FROM plan_rows "
            "WHERE superseded_by IS NULL AND state != 'retired'"
        )[0]["n"]

    def _live_tasks(self) -> int:
        """Every task, and the absence of a predicate is the decision.

        A task is never superseded and has no retired state, so there is no liveness check
        to make — and filtering out `done` would count a population the numerator does not:
        a finished task still carries whatever label was put on it. Same rule as
        `_live_lineages`, reaching the opposite-looking answer for the same reason.
        """
        return self.storage.query("SELECT COUNT(*) AS n FROM tasks")[0]["n"]

    def _targets(self, word: str) -> tuple[LabelTarget, ...]:
        """Everything carrying the word, each with a name beside its address.

        Convention 9: an address never travels alone. A report listing `requirements:61`
        hands its reader the lookup this whole design exists to remove.
        """
        out: list[LabelTarget] = []
        for attachment in self._attachments(word):
            if attachment.target_root is not None:
                ref = self.rows.lineage_head(attachment.target_root)
                out.append(LabelTarget(
                    kind="row", ref=ref, task_id=None, name=self.rows.get(ref).name
                ))
            else:
                found = self.storage.query(
                    "SELECT title FROM tasks WHERE id = ?", (attachment.task_id,)
                )
                out.append(LabelTarget(
                    kind="task",
                    ref=None,
                    task_id=attachment.task_id,
                    name=found[0]["title"] if found else "",
                ))
        return tuple(out)

    def _key(self, act: str, word: str, keys) -> str:
        """The idempotency key, carrying **the act's own name** and the word's history depth.

        Neither call takes a key from the caller, and the honest reason is that both are
        idempotent by construction: a repeat attach is a no-op that writes nothing at all, so
        there is nothing to protect against replaying.

        **The act is in the key because without it the two calls collide.** Derived from the
        word and the targets alone, `attach_label('part', refs)` and
        `detach_label('part', refs)` produce the *same* key — and `Storage.replay` returns
        the original receipt and skips execution, so a detach following an attach on the
        same targets would be swallowed as a replay and write nothing, silently. `terms.py`
        already carried the fix as a pattern: the act is always part of the key.

        **The third element is the count of every attachment this word has ever had**, live
        or detached, and it is *not* what the specification asked for. That said "include the
        current live-attachment keys", which does not work and was caught by the test written
        for it: after attach → detach the live set is empty again, so a re-attach re-derives
        the first attach's key exactly and is swallowed. The live set is a function of current
        state, and what distinguishes the third call from the first is history, not state.
        This count is monotonic — detaching stamps rather than deletes, so a row is never
        removed — and every attach that writes increments it, which makes each write of each
        act distinct without a caller having to supply anything.
        """
        depth = self.storage.query(
            "SELECT COUNT(*) AS n FROM label_attachments WHERE word = ?", (word,)
        )[0]["n"]
        return key(act, word, sorted(str(k) for k in keys), depth)

    @staticmethod
    def _key_of(attachment: LabelAttachment) -> tuple[str | None, int | None]:
        root = attachment.target_root
        return (str(root) if root is not None else None, attachment.task_id)

    @staticmethod
    def _word(term: str) -> str:
        word = (term or "").strip().lower()
        if not word:
            raise TermNotFound("a label is a word; this one is empty")
        return word

    @staticmethod
    def _hydrate(r) -> LabelAttachment:
        return LabelAttachment(
            id=r["id"],
            word=r["word"],
            target_root=RowRef.parse(r["target_root"]) if r["target_root"] else None,
            task_id=r["task_id"],
            detached_at=r["detached_at"],
            created_at=r["created_at"],
        )
