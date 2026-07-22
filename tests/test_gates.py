"""gate-engine (components:6)."""

import pytest

from engine.gates import BlockedByConflict, UnknownPackage
from engine.models import LinkSpec, Provenance, RowRef, RowSubmission


def submit(rows, *submissions, key="k"):
    return rows.submit_rows(list(submissions), key)


# --- contracts:22: the shape of a gate result --------------------------------------


def test_an_empty_plan_fails_package_one_with_row_level_holes(gate):
    result = gate.run_gate(1)
    assert result.passed is False
    ids = {h.criterion_id for h in result.holes}
    assert {"goals_recorded", "non_goals_recorded", "stack_recorded"} <= ids


def test_every_hole_names_table_problem_and_fix(gate):
    """requirements:20 — each hole names table, row, problem, and fix."""
    for hole in gate.run_gate(1).holes:
        assert hole.table and hole.problem and hole.fix


def test_a_package_outside_the_range_is_refused_with_the_range(gate):
    with pytest.raises(UnknownPackage) as exc:
        gate.run_gate(0)
    assert "1-8" in str(exc.value)
    with pytest.raises(UnknownPackage):
        gate.run_gate(9)


def test_results_are_deterministic(gate, rows):
    """requirements:46 — same plan in, same result out."""
    submit(rows, RowSubmission("goals", {"title": "ship it"}, name="ship it"))
    first, second = gate.run_gate(1), gate.run_gate(1)
    assert [(h.criterion_id, h.ref) for h in first.holes] == [
        (h.criterion_id, h.ref) for h in second.holes
    ]


def test_a_complete_package_passes_and_points_at_the_next(gate, rows):
    submit(
        rows,
        RowSubmission("goals", {"title": "ship it", "success_criteria": "M7 lands"}, name="ship it"),
        RowSubmission("non_goals", {"title": "no GUI"}, name="no GUI"),
        RowSubmission("stack", {"title": "Python 3.12 on Windows"}, name="Python 3.12 on Windows"),
        RowSubmission("use_cases", {"title": "Author a plan"}, links=[LinkSpec(0)], name="Author a plan"),
    )
    result = gate.run_gate(1)
    assert result.passed is True
    assert result.next_package == 2


# --- requirements:17: elicit-package coverage cross-checks ---------------------------


def test_an_actor_in_no_use_case_is_a_cross_check_hole(gate, rows):
    submit(rows, RowSubmission("actors", {"name": "Product owner"}, name="Product owner"))
    holes = [h for h in gate.run_gate(1).holes if h.criterion_id == "actor_participates"]
    assert holes and holes[0].cross_check is True
    assert "Product owner" in holes[0].problem
    assert holes[0].ref == RowRef("actors", 1)


def test_a_goal_reaching_a_use_case_clears_its_cross_check(gate, rows):
    submit(
        rows,
        RowSubmission("goals", {"title": "ship it", "success_criteria": "M7"}, name="ship it"),
        RowSubmission("use_cases", {"title": "Author a plan"}, links=[LinkSpec(0)], name="Author a plan"),
    )
    assert not [
        h for h in gate.run_gate(2).holes
        if h.criterion_id == "goal_traces_to_use_case"
    ]


def test_the_gate_reports_which_cross_checks_ran(gate):
    """A cross-check that silently stopped running is worse than one that fails."""
    assert "actor_participates" in gate.run_gate(1).cross_checks_run
    assert gate.run_gate(6).cross_checks_run == ()


# --- criterion types ----------------------------------------------------------------


def test_required_fields_names_what_is_missing(gate, rows):
    submit(rows, RowSubmission("goals", {"title": "ship it"}, name="ship it"))
    hole = next(
        h for h in gate.run_gate(1).holes
        if h.criterion_id == "goal_has_success_criteria"
    )
    assert "ship it" in hole.problem


def test_ears_slots_are_checked_per_type(gate, rows):
    submit(
        rows,
        RowSubmission("requirements", {"title": "A", "ears_type": "ubiquitous",
                                       "system_response": "logs the event"}, name="A"),
        RowSubmission("requirements", {"title": "B", "ears_type": "event",
                                       "system_response": "logs the event"}, name="B"),
    )
    flagged = {
        h.ref for h in gate.run_gate(3).holes if h.criterion_id == "ears_slots_filled"
    }
    assert flagged == {RowRef("requirements", 2)}  # B has no trigger_text


def test_only_nfrs_need_the_planguage_triad(gate, rows):
    submit(
        rows,
        RowSubmission("requirements", {"title": "A", "ears_type": "ubiquitous",
                                       "system_response": "x"}, name="A"),
        RowSubmission("requirements", {"title": "B", "ears_type": "ubiquitous",
                                       "system_response": "x", "is_nfr": True}, name="B"),
    )
    flagged = {h.ref for h in gate.run_gate(3).holes if h.criterion_id == "nfr_quantified"}
    assert flagged == {RowRef("requirements", 2)}


def test_covers_all_names_the_missing_values(gate, rows):
    submit(
        rows,
        RowSubmission("entities", {"name": "Plan", "lifecycle_reason": "n/a"}, name="Plan"),
        RowSubmission("crud_grid", {"op": "C", "actor": "owner"}, links=[LinkSpec(0)], name="C"),
        RowSubmission("crud_grid", {"op": "R", "actor": "agent"}, links=[LinkSpec(0)], name="R"),
    )
    hole = next(
        h for h in gate.run_gate(4).holes if h.criterion_id == "crud_grid_complete"
    )
    assert hole.problem.endswith("U, D")  # the covered C and R are not reported


def test_matrix_complete_flags_undefined_state_event_cells(gate, rows):
    submit(
        rows,
        # F28 — the cell's link to its machine was `LinkSpec(0)`, i.e. an *untyped*
        # edge. That is exactly v1's NOT NULL `machine_id` degraded into an optional
        # association nothing asserts. It is `belongs_to` now, and the machine declares
        # the entity that owns it.
        RowSubmission("entities", {"name": "Plan"}, name="Plan"),
        RowSubmission("state_machines", {"name": "Plan lifecycle",
                                         "states": ["draft", "frozen"],
                                         "events": ["freeze"]},
                      links=[LinkSpec(0, "belongs_to")], name="Plan lifecycle"),
        RowSubmission("sm_cells", {"state": "draft", "event": "freeze",
                                   "transition_to": "frozen"},
                      links=[LinkSpec(1, "belongs_to")],
                      name="draft becomes frozen on freeze"),
    )
    hole = next(
        h for h in gate.run_gate(4).holes
        if h.criterion_id == "state_machine_grid_complete"
    )
    assert "frozen x freeze" in hole.problem


def test_an_escape_row_satisfies_a_non_empty_criterion(gate, rows):
    """Package 5's vendored escape: 'there are none, and here is why' is an answer."""
    before = {h.criterion_id for h in gate.run_gate(5).holes}
    assert "dependencies_registered" in before
    submit(rows, RowSubmission("no_dependencies_decision",
                               {"text": "purely local; no external dependencies"}, name="purely local; no external dependencies"))
    after = {h.criterion_id for h in gate.run_gate(5).holes}
    assert "dependencies_registered" not in after


def test_an_unbacked_world_assumption_is_a_package_six_hole(gate, rows):
    submit(
        rows,
        RowSubmission("contracts", {"title": "SMB honours O_EXCL"},
                      provenance=Provenance.ASSUMED, assumption_kind="world", name="SMB honours O_EXCL"),
    )
    holes = [
        h for h in gate.run_gate(6).holes if h.criterion_id == "world_assumption_backed"
    ]
    assert holes and holes[0].ref == RowRef("contracts", 1)


def test_a_spike_backs_a_world_assumption(gate, rows):
    submit(
        rows,
        RowSubmission("contracts", {"title": "SMB honours O_EXCL"},
                      provenance=Provenance.ASSUMED, assumption_kind="world", name="SMB honours O_EXCL"),
        RowSubmission("spikes", {"title": "probe SMB locking"}, links=[LinkSpec(0)], name="probe SMB locking"),
    )
    assert not [
        h for h in gate.run_gate(6).holes if h.criterion_id == "world_assumption_backed"
    ]


def test_package_eight_folds_in_every_earlier_gate(gate):
    """An empty plan fails every package, so freeze must report all seven."""
    holes = [
        h for h in gate.run_gate(8).holes if h.criterion_id == "all_prior_gates_green"
    ]
    reported = {h.problem.split()[1] for h in holes}
    assert reported == {f"package-{n}" for n in range(1, 8)}


def test_an_open_conflict_out_of_scope_still_stops_the_freeze(gate, rows, conflicts):
    """Package 8's own criterion is plan-wide: a frozen plan cannot contradict itself
    anywhere, including in tables no gate's scope covers."""
    submit(rows, RowSubmission("scratch", {"title": "an off-package row"}, name="an off-package row"))
    conflicts.raise_conflict([RowRef("scratch", 1)], "contested", "pick one")
    holes = [h for h in gate.run_gate(8).holes if h.criterion_id == "no_open_conflicts"]
    assert holes and "contested" in holes[0].problem


# --- requirements:21 / decisions:31: warn, do not block ------------------------------


def test_a_gate_lists_every_open_gap_in_its_package_as_an_explicit_warning(gate, rows):
    """An actor with no use case is a package-2 gap as well as a package-1 gate hole."""
    submit(rows, RowSubmission("actors", {"name": "Auditor"}, name="Auditor"))
    result = gate.run_gate(2)
    assert any(
        w.kind == "open_gap" and "actor_without_use_case" in w.message
        for w in result.warnings
    )


def test_an_unresolved_assumption_warns_but_does_not_fail_the_gate(gate, rows):
    submit(
        rows,
        RowSubmission("goals", {"title": "ship it", "success_criteria": "M7"}, name="ship it"),
        RowSubmission("non_goals", {"title": "no GUI"}, name="no GUI"),
        RowSubmission("stack", {"title": "Python"}, provenance=Provenance.ASSUMED,
                      assumption_kind="intent", name="Python"),
        RowSubmission("use_cases", {"title": "Author"}, links=[LinkSpec(0)], name="Author"),
    )
    result = gate.run_gate(1)
    assert result.passed is True  # decisions:31 — gates warn, they do not block
    assert result.clean is False
    assert any(w.kind == "unresolved_assumption" for w in result.warnings)


def test_warnings_do_not_accumulate_across_repeated_gates(gate, rows, warns):
    submit(rows, RowSubmission("actors", {"name": "Auditor"}, name="Auditor"))
    gate.run_gate(2)
    first = len(warns.all_warnings())
    gate.run_gate(2)
    gate.run_gate(2)
    assert len(warns.all_warnings()) == first


def test_a_gate_does_not_warn_about_other_packages_gaps(gate, rows):
    """DEFECTS.md F10 — the first build warned "no components yet" at the package-1 gate
    of a plan three packages from needing components. Ten of twelve warnings were noise."""
    result = gate.run_gate(1)
    assert not [w for w in result.warnings if "no_components" in w.message]
    assert not [w for w in result.warnings if "no_entities" in w.message]


def test_a_warning_clears_when_its_condition_clears(gate, rows, warns):
    """A warning that outlives its cause trains the reader to ignore warnings."""
    gate.run_gate(1)
    stale = next(w for w in warns.active_warnings() if "package1_not_started" in w.message)
    submit(rows, RowSubmission("goals", {"title": "ship it", "success_criteria": "M7"}, name="ship it"))
    gate.run_gate(1)
    assert warns.get(stale.id).state == "resolved"
    assert warns.get(stale.id).resolved_by is None  # no row is falsely credited


def test_an_assumption_warns_exactly_once(gate, rows, warns):
    """Raised as both a gap and an assumption, it was suppressible only half at a time
    — the twin carried on nagging after the owner had answered."""
    submit(
        rows,
        RowSubmission("stack", {"title": "Deploy on the NAS"},
                      provenance=Provenance.ASSUMED, assumption_kind="intent", name="Deploy on the NAS"),
    )
    result = gate.run_gate(1)
    about_it = [w for w in result.warnings if "Deploy on the NAS" in w.message]
    assert len(about_it) == 1
    warns.suppress_warning(about_it[0].id, "my call; risk accepted")
    assert not [
        w for w in gate.run_gate(1).warnings if "Deploy on the NAS" in w.message
    ]


def test_a_suppressed_warning_stays_suppressed_through_a_gate(gate, rows, warns):
    submit(rows, RowSubmission("actors", {"name": "Auditor"}, name="Auditor"))
    gate.run_gate(2)
    target = warns.active_warnings()[0]
    warns.suppress_warning(target.id, "accepted until package 3")
    result = gate.run_gate(2)
    assert target.warning_key not in {w.warning_key for w in result.warnings}


# --- requirements:28: an open conflict blocks -----------------------------------------


def test_an_open_conflict_blocks_a_gate_that_depends_on_the_contested_rows(
    gate, rows, conflicts
):
    submit(rows, RowSubmission("goals", {"title": "ship it"}, name="ship it"))
    conflicts.raise_conflict(
        [RowRef("goals", 1)], "the goal contradicts the non-goal", "drop the non-goal"
    )
    with pytest.raises(BlockedByConflict) as exc:
        gate.run_gate(1)
    assert "goals:1" in str(exc.value)


def test_a_conflict_outside_the_gates_scope_does_not_block_it(gate, rows, conflicts):
    submit(rows, RowSubmission("contracts", {"title": "read_widget"}, name="read_widget"))
    conflicts.raise_conflict(
        [RowRef("contracts", 1)], "two contracts overlap", "keep the first"
    )
    gate.run_gate(1)  # package 1 does not depend on contracts


def test_resolving_the_conflict_unblocks_the_gate(gate, rows, conflicts):
    submit(rows, RowSubmission("goals", {"title": "ship it"}, name="ship it"))
    conflict = conflicts.raise_conflict(
        [RowRef("goals", 1)], "contested", "keep it"
    )
    conflicts.resolve_conflict(conflict.id, "overridden", "owner keeps the goal")
    assert gate.run_gate(1).passed is False  # blocked no more; merely incomplete


# --- D22 / F38: the package-7 gate reads the finding service, not plan_rows -------------


def _attacked(rows):
    submit(rows, RowSubmission("requirements", {"text": "the widget settles"},
                               name="the widget settles"))
    return RowRef("requirements", 1)


def test_the_gate_sees_a_finding_filed_the_way_the_script_says_to_file_it(
    gate, rows, findings
):
    """The whole of F38 in one test. The red-team script says to file with `file_finding`,
    which writes the finding service; the criteria used to read `plan_rows`, where findings
    have never been written, so the gate reported "no adversarial findings recorded" no
    matter how many were filed and could not be passed by the prescribed route."""
    result = gate.run_gate(7)
    assert any("no adversarial findings" in hole.problem for hole in result.holes)

    findings.file_finding([_attacked(rows)], "the gate is too weak", "high",
                          name="gate 4 passes with no tests")
    result = gate.run_gate(7)
    assert not any("no adversarial findings" in hole.problem for hole in result.holes)


def test_an_unresolved_finding_is_a_hole_that_names_it(gate, rows, findings):
    findings.file_finding([_attacked(rows)], "the gate is too weak", "high",
                          name="gate 4 passes with no tests")
    holes = [h for h in gate.run_gate(7).holes if h.criterion_id == "findings_dispositioned"]
    assert len(holes) == 1
    # D19: the hole names the finding before it addresses it.
    assert "gate 4 passes with no tests (findings:1)" in holes[0].problem
    assert "an outcome and a rationale" in holes[0].problem


def test_a_resolved_finding_leaves_no_hole(gate, rows, findings):
    finding = findings.file_finding([_attacked(rows)], "the gate is too weak", "high",
                                    name="gate 4 passes with no tests")
    findings.resolve_finding(finding.id, "addressed", "criteria tightened in package 4")
    assert not [
        h for h in gate.run_gate(7).holes if h.criterion_id == "findings_dispositioned"
    ]


def test_an_accepted_risk_still_needs_its_rationale(gate, rows, findings):
    """requirements:33 — the case the second half of the criterion exists for. A finding
    closed with no recorded acceptance is indistinguishable at handoff from one somebody
    forgot about."""
    finding = findings.file_finding([_attacked(rows)], "the gate is too weak", "high",
                                    name="gate 4 passes with no tests")
    findings.resolve_finding(finding.id, "accepted_risk", "the owner will live with it")
    assert not [
        h for h in gate.run_gate(7).holes if h.criterion_id == "findings_dispositioned"
    ]
