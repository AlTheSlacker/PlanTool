"""The plan's glossary (DEVIATIONS.md D23) — the mechanism F27 was missing."""

import json

import pytest

from engine.models import RowSubmission
from engine.terms import (
    BOTH,
    IDENTIFIER,
    PROSE,
    AlreadyApproved,
    BanNeedsReason,
    DefinitionRequired,
    TermExists,
    TermNotFound,
    TermService,
)


@pytest.fixture
def terms(store, rows):
    return TermService(store, rows)


@pytest.fixture
def gaps(store, rows):
    from engine.gaps import GapEngine

    return GapEngine(store, rows)


def _row(rows, content, name="a row", key=None):
    receipt = rows.submit_rows(
        [RowSubmission(table="requirements", content=content, name=name)],
        key or f"row:{name}",
    )
    return receipt.verdicts[0]


# --- defining, redefining, retiring ---


def test_a_term_records_what_a_word_means(terms):
    term = terms.define_term("package", "a declared grouping of tasks")
    assert term.term == "package"
    assert term.is_banned is False
    assert terms.find("Package").definition == "a declared grouping of tasks"


# --- proposed by the planner, settled by the owner ---


def test_a_definition_arrives_as_a_proposal(terms):
    """A definition the tool took from a planning session and filed as settled would be the
    tool deciding what the owner's words mean while looking like a record of him deciding."""
    term = terms.define_term("package", "a declared grouping of tasks")
    assert term.is_approved is False
    assert terms.awaiting_approval() == (term,)


def test_the_owner_can_accept_the_proposal_as_it_stands(terms):
    terms.define_term("package", "a declared grouping of tasks")
    settled = terms.approve_term("package")
    assert settled.is_approved is True
    assert settled.definition == "a declared grouping of tasks"
    assert terms.awaiting_approval() == ()
    assert len(terms.history("package")) == 1


def test_the_owner_rewriting_keeps_what_was_proposed(terms):
    """The difference between the two is the most interesting line in a glossary's history:
    it is where the tool's reading of the plan and the owner's diverged."""
    terms.define_term("package", "a declared grouping of tasks")
    settled = terms.approve_term("package", "the level at which I say 'the GUI'")

    assert settled.definition == "the level at which I say 'the GUI'"
    assert settled.is_approved is True
    history = terms.history("package")
    assert [t.definition for t in history] == [
        "a declared grouping of tasks", "the level at which I say 'the GUI'",
    ]
    assert history[0].is_approved is False


def test_approving_a_settled_definition_twice_is_refused(terms):
    terms.define_term("package", "a declared grouping of tasks")
    terms.approve_term("package")
    with pytest.raises(AlreadyApproved) as exc:
        terms.approve_term("package")
    assert "redefine_term" in str(exc.value)


def test_approving_with_an_empty_definition_is_refused(terms):
    terms.define_term("package", "a declared grouping of tasks")
    with pytest.raises(DefinitionRequired):
        terms.approve_term("package", "   ")


def test_a_new_meaning_needs_settling_again(terms):
    """Approval that survived the definition it approved would be the plan recording the
    owner's assent to words he never saw."""
    terms.define_term("task", "a unit of work")
    terms.approve_term("task")
    terms.redefine_term("task", "the work of realising one component")
    assert terms.find("task").is_approved is False


def test_the_owner_rewriting_does_not_put_a_retired_word_back_into_use(terms):
    """A rewrite at approval settles what the word meant; it is not the act that brings a
    retired word back. Redefinition is."""
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings")
    terms.approve_term("component", "what we called a task before 2026")
    assert terms.find("component").is_banned is True


def test_a_word_cannot_be_defined_twice(terms):
    """Two live entries for one word is the collision the whole table exists to catch."""
    terms.define_term("package", "a declared grouping of tasks")
    with pytest.raises(TermExists) as exc:
        terms.define_term("package", "something else entirely")
    assert "redefine_term" in str(exc.value)


def test_a_term_needs_a_definition(terms):
    with pytest.raises(DefinitionRequired):
        terms.define_term("package", "   ")


def test_redefining_keeps_the_old_wording_as_history(terms):
    terms.define_term("task", "a unit of work")
    terms.redefine_term("task", "the work of realising one component")

    assert terms.find("task").definition == "the work of realising one component"
    history = terms.history("task")
    assert len(history) == 2
    assert history[0].definition == "a unit of work"
    assert history[0].is_live is False
    assert len([t for t in terms.glossary() if t.term == "task"]) == 1


def test_redefining_carries_the_named_row_forward(terms, rows):
    ref = _row(rows, {"text": "packages are declared"}).ref
    terms.define_term("package", "a declared grouping", names_ref=ref)
    later = terms.redefine_term("package", "a declared grouping of tasks")
    assert later.names_ref == ref


def test_redefining_a_word_nobody_defined_says_so(terms):
    with pytest.raises(TermNotFound) as exc:
        terms.redefine_term("package", "a declared grouping")
    assert "define_term" in str(exc.value)


# --- the trap: a retired word must stay in live reads ---


def test_a_retired_word_stays_in_the_glossary(terms):
    """The one that matters. Retirement drops a row out of live reads everywhere else in
    v2; do that here and the banned list empties, so every check downstream runs, finds
    nothing to ban and reports success — F23's missing denominator, inside the mechanism
    built to prevent F27."""
    terms.define_term("task", "the work of realising one component")
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings", use_instead="task")

    live_words = [t.term for t in terms.glossary()]
    assert "component" in live_words
    assert [t.term for t in terms.banned()] == ["component"]
    assert terms.find("component").use_instead == "task"


def test_the_banned_list_is_empty_only_when_nothing_is_retired(terms):
    """F23's own test, applied to this table: a denominator that can never be non-empty
    is a check that reports success by construction."""
    terms.define_term("component", "the old word for a task")
    assert terms.banned() == ()
    terms.retire_term("component", PROSE, "one entity, two spellings")
    assert len(terms.banned()) == 1


def test_retiring_records_why(terms):
    terms.define_term("component", "the old word")
    with pytest.raises(BanNeedsReason):
        terms.retire_term("component", PROSE, "  ")


def test_retiring_names_where_the_word_is_out(terms):
    terms.define_term("component", "the old word")
    with pytest.raises(BanNeedsReason) as exc:
        terms.retire_term("component", "everywhere", "one entity, two spellings")
    assert "prose" in str(exc.value)


def test_a_replacement_must_be_a_word_the_plan_defines(terms):
    """A retirement pointing at an undefined word hands the reader a second lookup, which
    is the failure the naming design removed everywhere else."""
    terms.define_term("component", "the old word")
    with pytest.raises(TermNotFound):
        terms.retire_term("component", PROSE, "two spellings", use_instead="task")


def test_a_retired_word_comes_back_by_being_redefined(terms):
    """Un-banning needs no call of its own: a word that returns returns with a meaning,
    and the banned entry keeps its reason behind it forever."""
    terms.define_term("spike", "a bounded experiment")
    terms.retire_term("spike", BOTH, "we called it something else that week")
    assert terms.banned()

    terms.redefine_term("spike", "an executable experiment against a real dependency")
    assert terms.banned() == ()
    assert terms.history("spike")[0].ban_reason == "we called it something else that week"


# --- the lexical scan ---


def test_the_scan_finds_a_retired_word_in_prose(terms):
    terms.define_term("task", "the work of realising one component")
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings", use_instead="task")

    found = terms.violations({"text": "each component owns one responsibility"})
    assert [u.term for u in found] == ["component"]
    assert "say 'task'" in str(found[0])


def test_the_scan_reads_content_keys_as_identifiers(terms):
    """The two scopes map onto something real: a content key becomes a field name every
    reader types, and a value is prose."""
    terms.define_term("task", "the atomic unit of executable work")
    terms.define_term("packet", "the old word for a task")
    terms.retire_term("packet", IDENTIFIER, "our own coinage", use_instead="task")

    assert terms.violations({"packet_id": 3}) != ()
    assert terms.violations({"text": "he called it a packet at the time"}) == ()


def test_an_address_is_not_a_use_of_the_word(terms):
    """`components:15` cites a row. A plan whose tables are named for a retired word would
    otherwise warn on every citation, and a meter that cries wolf stops being read."""
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings")
    assert terms.violations({"text": "see components:15 for the surface"}) == ()


def test_the_scan_folds_the_plural_onto_the_word(terms):
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings")
    assert terms.violations({"text": "the components disagree"}) != ()


def test_nothing_retired_means_nothing_scanned(terms):
    terms.define_term("component", "a unit of the architecture")
    assert terms.violations({"text": "each component owns one responsibility"}) == ()


# --- warn at submission (delivery point 3) ---


def test_a_retired_word_is_mentioned_when_the_row_is_filed(rows, terms):
    terms.define_term("task", "the work of realising one component")
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings", use_instead="task")

    verdict = _row(rows, {"text": "each component owns one responsibility"})
    assert verdict.accepted is True
    assert "component" in verdict.note
    assert "task" in verdict.note


def test_the_row_still_stands(rows, terms):
    """Warn, never block. A retired word inside a quotation of the owner is legitimate,
    and refusing one would put the tool in the business of editing his words."""
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings")

    verdict = _row(rows, {"text": 'he said "the component is late"'})
    assert verdict.accepted is True
    assert verdict.ref is not None


def test_a_clean_row_carries_no_note(rows, terms):
    terms.define_term("task", "the work of realising one component")
    assert _row(rows, {"text": "each task owns one responsibility"}).note is None


def test_the_note_survives_an_idempotent_replay(rows, terms):
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings")
    batch = [RowSubmission(
        table="requirements", content={"text": "the component is late"}, name="late",
    )]

    first = rows.submit_rows(batch, "replay-me")
    again = rows.submit_rows(batch, "replay-me")
    assert again.replayed is True
    assert again.verdicts[0].note == first.verdicts[0].note


# --- the reserved table name (F38's lesson, applied) ---


def test_terms_is_not_a_plan_row_table(rows):
    """Deciding which store owns a word is half a fix; `plan_rows.table` is open by
    design, so without a refusal the collision returns as data."""
    verdict = _row(rows, {"term": "package"}, name="package")
    receipt = rows.submit_rows(
        [RowSubmission(table="terms", content={"term": "package"}, name="package")],
        "reserved",
    )
    assert receipt.verdicts[0].accepted is False
    assert "define_term" in receipt.verdicts[0].problem
    assert verdict.accepted is True


# --- count at the gate (delivery point 3, the other half) ---


def test_the_gate_warns_about_rows_written_before_the_word_was_retired(
    rows, terms, gate
):
    """The case submission cannot catch, and the common one: a word is retired *because*
    the plan has been using it two ways, so the rows carrying it are already filed."""
    _row(rows, {"text": "each component owns one responsibility"}, name="responsibility")
    terms.define_term("task", "the work of realising one component")
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings", use_instead="task")

    result = gate.run_gate(1)
    retired = [w for w in result.warnings if w.kind == "retired_term"]
    assert len(retired) == 1
    assert "component" in retired[0].message
    assert result.passed is not None  # a warning never decides the verdict


def test_the_warning_settles_when_the_word_comes_back(rows, terms, gate):
    _row(rows, {"text": "each component owns one responsibility"}, name="responsibility")
    terms.define_term("component", "the old word for a task")
    terms.retire_term("component", PROSE, "one entity, two spellings")
    gate.run_gate(1)

    terms.redefine_term("component", "a unit of the architecture, and a fine word")
    gate.run_gate(1)
    assert [w for w in gate.warnings.active_warnings() if w.kind == "retired_term"] == []


# --- the export (delivery point 1) ---


def test_the_export_publishes_the_words_and_the_bans(terms, rows, store):
    ref = _row(rows, {"text": "packages are declared"}, name="packages are declared").ref
    terms.define_term("package", "a declared grouping of tasks", names_ref=ref)
    terms.define_term("milestone", "the old word for a package")
    terms.retire_term(
        "milestone", BOTH, "never an entity, only a phrase", use_instead="package",
    )

    receipt = terms.export_glossary()
    payload = json.loads((store.workspace / "glossary.json").read_text(encoding="utf-8"))

    assert receipt.terms == 2
    assert receipt.banned == 1
    assert payload["banned"] == [{
        "term": "milestone",
        "scope": BOTH,
        "reason": "never an entity, only a phrase",
        "use_instead": "package",
    }]
    assert payload["terms"][1]["names"] == {
        "ref": str(ref), "name": "packages are declared",
    }


def test_the_export_names_the_row_a_word_names(terms, store):
    """A manifest carrying a bare address hands its reader the lookup this design
    removed. With no row service to ask, it says so rather than inventing a name."""
    bare = TermService(store)
    bare.define_term("package", "a declared grouping", names_ref="requirements:1")
    bare.export_glossary()
    payload = json.loads((store.workspace / "glossary.json").read_text(encoding="utf-8"))
    assert payload["terms"][0]["names"] == {"ref": "requirements:1", "name": None}


# --- the glossary reaches the writer (delivery point 2) ---


def test_the_brief_carries_the_glossary_outside_the_accounting(briefs, tasks, rows, terms):
    """A candidate row is context and may be waived with a reason; a glossary is a
    constraint on the output and cannot be, or it is not a constraint. So it arrives as a
    section of its own, and `audit_brief` never counts it."""
    from engine.briefs import BriefSelection  # noqa: PLC0415

    rows.submit_rows(
        [RowSubmission(
            table="contracts",
            content={"title": "the contract", "behaviours": ["does the thing"]},
            name="the contract",
        )],
        "contract",
    )
    tasks.finalize_plan()
    tasks.serve_brief(1)
    terms.define_term("package", "a declared grouping of tasks")

    candidates = briefs._candidates(tasks.get(1))
    brief = briefs.compose_brief(
        1, BriefSelection(included=tuple(ref for ref, _ in candidates))
    )
    assert [t.term for t in brief.glossary] == ["package"]
    audit = briefs.audit_brief(brief.id)
    assert audit.candidates == len(candidates)


def test_the_glossary_in_a_brief_is_the_one_in_force_now(briefs, tasks, rows, terms):
    """The mirror of F26, not a repeat of it. F26 froze the candidate closure because an
    *accounting* measured against a moving set is meaningless. A constraint is the other
    case: it binds as it stands, and a brief serving last week's vocabulary would enforce
    a rule the plan has since retired."""
    from engine.briefs import BriefSelection  # noqa: PLC0415

    rows.submit_rows(
        [RowSubmission(
            table="contracts",
            content={"title": "the contract", "behaviours": ["does the thing"]},
            name="the contract",
        )],
        "contract",
    )
    tasks.finalize_plan()
    tasks.serve_brief(1)
    candidates = briefs._candidates(tasks.get(1))
    brief = briefs.compose_brief(
        1, BriefSelection(included=tuple(ref for ref, _ in candidates))
    )
    assert brief.glossary == ()

    terms.define_term("package", "a declared grouping of tasks")
    assert [t.term for t in briefs.get(brief.id).glossary] == ["package"]


# --- migration ---


def test_a_store_written_before_the_glossary_migrates_to_an_empty_one(store):
    """The migration is honest because the answer is true: a plan that predates the
    glossary has an empty one. That is what distinguishes it from the 2 -> 3 bump, which
    would have had to invent a name for every finding."""
    store.conn.execute("DROP TABLE terms")
    store.conn.execute("UPDATE plan SET schema_version = 3 WHERE guard = 1")
    store.conn.commit()

    report = store.migrate(4)
    assert report.from_version == 3
    assert report.to_version == 4
    assert TermService(store).glossary() == ()
    assert TermService(store).define_term("package", "a declared grouping").id == 1


def test_a_migration_with_no_path_is_still_refused(store):
    from engine.storage import MigrationFailed

    with pytest.raises(MigrationFailed):
        store.migrate(99)


# --- the interview asks for the words (D23, the owner's replacement for a count) ---


def test_the_owner_is_asked_for_the_words_once_the_plan_has_content(gaps, rows):
    """Not a count of how often a word appears — the owner killed that on sight, and was
    right: the line between a load-bearing word and ordinary English is a judgment. The
    planner names the words; this makes sure the owner is asked at all."""
    assert [g.rule_key for g in gaps.open_gaps() if g.rule_key == "no_glossary"] == []

    rows.submit_rows(
        [RowSubmission(table="use_cases", content={"title": "settle a widget"},
                       name="settle a widget")],
        "uc",
    )
    asked = [g for g in gaps.open_gaps() if g.rule_key == "no_glossary"]
    assert len(asked) == 1
    assert "define_term" in asked[0].ask


def test_the_question_stops_once_any_word_is_defined(gaps, rows, store):
    rows.submit_rows(
        [RowSubmission(table="use_cases", content={"title": "settle a widget"},
                       name="settle a widget")],
        "uc",
    )
    TermService(store).define_term("widget", "the thing that settles")
    assert [g for g in gaps.open_gaps() if g.rule_key == "no_glossary"] == []


def test_an_unsettled_definition_is_an_open_question_for_the_owner(gaps, store):
    """The same shape as an assumed-intent row: it carries the planner's best answer, it
    is visible as unsettled, and only the owner can close it."""
    terms = TermService(store)
    terms.define_term("widget", "the thing that settles")
    gap = [g for g in gaps.open_gaps() if g.rule_key == "unsettled_term"][0]
    assert "widget" in gap.ask
    assert "the thing that settles" in gap.ask
    assert "approve_term" in gap.ask

    terms.approve_term("widget")
    assert [g for g in gaps.open_gaps() if g.rule_key == "unsettled_term"] == []


def test_the_question_survives_the_definition_being_rewritten(gaps, store):
    """Keyed on the word, which is this table's identity everywhere else — so a dismissal
    does not silently detach when the entry behind it is superseded."""
    terms = TermService(store)
    terms.define_term("widget", "the thing that settles")
    first = [g for g in gaps.open_gaps() if g.rule_key == "unsettled_term"][0]
    terms.redefine_term("widget", "the thing that settles, within 40 ms")
    again = [g for g in gaps.open_gaps() if g.rule_key == "unsettled_term"][0]
    assert again.key == first.key
