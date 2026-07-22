"""Scope-attachment framework — DEVIATIONS.md D8/D13, M5_PLAN.md section 2.

Levels are plan > package > task > subtask (`GLOSSARY.md`).
"""

import pytest

from engine.attachments import (
    PACKAGE,
    PLAN,
    SUBTASK,
    TASK,
    PromotionNeedsReason,
    UnknownScopeLevel,
)
from engine.models import RowSubmission


def _row(rows, text, key):
    return rows.submit_rows(
        [RowSubmission(table="decisions", content={"text": text}, name=text)], key
    ).verdicts[0].ref


def test_subtask_context_unions_enclosing_scopes(attachments, rows):
    """M5_PLAN.md 2.3 — a sub-task's context is its own attachments plus every enclosing
    scope. This is the structural bound that replaces 'last N' (DEFECTS.md F16)."""
    wide = _row(rows, "no LLM inside the tool, ever", "a")
    pkg = _row(rows, "the GUI is single-window", "b")
    task = _row(rows, "this task uses typed dependency links", "c")
    narrow = _row(rows, "this sub-task needs the WAL note", "d")

    # Keys are ids, never names (GLOSSARY.md) — a name-keyed scope returns an empty set on
    # a typo, and the sub-task silently missing its context is what decisions:14 measures.
    attachments.attach(wide, PLAN, reason="binds every task")
    attachments.attach(pkg, PACKAGE, scope_key="3", reason="GUI-wide")
    attachments.attach(task, TASK, scope_key="11", reason="task-wide")
    attachments.attach(narrow, SUBTASK, scope_key="7", reason="local")

    context = attachments.context_for(subtask_key="7", task_key="11", package_key="3")
    assert [str(r) for r in context] == [str(wide), str(pkg), str(task), str(narrow)]


def test_a_subtask_does_not_see_a_sibling_subtasks_attachments(attachments, rows):
    mine = _row(rows, "mine", "a")
    theirs = _row(rows, "theirs", "b")
    attachments.attach(mine, SUBTASK, scope_key="7", reason="local")
    attachments.attach(theirs, SUBTASK, scope_key="8", reason="local")

    assert [str(r) for r in attachments.context_for(subtask_key="7")] == [str(mine)]


def test_attachment_keys_on_lineage_root(attachments, rows):
    """M5_PLAN.md 2.4 — decisions:3 makes the plan a living source of truth, so an
    allocation keyed on a row id detaches the moment its target is superseded. Same
    problem and same answer as findings:16 / requirements:78."""
    original = _row(rows, "settling is fast", "a")
    attachments.attach(original, PLAN, reason="load-bearing")

    replacement = rows.supersede_row(
        original,
        RowSubmission(table="decisions", content={"text": "settling is 40ms"}, name="settling is 40ms"),
        "supersede",
    )
    root = rows.lineage_root(replacement["new"])
    assert str(root) == str(original)
    assert attachments.context_for()[0] == root


def test_promotion_requires_a_recorded_reason(attachments, rows):
    """M5_PLAN.md 2.5 — asymmetric friction. Too high is the silent failure: a
    plan-level attachment is in every sub-task forever and nobody notices a cost spread
    evenly."""
    ref = _row(rows, "a local note", "a")
    attachments.attach(ref, SUBTASK, scope_key="7", reason="local")

    with pytest.raises(PromotionNeedsReason):
        attachments.attach(ref, PLAN)

    promoted = attachments.attach(ref, PLAN, reason="it turned out to bind everything")
    assert promoted.promoted_from == SUBTASK


def test_narrowing_is_free(attachments, rows):
    ref = _row(rows, "a broad note", "a")
    attachments.attach(ref, PLAN, reason="seemed broad")
    narrowed = attachments.attach(ref, SUBTASK, scope_key="7")
    assert narrowed.promoted_from is None


def test_narrowing_actually_narrows(attachments, rows):
    """Caught by driving the engine, not by the suite. The first implementation inserted
    a new row and left the old one live, so a narrowed attachment stayed plan-scoped
    and remained in every sub-task forever — the exact 'too high' failure M5_PLAN.md 2.5's
    friction exists to prevent, made unfixable by the direction that is supposed to be
    free. The test above passed throughout: it asserted on `promoted_from` and never
    checked where the row ended up."""
    ref = _row(rows, "a broad note", "a")
    attachments.attach(ref, PLAN, reason="seemed broad")
    assert attachments.context_for() == (ref,)

    attachments.attach(ref, SUBTASK, scope_key="7")
    assert attachments.context_for() == ()
    assert attachments.context_for(subtask_key="7") == (ref,)


def test_superseded_placements_are_kept_not_deleted(attachments, rows, store):
    """The promotion history is the owner's review surface, so a replaced placement is
    stamped rather than removed."""
    ref = _row(rows, "a note", "a")
    attachments.attach(ref, PLAN, reason="seemed broad")
    attachments.attach(ref, SUBTASK, scope_key="7")

    stored = store.query("SELECT * FROM scope_attachments ORDER BY id")
    assert len(stored) == 2
    assert stored[0]["superseded_at"] is not None
    assert stored[1]["superseded_at"] is None


def test_promotions_are_reviewable(attachments, rows):
    """The GUI review surface's input. Gaming the accounting should require lying in a
    log the owner reads — the same shape as requirements:79."""
    ref = _row(rows, "a note", "a")
    attachments.attach(ref, SUBTASK, scope_key="7", reason="local")
    attachments.attach(ref, PLAN, reason="binds every component after all")

    entries = attachments.promotions()
    assert len(entries) == 1
    assert entries[0].reason == "binds every component after all"


def test_unknown_scope_level_is_refused(attachments, rows):
    """`session` was dropped on review: the other three are plan structure, whereas a
    session is an episode of work — and session-scoped attachment is the journal."""
    ref = _row(rows, "a note", "a")
    with pytest.raises(UnknownScopeLevel):
        attachments.attach(ref, "session", reason="x")
