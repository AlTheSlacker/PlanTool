"""mcp-surface (`components:15`).

The first test in this file is the one that matters most: it is the *mechanism* behind the
component's claim to wrap every service contract. The claim is an accounting claim, so it
needs a denominator defined somewhere other than the thing being measured — and the frozen
plan defines its own, in the `consumed by: components:15` line on each contract. A
hand-kept list inside `engine/surface.py` would report success the first time somebody
added a contract and forgot about it.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from engine.door import (
    BareAddress,
    CALL,
    INTERNAL_DOCUMENTS,
    NO_LIVE_ROW,
    UnreachableCall,
    scan,
)
from engine.methodology import load
from engine.storage import Storage
from engine.surface import (
    ADDED,
    DEFERRED,
    DEVIATION,
    EXCLUDED,
    MOOT_OUTCOMES,
    REGISTRY,
    LogEvent,
    Surface,
    ToolCall,
)

PLAN = Path(__file__).resolve().parents[1] / "spec" / "v2" / "plan.md"
ENGINE = Path(__file__).resolve().parents[1] / "engine"

CONTRACT_LINE = re.compile(r"^- \*\*(\w+)\*\* \((?:function|api|event)\):.*?\(`(contracts:\d+)`")


def contracts_declared_live() -> dict[str, str]:
    """Every contract `plan.md` declares, as {contract: call}, whoever consumes it.

    `plan.md` renders active rows only, so this is the plan's live contracts — a
    superseded address is absent. Distinct from `contracts_for_the_surface()` below,
    which narrows to the ones the plan sends to `components:15`.
    """
    return {
        match.group(2): match.group(1)
        for line in PLAN.read_text(encoding="utf-8").splitlines()
        if (match := CONTRACT_LINE.match(line))
    }


def contracts_for_the_surface() -> dict[str, str]:
    """Every contract the frozen plan sends to `components:15`, as {contract: call}.

    Parsed rather than listed. The plan is frozen, so unlike F26's brief the denominator
    has no moving target — it is fixed permanently, which is exactly the property that
    makes an accounting check mean something.
    """
    found: dict[str, str] = {}
    pending: tuple[str, str] | None = None
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        match = CONTRACT_LINE.match(line)
        if match:
            pending = (match.group(2), match.group(1))
            continue
        if pending and line.strip().startswith("- consumed by:"):
            if "components:15" in line:
                found[pending[0]] = pending[1]
            pending = None
    return found


class TestTheDenominator:
    def test_the_plan_still_declares_thirty_nine(self):
        """A guard on the parser, not on the plan.

        If this number moves, either the plan was edited — it must not be — or the parser
        stopped seeing contracts it used to see. Both are worth failing on, and without
        this the coverage test below could silently start measuring against a smaller set
        and report a clean sheet.
        """
        assert len(contracts_for_the_surface()) == 39

    def test_every_contract_is_exposed_excluded_or_deferred(self):
        declared = contracts_for_the_surface()
        exposed = {tool.contract for tool in REGISTRY.values()}
        accounted = (
            exposed
            | {absence.contract for absence in EXCLUDED}
            | {absence.contract for absence in DEFERRED}
        )
        missing = {c: declared[c] for c in declared if c not in accounted}
        assert not missing, (
            f"the plan sends these to the surface and nothing accounts for them: {missing}"
        )

    def test_thirty_five_are_required_once_the_exclusions_are_taken_out(self):
        """39 declared, less the three writer-lock contracts and the split, which went
        with the level it divided in v3 change 1."""
        declared = contracts_for_the_surface()
        required = set(declared) - {absence.contract for absence in EXCLUDED}
        assert len(required) == 35

    def test_every_absence_carries_a_reason(self):
        """An exclusion with no reason is an omission with better manners."""
        for absence in EXCLUDED + DEFERRED:
            assert absence.reason.strip(), absence.call

    def test_every_deferral_names_the_stage_that_owes_it(self):
        """The outstanding-problem rule: bound to a named gate, never floating."""
        for absence in DEFERRED:
            assert re.search(r"\bM\d\b", absence.reason), absence.call

    def test_every_tool_without_a_contract_says_so_and_says_why(self):
        """The coverage test reads plan → surface and would never notice a tool that no
        contract asked for. This reads the other way: a tool carrying no contract address
        must appear in `ADDED` with the deviation that decided it, and an entry there must
        be a tool that exists. Both halves, because a list that drifts either way is a list
        the next reader learns to skip."""
        undeclared = {
            tool.name for tool in REGISTRY.values() if tool.contract == DEVIATION
        }
        named = {absence.call for absence in ADDED}
        assert undeclared == named, undeclared ^ named
        for absence in ADDED:
            assert absence.reason.strip(), absence.call

    def test_the_writer_lock_calls_are_excluded_and_not_exposed(self):
        for absence in EXCLUDED:
            assert absence.call not in REGISTRY

    def test_notwriter_is_recorded_as_moot_rather_than_implemented(self):
        assert "NotWriter" in MOOT_OUTCOMES
        source = (ENGINE / "surface.py").read_text(encoding="utf-8")
        assert "class NotWriter" not in source


class TestTheRegistry:
    def test_every_tool_reaches_a_real_method(self, tmp_path):
        surface = Surface(Storage(tmp_path))
        for tool in REGISTRY.values():
            service = getattr(surface, tool.service, None)
            assert service is not None, f"{tool.name}: no service {tool.service!r}"
            assert callable(getattr(service, tool.method, None)), tool.name

    def test_every_argument_is_described(self):
        """The notes are the tool's whole documented interface — a caller sees nothing
        else. An undescribed argument is one the caller guesses at."""
        for tool in REGISTRY.values():
            assert tool.summary.strip(), tool.name
            for param in tool.params:
                assert param.note.strip(), f"{tool.name}.{param.name}"

    def test_the_six_widened_tools_are_here(self):
        """D18's deviation. They are exposed because `plan_status` names them, and the
        door now fails any output naming a call that is not exposed — so if one of these
        is dropped, the digest stops working rather than quietly lying."""
        for call in (
            "get_mandate", "get_stage_script", "active_warnings",
            "journal", "gate_runs", "compose_brief",
        ):
            assert call in REGISTRY


class TestNoInternalDocumentsInMessages:
    """M6_PLAN.md §6.9a — our build documents may be cited in comments and docstrings,
    which we read, and never in a message the tool hands out, which a planner reads and
    cannot open.

    A static check rather than a runtime one, because at runtime the only options are
    letting the citation through or destroying a pedagogical error to complain about it.
    Neither helps; catching it at the moment of writing does.

    **What it covers, stated so it is not oversold:** text that is raised and text that is
    returned. Both known instances were of those shapes — one an error message, one a row
    verdict's problem string — and both are the shapes a message naturally takes. A message
    assembled into a local variable first would slip past, and every literal in the codebase
    is too wide a net: `engine/schema.py` carries its DDL as a string full of SQL comments
    that no planner will ever see.
    """

    def messages_out_of(self, path: Path) -> list[tuple[int, str]]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out: list[tuple[int, str]] = []

        def texts(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append((node.lineno, node.value))
            elif isinstance(node, ast.JoinedStr):
                for piece in node.values:
                    if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                        out.append((node.lineno, piece.value))
            elif isinstance(node, (ast.Tuple, ast.List)):
                for item in node.elts:
                    texts(item)

        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                for arg in list(node.exc.args) + [kw.value for kw in node.exc.keywords]:
                    texts(arg)
            elif isinstance(node, ast.Return) and node.value is not None:
                texts(node.value)
        return out

    def test_no_message_the_tool_hands_out_cites_one(self):
        offences = []
        for path in sorted(ENGINE.glob("*.py")):
            for lineno, text in self.messages_out_of(path):
                if text.strip() in INTERNAL_DOCUMENTS:
                    continue  # the list itself, in engine/door.py
                for document in INTERNAL_DOCUMENTS:
                    if document in text:
                        offences.append(f"{path.name}:{lineno} cites {document}")
        assert not offences, offences

    def test_the_check_can_fail(self, tmp_path):
        """A check that has never been shown to fail is a check nobody has tested."""
        planted = tmp_path / "planted.py"
        planted.write_text(
            "def f():\n"
            "    raise ValueError('see DEFECTS.md F28')\n"
            "def g():\n"
            "    return 'as M6_PLAN.md says'\n",
            encoding="utf-8",
        )
        found = [text for _, text in self.messages_out_of(planted)]
        assert any("DEFECTS.md" in text for text in found)
        assert any("M6_PLAN.md" in text for text in found)


class TestTheMethodologyNamesReachableCalls:
    """The vendored methodology is the one thing the tool serves that it did not write, and
    it is served verbatim — so the door annotates it rather than rejecting it, and a call
    name in it that no tool exposes would sail straight through to the planner.

    That is not hypothetical: driving the surface printed a mandate telling a cold planner
    to resume from `plan_status()` + `next_gap()`, and there is no `next_gap`. The runtime
    scan cannot catch this without editing the owner's methodology in flight, so the check
    moves here, where it costs nothing and fires before anything ships.
    """

    #: Named in the live revision and not exposed, each with the reason and where it is
    #: owed. Same shape as the registry's own absences, for the same reason: an exception
    #: with no entry fails the suite, and an entry is a visible act with a sentence
    #: attached.
    NOT_YET: dict[str, str] = {}

    def calls_named_in_the_methodology(self) -> dict[str, str]:
        """The revision the loader actually serves, not a directory named here.

        It read `rev3` by name until v3 change 1 minted rev 4. A check pinned to a
        revision keeps running and quietly measures the wrong one — it would have gone on
        passing against a frozen archive while the served scripts named calls that no
        longer exist, which is the exact failure it was written to catch.
        """
        found: dict[str, str] = {}
        for path in sorted(load().root.rglob("*")):
            if path.suffix not in (".md", ".yaml", ".yml"):
                continue
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                for name in CALL.findall(line):
                    found.setdefault(name, f"{path.name}:{lineno}")
        return found

    def test_every_call_the_methodology_names_is_exposed_or_declared(self):
        named = self.calls_named_in_the_methodology()
        unreachable = {
            name: where
            for name, where in named.items()
            if name not in REGISTRY and name not in self.NOT_YET
        }
        assert not unreachable, unreachable

    def test_every_v1_call_name_is_gone(self):
        """The scripts addressed v1's tool surface until 2026-07-22.

        The regex above only sees a name written as a call — `name()`, `name(3)` — and most
        of these were written as bare backticked identifiers, which is how eighteen of them
        sat behind a check that found four. So this reads the assets as text. The list is
        v1's surface, taken from `archive/v1/`; nothing on it may reappear.

        YAML comments are skipped, and only they: the manifest's provenance note records
        what was replaced and by what, which is the one place naming a dead call is the
        point. Everything else in these files is either served to a planner or read by the
        engine.
        """
        gone = (
            "submit_use_cases", "submit_uc_extensions", "submit_requirements",
            "submit_entities", "submit_crud", "submit_states", "submit_state_cells",
            "submit_dependencies", "submit_dep_failure_modes", "submit_components",
            "submit_contracts", "submit_contract_deps", "record_decision",
            "confirm_assumption", "file_question", "resolve_question", "get_rows",
            "get_plan_pack", "get_stage_prompt", "disposition_finding", "export_plan",
            "freeze_plan",
        )
        offences = []
        rev3 = ENGINE / "methodology" / "rev3"
        for path in sorted(rev3.rglob("*")):
            if path.suffix not in (".md", ".yaml", ".yml"):
                continue
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if path.suffix != ".md" and line.lstrip().startswith("#"):
                    continue
                for name in gone:
                    if name in line:
                        offences.append(f"{path.name}:{lineno} names {name}")
        assert not offences, offences

    def test_no_declared_absence_has_quietly_been_built(self):
        """An exception that is no longer true is worse than none: it teaches the reader to
        skip the list."""
        for name in self.NOT_YET:
            assert name not in REGISTRY, f"{name} is exposed now; drop it from NOT_YET"


@pytest.fixture
def surface(tmp_path):
    storage = Storage(tmp_path)
    storage.init_plan("surface test", "standard")
    made = Surface(storage)
    yield made
    storage.close()


def a_row(surface, table="requirements", name="the widget settles in 40 ms"):
    result = surface.dispatch(ToolCall("submit_rows", {
        "batch": [{
            "table": table,
            "name": name,
            "content": {"text": "The widget shall settle within 40 ms."},
        }],
        "idempotency_key": f"seed-{table}-{name}",
    }))
    assert result.ok, result.problem
    return result


class TestDispatch:
    def test_an_unknown_tool_names_the_valid_ones(self, surface):
        result = surface.dispatch(ToolCall("summon_the_plan", {}))
        assert not result.ok
        assert result.error == "UnknownTool"
        assert "next_gaps" in str(result.problem)

    def test_a_missing_argument_says_what_it_is_for(self, surface):
        result = surface.dispatch(ToolCall("run_gate", {}))
        assert not result.ok
        assert result.error == "MalformedCall"
        assert "which stage to gate" in str(result.problem)

    def test_an_unknown_argument_is_refused_by_name(self, surface):
        result = surface.dispatch(ToolCall("run_gate", {"packet": 1}))
        assert not result.ok
        assert "packet" in str(result.problem)

    def test_a_wrong_type_names_the_field(self, surface):
        result = surface.dispatch(ToolCall("run_gate", {"stage": "one"}))
        assert not result.ok
        assert "stage" in str(result.problem)

    def test_a_malformed_address_is_refused_before_anything_is_filed(self, surface):
        result = surface.dispatch(ToolCall("retire_row", {
            "ref": "requirements-61", "reason": "no", "idempotency_key": "k",
        }))
        assert not result.ok
        assert result.error == "MalformedCall"

    def test_a_row_cannot_be_filed_without_a_name(self, surface):
        result = surface.dispatch(ToolCall("submit_rows", {
            "batch": [{"table": "requirements", "content": {"text": "x"}}],
            "idempotency_key": "no-name",
        }))
        assert not result.ok
        assert "name" in str(result.problem)

    def test_a_good_call_comes_back_rendered(self, surface):
        result = a_row(surface)
        assert result.ok
        assert result.payload["verdicts"][0]["accepted"] is True

    def test_an_engine_refusal_keeps_its_own_words(self, surface):
        result = surface.dispatch(ToolCall("retire_row", {
            "ref": "requirements:999", "reason": "gone", "idempotency_key": "k",
        }))
        assert not result.ok
        assert result.error == "RowNotFound"


    def test_a_plan_can_be_finalized_through_the_surface(self, surface):
        """DEFECTS.md F39's standing question, asked of what is left.

        F39 was an invariant that was enforceable and not satisfiable: finalization
        refused a plan whose tasks were in no group and no exposed call could put one
        there, so every plan authored through this surface was permanently unfinalizable.
        The grouping is gone (v3 change 1) and the three tools with it, which removes that
        instance and not the class. So the test that survives is the one that asks the
        question directly — can a plan authored here actually be finalized here? — because
        the answer was 'no' for a month and nothing noticed.
        """
        submitted = surface.dispatch(ToolCall("submit_rows", {
            "batch": [{
                "table": "contracts",
                "content": {"title": "compose_brief",
                            "behaviours": ["records the selection"]},
                "name": "compose_brief",
            }],
            "idempotency_key": "contract",
        }))
        assert submitted.ok, submitted.problem

        finalized = surface.dispatch(ToolCall("finalize_plan", {}))
        assert finalized.ok, finalized.problem
        assert finalized.payload["tasks"][0]["contract_ref"] == (
            "compose_brief (contracts:1)"
        )
        assert finalized.payload["unenumerated"] == []

        served = surface.dispatch(ToolCall("next_task", {}))
        assert served.ok, served.problem
        assert served.payload["task"]["contract_ref"] == "compose_brief (contracts:1)"


class TestTheDoorInPractice:
    def test_an_address_in_a_payload_arrives_with_its_name(self, surface):
        a_row(surface, name="the settling requirement")
        result = surface.dispatch(ToolCall("read_rows", {
            "selector": {"table": "requirements"},
        }))
        assert result.ok
        rendered = json.dumps(result.payload)
        assert "the settling requirement (requirements:1)" in rendered

    def test_a_dead_address_in_an_error_resolves_rather_than_dangling(self, surface):
        """F17 stops being silent: the address is served exactly as the engine wrote it,
        and what it points at comes back beside it."""
        result = surface.dispatch(ToolCall("retire_row", {
            "ref": "requirements:404", "reason": "gone", "idempotency_key": "k",
        }))
        assert not result.ok
        assert result.problem == "no such row (ref='requirements:404')"
        assert result.cites == (
            {"address": "requirements:404", "name": NO_LIVE_ROW, "state": "absent"},
        )

    def test_annotation_never_changes_a_value_s_shape(self, surface):
        """The defect the driver caught: a gap key contains an address, and an earlier
        version turned it into an object — so a caller who read one could no longer hand it
        back to `dismiss_gap`. Keys stay strings; the resolutions live beside the payload."""
        a_row(surface, name="runs on Windows")
        result = surface.dispatch(ToolCall("next_gaps", {"limit": 5}))
        assert result.ok, result.problem
        for gap in result.payload["gaps"]:
            assert isinstance(gap["key"], str)
        surface.dispatch(ToolCall("dismiss_gap", {
            "gap_key": result.payload["gaps"][0]["key"], "reason": "not now",
        }))

    def test_a_cited_address_is_resolved_beside_the_payload(self, surface):
        a_row(surface, name="settles inside 40 ms")
        surface.dispatch(ToolCall("submit_rows", {
            "batch": [{
                "table": "decisions", "name": "one backend, SQLite",
                "content": {"text": "SQLite only. See requirements:1."},
            }],
            "idempotency_key": "cites",
        }))
        result = surface.dispatch(ToolCall("read_rows", {
            "selector": {"table": "decisions"},
        }))
        assert result.ok
        assert {"address": "requirements:1", "name": "settles inside 40 ms",
                "state": "active"} in result.cites

    def test_the_digest_names_only_calls_the_surface_exposes(self, surface):
        """The finding the pre-build audit turned up, now unable to recur: of the six
        calls `plan_status` names, one used to be reachable."""
        result = surface.dispatch(ToolCall("plan_status", {}))
        assert result.ok, result.problem
        named = set(re.findall(r"\b([a-z_][a-z0-9_]*)\(", result.payload["summary"]))
        assert named, "the digest named no calls at all, which is a different defect"
        assert named <= surface.tool_names

    def test_a_bare_address_fails_the_call(self, surface):
        with pytest.raises(BareAddress):
            scan({"summary": "see requirements:61"}, surface.tool_names)

    def test_an_unexposed_call_fails_the_call(self, surface):
        with pytest.raises(UnreachableCall):
            scan({"summary": "run acquire_writer_lock() first"}, surface.tool_names)

    def test_an_accompanied_address_passes(self, surface):
        scan({"summary": "the settling requirement (requirements:61)"}, surface.tool_names)

    def test_a_neighbouring_address_does_not_borrow_its_neighbour_s_name(self, surface):
        """`requirements:6` is a substring of `(requirements:61)`. A containment check on
        the text rather than the span would let the bare one through on the back of the
        accompanied one."""
        with pytest.raises(BareAddress):
            scan(
                {"summary": "see requirements:6 and the settler (requirements:61)"},
                surface.tool_names,
            )

    def test_a_digest_quoting_a_ref_shaped_token_in_owner_prose_does_not_crash(self, surface):
        """DEFECTS.md F49 — `plan_status` crashed when its hand-assembled summary quoted
        stored prose containing a `table:ordinal` token: a by-example `contracts:12` inside a
        glossary definition, surfaced as a warning, tripped the strict bare-address guard and
        refused the one call a cold planner must make. A journal note is the same class — the
        planner's own words, which may name a row. The digest must annotate the address, never
        fail the call over it, while the tool's own composed lines stay strictly checked."""
        a_row(surface)
        note = surface.dispatch(ToolCall("journal_note", {
            "note": "the resolver pattern to reuse lives in contracts:12",
        }))
        # journal_note is summarised too, so pre-F49 this write also crashed on the token.
        assert note.ok, note.problem

        result = surface.dispatch(ToolCall("plan_status", {}))
        assert result.ok, result.problem
        assert "contracts:12" in result.payload["summary"], "the owner's words were dropped"
        assert any(c["address"] == "contracts:12" for c in result.cites), "not annotated"


class TestTheLog:
    def test_a_successful_call_is_logged(self, surface):
        a_row(surface)
        events = surface.log.read()
        assert any(e["tool"] == "submit_rows" and e["outcome"] == "ok" for e in events)

    def test_a_refusal_is_logged_with_a_failure_mode(self, surface):
        surface.dispatch(ToolCall("run_gate", {}))
        refusal = [e for e in surface.log.read() if e["outcome"] == "refused"][-1]
        assert refusal["failure_mode"] == "malformed"

    def test_an_unknown_tool_is_logged_too(self, surface):
        surface.dispatch(ToolCall("summon_the_plan", {}))
        assert any(e["tool"] == "summon_the_plan" for e in surface.log.read())

    def test_the_log_only_appends(self, surface):
        a_row(surface, name="first")
        before = len(surface.log.read())
        a_row(surface, table="decisions", name="second")
        after = surface.log.read()
        assert len(after) == before + 1
        assert after[0]["tool"] == "submit_rows"

    def test_the_log_carries_no_plan_content(self, surface):
        """The log records that a call happened and how it went. A log carrying plan text
        is a second copy of the plan that nothing keeps in step."""
        a_row(surface, name="the settling requirement")
        assert "settle within 40 ms" not in surface.log.path.read_text(encoding="utf-8")

    def test_an_unknown_failure_mode_is_refused(self, surface):
        from engine.surface import LogWriteError

        with pytest.raises(LogWriteError):
            surface.log.append_log(LogEvent(
                tool="x", started_at="a", finished_at="b", outcome="refused",
                summary="s", failure_mode="confused",
            ))


class TestTheGlossary:
    """The glossary through the door (D23). Every one of these tools returns something the
    surface composes — a term, a usage note, a receipt line — which is the half of the
    output the strict invariants apply to."""

    def define(self, surface, term="component", definition="the old word for a task"):
        return surface.dispatch(ToolCall(
            "define_term", {"term": term, "definition": definition}
        ))

    def test_a_term_can_be_recorded_and_read_back(self, surface):
        assert self.define(surface).ok
        result = surface.dispatch(ToolCall("glossary", {}))
        assert result.ok
        assert [t["term"] for t in result.payload] == ["component"]

    def test_the_struck_tools_are_gone_from_the_door(self, surface):
        """`approve_term`, `retire_term` and `export_glossary` went with the machinery
        behind them — the proposal lifecycle, the banned list, and a manifest nothing ever
        read. Asserted through `dispatch`, because the registry is what the door resolves
        against and a tool removed from one list and not the other is the failure this
        surface's own coverage tests exist for."""
        for name in ("approve_term", "retire_term", "export_glossary"):
            result = surface.dispatch(ToolCall(name, {}))
            assert not result.ok
            assert result.error == "UnknownTool"
        assert not (surface.storage.workspace / "glossary.json").exists()

    def test_redefining_changes_the_meaning_in_place(self, surface):
        self.define(surface)
        assert surface.dispatch(ToolCall("redefine_term", {
            "term": "component", "definition": "a unit of the design",
        })).ok
        result = surface.dispatch(ToolCall("glossary", {}))
        assert [(t["term"], t["definition"]) for t in result.payload] == [
            ("component", "a unit of the design")
        ]

    def test_a_label_must_be_a_word_the_glossary_holds(self, surface):
        """The glossary's one mechanical use, through the door."""
        row = a_row(surface)
        ref = row.payload["verdicts"][0]["ref"]
        refused = surface.dispatch(ToolCall("attach_label", {
            "word": "widget", "targets": [ref],
        }))
        assert not refused.ok
        assert "define_term" in str(refused.problem)

        assert self.define(surface, "widget", "the thing that settles").ok
        assert surface.dispatch(ToolCall("attach_label", {
            "word": "widget", "targets": [ref],
        })).ok

    def test_a_page_shows_each_row_s_labels_with_a_name_beside_the_address(self, surface):
        """D19 through a mapping, which is the shape that would have escaped: `render` walks
        a payload's values and never its keys, so a ref-keyed dict would have printed a bare
        `table:ordinal` with no check able to see it."""
        row = a_row(surface)
        ref = row.payload["verdicts"][0]["ref"]
        self.define(surface, "widget", "the thing that settles")
        surface.dispatch(ToolCall("attach_label", {"word": "widget", "targets": [ref]}))

        page = surface.dispatch(ToolCall("read_rows", {"selector": {"table": "requirements"}}))
        assert page.ok
        assert page.payload["labels"] == {
            "the widget settles in 40 ms (requirements:1)": ["widget"]
        }

    def test_the_label_filter_is_a_field_of_the_selector(self, surface):
        """A top-level `labels` parameter would be a `TypeError` caught by the blanket
        handler and reported as the caller's mistake, and `as_selector` refuses any key it
        does not whitelist — so both halves had to move together."""
        row = a_row(surface)
        ref = row.payload["verdicts"][0]["ref"]
        self.define(surface, "widget", "the thing that settles")
        surface.dispatch(ToolCall("attach_label", {"word": "widget", "targets": [ref]}))

        found = surface.dispatch(ToolCall("read_rows", {
            "selector": {"labels": ["widget"]},
        }))
        assert found.ok, found.problem
        assert found.payload["total"] == 1

        # The parser is the one place allowed to be generous about a bare string.
        one = surface.dispatch(ToolCall("read_rows", {"selector": {"labels": "widget"}}))
        assert one.ok and one.payload["total"] == 1

        stray = surface.dispatch(ToolCall("read_rows", {
            "selector": {"labels": ["widget"], "nosuchfield": 1},
        }))
        assert not stray.ok

    def test_removing_a_word_in_use_refuses_through_the_door(self, surface):
        row = a_row(surface)
        ref = row.payload["verdicts"][0]["ref"]
        self.define(surface, "widget", "the thing that settles")
        surface.dispatch(ToolCall("attach_label", {"word": "widget", "targets": [ref]}))

        refused = surface.dispatch(ToolCall("remove_term", {"term": "widget"}))
        assert not refused.ok
        assert refused.error == "TermInUse"
        assert "1 plan row(s)" in str(refused.problem)

        assert surface.dispatch(ToolCall("remove_term", {
            "term": "widget", "detach_all": True,
        })).ok
        assert surface.dispatch(ToolCall("glossary", {})).payload == []

    def test_the_label_report_names_every_target(self, surface):
        row = a_row(surface)
        ref = row.payload["verdicts"][0]["ref"]
        self.define(surface, "widget", "the thing that settles")
        surface.dispatch(ToolCall("attach_label", {"word": "widget", "targets": [ref]}))

        report = surface.dispatch(ToolCall("labels", {"word": "widget"}))
        assert report.ok, report.problem
        usage = report.payload["usages"][0]
        assert (usage["row_count"], usage["task_count"]) == (1, 0)
        assert report.payload["live_rows"] == 1
        assert report.payload["targets"][0]["ref"] == ref

    def test_terms_cannot_be_submitted_as_plan_rows(self, surface):
        result = surface.dispatch(ToolCall("submit_rows", {
            "batch": [{"table": "terms", "name": "stage", "content": {"term": "x"}}],
            "idempotency_key": "reserved-terms",
        }))
        assert result.ok  # the batch stands; the row alone is refused
        verdict = result.payload["verdicts"][0]
        assert verdict["accepted"] is False
        assert "define_term" in verdict["problem"]


class TestWhatGoesOutComesBack:
    """DEFECTS.md F41. Every address this surface prints is in display form — D19 forbids
    a bare one — so the display form is what a caller has to hand back, and every tool
    taking a ref refused it. The tool's own output was not valid input to the tool."""

    def test_a_ref_read_out_of_a_payload_is_accepted_back(self, surface):
        printed = a_row(surface).payload["verdicts"][0]["ref"]
        assert printed == "the widget settles in 40 ms (requirements:1)"

        result = surface.dispatch(ToolCall("retire_row", {
            "ref": printed, "reason": "superseded by the real one",
            "idempotency_key": "retire-printed",
        }))
        assert result.ok, result.problem

    def test_the_storage_form_still_works(self, surface):
        a_row(surface)
        result = surface.dispatch(ToolCall("read_rows", {
            "selector": {"ids": ["requirements:1"]},
        }))
        assert result.ok, result.problem

    def test_something_that_is_not_an_address_either_way_still_fails(self, surface):
        result = surface.dispatch(ToolCall("retire_row", {
            "ref": "the widget settles", "reason": "x", "idempotency_key": "k",
        }))
        assert not result.ok
        assert result.error == "MalformedCall"


class TestTheWarningLedgerStaysReconciled:
    """DEFECTS.md F50 — the digest may not nag about a condition it has already dropped.

    This class tested the same mechanism through the glossary until v3 change 4: a gate
    raised an `unsettled_term` warning, `approve_term` settled the definition, and the
    digest had to stop nagging without waiting for the next gate. Approval and that warning
    kind are both gone, and **the reconciliation is not** — it is what `SETTLEABLE_KINDS`
    and `GapEngine.live_warning_keys` exist for. So the check moves to a kind that survives
    rather than being deleted with its old subject, which would have taken a live mechanism
    out of the suite along with the dead one.
    """

    def test_the_digest_drops_a_warning_the_moment_its_condition_clears(self, surface):
        """Warnings are persisted rows the gate raises and settles; gaps are recomputed
        live. Between two gates the ledger is stale, and the reconciliation at read time is
        what stops one digest contradicting itself. Asserted on what the resuming planner
        sees (the digest text), not on the ledger row (F22)."""
        surface.dispatch(ToolCall("run_gate", {"stage": 1}))
        raised = surface.dispatch(ToolCall("plan_status", {})).payload["summary"]
        assert "goals" in raised, "the gate put the empty stage in front of the planner"

        surface.dispatch(ToolCall("submit_rows", {
            "batch": [
                {"table": "goals", "name": "ship it",
                 "content": {"title": "ship it", "success_criteria": "it lands"}},
                {"table": "non_goals", "name": "no GUI", "content": {"title": "no GUI"}},
                {"table": "stack", "name": "Python", "content": {"title": "Python 3.12"}},
            ],
            "idempotency_key": "fill-stage-one",
        }))
        settled = surface.dispatch(ToolCall("plan_status", {})).payload["summary"]
        assert "goals_recorded" not in settled, "no second gate should be needed"

    def test_the_retired_word_kind_has_no_producer_left(self, surface):
        """Its only producer was the glossary's lexical scan. A kind table listing a kind
        nothing can raise is a menu item that is never cooked — and worse, once it left
        `SETTLEABLE_KINDS` nothing could settle an existing row either, which is why the
        10 -> 11 migration settles them rather than leaving them active forever."""
        import engine.warnings as warnings_module

        surface.dispatch(ToolCall("define_term", {
            "term": "widget", "definition": "the thing that settles",
        }))
        surface.dispatch(ToolCall("run_gate", {"stage": 1}))
        assert not hasattr(warnings_module, "RETIRED_TERM")
        assert all(
            w.kind != "retired_term" for w in surface.warns.all_warnings()
        )


class TestTheDecisionContext:
    """v3 D11 through the surface, which is the only route a client has."""

    def test_a_row_can_be_filed_with_its_argument(self, surface):
        result = surface.dispatch(ToolCall("submit_rows", {
            "batch": [{
                "table": "entities", "name": "Order",
                "content": {"text": "The aggregate every line hangs off."},
                "grounds": "the order is what a customer thinks they placed",
                "alternatives": "a line-item aggregate — rejected, it orphans totals",
            }],
            "idempotency_key": "argued",
        }))
        assert result.ok, result.problem
        read = surface.dispatch(ToolCall("read_rows", {"selector": {"ids": ["entities:1"]}}))
        assert read.payload["rows"][0]["grounds"].startswith("the order is what")

    def test_a_non_string_argument_is_refused_by_name(self, surface):
        result = surface.dispatch(ToolCall("submit_rows", {
            "batch": [{"table": "entities", "name": "Order", "content": {"text": "x"},
                       "grounds": ["a list"]}],
            "idempotency_key": "bad-grounds",
        }))
        assert not result.ok
        assert "grounds" in str(result.problem)

    def test_a_replacement_can_carry_its_argument_too(self, surface):
        """One decoder serves `submit_rows` and a supersede replacement. If it did not,
        supersession would be the one path that loses the field — and `record_grounds`
        deliberately refuses a superseded row, so nothing could repair it."""
        a_row(surface, table="entities", name="Order")
        result = surface.dispatch(ToolCall("supersede_row", {
            "old": "entities:1",
            "replacement": {
                "table": "entities", "name": "Order",
                "content": {"text": "The aggregate, with its lines."},
                "grounds": "lines have no life outside the order",
                "alternatives": "lines as their own aggregate — rejected, totals drift",
            },
            "reason": "stage 5 found the lines have no independent lifecycle",
            "idempotency_key": "sup",
        }))
        assert result.ok, result.problem
        read = surface.dispatch(ToolCall("read_rows", {"selector": {"ids": ["entities:1"]}}))
        old = read.payload["rows"][0]
        assert old["supersede_reason"].startswith("stage 5 found")
        read = surface.dispatch(ToolCall("read_rows", {"selector": {"ids": ["entities:2"]}}))
        assert read.payload["rows"][0]["grounds"] == "lines have no life outside the order"

    def test_the_gap_names_a_call_the_surface_exposes(self, surface):
        """The ask ends in `record_grounds()`, and the door fails any outgoing text naming
        a call no tool exposes — so the tool has to be registered before the rule ships."""
        a_row(surface, table="entities", name="Order")
        result = surface.dispatch(ToolCall("next_gaps", {"stage": 4}))
        assert result.ok, result.problem
        asks = [g["ask"] for g in result.payload["gaps"]
                if g["rule_key"] == "entity_without_grounds"]
        assert asks and "record_grounds()" in asks[0]

    def test_record_grounds_closes_the_gap_through_the_surface(self, surface):
        a_row(surface, table="entities", name="Order")
        result = surface.dispatch(ToolCall("record_grounds", {
            "ref": "entities:1",
            "grounds": "the order is what a customer thinks they placed",
            "alternatives": "none, it follows from the use case",
            "idempotency_key": "g1",
        }))
        assert result.ok, result.problem
        after = surface.dispatch(ToolCall("next_gaps", {"stage": 4}))
        assert not [g for g in after.payload["gaps"]
                    if g["rule_key"] == "entity_without_grounds"]

    def test_no_registry_entry_cites_a_superseded_contract(self):
        """The successor of an amended contract, not the row it replaced.

        This replaces `test_every_amended_contract_is_real_and_says_what_changed`, which
        guarded the `AMENDED` list that v3 change 2 used to record five stale contracts.
        Al ruled that a contract a change has altered is superseded in the frozen plan
        rather than annotated at the code, so the five became `contracts:69`-`73` and the
        list went with them.

        `plan.md` renders active rows only, so a superseded address is simply absent from
        it, and a registry entry still naming one is caught by name here — as well as by
        the unaccounted successor in `test_every_contract_is_exposed_excluded_or_deferred`.

        The denominator is every contract the plan declares, NOT
        `contracts_for_the_surface()`: that one is the subset consumed by `components:15`,
        and four contracts this surface exposes are consumed by other components too.
        Measured against the subset, this test reported four false positives.
        """
        live = set(contracts_declared_live())
        stale = {
            tool.contract: name
            for name, tool in REGISTRY.items()
            if tool.contract != DEVIATION and tool.contract not in live
        }
        assert not stale, (
            f"these registry entries cite a contract the frozen plan no longer declares "
            f"live — supersession moves the address, and the citation moves with it: {stale}"
        )
