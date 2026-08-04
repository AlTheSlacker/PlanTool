"""gap-engine (components:5)."""

import pytest

from engine.gaps import AlreadyResolved, GapEngine, GapNotFound, NotDismissed
from engine.models import LinkSpec, Provenance, RowRef, RowSubmission, SpikeSpec

from .conftest import PAPER


@pytest.fixture
def gaps(store, rows, refs):
    return GapEngine(store, rows, refs)


def test_empty_plan_reports_package_one_not_started(gaps):
    cluster = gaps.next_gaps()
    assert cluster.package == 1
    assert any(g.rule_key == "package1_not_started" for g in cluster.gaps)


def test_gate_is_recommended_when_a_package_is_clean(gaps, rows):
    """requirements:12 — while the package has no open gaps, recommend the gate."""
    # `goals`, not `decisions`: package 1 fills goals/non_goals/stack in v2 (DEFECTS.md
    # F11 — the vendored rule still tested v1's decisions-with-a-"Goal:"-prefix shape).
    rows.submit_rows(
        [RowSubmission("goals", {"title": "ship it", "success_criteria": "M7 lands"}, name="ship it")],
        "k",
    )
    cluster = gaps.next_gaps(package=1)
    assert cluster.recommend_gate is True
    assert "run the package gate" in cluster.guidance.lower()


def test_untraced_use_case_is_a_gap(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "Place an order"}, name="Place an order")], "k")
    cluster = gaps.next_gaps(package=3)
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
    cluster = gaps.next_gaps(package=3)
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
    cluster = gaps.next_gaps(package=2)
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
    cluster = gaps.next_gaps(package=3)
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
    cluster = gaps.next_gaps(package=1, limit=20)
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
    cluster = gaps.next_gaps(package=1, limit=20)
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
    cluster = gaps.next_gaps(package=1, limit=50)
    headings = [
        g.ask for g in cluster.gaps if g.rule_key == "source_section_uncited"
    ]
    assert not any("References" in h for h in headings)


def test_cluster_is_coherent_and_bounded(gaps, rows):
    rows.submit_rows(
        [RowSubmission("use_cases", {"title": f"UC {i}"}, name=f"UC {i}") for i in range(10)], "k"
    )
    cluster = gaps.next_gaps(package=3, limit=5)
    assert len(cluster.gaps) == 5
    assert cluster.total_open >= 10
    assert cluster.grouped_by == "use_cases"


def test_elicit_guidance_puts_divergence_before_drafts(gaps, rows):
    """decisions:36 — v1's guidance was proposal-first only, which under-pushed the
    owner. On elicit packages divergence now comes first."""
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
    cluster = gaps.next_gaps(package=2)
    assert cluster.gaps, "expected a package-2 gap so guidance is interview guidance"
    guidance = cluster.guidance.lower()
    assert "divergence round before" in guidance
    assert guidance.index("divergence") < guidance.index("propos")


def test_synthesize_guidance_makes_the_agent_the_source(gaps, rows):
    rows.submit_rows([RowSubmission("entities", {"title": "Order"}, name="Order")], "k")
    guidance = gaps.next_gaps(package=4).guidance.lower()
    assert "you are the source" in guidance


def test_dismissal_stops_the_gap_surfacing(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(package=3).gaps if g.rule_key == "use_case_untraced"
    )
    gaps.dismiss_gap(target.key, "out of scope for v1")
    assert not [
        g for g in gaps.next_gaps(package=3).gaps if g.key == target.key
    ]


def test_dismissal_is_reversible(gaps, rows):
    """requirements:15 — the dismissal is recorded and reversible."""
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(package=3).gaps if g.rule_key == "use_case_untraced"
    )
    gaps.dismiss_gap(target.key, "later")
    gaps.reopen_gap(target.key, "changed my mind")
    assert [g for g in gaps.next_gaps(package=3).gaps if g.key == target.key]


def test_dismissal_survives_supersession_of_its_row(gaps, rows):
    """requirements:78 / findings:16 — the overlay is keyed by the lineage root, so a
    dismissal neither re-surfaces nor silently detaches when the row is superseded."""
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC v1"}, name="UC v1")], "k1")
    target = next(
        g for g in gaps.next_gaps(package=3).gaps if g.rule_key == "use_case_untraced"
    )
    gaps.dismiss_gap(target.key, "deliberately untraced for now")

    rows.supersede_row(
        "use_cases:1", RowSubmission("use_cases", {"title": "UC v2"}, name="UC v2"), "k2"
    )
    still_dismissed = [
        g for g in gaps.next_gaps(package=3).gaps if g.rule_key == "use_case_untraced"
    ]
    assert not still_dismissed


def test_lineage_root_walks_the_whole_chain(gaps, rows):
    rows.submit_rows([RowSubmission("decisions", {"title": "a"}, name="a")], "k1")
    rows.supersede_row("decisions:1", RowSubmission("decisions", {"title": "b"}, name="b"), "k2")
    rows.supersede_row("decisions:2", RowSubmission("decisions", {"title": "c"}, name="c"), "k3")
    assert gaps.lineage_root("decisions:3") == RowRef("decisions", 1)


def test_reopen_requires_a_dismissal(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(package=3).gaps if g.rule_key == "use_case_untraced"
    )
    with pytest.raises(GapNotFound):
        gaps.reopen_gap(target.key, "never dismissed")


def test_reopening_an_open_gap_is_refused(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(package=3).gaps if g.rule_key == "use_case_untraced"
    )
    gaps.dismiss_gap(target.key, "later")
    gaps.reopen_gap(target.key, "back")
    with pytest.raises(NotDismissed):
        gaps.reopen_gap(target.key, "again")


def test_dismissal_requires_a_reason(gaps, rows):
    rows.submit_rows([RowSubmission("use_cases", {"title": "UC"}, name="UC")], "k")
    target = next(
        g for g in gaps.next_gaps(package=3).gaps if g.rule_key == "use_case_untraced"
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
