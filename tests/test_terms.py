"""The plan's glossary (DEVIATIONS.md D23) — a table the owner owns.

**Six tests survive v3 change 4 unchanged**, and they are the ones whose subject survived:
`test_a_word_cannot_be_defined_twice`, `test_a_term_needs_a_definition`,
`test_redefining_a_word_nobody_defined_says_so`, `test_terms_is_not_a_plan_row_table`,
`test_a_store_written_before_the_glossary_migrates_to_an_empty_one` and
`test_a_migration_with_no_path_is_still_refused`. Everything else went with the machinery it
tested — approval, the banned list, the lexical scan, the definition lineage, the export
manifest, the two gap rules and the brief's glossary section.

Most of them would have failed loudly whatever anyone did, and the mechanism that guarantees
it is the import line above: this module used to name `BOTH`, `IDENTIFIER`, `PROSE`,
`AlreadyApproved` and `BanNeedsReason`, so the file could not even be collected once those
were gone. Two would **not** have failed loudly and are deleted deliberately — see
`test_labels.py`'s note on checks that cannot fail.
"""

import pytest

from engine.models import RowSubmission
from engine.terms import (
    AmbiguousRemoval,
    DefinitionRequired,
    TermExists,
    TermInUse,
    TermNotFound,
    TermService,
)


@pytest.fixture
def terms(store):
    return TermService(store)


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


# --- defining and redefining ---


def test_a_term_records_what_a_word_means(terms):
    term = terms.define_term("stage", "an ordered step of the interview")
    assert term.term == "stage"
    assert terms.find("Stage").definition == "an ordered step of the interview"


def test_a_word_cannot_be_defined_twice(terms):
    """Kept as a refusal **by decision** rather than by inheritance. The owner ruled for two
    calls on 2026-07-30 — "there should be a tool to create terms and a tool to edit
    (redefine) them" — and the argument for merging them into one upsert is otherwise good
    enough that it would be made again."""
    terms.define_term("stage", "an ordered step of the interview")
    with pytest.raises(TermExists) as exc:
        terms.define_term("Stage", "something else")
    assert "redefine_term" in str(exc.value)


def test_a_term_needs_a_definition(terms):
    """A word listed with no meaning beside it is a word two readers read two ways — the
    failure this table exists to prevent, arriving through the table itself."""
    with pytest.raises(DefinitionRequired):
        terms.define_term("stage", "   ")


def test_redefining_changes_the_meaning_in_place(terms):
    """One row, same id, same `created_at`, changed `updated_at`.

    It was a supersession until v3 change 4 — stamp the old row, write a new one — and all
    of that existed to keep a definition's history. Nothing cites a definition, which is
    change 3's settled ground for purpose lines, so there is no argument resting on the
    wording it had last week.
    """
    first = terms.define_term("stage", "an ordered step")
    second = terms.redefine_term("stage", "an ordered step of the interview")
    assert second.id == first.id
    assert second.created_at == first.created_at
    assert second.updated_at >= first.updated_at
    assert second.definition == "an ordered step of the interview"
    assert len(terms.glossary()) == 1


def test_redefining_a_word_nobody_defined_says_so(terms):
    with pytest.raises(TermNotFound) as exc:
        terms.redefine_term("stage", "an ordered step")
    assert "define_term" in str(exc.value)


def test_redefining_needs_a_definition_too(terms):
    terms.define_term("stage", "an ordered step")
    with pytest.raises(DefinitionRequired):
        terms.redefine_term("stage", "")


def test_the_glossary_is_alphabetical(terms):
    terms.define_term("stage", "an ordered step")
    terms.define_term("behaviour", "one dischargeable commitment of a contract")
    terms.define_term("label", "a glossary word attached to rows")
    assert [t.term for t in terms.glossary()] == ["behaviour", "label", "stage"]


# --- removing ---


def test_removing_an_unused_word_deletes_it(terms):
    terms.define_term("stage", "an ordered step")
    terms.remove_term("stage")
    assert terms.glossary() == ()
    assert terms.find("stage") is None


def test_removing_a_word_nobody_defined_says_so(terms):
    with pytest.raises(TermNotFound):
        terms.remove_term("stage")


def test_removing_a_word_in_use_refuses_and_names_both_counts(terms, labels, rows):
    """The refusal **is** the prompt — this engine has no other way to ask a question — so
    it carries what the owner needs in order to answer: not that the word is in use, but how
    widely, split by population.

    **Two counts, never their sum.** A word on three rows and a word on four hundred are
    different decisions, and a total hides which one this is. The fixture makes the two
    counts differ, so a summed count would pass neither assertion.
    """
    _row(rows, {"text": "a"}, name="one")
    _row(rows, {"text": "b"}, name="two", key="k2")
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1", "requirements:2"])

    with pytest.raises(TermInUse) as exc:
        terms.remove_term("engine")
    assert exc.value.detail["rows"] == 2
    assert exc.value.detail["tasks"] == 0
    assert "2 plan row(s)" in str(exc.value) and "0 task(s)" in str(exc.value)
    assert terms.find("engine") is not None, "the word must still be there"


def test_a_replacement_moves_every_attachment_and_removes_the_word(terms, labels, rows):
    _row(rows, {"text": "a"}, name="one")
    _row(rows, {"text": "b"}, name="two", key="k2")
    terms.define_term("engine", "the planning engine")
    terms.define_term("component", "a unit of the design")
    labels.attach_label("engine", ["requirements:1", "requirements:2"])

    terms.remove_term("engine", replacement="component")
    assert terms.find("engine") is None
    report = labels.labels("component")
    assert report.usages[0].row_count == 2
    assert [str(t.ref) for t in report.targets] == ["requirements:1", "requirements:2"]


def test_a_target_already_carrying_the_replacement_collapses(terms, labels, rows):
    """Moving `part` to `component` on a row that already carries `component` is two live
    attachments for one pair, which the unique index refuses — aborting the whole
    transaction, so a single already-tagged row would make the entire replacement fail."""
    _row(rows, {"text": "a"}, name="one")
    _row(rows, {"text": "b"}, name="two", key="k2")
    terms.define_term("part", "the old word")
    terms.define_term("component", "the word we use")
    labels.attach_label("part", ["requirements:1", "requirements:2"])
    labels.attach_label("component", ["requirements:1"])

    terms.remove_term("part", replacement="component")
    report = labels.labels("component")
    assert report.usages[0].row_count == 2
    assert len(report.targets) == 2, "the duplicate collapsed rather than raising"


def test_a_detached_attachment_keeps_pointing_at_the_dead_word(terms, labels, rows):
    """It is the record that the label was once there, so rewriting it to the replacement
    would falsify that record and deleting it would destroy it. This is also why
    `label_attachments.word` carries no foreign key to `terms`."""
    _row(rows, {"text": "a"}, name="one")
    _row(rows, {"text": "b"}, name="two", key="k2")
    terms.define_term("part", "the old word")
    terms.define_term("component", "the word we use")
    labels.attach_label("part", ["requirements:1", "requirements:2"])
    labels.detach_label("part", ["requirements:2"])

    terms.remove_term("part", replacement="component")
    dead = [
        a for a in labels._attachments("part", live_only=False) if not a.is_live
    ]
    assert len(dead) == 1
    assert str(dead[0].target_root) == "requirements:2"


def test_take_it_off_everything_is_an_allowed_answer(terms, labels, rows):
    """The owner's ruling of 2026-07-30, in his words: "yes to take it off everything". It
    is opt-in and explicit; the alternative — deletion blocked until he detaches by hand —
    would mean peeling a filter he has decided is wrong off forty rows before he is allowed
    to say so."""
    _row(rows, {"text": "a"}, name="one")
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1"])

    terms.remove_term("engine", detach_all=True)
    assert terms.find("engine") is None
    assert labels._attachments("engine") == ()
    assert len(labels._attachments("engine", live_only=False)) == 1


def test_a_replacement_and_detach_all_together_are_refused(terms, labels, rows):
    _row(rows, {"text": "a"}, name="one")
    terms.define_term("engine", "the planning engine")
    terms.define_term("component", "a unit of the design")
    labels.attach_label("engine", ["requirements:1"])
    with pytest.raises(AmbiguousRemoval):
        terms.remove_term("engine", replacement="component", detach_all=True)


def test_a_word_cannot_replace_itself(terms):
    terms.define_term("engine", "the planning engine")
    with pytest.raises(AmbiguousRemoval):
        terms.remove_term("engine", replacement="Engine")


def test_a_replacement_is_validated_even_when_nothing_is_attached(terms):
    """A replacement that names no term is a mistake whether or not this word happens to be
    carried, and accepting it silently would teach the caller it was fine."""
    terms.define_term("engine", "the planning engine")
    with pytest.raises(TermNotFound) as exc:
        terms.remove_term("engine", replacement="nosuchword")
    assert "define_term" in str(exc.value)
    assert terms.find("engine") is not None


# --- the store's op vocabulary ---


def test_delete_is_refused_against_any_other_table(store):
    """`Storage` gained one op kind for one table, and the narrowness is the guard. Plan
    history is append-only because a superseded row records what the plan used to say; a
    later change that wants to delete from somewhere else has to argue for it in its own
    words rather than inherit permission from here.

    Broken deliberately rather than trusted: a guard nobody has watched fail is a guard
    nobody knows works.
    """
    from engine.storage import Op

    with pytest.raises(ValueError) as exc:
        store.write_atomic(
            [Op("delete", "plan_rows", {}, where={"id": 1})], "delete-plan-rows"
        )
    assert "append-only" in str(exc.value)


def test_removing_a_word_is_announced_to_the_change_feed(terms, store):
    """A watching GUI re-fetches the row a `ref` names, and there is now nothing there to
    fetch — so a deletion that recorded nothing would leave a removed word on screen until
    the next full reload."""
    term = terms.define_term("engine", "the planning engine")
    terms.remove_term("engine")
    feed = store.query("SELECT op_type, ref FROM change_log ORDER BY seq")
    assert (feed[-1]["op_type"], feed[-1]["ref"]) == ("delete", f"terms:{term.id}")


# --- the reserved table name (F38's lesson, applied) ---


def test_terms_is_not_a_plan_row_table(rows):
    """Deciding which store owns a word is half a fix; `plan_rows.table` is open by
    design, so without a refusal the collision returns as data.

    The reservation survives v3 change 4; the *reason* in its text did not. It argued that
    the glossary is a real table because redefinition and replacement are two relations that
    supersession collapses into one — and after that change a redefinition is an `UPDATE`, a
    replacement is a parameter of the delete, and supersession is gone from this table.
    """
    verdict = _row(rows, {"term": "stage"}, name="stage")
    receipt = rows.submit_rows(
        [RowSubmission(table="terms", content={"term": "stage"}, name="stage")],
        "reserved",
    )
    assert receipt.verdicts[0].accepted is False
    assert "define_term" in receipt.verdicts[0].problem
    assert verdict.accepted is True


# --- what 4C removed, asserted positively ---
#
# The draft's entire coverage of packet 4C was one line saying *no test asserts* the deleted
# things — a statement about the repository rather than code that executes. Nineteen
# behaviours across six modules had nothing that would fail if a builder simply kept them.


def test_a_submitted_row_carries_no_vocabulary_note(rows, terms):
    """`rows.py`'s submission scan is gone with `_vocabulary_note`. Asserted against a row
    whose content would have tripped the old scan, so the check has something to catch."""
    terms.define_term("component", "a unit of the design")
    verdict = _row(rows, {"text": "each component owns one responsibility"}, name="one")
    assert verdict.accepted is True
    assert verdict.note is None
    assert not hasattr(rows, "terms")
    assert not hasattr(rows, "_vocabulary_note")


def test_the_gate_no_longer_scans_for_retired_words(rows, terms, gate):
    """`gates.py`'s `_retired_words` and its `RETIRED_TERM` import are gone. The import is
    the one that would have taken the whole suite down rather than the glossary tests."""
    import engine.warnings as warnings_module

    _row(rows, {"text": "each component owns one responsibility"}, name="one")
    terms.define_term("component", "a unit of the design")
    assert not hasattr(gate, "_retired_words")
    assert not hasattr(gate, "terms")
    assert not hasattr(warnings_module, "RETIRED_TERM")
    assert "retired_term" not in warnings_module.SETTLEABLE_KINDS
    assert all(w.kind != "retired_term" for w in gate.run_gate(1).warnings or [])


def test_the_gap_engine_has_no_glossary_rules(gaps, rows, store):
    """Both rules go on the owner's instruction — "forget you prompting the user, it's
    another friction point" — and `live_warning_keys` loses its violations branch, which is
    the F50 reconciliation method rather than a rule."""
    _row(rows, {"text": "a"}, name="one")
    assert not hasattr(gaps, "terms")
    assert not hasattr(gaps, "_rule_no_glossary")
    assert not hasattr(gaps, "_rule_unsettled_term")
    assert all(
        g.rule_key not in ("no_glossary", "unsettled_term") for g in gaps.open_gaps()
    )
    assert all(not k.startswith("term:") for k in gaps.live_warning_keys())


def test_the_loadable_revisions_declare_no_glossary_rules():
    """Stripped from every loadable revision and not only the newest. `gaps.py` implements
    neither type now, so a plan on an older revision would raise on its first derive, and
    `unsettled_term`'s ask named a tool the registry can no longer resolve."""
    from engine.methodology import DEFAULT_REVISION, EARLIEST_LOADABLE_REVISION, load

    for revision in range(EARLIEST_LOADABLE_REVISION, DEFAULT_REVISION + 1):
        types = {rule.type for rule in load(revision).rules}
        assert not types & {"no_glossary", "unsettled_term"}, revision
        assert "approve_term" not in load(revision).read("mandate.md")


def test_the_digest_says_nothing_about_the_glossary(store, rows, terms):
    """The count, the awaiting-approval line, and the "No agreed terms yet" line all go.
    That last one is the one a builder wants to keep, because it reads as onboarding rather
    than as a nag — and it is the mechanical prompt the owner struck, firing on exactly the
    plans where he had not yet decided he wanted a glossary.

    Asserted on a plan **with no terms**, which is the state that produced the line.
    """
    from engine.gaps import GapEngine
    from engine.guidance import Guidance
    from engine.resume import ResumeService
    from engine.warnings import WarningService

    resume = ResumeService(
        store, gaps=GapEngine(store, rows), warnings=WarningService(store),
        guidance=Guidance(),
    )
    text = resume.plan_status().present()
    assert "term" not in text.lower()
    assert "glossar" not in text.lower()
    assert not hasattr(resume, "terms")


def test_a_brief_carries_no_glossary(briefs, tasks, rows, terms):
    """The owner's reasoning, which is better than the one the module carried: "the brief
    idea is dumb, you don't build it until the plan is finished, but you need the glossary
    context during the plan." The brief is served after finalization; naming drift happens
    while the rows are being written."""
    from engine.briefs import Brief

    terms.define_term("stage", "an ordered step")
    assert "glossary" not in {f for f in Brief.__dataclass_fields__}
    assert not hasattr(briefs, "terms")


# --- migration (the 3 -> 4 branch, now on its own frozen text) ---


def test_a_store_written_before_the_glossary_migrates_to_an_empty_one(store):
    """The migration is honest because the answer is true: a plan that predates the
    glossary has an empty one. That is what distinguishes it from the 2 -> 3 bump, which
    would have had to invent a name for every finding.

    Since v3 change 4 this exercises `storage._TERMS_DDL_AT_4` rather than
    `schema.TERMS_DDL`: a migration is a point-in-time step and must name a point-in-time
    text, or a store climbing from 3 would be handed today's five-column table and then
    asked at 10 -> 11 to drop columns it never had.
    """
    store.conn.execute("DROP TABLE terms")
    store.conn.execute("UPDATE plan SET schema_version = 3 WHERE guard = 1")
    store.conn.commit()

    report = store.migrate(4)
    assert report.from_version == 3
    assert report.to_version == 4
    columns = {r[1] for r in store.conn.execute("PRAGMA table_info(terms)")}
    assert {"approved_at", "ban_scope", "superseded_at"} <= columns, (
        "the 3 -> 4 step must create the table schema 4 actually had"
    )
    assert TermService(store).glossary() == ()
    assert TermService(store).define_term("stage", "an ordered step").id == 1


def test_a_migration_with_no_path_is_still_refused(store):
    from engine.storage import MigrationFailed

    with pytest.raises(MigrationFailed):
        store.migrate(99)
