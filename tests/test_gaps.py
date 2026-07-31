"""gap-engine (components:5)."""

import pytest

from engine.gaps import AlreadyResolved, GapEngine, GapNotFound, NotDismissed
from engine.models import LinkSpec, Provenance, RowRef, RowSubmission, SpikeSpec

from .conftest import PAPER


@pytest.fixture
def gaps(store, rows, refs):
    return GapEngine(store, rows, refs)


def test_empty_plan_reports_stage_one_not_started(gaps):
    cluster = gaps.next_gaps()
    assert cluster.stage == 1
    assert any(g.rule_key == "stage1_not_started" for g in cluster.gaps)


def test_gate_is_recommended_when_a_stage_is_clean(gaps, rows):
    """requirements:12 — while the stage has no open gaps, recommend the gate."""
    # `goals`, not `decisions`: stage 1 fills goals/non_goals/stack in v2 (DEFECTS.md
    # F11 — the vendored rule still tested v1's decisions-with-a-"Goal:"-prefix shape).
    rows.submit_rows(
        [RowSubmission("goals", {"title": "ship it", "success_criteria": "M7 lands"}, name="ship it")],
        "k",
    )
    cluster = gaps.next_gaps(stage=1)
    assert cluster.recommend_gate is True
    assert "run the stage gate" in cluster.guidance.lower()


def test_untraced_use_case_is_a_gap(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "Place an order"}, name="Place an order")], "k")
    cluster = gaps.next_gaps(stage=3)
    untraced = [g for g in cluster.gaps if g.rule_key == "use_case_untraced"]
    assert untraced
    assert "Place an order" in untraced[0].ask
    assert untraced[0].target == RowRef("use_cases", 1)


def test_traced_use_case_is_not_a_gap(gaps, rows):
    rows.submit_rows(
        [
            RowSubmission("use_cases", {"title": "Place an order"}, name="Place an order"),
            RowSubmission("requirements", {"title": "Orders persist"},
                          links=[LinkSpec(0)], name="Orders persist"),
        ],
        "k",
    )
    cluster = gaps.next_gaps(stage=3)
    assert not [g for g in cluster.gaps if g.rule_key == "use_case_untraced"]


def test_unless_field_exempts_a_row(gaps, rows):
    """A step that explains why it has no extensions is not a gap."""
    rows.submit_rows(
        [
            # F28 — a step declares the use case that owns it. This fixture used to
            # write orphans, which v1's NOT NULL `use_case_id` would have refused.
            RowSubmission("use_cases", {"title": "A scenario"}, name="A scenario"),
            RowSubmission("uc_steps", {"title": "Step one"},
                          links=[LinkSpec(0, "belongs_to")], name="Step one"),
            RowSubmission("uc_steps", {"title": "Step two",
                                       "no_extension_reason": "cannot fail"},
                          links=[LinkSpec(0, "belongs_to")], name="Step two"),
        ],
        "k",
    )
    cluster = gaps.next_gaps(stage=2)
    flagged = [g.target for g in cluster.gaps if g.rule_key == "step_without_extensions"]
    assert RowRef("uc_steps", 1) in flagged
    assert RowRef("uc_steps", 2) not in flagged


def test_when_field_scopes_a_rule(gaps, rows):
    """Only NFRs need the Planguage triad."""
    rows.submit_rows(
        [
            RowSubmission("requirements", {"title": "functional one"}, name="functional one"),
            RowSubmission("requirements", {"title": "an NFR", "is_nfr": True}, name="an NFR"),
        ],
        "k",
    )
    cluster = gaps.next_gaps(stage=3)
    flagged = [g.target for g in cluster.gaps if g.rule_key == "nfr_unquantified"]
    assert flagged == [RowRef("requirements", 2)]


def test_world_and_intent_assumptions_are_separated(gaps, rows):
    """World assumptions are spiked; intent assumptions go to the owner. Never
    swapped."""
    rows.submit_rows(
        [
            RowSubmission("decisions", {"title": "SMB handles O_EXCL"},
                          provenance=Provenance.ASSUMED, assumption_kind="world",
                          name="SMB handles O_EXCL",
                          spike=SpikeSpec("Does SMB handle O_EXCL?", "it does",
                                          "race two writers", "1 day")),
            RowSubmission("decisions", {"title": "owner wants dark mode"},
                          provenance=Provenance.ASSUMED, assumption_kind="intent", name="owner wants dark mode"),
        ],
        "k",
    )
    cluster = gaps.next_gaps(stage=1, limit=20)
    world = [g for g in cluster.gaps if g.rule_key == "world_assumption_open"]
    intent = [g for g in cluster.gaps if g.rule_key == "intent_assumption_open"]

    assert "spike" in world[0].ask.lower()
    assert world[0].priority == 3
    assert "owner" in intent[0].ask.lower()
    assert intent[0].priority == 4


def test_uncited_section_becomes_a_gap(gaps, refs):
    """The coverage meter wired into the interview."""
    source = refs.add_source("Widget Settling", PAPER, "k1")
    refs.add_extract(
        source, "The measured settling time was 40 ms under nominal load.", "k2"
    )
    cluster = gaps.next_gaps(stage=1, limit=20)
    uncited = [g for g in cluster.gaps if g.rule_key == "source_section_uncited"]
    headings = {g.ask.split(" section")[0].split("its ")[-1] for g in uncited}
    assert "Limitations" in headings
    assert "Results" not in headings
    # Abstract restates findings that appear in full elsewhere; flagging it is noise.
    assert "Abstract" not in headings


def test_reference_sections_are_not_gaps(gaps, refs):
    """Nobody needs to cite a bibliography."""
    paper = PAPER + "\nReferences\n[1] Someone, 2020.\n"
    source = refs.add_source("With refs", paper, "k1")
    cluster = gaps.next_gaps(stage=1, limit=50)
    headings = [
        g.ask for g in cluster.gaps if g.rule_key == "source_section_uncited"
    ]
    assert not any("References" in h for h in headings)


def test_cluster_is_coherent_and_bounded(gaps, rows):
    rows.submit_rows(
        [RowSubmission("use_cases", {"title": f"UC {i}"}, name=f"UC {i}") for i in range(10)], "k"
    )
    cluster = gaps.next_gaps(stage=3, limit=5)
    assert len(cluster.gaps) == 5
    assert cluster.total_open >= 10
    assert cluster.grouped_by == "use_cases"


def test_elicit_guidance_puts_divergence_before_drafts(gaps, rows):
    """decisions:36 — v1's guidance was proposal-first only, which under-pushed the
    owner. On elicit stages divergence now comes first."""
    rows.submit_rows(
        [
            RowSubmission("use_cases", {"title": "UC"}, name="UC"),
            # F28 — the step declares its owning use case. Without it the step is
            # refused and this fixture silently tested an empty plan.
            RowSubmission("uc_steps", {"title": "Step one"},
                          links=[LinkSpec(0, "belongs_to")], name="Step one"),
        ],
        "k",
    )
    cluster = gaps.next_gaps(stage=2)
    assert cluster.gaps, "expected a stage-2 gap so guidance is interview guidance"
    guidance = cluster.guidance.lower()
    assert "divergence round before" in guidance
    assert guidance.index("divergence") < guidance.index("propos")


def test_synthesize_guidance_makes_the_agent_the_source(gaps, rows):
    rows.submit_rows([RowSubmission("entities", {"title": "Order"}, name="Order")], "k")
    guidance = gaps.next_gaps(stage=4).guidance.lower()
    assert "you are the source" in guidance


def test_dismissal_stops_the_gap_surfacing(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(stage=3).gaps if g.rule_key == "use_case_untraced"
    )
    gaps.dismiss_gap(target.key, "out of scope for v1")
    assert not [
        g for g in gaps.next_gaps(stage=3).gaps if g.key == target.key
    ]


def test_dismissal_is_reversible(gaps, rows):
    """requirements:15 — the dismissal is recorded and reversible."""
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(stage=3).gaps if g.rule_key == "use_case_untraced"
    )
    gaps.dismiss_gap(target.key, "later")
    gaps.reopen_gap(target.key, "changed my mind")
    assert [g for g in gaps.next_gaps(stage=3).gaps if g.key == target.key]


def test_dismissal_survives_supersession_of_its_row(gaps, rows):
    """requirements:78 / findings:16 — the overlay is keyed by the lineage root, so a
    dismissal neither re-surfaces nor silently detaches when the row is superseded."""
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC v1"}, name="UC v1")], "k1")
    target = next(
        g for g in gaps.next_gaps(stage=3).gaps if g.rule_key == "use_case_untraced"
    )
    gaps.dismiss_gap(target.key, "deliberately untraced for now")

    rows.supersede_row(
        "use_cases:1", RowSubmission("use_cases", {"title": "UC v2"}, name="UC v2"),
        "the flow changed at stage 2", "k2"
    )
    still_dismissed = [
        g for g in gaps.next_gaps(stage=3).gaps if g.rule_key == "use_case_untraced"
    ]
    assert not still_dismissed


def test_lineage_root_walks_the_whole_chain(gaps, rows):
    rows.submit_rows([RowSubmission("decisions", {"title": "a"}, name="a")], "k1")
    rows.supersede_row("decisions:1", RowSubmission("decisions", {"title": "b"}, name="b"),
                       "sharpened", "k2")
    rows.supersede_row("decisions:2", RowSubmission("decisions", {"title": "c"}, name="c"),
                       "sharpened again", "k3")
    assert gaps.lineage_root("decisions:3") == RowRef("decisions", 1)


def test_reopen_requires_a_dismissal(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(stage=3).gaps if g.rule_key == "use_case_untraced"
    )
    with pytest.raises(GapNotFound):
        gaps.reopen_gap(target.key, "never dismissed")


def test_reopening_an_open_gap_is_refused(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(stage=3).gaps if g.rule_key == "use_case_untraced"
    )
    gaps.dismiss_gap(target.key, "later")
    gaps.reopen_gap(target.key, "back")
    with pytest.raises(NotDismissed):
        gaps.reopen_gap(target.key, "again")


def test_dismissal_requires_a_reason(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(stage=3).gaps if g.rule_key == "use_case_untraced"
    )
    with pytest.raises(GapNotFound):
        gaps.dismiss_gap(target.key, "   ")


def test_unreadable_rows_route_to_recovery(gaps, rows, store):
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    store.conn.execute("UPDATE plan_rows SET content = 'broken' WHERE ordinal = 1")
    store.conn.commit()
    from engine.gaps import PlanUnreadable

    with pytest.raises(PlanUnreadable):
        gaps.next_gaps()


# --- the decision context (v3 D11) ---


def test_a_row_with_no_grounds_is_one_gap_at_the_stage_that_owns_its_table(gaps, rows):
    """One gap, not two, and at the stage the manifest assigns `entities` — a gap
    allocated to a stage that does not own its table fires where the planner cannot act
    on it."""
    rows.submit_rows(
        [RowSubmission("entities", {"title": "Order"}, name="Order")], "k"
    )
    unreasoned = [
        g for g in gaps.next_gaps(stage=4).gaps
        if g.rule_key == "entity_without_grounds"
    ]
    assert len(unreasoned) == 1
    assert unreasoned[0].target == RowRef("entities", 1)
    assert unreasoned[0].stage == 4
    assert unreasoned[0].priority == 2
    # The ask names the row, what is missing, and the call that fixes it — in the order
    # the rule declares the fields, not sorted, which would say "alternatives and grounds".
    assert '"Order" records no grounds and alternatives' in unreasoned[0].ask
    assert "record_grounds()" in unreasoned[0].ask


def test_whitespace_grounds_are_the_same_gap_as_none(gaps, rows):
    """The rule reads the column raw. Nothing but row-service writes `plan_rows`, so
    stripping once at the write is the single point where a whitespace value is caught;
    a second strip here would be the same decision made twice, and the two would drift."""
    rows.submit_rows(
        [RowSubmission("entities", {"title": "Order"}, name="Order",
                       grounds="   ", alternatives="\n\t ")],
        "k",
    )
    unreasoned = [
        g for g in gaps.next_gaps(stage=4).gaps
        if g.rule_key == "entity_without_grounds"
    ]
    assert len(unreasoned) == 1
    assert "records no grounds and alternatives" in unreasoned[0].ask


def test_a_row_filed_with_its_argument_is_not_a_gap(gaps, rows):
    rows.submit_rows(
        [RowSubmission("entities", {"title": "Order"}, name="Order",
                       grounds="the order is the aggregate every line hangs off",
                       alternatives="a line-item aggregate — rejected, it orphans totals")],
        "k",
    )
    assert not [
        g for g in gaps.next_gaps(stage=4).gaps
        if g.rule_key == "entity_without_grounds"
    ]


def test_record_grounds_closes_the_gap_one_field_at_a_time(gaps, rows):
    """The end-to-end path §3.5 is about: a gap exists, a call closes it, the call is
    write-once *per field*. The last half is what a builder would skip, and it is the half
    that would have caught the per-row dead end."""
    rows.submit_rows(
        [RowSubmission("entities", {"title": "Order"}, name="Order",
                       grounds="the order is the aggregate every line hangs off")],
        "k",
    )
    open_gap = [
        g for g in gaps.next_gaps(stage=4).gaps
        if g.rule_key == "entity_without_grounds"
    ]
    assert len(open_gap) == 1
    assert "records no alternatives" in open_gap[0].ask

    # Rewriting the field that is already set is refused; the one that is missing lands.
    from engine.errors import GroundsAlreadyRecorded

    with pytest.raises(GroundsAlreadyRecorded):
        rows.record_grounds("entities:1", "a better argument", "none", "g0")
    row = rows.record_grounds(
        "entities:1", "", "a line-item aggregate — rejected, it orphans totals", "g1"
    )
    assert row.grounds == "the order is the aggregate every line hangs off"
    assert row.alternatives.startswith("a line-item aggregate")
    assert not [
        g for g in gaps.next_gaps(stage=4).gaps
        if g.rule_key == "entity_without_grounds"
    ]


def test_a_rule_naming_a_column_plan_rows_does_not_have_is_refused_at_load(store, rows):
    """`getattr(row, f, None)` would turn a misspelt column into a gap on every live row —
    a rule silently measuring something other than its name. Checked once per engine."""
    from dataclasses import replace as replace_field

    from engine.gaps import PlanUnreadable
    from engine.methodology import Rule, load

    loaded = load()
    broken = replace_field(
        loaded,
        rules=(*loaded.rules, Rule(
            id="entity_without_grounds_typo", priority=2, stage=4, type="unreasoned",
            ask="{name} records no {missing}.",
            spec={"table": "entities", "fields": ["grouds", "alternatives"]},
        )),
    )
    with pytest.raises(PlanUnreadable) as exc:
        GapEngine(store, rows, methodology=broken)
    assert "grouds" in str(exc.value)
    assert "entity_without_grounds_typo" in str(exc.value)

    empty = replace_field(
        loaded,
        rules=(*loaded.rules, Rule(
            id="entity_without_grounds_empty", priority=2, stage=4, type="unreasoned",
            ask="{name} records no {missing}.", spec={"table": "entities", "fields": []},
        )),
    )
    with pytest.raises(PlanUnreadable):
        GapEngine(store, rows, methodology=empty)
