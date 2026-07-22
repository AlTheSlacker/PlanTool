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

    def test_thirty_six_are_required_once_the_writer_lock_is_taken_out(self):
        declared = contracts_for_the_surface()
        required = set(declared) - {absence.contract for absence in EXCLUDED}
        assert len(required) == 36

    def test_every_absence_carries_a_reason(self):
        """An exclusion with no reason is an omission with better manners."""
        for absence in EXCLUDED + DEFERRED:
            assert absence.reason.strip(), absence.call

    def test_every_deferral_names_the_package_that_owes_it(self):
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
            "get_mandate", "get_package_script", "active_warnings",
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

    #: Named in rev 3 and not exposed, each with the reason and where it is owed. Same
    #: shape as the registry's own absences, for the same reason: an exception with no
    #: entry fails the suite, and an entry is a visible act with a sentence attached.
    NOT_YET: dict[str, str] = {}

    def calls_named_in_rev3(self) -> dict[str, str]:
        found: dict[str, str] = {}
        rev3 = ENGINE / "methodology" / "rev3"
        for path in sorted(rev3.rglob("*")):
            if path.suffix not in (".md", ".yaml", ".yml"):
                continue
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                for name in CALL.findall(line):
                    found.setdefault(name, f"{path.name}:{lineno}")
        return found

    def test_every_call_the_methodology_names_is_exposed_or_declared(self):
        named = self.calls_named_in_rev3()
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
        assert "which package to gate" in str(result.problem)

    def test_an_unknown_argument_is_refused_by_name(self, surface):
        result = surface.dispatch(ToolCall("run_gate", {"packet": 1}))
        assert not result.ok
        assert "packet" in str(result.problem)

    def test_a_wrong_type_names_the_field(self, surface):
        result = surface.dispatch(ToolCall("run_gate", {"package": "one"}))
        assert not result.ok
        assert "package" in str(result.problem)

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
