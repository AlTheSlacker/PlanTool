"""task-graph (components:11) — contracts:35/38/55/60/62, plus the two contracts
DEFECTS.md F18 found missing."""

import pytest

from engine.models import LinkSpec, RowRef, RowSubmission
from engine.tasks import (
    BLOCKED,
    DONE,
    IN_PROGRESS,
    PENDING,
    READY,
    REWORK_FLAGGED,
    CycleDetected,
    EvidenceIncomplete,
    InvalidTransition,
    MalformedReport,
    NotInProgress,
    PlanNotFinalized,
    TaskNotFound,
    UnresolvedFindings,
    VerificationMissing,
)


def _contracts(rows, n, deps=None):
    """n contract rows; `deps` is a list of (consumer_index, provider_index) pairs
    recorded as D11's typed `depends_on` links."""
    deps = deps or []
    subs = []
    for i in range(n):
        links = [
            LinkSpec(target=provider, edge_type="depends_on")
            for consumer, provider in deps
            if consumer == i
        ]
        subs.append(
            RowSubmission(
                table="contracts",
                # The behaviour surface a planning session declares on a contract
                # (DEVIATIONS.md D12). Without it the task has no accounting
                # denominator and verify_completion refuses — which is F23's fix
                # working, not a test-fixture detail.
                content={
                    "title": f"contract {i}",
                    "behaviours": [
                        {"key": "effect", "kind": "effect",
                         "statement": f"contract {i} does what it says"},
                        {"key": "NotFound", "kind": "error",
                         "statement": f"contract {i} names a missing id"},
                    ],
                },
                name=f"contract {i}",
                links=links,
            )
        )
    receipt = rows.submit_rows(subs, f"contracts:{n}:{deps}")
    return [v.ref for v in receipt.verdicts]


def _finalize(tasks, rows, n=3, deps=None):
    _contracts(rows, n, deps)
    return tasks.finalize_plan()


# --- contracts:35 finalize_plan ---


def test_finalize_derives_one_task_per_contract(tasks, rows):
    """decisions:63 — one Task is the implementation unit of exactly one contract."""
    graph = _finalize(tasks, rows, n=3)
    assert len(graph.tasks) == 3
    assert {str(s.contract_ref) for s in graph.tasks} == {
        "contracts:1", "contracts:2", "contracts:3"
    }


def test_finalize_moves_the_plan_out_of_draft(tasks, rows, store):
    """M5_PLAN.md 1.2 — this is the sole contract firing state_machines:1's `finalize`.
    Before it existed nothing wrote `finalized` and the revision loop was unreachable."""
    assert store.plan_handle()["state"] == "draft"
    _finalize(tasks, rows)
    assert store.plan_handle()["state"] == "finalized"


def test_finalize_orders_dependencies_first(tasks, rows):
    """requirements:34 — no task precedes its dependencies."""
    graph = _finalize(tasks, rows, n=3, deps=[(0, 1), (1, 2)])
    ids = {str(s.contract_ref): s.id for s in graph.tasks}
    order = list(graph.order)
    assert order.index(ids["contracts:3"]) < order.index(ids["contracts:2"])
    assert order.index(ids["contracts:2"]) < order.index(ids["contracts:1"])


def test_finalize_detects_cycles(tasks, rows):
    """requirements:35 — surfaced as a design conflict before implementation starts."""
    with pytest.raises(CycleDetected) as exc:
        _finalize(tasks, rows, n=2, deps=[(0, 1), (1, 0)])
    assert "contracts:1" in str(exc.value)


def test_finalize_blocks_on_unresolved_findings(tasks, rows, findings):
    """requirements:32 — wired to findings.open_findings(), not reinvented."""
    ref = _contracts(rows, 1)[0]
    findings.file_finding([ref], "the gate is too weak", "high", name="the gate is too weak", resolve_by=8)
    with pytest.raises(UnresolvedFindings) as exc:
        tasks.finalize_plan()
    assert "findings:1" in str(exc.value)


def test_finalize_captures_the_drift_baseline(tasks, rows, store):
    """requirements:73 — without this nothing ever wrote a baseline, so plan_status's
    drift flags could only ever report 'no baseline' (M5_PLAN.md 1.2)."""
    _finalize(tasks, rows)
    captured = store.query("SELECT * FROM workspace_fingerprints")
    assert len(captured) == 1
    assert captured[0]["occasion"] == "finalization"


def test_untyped_links_are_not_build_dependencies(tasks, rows):
    """D11 — a contract cites its requirements with the same edge it would cite a
    sibling. Walking those as dependencies would make every citation a dependency."""
    req = rows.submit_rows(
        [RowSubmission(table="requirements", content={"text": "a requirement"},
                       name="a requirement")], "r"
    ).verdicts[0].ref
    rows.submit_rows(
        [RowSubmission(table="contracts", content={"title": "c"}, name="c",
                       links=[LinkSpec(target=req)])],
        "c",
    )
    graph = tasks.finalize_plan()
    assert graph.edge_count == 0
    assert graph.tasks[0].deps == ()


# --- readiness: D10, and the F18 `deps_satisfied` hole ---


def test_readiness_is_derived_not_stored(tasks, rows, store):
    """D10 — `ready` is never written to tasks.state."""
    _finalize(tasks, rows, n=1)
    assert store.query("SELECT state FROM tasks")[0]["state"] == PENDING
    assert tasks.readiness_of(tasks.get(1)) == READY


def test_a_task_with_unfinished_deps_is_not_ready(tasks, rows):
    _finalize(tasks, rows, n=2, deps=[(0, 1)])
    consumer = next(s for s in tasks._all() if str(s.contract_ref) == "contracts:1")
    assert tasks.readiness_of(consumer) == PENDING
    assert tasks.blocking_deps(consumer)


def test_rework_flagged_becomes_ready_again(tasks, rows):
    """DEFECTS.md F19(a) — the trap. Under an edge-triggered reading a rework_flagged
    task's `deps_satisfied` edge has already fired for the last time (its
    dependencies are all long since done), so it could never re-enter readiness and the
    only escape would be declaring a block that does not exist."""
    _finalize(tasks, rows, n=2, deps=[(0, 1)])
    provider = next(s for s in tasks._all() if str(s.contract_ref) == "contracts:2")
    consumer = next(s for s in tasks._all() if str(s.contract_ref) == "contracts:1")

    _drive_to_done(tasks, provider.id)
    _drive_to_done(tasks, consumer.id)

    tasks.report_status(consumer.id, "flag_rework", "the revision changed the contract")
    reworked = tasks.get(consumer.id)
    assert reworked.state == REWORK_FLAGGED
    assert tasks.readiness_of(reworked) == READY


def _evidence(tasks, task_id, artifact="pytest -q passed"):
    """One evidence item per *behaviour* (D12), not per contract."""
    return {b.ref: artifact for b in tasks.behaviours.for_task(task_id)}


def _drive_to_done(tasks, task_id):
    tasks.serve_brief(task_id)
    tasks.verify_completion(task_id, _evidence(tasks, task_id))
    return tasks.report_status(task_id, "complete", "built and tested")


# --- the F18 `serve_brief` hole ---


def test_next_task_does_not_start_the_work(tasks, rows):
    """Candidacy is not delivery. A task may be offered and never briefed; marking
    it in_progress here would fill the graph with work nobody is doing."""
    _finalize(tasks, rows, n=1)
    tasks.next_task()
    assert tasks.get(1).state == PENDING


def test_serve_brief_starts_the_work_and_counts_the_episode(tasks, rows):
    _finalize(tasks, rows, n=1)
    served = tasks.serve_brief(1)
    assert served.state == IN_PROGRESS
    assert served.serve_epoch == 1


def test_serve_brief_captures_a_fingerprint(tasks, rows, store):
    """requirements:73 — a baseline at finalization *and each brief issue*."""
    _finalize(tasks, rows, n=1)
    tasks.serve_brief(1)
    occasions = [r["occasion"] for r in store.query(
        "SELECT occasion FROM workspace_fingerprints ORDER BY id")]
    assert occasions == ["finalization", "brief_issue"]


def test_the_engine_cannot_assert_its_own_readiness(tasks, rows):
    """DEFECTS.md F18 — crud_grid:35 splits system-owned readiness from engine-owned
    status reports. A gate the graded party can open is not a gate."""
    _finalize(tasks, rows, n=1)
    for usurped in ("deps_satisfied", "serve_brief"):
        with pytest.raises(MalformedReport) as exc:
            tasks.report_status(1, usurped, "ready now")
        assert "crud_grid:35" in str(exc.value)


# --- contracts:60 report_status ---


def test_done_requires_a_passing_verdict(tasks, rows):
    """findings:9's fix — 'done' must not mean 'the engine said so'."""
    _finalize(tasks, rows, n=1)
    tasks.serve_brief(1)
    with pytest.raises(VerificationMissing):
        tasks.report_status(1, "complete", "all finished, trust me")
    assert tasks.get(1).state == IN_PROGRESS


def test_complete_after_verification_succeeds(tasks, rows):
    _finalize(tasks, rows, n=1)
    assert _drive_to_done(tasks, 1).state == DONE


def test_illegal_transitions_are_refused_with_the_plans_own_reason(tasks, rows):
    _finalize(tasks, rows, n=1)
    with pytest.raises(InvalidTransition) as exc:
        tasks.report_status(1, "flag_rework", "nope")
    assert "nothing built" in str(exc.value)
    assert tasks.get(1).state == PENDING


def test_block_report_must_say_what_is_blocking(tasks, rows):
    """dep_failure_modes:8 — rejected naming the specific problem, state unchanged."""
    _finalize(tasks, rows, n=1)
    with pytest.raises(MalformedReport):
        tasks.report_status(1, "block", "   ")
    assert tasks.get(1).state == PENDING


def test_block_then_unblock_returns_to_readiness(tasks, rows):
    _finalize(tasks, rows, n=1)
    tasks.report_status(1, "block", "the vendor API is down")
    assert tasks.get(1).state == BLOCKED
    tasks.report_status(1, "unblock", "vendor restored service")
    assert tasks.readiness_of(tasks.get(1)) == READY


def test_report_status_names_the_missing_task(tasks, rows):
    _finalize(tasks, rows, n=1)
    with pytest.raises(TaskNotFound):
        tasks.report_status(99, "complete", "x")


# --- contracts:62 verify_completion ---


def test_verification_refuses_unmapped_contracts(tasks, rows):
    """EvidenceIncomplete — naming the unaccounted contracts, state unchanged."""
    _finalize(tasks, rows, n=1)
    tasks.serve_brief(1)
    with pytest.raises(EvidenceIncomplete) as exc:
        tasks.verify_completion(1, {})
    assert "contracts:1" in str(exc.value)
    assert tasks.get(1).state == IN_PROGRESS


def test_a_verdict_cannot_be_banked_before_the_work_is_served(tasks, rows):
    """DEFECTS.md F19(b) — contracts:62 declares no state precondition, so a pass could
    be recorded against a `pending` task and satisfy contracts:60's guard later:
    verification of work that was never served, which re-opens findings:9's hole."""
    _finalize(tasks, rows, n=1)
    with pytest.raises(NotInProgress):
        tasks.verify_completion(1, {"contracts:1": "tests pass"})


def test_a_verdict_does_not_survive_rework(tasks, rows):
    """The stale-verdict half of F19(b). A pass earned before a rework must not certify
    the rework — which is exactly when a banked pass is most dangerous."""
    _finalize(tasks, rows, n=1)
    _drive_to_done(tasks, 1)
    tasks.report_status(1, "flag_rework", "the revision changed the contract")
    tasks.serve_brief(1)

    assert tasks.get(1).serve_epoch == 2
    with pytest.raises(VerificationMissing):
        tasks.report_status(1, "complete", "same as before")


# --- contracts:38 graph_status / contracts:55 next_task ---


def test_graph_status_buckets_by_derived_readiness(tasks, rows):
    _finalize(tasks, rows, n=2, deps=[(0, 1)])
    status = tasks.graph_status()
    assert len(status.ready) == 1
    assert len(status.pending) == 1
    assert status.complete is False


def test_next_task_refuses_a_draft_plan(tasks, rows):
    """requirements:40 — draft briefs need recorded owner consent and a watermark."""
    _contracts(rows, 1)
    with pytest.raises(PlanNotFinalized):
        tasks.next_task()


def test_allow_draft_has_nothing_to_serve_before_finalization(tasks, rows):
    """DEFECTS.md F21 — contracts:55 offers `allow_draft` as an escape from
    PlanNotFinalized, but tasks are derived *at* finalization (crud_grid:33), so a
    never-finalized plan has no graph for the flag to serve from. The error says so
    rather than reporting an empty graph as 'everything is blocked'."""
    _contracts(rows, 1)
    with pytest.raises(PlanNotFinalized) as exc:
        tasks.next_task(allow_draft=True, consent="owner said go, 2026-07-21")
    assert "derived at finalization" in str(exc.value)


def test_next_task_names_the_blockers_rather_than_serving(tasks, rows):
    """uc_extensions:34 — never serve unbuildable work."""
    _finalize(tasks, rows, n=2, deps=[(0, 1)])
    tasks.serve_brief(2)
    report = tasks.next_task()
    assert bool(report) is False
    assert report.blocking[1] == (2,)


def test_next_task_returns_the_closure_not_a_brief(tasks, rows):
    """findings:3 — the closure goes to the planning session's LLM, which makes the
    BriefSelection. Composing is a separate second call; this contract must not pick."""
    _finalize(tasks, rows, n=1)
    candidates = tasks.next_task()
    assert RowRef.parse("contracts:1") in candidates.closure
    assert not hasattr(candidates, "brief")


# --- the package/task levels (DEVIATIONS.md D13, DEFECTS.md F24) ---


def test_finalization_refuses_an_unpackaged_task(tasks, rows):
    """D13 — every task belongs to exactly one package, and there is deliberately no
    catch-all: a default bucket satisfies the invariant while quietly restoring the
    three-level model, and a grouping nobody chose is a grouping nobody reviews."""
    from engine.tasks import UnpackagedTask

    rows.submit_rows(
        [RowSubmission(table="components", content={"title": "brief-composer"},
                       name="brief-composer")], "comp"
    )
    with pytest.raises(UnpackagedTask) as exc:
        tasks.finalize_plan()
    assert "components:1" in str(exc.value)


def test_task_membership_survives_as_a_typed_link(tasks, rows):
    """DEFECTS.md F24 — v1 carried this as `contracts.component_id`, a real foreign key,
    and the package-6 flattening kept the rows and dropped the relation. D13 restores it
    as `edge_type='belongs_to'`, member -> owner."""
    rows.submit_rows(
        [RowSubmission(table="components", content={"title": "brief-composer"},
                       name="brief-composer")], "comp"
    )
    package = tasks.declare_package("the engine", "everything behind the surface")
    task = tasks.assign_task("components:1", package.id)
    rows.submit_rows([RowSubmission(
        table="contracts",
        content={"title": "compose_brief", "behaviours": [
            {"key": "effect", "statement": "composes"}]},
        name="compose_brief",
        links=[LinkSpec(target="components:1", edge_type="belongs_to")],
    )], "contract")

    graph = tasks.finalize_plan()
    assert graph.tasks[0].task_id == task.id


def test_a_contract_with_no_owner_is_reported_never_guessed(tasks, rows):
    """Choosing an owner — or a package — would be the tool exercising judgment
    (`decisions:12`). None is the honest answer."""
    _finalize(tasks, rows, n=1)
    assert tasks.get(1).task_id is None


def test_packaging_shows_the_cut_and_what_is_outside_it(tasks, rows):
    """The read that makes mandatory membership satisfiable rather than merely enforced.
    A declaration hands back an id once; without a way to read the ids back, a planner who
    resumes cold cannot assign anything — DEFECTS.md F39."""
    rows.submit_rows(
        [RowSubmission(table="components", content={"title": "brief-composer"},
                       name="brief-composer"),
         RowSubmission(table="components", content={"title": "gap-engine"},
                       name="gap-engine")], "comps"
    )
    package = tasks.declare_package("the engine", "everything behind the surface")
    tasks.assign_task("components:1", package.id)

    cut = tasks.packaging()
    assert [(p.id, p.name) for p in cut.packages] == [(package.id, "the engine")]
    assert [str(t.source_ref) for t in cut.packages[0].tasks] == ["components:1"]
    assert [str(ref) for ref in cut.unpackaged] == ["components:2"]


def test_the_planner_sees_the_same_unplaced_set_finalization_refuses_on(tasks, rows):
    """Two readers, one query. A view of the remaining work that is computed separately
    from the guard is a view that drifts from it, and the drift shows up as a refusal
    nobody was warned about."""
    from engine.tasks import UnpackagedTask

    rows.submit_rows(
        [RowSubmission(table="components", content={"title": "gap-engine"},
                       name="gap-engine")], "comp"
    )
    assert [str(r) for r in tasks.packaging().unpackaged] == ["components:1"]
    with pytest.raises(UnpackagedTask) as exc:
        tasks.finalize_plan()
    assert "gap-engine (components:1)" in str(exc.value)


def test_a_package_is_referenced_by_id_never_by_name(tasks, rows):
    """A name-keyed grouping yields an empty context set on a typo, and a task quietly
    missing its mid-level context is the failure `decisions:14` measures. This is the
    mistake the retired `milestone` column made."""
    from engine.tasks import PackageNotFound

    rows.submit_rows(
        [RowSubmission(table="components", content={"title": "brief-composer"},
                       name="brief-composer")], "comp"
    )
    with pytest.raises(PackageNotFound):
        tasks.assign_task("components:1", 99)
