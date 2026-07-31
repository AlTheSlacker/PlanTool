"""Every row has a name (M6_PLAN.md §6).

A row is addressed as `table:ordinal`, and an address on its own makes the reader go and
look something up — which a person does not do, and which a model answers by inventing
something plausible. These tests hold the four clauses: named at creation, unique among
live rows, re-affirmed when the content changes, and never replaced by a bare address.

The last clause is the one with history. Until 2026-07-22 three separate functions guessed
a row's name out of free-form content and fell back to printing the address when the guess
failed, so `crud_grid` rows — which carry `op` and `actor` and none of the five keys the
guess looked for — were announced to the reader as an address and nothing else.
"""

from __future__ import annotations

import pytest

from engine.errors import UpgradeFailed
from engine.gaps import name_of
from engine.models import (
    Provenance,
    RowSelector,
    RowSubmission,
    SpikeSpec,
    content_fingerprint,
)


def _submit(rows, key, **kwargs):
    return rows.submit_rows([RowSubmission(**kwargs)], key)


# --- clause 1: named at creation ----------------------------------------------------


def test_a_row_without_a_name_is_rejected_and_told_why(rows):
    receipt = _submit(rows, "k", table="requirements", content={"text": "x"}, name="")
    verdict = receipt.verdicts[0]

    assert not verdict.accepted
    assert "needs a name" in verdict.problem
    # Pedagogical, per requirements:14 — it says what a name is for, not just that one
    # is missing.
    assert "look it up" in verdict.problem


def test_a_whitespace_name_is_not_a_name(rows):
    receipt = _submit(rows, "k", table="requirements", content={"text": "x"}, name="   ")
    assert not receipt.verdicts[0].accepted


def test_the_name_is_stored_and_read_back(rows):
    _submit(rows, "k", table="requirements", content={"text": "x"},
            name="plans survive a crash")
    row = rows.get("requirements:1")

    assert row.name == "plans survive a crash"
    # The single owner of "what do we call this row" reads the column and nothing else.
    assert name_of(row) == "plans survive a crash"


def test_a_row_whose_content_has_no_name_like_key_still_has_a_name(rows):
    """The case the old guess could not serve at all.

    A `crud_grid` row carries `op` and `actor`. None of the five keys the fallback chain
    tried was present, so it printed the bare ref — the exact lookup this design removes.
    """
    from engine.models import LinkSpec

    rows.submit_rows(
        [
            RowSubmission(table="entities", content={"text": "Plan"}, name="Plan"),
            RowSubmission(table="crud_grid", content={"op": "C", "actor": "owner"},
                          name="the owner creates a plan",
                          links=[LinkSpec(0, "belongs_to")]),
        ],
        "k",
    )
    row = rows.get("crud_grid:1")

    assert name_of(row) == "the owner creates a plan"
    assert str(row.ref) not in name_of(row)


# --- clause 2: unique among live rows ------------------------------------------------


def test_two_live_rows_in_one_table_cannot_share_a_name(rows):
    _submit(rows, "k1", table="requirements", content={"text": "a"}, name="atomic writes")
    receipt = _submit(rows, "k2", table="requirements", content={"text": "b"},
                      name="atomic writes")
    verdict = receipt.verdicts[0]

    assert not verdict.accepted
    # The clash names the row it collided with, and names it by name — an address alone
    # would be the very failure this file is about.
    assert "atomic writes" in verdict.problem
    assert "requirements:1" in verdict.problem
    assert "filed twice" in verdict.problem


def test_a_collision_inside_one_batch_is_caught_too(rows):
    receipt = rows.submit_rows(
        [
            RowSubmission(table="requirements", content={"text": "a"}, name="one name"),
            RowSubmission(table="requirements", content={"text": "b"}, name="one name"),
        ],
        "k",
    )

    assert receipt.verdicts[0].accepted
    assert not receipt.verdicts[1].accepted
    assert "batch" in receipt.verdicts[1].problem


def test_capitalisation_is_not_a_distinction(rows):
    _submit(rows, "k1", table="requirements", content={"text": "a"}, name="Atomic Writes")
    receipt = _submit(rows, "k2", table="requirements", content={"text": "b"},
                      name="atomic writes")

    assert not receipt.verdicts[0].accepted


def test_different_tables_may_share_a_name(rows):
    """A requirement and the contract that satisfies it legitimately share a word."""
    _submit(rows, "k1", table="requirements", content={"text": "a"}, name="atomic writes")
    receipt = _submit(rows, "k2", table="contracts", content={"text": "b"},
                      name="atomic writes")

    assert receipt.verdicts[0].accepted


def test_a_superseded_rows_name_is_free_for_its_replacement(rows):
    """Redefinition: the same thing said more sharply, under the same name.

    This is why the index is scoped to live rows, and why supersession writes the old
    row's state and the replacement in one transaction — for the statement in between,
    both would otherwise be live under one name.
    """
    _submit(rows, "k1", table="decisions", content={"text": "SQLite"},
            name="where plans are stored")
    rows.supersede_row(
        "decisions:1",
        RowSubmission(table="decisions", content={"text": "SQLite, WAL mode"},
                      name="where plans are stored"),
        "WAL was not in the original wording",
        "k2",
    )

    live = rows.read_rows(RowSelector(table="decisions", live_only=True))
    assert [r.name for r in live.rows] == ["where plans are stored"]
    assert rows.get("decisions:2").content["text"] == "SQLite, WAL mode"


def test_a_retired_rows_name_is_free_again(rows):
    _submit(rows, "k1", table="decisions", content={"text": "a"}, name="the storage call")
    rows.retire_row("decisions:1", "withdrawn", "k2")

    receipt = _submit(rows, "k3", table="decisions", content={"text": "b"},
                      name="the storage call")
    assert receipt.verdicts[0].accepted


# --- clause 3: a name does not survive a change of meaning ---------------------------


def _assumption(rows, key="k"):
    receipt = _submit(rows, key, table="assumptions",
                      content={"text": "SMB honours fsync"},
                      name="the share honours fsync", provenance=Provenance.ASSUMED,
                      assumption_kind="world",
                      spike=SpikeSpec("Does the share honour fsync?", "it does",
                                      "fsync then pull the plug", "1 day"))
    return receipt.verdicts[0].ref


def test_revising_in_place_demands_a_name(rows):
    ref = _assumption(rows)

    with pytest.raises(UpgradeFailed) as exc:
        rows.resolve_assumption(ref, quote="not on this filer", resolution="revise",
                                idempotency_key="k2")

    # It names the row it is talking about, and says what to do about it.
    assert "the share honours fsync" in str(exc.value)
    assert "pass the same one" in str(exc.value)


def test_revising_with_a_name_records_it(rows):
    ref = _assumption(rows)
    row = rows.resolve_assumption(ref, quote="not on this filer", resolution="revise",
                                  idempotency_key="k2",
                                  name="the share does not honour fsync")

    assert row.name == "the share does not honour fsync"


def test_confirming_needs_no_new_name_because_nothing_changed_meaning(rows):
    ref = _assumption(rows)
    row = rows.resolve_assumption(ref, quote="yes, it does", resolution="confirm",
                                  idempotency_key="k2")

    assert row.name == "the share honours fsync"


def test_rejecting_needs_no_name_because_the_row_leaves_live_reads(rows):
    ref = _assumption(rows)
    row = rows.resolve_assumption(ref, quote="no", resolution="reject",
                                  idempotency_key="k2")

    assert not row.is_live


def test_a_confirm_refreshes_the_fingerprint_it_changed(rows):
    """A confirm appends the owner's answer to content, so the fingerprint must move.

    Leaving it stale would make the *next* write look like a change of meaning when the
    change already happened here — a check firing for something that already had its
    moment of attention is a check people learn to click through.
    """
    ref = _assumption(rows)
    before = rows.storage.query(
        "SELECT named_for FROM plan_rows WHERE table_name='assumptions'"
    )[0]["named_for"]

    rows.resolve_assumption(ref, quote="yes", resolution="confirm", idempotency_key="k2")

    after_row = rows.get(ref)
    after = rows.storage.query(
        "SELECT named_for FROM plan_rows WHERE table_name='assumptions'"
    )[0]["named_for"]

    assert after != before
    assert after == content_fingerprint(after_row.content)


def test_a_rename_cannot_collide_with_a_live_sibling(rows):
    _submit(rows, "k0", table="assumptions", content={"text": "other"},
            name="taken already")
    ref = _assumption(rows, key="k1")

    with pytest.raises(UpgradeFailed) as exc:
        rows.resolve_assumption(ref, quote="q", resolution="revise",
                                idempotency_key="k2", name="taken already")

    assert "cannot share" in str(exc.value)


def test_a_replacement_must_be_named(rows):
    _submit(rows, "k1", table="decisions", content={"text": "a"}, name="the original")

    with pytest.raises(Exception) as exc:
        rows.supersede_row(
            "decisions:1",
            RowSubmission(table="decisions", content={"text": "b"}, name=""),
            "reworded",
            "k2",
        )

    assert "needs a name" in str(exc.value)


# --- the fingerprint itself ----------------------------------------------------------


def test_key_order_does_not_read_as_a_change(rows):
    """Re-serialising an unchanged dict must not demand a pointless re-naming."""
    assert content_fingerprint({"a": 1, "b": 2}) == content_fingerprint({"b": 2, "a": 1})


def test_changed_content_changes_the_fingerprint(rows):
    assert content_fingerprint({"a": 1}) != content_fingerprint({"a": 2})
