"""row-service (components:2)."""

import pytest

from engine.errors import (
    AlreadyRetired,
    AlreadySuperseded,
    ConflictRequired,
    InvalidSelector,
    NotAssumed,
    RowNotFound,
)
from engine.models import LinkSpec, Provenance, RowRef, RowSelector, RowSubmission
from engine.rows import RowService


def test_submit_assigns_per_table_ordinals(rows):
    receipt = rows.submit_rows(
        [
            RowSubmission("requirements", {"text": "first"}, name="first"),
            RowSubmission("requirements", {"text": "second"}, name="second"),
            RowSubmission("decisions", {"text": "other table"}, name="other table"),
        ],
        "k",
    )
    assert [str(v.ref) for v in receipt.verdicts] == [
        "requirements:1", "requirements:2", "decisions:1",
    ]


def test_one_bad_row_is_rejected_alone(rows):
    """requirements:14 — reject only that row, naming the specific problem."""
    receipt = rows.submit_rows(
        [
            RowSubmission("requirements", {"text": "good"}, name="good"),
            RowSubmission("requirements", {}, name="empty"),  # empty content
            RowSubmission("requirements", {"text": "also good"}, name="also good"),
        ],
        "k",
    )
    assert [v.accepted for v in receipt.verdicts] == [True, False, True]
    assert "non-empty" in receipt.verdicts[1].problem
    assert rows.read_rows(RowSelector(table="requirements")).total == 2


def test_assumed_row_must_declare_its_kind(rows):
    """requirements:5 — provenance, and for assumptions the assumption kind."""
    receipt = rows.submit_rows(
        [RowSubmission("decisions", {"text": "guessing"},
                       provenance=Provenance.ASSUMED, name="guessing")],
        "k",
    )
    assert receipt.verdicts[0].accepted is False
    assert "assumption_kind" in receipt.verdicts[0].problem


def test_links_are_written_with_their_row(rows):
    rows.submit_rows([RowSubmission("use_cases", {"text": "uc"}, name="uc")], "k1")
    rows.submit_rows(
        [RowSubmission("requirements", {"text": "req"},
                       links=[LinkSpec(RowRef("use_cases", 1))], name="req")],
        "k2",
    )
    row = rows.get("requirements:1")
    assert row.links[0].target == RowRef("use_cases", 1)


def test_row_can_link_to_a_sibling_in_the_same_batch(rows):
    """DEFECTS.md F5 — the plan says links are created with their row but never says
    how a row references a sibling whose ref does not exist yet."""
    receipt = rows.submit_rows(
        [
            RowSubmission("use_cases", {"text": "uc"}, name="uc"),
            RowSubmission("requirements", {"text": "req"}, links=[LinkSpec(0)], name="req"),
        ],
        "k",
    )
    assert all(v.accepted for v in receipt.verdicts)
    assert rows.get("requirements:1").links[0].target == RowRef("use_cases", 1)


def test_sibling_link_to_a_rejected_row_cascades(rows):
    """Filing the row while silently dropping its link would give it less provenance
    than it declared."""
    receipt = rows.submit_rows(
        [
            RowSubmission("use_cases", {}, name="empty"),  # rejected: empty content
            RowSubmission("requirements", {"text": "req"}, links=[LinkSpec(0)], name="req"),
            RowSubmission("contracts", {"text": "con"}, links=[LinkSpec(1)], name="con"),
        ],
        "k",
    )
    assert [v.accepted for v in receipt.verdicts] == [False, False, False]
    assert "was rejected" in receipt.verdicts[2].problem


def test_sibling_link_out_of_range_is_rejected(rows):
    receipt = rows.submit_rows(
        [RowSubmission("requirements", {"text": "r"}, links=[LinkSpec(7)], name="r")], "k"
    )
    assert receipt.verdicts[0].accepted is False
    assert "outside this batch" in receipt.verdicts[0].problem


def test_self_link_is_rejected(rows):
    receipt = rows.submit_rows(
        [RowSubmission("requirements", {"text": "r"}, links=[LinkSpec(0)], name="r")], "k"
    )
    assert receipt.verdicts[0].accepted is False
    assert "cannot link to itself" in receipt.verdicts[0].problem


def test_replay_returns_the_original_verdicts(rows):
    """decisions:43 — a replayed key returns the ORIGINAL receipt, and the batch
    presented on replay is not re-evaluated."""
    first = rows.submit_rows(
        [
            RowSubmission("requirements", {"text": "kept"}, name="kept"),
            RowSubmission("requirements", {}, name="empty"),  # rejected
        ],
        "same-key",
    )
    second = rows.submit_rows(
        [RowSubmission("decisions", {"text": "totally different batch"}, name="totally different batch")], "same-key"
    )
    assert second.replayed is True
    assert [str(v.ref) if v.ref else None for v in second.verdicts] == [
        str(v.ref) if v.ref else None for v in first.verdicts
    ]
    assert [v.accepted for v in second.verdicts] == [True, False]
    # The replayed batch wrote nothing.
    assert rows.read_rows(RowSelector(table="decisions")).total == 0


def test_link_to_a_missing_row_is_rejected(rows):
    receipt = rows.submit_rows(
        [RowSubmission("requirements", {"text": "req"},
                       links=[LinkSpec(RowRef("use_cases", 99))], name="req")],
        "k",
    )
    assert receipt.verdicts[0].accepted is False
    assert "does not exist" in receipt.verdicts[0].problem


def test_contradiction_blocks_the_whole_batch(store):
    """requirements:27 — nothing is filed until a conflict is raised and presented."""
    def detector(submission, service):
        if submission.content.get("text") == "contradictory":
            return "contradicts requirements:1"
        return None

    service = RowService(store, detector)
    with pytest.raises(ConflictRequired):
        service.submit_rows(
            [
                RowSubmission("requirements", {"text": "fine"}, name="fine"),
                RowSubmission("requirements", {"text": "contradictory"}, name="contradictory"),
            ],
            "k",
        )
    assert service.read_rows(RowSelector(table="requirements")).total == 0


def test_read_rows_selectors(rows):
    rows.submit_rows(
        [
            RowSubmission("requirements", {"text": "a"}, stage=3, name="a"),
            RowSubmission("requirements", {"text": "b"}, stage=4, name="b"),
            RowSubmission("decisions", {"text": "c"}, stage=3, name="c"),
        ],
        "k",
    )
    assert rows.read_rows(RowSelector(table="requirements")).total == 2
    assert rows.read_rows(RowSelector(stage=3)).total == 2
    assert rows.read_rows(RowSelector(ids=[RowRef("decisions", 1)])).total == 1


def test_read_rows_paginates(rows):
    """requirements:62 — resume cost scales with the working set, never a full dump."""
    rows.submit_rows(
        [RowSubmission("requirements", {"text": str(i)}, name=f"req {i}")
         for i in range(10)], "k"
    )
    page = rows.read_rows(RowSelector(table="requirements", limit=4))
    assert len(page.rows) == 4
    assert page.total == 10
    assert page.has_more is True

    last = rows.read_rows(RowSelector(table="requirements", limit=4, offset=8))
    assert last.has_more is False


def test_bad_selector_names_the_field(rows):
    with pytest.raises(InvalidSelector) as exc:
        rows.read_rows(RowSelector(limit=0))
    assert exc.value.detail["field"] == "limit"


def test_neighbourhood_selector_walks_links(rows):
    rows.submit_rows([RowSubmission("use_cases", {"text": "uc"}, name="uc")], "k1")
    rows.submit_rows(
        [RowSubmission("requirements", {"text": "req"},
                       links=[LinkSpec(RowRef("use_cases", 1))], name="req")],
        "k2",
    )
    page = rows.read_rows(RowSelector(neighbourhood_of=RowRef("use_cases", 1)))
    assert [str(r.ref) for r in page.rows] == ["requirements:1"]


def test_resolve_assumption_upgrades_in_place(rows):
    """contracts:70 / decisions:28(a) — the SAME row upgrades; no duplicate appears."""
    rows.submit_rows(
        [RowSubmission("decisions", {"text": "assumed thing"},
                       provenance=Provenance.ASSUMED, assumption_kind="intent", name="assumed thing")],
        "k1",
    )
    upgraded = rows.resolve_assumption(
        "decisions:1", "Yes, that's right.", "confirm", "k2"
    )
    assert upgraded.provenance is Provenance.DECIDED
    assert upgraded.content["owner_answer"]["quote"] == "Yes, that's right."
    assert rows.read_rows(RowSelector(table="decisions")).total == 1


def test_resolve_requires_a_verbatim_quote(rows):
    from engine.errors import UpgradeFailed

    rows.submit_rows(
        [RowSubmission("decisions", {"text": "x"},
                       provenance=Provenance.ASSUMED, assumption_kind="intent", name="x")],
        "k1",
    )
    with pytest.raises(UpgradeFailed):
        rows.resolve_assumption("decisions:1", "   ", "confirm", "k2")


def test_resolve_rejects_non_assumptions(rows):
    rows.submit_rows([RowSubmission("decisions", {"text": "decided"}, name="decided")], "k1")
    with pytest.raises(NotAssumed):
        rows.resolve_assumption("decisions:1", "quote", "confirm", "k2")


def test_supersede_sets_both_pointers_once(rows):
    """requirements:61 — stamped once, content never edited, lineage bidirectional."""
    rows.submit_rows([RowSubmission("decisions", {"text": "old"}, name="old")], "k1")
    result = rows.supersede_row(
        "decisions:1", RowSubmission("decisions", {"text": "new"}, name="new"),
        "the old wording was wrong", "k2"
    )
    old = rows.get("decisions:1")
    new = rows.get(result["new"])

    assert old.superseded_by == new.ref
    assert old.superseded_at is not None
    assert old.is_live is False
    assert new.supersedes == old.ref
    assert new.is_live is True
    assert old.content["text"] == "old"  # content never edited


def test_supersession_lineage_is_write_once(rows):
    rows.submit_rows([RowSubmission("decisions", {"text": "old"}, name="old")], "k1")
    rows.supersede_row("decisions:1", RowSubmission("decisions", {"text": "a"}, name="a"),
                       "reworded", "k2")
    with pytest.raises(AlreadySuperseded):
        rows.supersede_row(
            "decisions:1", RowSubmission("decisions", {"text": "b"}, name="b"),
            "reworded again", "k3"
        )


def test_retire_is_recorded_exactly_once(rows):
    rows.submit_rows([RowSubmission("decisions", {"text": "x"}, name="x")], "k1")
    retired = rows.retire_row("decisions:1", "no longer relevant", "k2")
    assert retired.is_live is False
    assert retired.retire_reason == "no longer relevant"
    with pytest.raises(AlreadyRetired):
        rows.retire_row("decisions:1", "again", "k3")


def test_live_only_excludes_superseded_and_retired(rows):
    rows.submit_rows(
        [RowSubmission("decisions", {"text": "a"}, name="a"),
         RowSubmission("decisions", {"text": "b"}, name="b")],
        "k1",
    )
    rows.supersede_row("decisions:1", RowSubmission("decisions", {"text": "a2"}, name="a2"),
                       "reworded", "k2")
    rows.retire_row("decisions:2", "gone", "k3")

    live = rows.read_rows(RowSelector(table="decisions", live_only=True))
    assert [str(r.ref) for r in live.rows] == ["decisions:3"]


def test_missing_row_is_named(rows):
    with pytest.raises(RowNotFound) as exc:
        rows.get("decisions:42")
    assert exc.value.detail["ref"] == "decisions:42"


# --- lineage as the answer to "what became of what I said?" (owner, 2026-07-21) ---


def test_updated_at_is_derived_from_the_rows_own_lifecycle(rows):
    """Never stored. A planning row is immutable (requirements:61), so a stored
    `updated_at` would equal `created_at` forever — a column promising a change it cannot
    deliver, and a second copy of what `superseded_at` already records."""
    ref = rows.submit_rows(
        [RowSubmission(table="decisions", content={"title": "first thought"}, name="first thought")], "a"
    ).verdicts[0].ref
    original = rows.get(ref)
    assert original.updated_at == original.created_at

    rows.supersede_row(
        ref,
        RowSubmission(table="decisions", content={"title": "second thought"},
                      name="second thought"),
        "thought again", "b"
    )

    superseded = rows.get(ref)
    assert superseded.updated_at == superseded.superseded_at
    assert superseded.updated_at != superseded.created_at


def test_lineage_head_answers_where_a_decision_stands_now(rows):
    """`lineage_root` is a thing's stable identity; `lineage_head` is its current state.
    Both are needed, for opposite reasons."""
    ref = rows.submit_rows(
        [RowSubmission(table="decisions", content={"title": "first"}, name="first")], "a"
    ).verdicts[0].ref
    second = rows.supersede_row(
        ref, RowSubmission(table="decisions", content={"title": "second"}, name="second"),
        "thought again", "b"
    )["new"]
    third = rows.supersede_row(
        second, RowSubmission(table="decisions", content={"title": "third"}, name="third"),
        "and again", "c"
    )["new"]

    assert rows.lineage_head(ref) == third
    assert rows.lineage_root(third) == ref
    assert rows.lineage_head(third) == third


def test_history_reads_the_whole_chain_with_each_versions_timestamp(rows):
    """"I said something yesterday — find it" is a question about a lineage. Each version
    carries its own created_at, so the answer is both when it was said and what it said."""
    ref = rows.submit_rows(
        [RowSubmission(table="decisions", content={"title": "first"}, name="first")], "a"
    ).verdicts[0].ref
    rows.supersede_row(
        ref, RowSubmission(table="decisions", content={"title": "second"}, name="second"),
        "thought again", "b"
    )

    chain = rows.history(ref)
    assert [r.content["title"] for r in chain] == ["first", "second"]
    assert all(r.created_at for r in chain)
    assert chain[-1].is_live and not chain[0].is_live


# --- the decision context (v3 D11) ---


def test_a_submission_carries_its_argument_and_is_accepted_without_one(rows, store):
    """Both fields are optional at submission: absence is a gap, not a rejection. A value
    that strips to empty is stored NULL rather than `''`, so the gap rule reading the
    column raw sees one thing and not two."""
    rows.submit_rows(
        [
            RowSubmission("entities", {"t": "argued"}, name="argued",
                          grounds="  one store keeps lineage in one place  ",
                          alternatives="a table per type — rejected, a migration per type"),
            RowSubmission("entities", {"t": "bare"}, name="bare"),
            RowSubmission("entities", {"t": "blank"}, name="blank",
                          grounds="   ", alternatives=""),
        ],
        "k",
    )
    argued = rows.get("entities:1")
    assert argued.grounds == "one store keeps lineage in one place"
    assert argued.alternatives.startswith("a table per type")
    assert rows.get("entities:2").grounds is None
    stored = store.query(
        "SELECT grounds, alternatives FROM plan_rows WHERE ordinal = 3"
    )[0]
    assert stored["grounds"] is None and stored["alternatives"] is None


def test_record_grounds_writes_once_per_field(rows):
    from engine.errors import GroundsAlreadyRecorded, GroundsNeedBoth

    rows.submit_rows([RowSubmission("entities", {"t": "a"}, name="a")], "k")
    with pytest.raises(GroundsNeedBoth) as exc:
        rows.record_grounds("entities:1", "because it is the aggregate", "", "g1")
    assert "alternatives" in str(exc.value)

    row = rows.record_grounds(
        "entities:1", "because it is the aggregate", "none, it follows from the use case",
        "g2",
    )
    assert row.grounds == "because it is the aggregate"
    with pytest.raises(GroundsAlreadyRecorded) as exc:
        rows.record_grounds("entities:1", "a sharper argument", "", "g3")
    assert "supersede_row()" in str(exc.value)


def test_record_grounds_replays_its_first_answer(rows):
    rows.submit_rows([RowSubmission("entities", {"t": "a"}, name="a")], "k")
    first = rows.record_grounds("entities:1", "because", "none", "g1")
    again = rows.record_grounds("entities:1", "because", "none", "g1")
    assert again.grounds == first.grounds == "because"


def test_record_grounds_refuses_a_row_that_is_not_live(rows):
    from engine.errors import RowNotLive

    rows.submit_rows([RowSubmission("entities", {"t": "a"}, name="a")], "k")
    rows.supersede_row(
        "entities:1", RowSubmission("entities", {"t": "b"}, name="b"),
        "the first wording read as two claims", "s1",
    )
    with pytest.raises(RowNotLive) as exc:
        rows.record_grounds("entities:1", "because", "none", "g1")
    assert "superseded" in str(exc.value)
    with pytest.raises(RowNotFound):
        rows.record_grounds("entities:99", "because", "none", "g2")


def test_record_grounds_refuses_an_address_that_names_no_row(rows):
    """The door raises on an address in an outgoing payload that names nothing, and this
    text is written once — so an unresolvable ref would fail every later read of the row,
    repairable only by superseding a row whose content is fine."""
    from engine.errors import UnresolvedReference

    rows.submit_rows([RowSubmission("entities", {"t": "a"}, name="a")], "k")
    with pytest.raises(UnresolvedReference) as exc:
        rows.record_grounds("entities:1", "see entities:99", "none", "g1")
    assert "entities:99" in str(exc.value)
    # A live address is what an argument is made of, and passes.
    row = rows.record_grounds("entities:1", "it follows from entities:1", "none", "g2")
    assert "entities:1" in row.grounds


def test_supersession_records_why_the_old_row_went(rows):
    from engine.errors import SupersedeNeedsReason

    rows.submit_rows([RowSubmission("entities", {"t": "a"}, name="a")], "k")
    with pytest.raises(SupersedeNeedsReason):
        rows.supersede_row(
            "entities:1", RowSubmission("entities", {"t": "b"}, name="b"), "  ", "s0"
        )
    # Refused before anything is written.
    assert rows.get("entities:1").is_live

    rows.supersede_row(
        "entities:1", RowSubmission("entities", {"t": "b"}, name="b"),
        "stage 5 found sources need the same machinery", "s1",
    )
    old = rows.get("entities:1")
    assert old.supersede_reason == "stage 5 found sources need the same machinery"
    assert rows.get("entities:2").supersede_reason is None


def test_a_missing_row_is_reported_before_a_blank_reason(rows):
    """The guards are ordered so the message names the thing most wrong."""
    with pytest.raises(RowNotFound):
        rows.supersede_row(
            "entities:9", RowSubmission("entities", {"t": "b"}, name="b"), "", "s1"
        )


def test_retirement_records_why(rows):
    from engine.errors import RetireNeedsReason

    rows.submit_rows([RowSubmission("entities", {"t": "a"}, name="a")], "k")
    with pytest.raises(RetireNeedsReason):
        rows.retire_row("entities:1", "   ", "r1")
    assert rows.get("entities:1").is_live


def test_a_rejected_assumption_refuses_a_blank_reason_and_keeps_its_default(rows):
    """Omitting the reason takes the documented default; supplying a blank one is refused,
    because the default says the *owner* rejected it and validation-service closing a
    world-assumption from spike evidence would be recording a falsehood (F14)."""
    from engine.errors import RetireNeedsReason

    rows.submit_rows(
        [RowSubmission("entities", {"t": "a"}, name="a",
                       provenance=Provenance.ASSUMED, assumption_kind="intent")],
        "k",
    )
    with pytest.raises(RetireNeedsReason):
        rows.resolve_assumption("entities:1", "no", "reject", "u1", retire_reason="  ")
    row = rows.resolve_assumption("entities:1", "no", "reject", "u2")
    assert row.retire_reason == "assumption rejected by the owner"
