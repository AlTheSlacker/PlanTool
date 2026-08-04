"""Labels — a glossary term attached to plan rows and tasks (v3 D12, as amended).

**Every count and every emptiness assertion here carries a positive control**: a fixture the
assertion demonstrably fails against. This repository's own idiom is
`test_the_check_can_actually_fail`, and the standing evidence is a check that ran green
while seeing four names where there were twenty-two.

It is not a formality. The draft of this packet asserted emptiness three times — an unknown
word, a typo, and the implied negatives — all of which a filter returning nothing for every
input satisfies; its "returned once" case filtered on a single label, so no row could have
duplicated; and its two-count refusal had no fixture where the two counts differed, so a
summed count would have passed the rule that exists to forbid summing.
"""

import pytest

from engine.errors import InvalidSelector, RowNotFound
from engine.labels import InvalidTarget
from engine.models import RowSelector, RowSubmission
from engine.terms import TermNotFound


@pytest.fixture
def terms(store):
    from engine.terms import TermService

    return TermService(store)


def _rows(rows, count, table="requirements"):
    rows.submit_rows(
        [
            RowSubmission(table=table, content={"t": str(n)}, name=f"row {n}")
            for n in range(1, count + 1)
        ],
        f"batch:{table}:{count}",
    )
    return [f"{table}:{n}" for n in range(1, count + 1)]


def _task(store, task_id, title="a task"):
    store.conn.execute(
        "INSERT INTO tasks (id, contract_ref, title, state, serve_epoch, created_at, "
        "updated_at) VALUES (?, ?, ?, 'pending', 0, 'now', 'now')",
        (task_id, f"contracts:{task_id}", title),
    )
    store.conn.commit()
    return task_id


# --- the glossary's one mechanical use ---


def test_a_label_must_be_a_live_term(labels, terms, rows):
    _rows(rows, 1)
    with pytest.raises(TermNotFound) as exc:
        labels.attach_label("engine", ["requirements:1"])
    assert "define_term" in str(exc.value)

    terms.define_term("engine", "the planning engine")
    assert len(labels.attach_label("engine", ["requirements:1"])) == 1, (
        "the positive control: the same call succeeds once the word is defined, so the "
        "refusal above is about the term and not about the target"
    )


def test_a_repeat_attach_is_a_no_op_and_duplicates_in_one_call_collapse(
    labels, terms, rows
):
    """Service-side guards, with the index as the backstop rather than the mechanism: a
    unique index does not produce a no-op, it raises and aborts the batch — so one
    already-labelled row in a batch of ten would take the other nine with it."""
    _rows(rows, 2)
    terms.define_term("engine", "the planning engine")
    first = labels.attach_label("engine", ["requirements:1"])
    again = labels.attach_label("engine", ["requirements:1", "requirements:2"])
    assert [a.id for a in first] == [again[0].id]
    assert len(again) == 2

    collapsed = labels.attach_label("engine", ["requirements:1", "requirements:1"])
    assert len(collapsed) == 2, "a duplicate within one call did not add a second row"


def test_a_bool_does_not_read_as_task_one(labels, terms, rows, store):
    """`bool` subclasses `int`, so `isinstance(True, int)` is `True` and a naive test would
    attach to whatever task holds id 1. One line for a defect that is invisible until a
    caller passes a flag."""
    _task(store, 1)
    terms.define_term("engine", "the planning engine")
    with pytest.raises(InvalidTarget):
        labels.attach_label("engine", [True])
    assert labels.labels("engine").usages[0].task_count == 0

    labels.attach_label("engine", [1])
    assert labels.labels("engine").usages[0].task_count == 1, (
        "the positive control: a real task id does attach, so the refusal was about `bool`"
    )


def test_an_unknown_target_is_refused_rather_than_written(labels, terms, rows):
    """`lineage_root` refuses nothing — a row that does not exist and a row with no parent
    take the same branch and both return the input ref — so without an explicit existence
    check this would write an attachment to a target that has never existed and that nothing
    would ever clean up, neither target column carrying a foreign key."""
    _rows(rows, 1)
    terms.define_term("engine", "the planning engine")
    with pytest.raises(RowNotFound):
        labels.attach_label("engine", ["requirements:99"])
    with pytest.raises(InvalidTarget):
        labels.attach_label("engine", [404])
    assert labels.labels("engine").usages[0].row_count == 0


def test_a_word_is_normalised(labels, terms, rows):
    _rows(rows, 1)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("  Engine  ", ["requirements:1"])
    assert labels.labels().usages[0].word == "engine"


# --- detaching ---


def test_detaching_stamps_rather_than_deletes(labels, terms, rows, store):
    _rows(rows, 1)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1"])
    labels.detach_label("engine", ["requirements:1"])
    assert labels.labels("engine").usages[0].row_count == 0
    assert len(store.query("SELECT * FROM label_attachments")) == 1
    assert store.query("SELECT detached_at FROM label_attachments")[0]["detached_at"]


def test_detaching_something_unattached_is_a_no_op(labels, terms, rows):
    _rows(rows, 2)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1"])
    assert len(labels.detach_label("engine", ["requirements:2"])) == 1


def test_attach_detach_reattach_leaves_the_label_on(labels, terms, rows, store):
    """The replay hazard that produces **wrong data** rather than a loud failure.

    The key must carry the act's own name — without it, `attach_label(w, refs)` and
    `detach_label(w, refs)` derive the same key and `Storage.replay` swallows the second as
    a replay of the first.

    It must also distinguish the *third* call from the first, and **the specification's fix
    for that does not work**: it said to carry the resolved live set, and after attach →
    detach the live set is empty again, so the re-attach re-derives the first attach's key
    exactly. Current state cannot tell the two apart; history can. The key carries the
    word's total attachment count, which detaching never reduces because detaching stamps
    rather than deletes. See `LabelService._key`.
    """
    _rows(rows, 1)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1"])
    labels.detach_label("engine", ["requirements:1"])
    assert labels.labels("engine").usages[0].row_count == 0, (
        "the detach was swallowed as a replay of the attach"
    )
    labels.attach_label("engine", ["requirements:1"])
    assert labels.labels("engine").usages[0].row_count == 1, (
        "the re-attach was swallowed as a replay of the first attach"
    )


# --- the report ---


def test_the_report_carries_two_denominators_that_differ(labels, terms, rows, store):
    """The half a builder drops, because a count reads as complete on its own. It is not: a
    label on all 687 rows and a label on one are both useless for filtering.

    The fixture makes the two counts and the two denominators all differ, so a summed count
    or a shared denominator fails rather than passing by coincidence.
    """
    _rows(rows, 3)
    _task(store, 1)
    _task(store, 2, "another task")
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1", "requirements:2", 1])

    report = labels.labels()
    usage = report.usages[0]
    assert (usage.row_count, usage.task_count) == (2, 1)
    assert (report.live_rows, report.live_tasks) == (3, 2)
    assert usage.row_count != usage.task_count
    assert report.live_rows != report.live_tasks


def test_the_report_is_alphabetical_from_an_out_of_order_fixture(labels, terms, rows):
    _rows(rows, 1)
    for word in ("stage", "engine", "label"):
        terms.define_term(word, f"what {word} means")
        labels.attach_label(word, ["requirements:1"])
    assert [u.word for u in labels.labels().usages] == ["engine", "label", "stage"]


def test_a_named_word_with_no_attachment_reports_zero_not_missing(labels, terms, rows):
    """Reporting it as missing would tell the planner the word is free, which is the moment
    they define it again — and `define_term` would refuse it as a duplicate, so the report
    would have walked them into a refusal."""
    _rows(rows, 1)
    terms.define_term("engine", "the planning engine")
    report = labels.labels("engine")
    assert [(u.word, u.row_count, u.task_count) for u in report.usages] == [
        ("engine", 0, 0)
    ]


def test_the_report_counts_terms_nothing_carries(labels, terms, rows):
    _rows(rows, 1)
    terms.define_term("engine", "the planning engine")
    terms.define_term("stage", "an ordered step")
    assert labels.labels().unattached_terms == 2
    labels.attach_label("engine", ["requirements:1"])
    assert labels.labels().unattached_terms == 1


def test_naming_a_word_lists_what_carries_it_with_names(labels, terms, rows, store):
    """Convention 9: an address never travels alone. A report listing `requirements:1` hands
    its reader the lookup this whole design exists to remove."""
    _rows(rows, 2)
    _task(store, 1, "build the door")
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1", 1])

    targets = labels.labels("engine").targets
    assert {(t.kind, t.name) for t in targets} == {
        ("row", "row 1"), ("task", "build the door")
    }
    assert str(next(t.ref for t in targets if t.kind == "row")) == "requirements:1"


# --- the filter ---


def test_the_and_is_exclusive(labels, terms, rows):
    """The test that fails if the query is ever written as OR: one row carries `engine`
    alone, one carries `schema` alone, and one carries both."""
    _rows(rows, 3)
    for word in ("engine", "schema"):
        terms.define_term(word, f"what {word} means")
    labels.attach_label("engine", ["requirements:1", "requirements:3"])
    labels.attach_label("schema", ["requirements:2", "requirements:3"])

    found = [str(r.ref) for r in rows.read_rows(
        RowSelector(labels=("engine", "schema"))
    ).rows]
    assert found == ["requirements:3"]


def test_a_superset_of_the_requested_labels_still_matches(labels, terms, rows):
    _rows(rows, 1)
    for word in ("engine", "schema", "door"):
        terms.define_term(word, f"what {word} means")
        labels.attach_label(word, ["requirements:1"])
    found = [str(r.ref) for r in rows.read_rows(
        RowSelector(labels=("engine", "schema"))
    ).rows]
    assert found == ["requirements:1"]


def test_a_typo_returns_nothing_not_the_real_label_s_rows(labels, terms, rows):
    """It will look like a bug and it is what AND means. Two of the three ways to get an
    empty page from this filter are input mistakes, and only the third is a real answer."""
    _rows(rows, 2)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1"])
    assert rows.read_rows(RowSelector(labels=("engine", "schemer"))).rows == ()
    assert len(rows.read_rows(RowSelector(labels=("engine",))).rows) == 1, (
        "the positive control: the same fixture returns a row for the label that exists"
    )


def test_an_unknown_word_returns_an_empty_page_rather_than_raising(labels, rows):
    _rows(rows, 2)
    page = rows.read_rows(RowSelector(labels=("nosuchword",)))
    assert page.rows == () and page.total == 0
    assert len(rows.read_rows(RowSelector()).rows) == 2, (
        "the positive control: the unfiltered page is not empty"
    )


def test_a_repeated_word_matches_the_same_rows_as_one(labels, terms, rows):
    """`("engine", "engine")` would set the HAVING count to two while the query can only
    ever reach one, so the filter would silently match nothing because the caller repeated a
    word."""
    _rows(rows, 2)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1"])
    doubled = rows.read_rows(RowSelector(labels=("engine", "engine")))
    single = rows.read_rows(RowSelector(labels=("engine",)))
    assert [str(r.ref) for r in doubled.rows] == [str(r.ref) for r in single.rows] == [
        "requirements:1"
    ]


def test_case_collapses_rather_than_guaranteeing_an_empty_page(labels, terms, rows):
    _rows(rows, 1)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1"])
    assert len(rows.read_rows(RowSelector(labels=("Engine", "engine"))).rows) == 1


def test_a_bare_string_is_refused(labels, terms, rows):
    """The same class of trap as `isinstance(True, int)` and worse, because it fails
    quietly: a `str` **is** a sequence of `str`, so `labels="engine"` iterates to four
    distinct characters after dedupe, none of which is a term, and the page comes back empty
    and correct-looking."""
    _rows(rows, 1)
    with pytest.raises(InvalidSelector) as exc:
        rows.read_rows(RowSelector(labels="engine"))
    assert "tuple" in str(exc.value) or "('engine',)" in str(exc.value)


def test_an_empty_labels_tuple_is_not_a_filter(labels, rows):
    _rows(rows, 2)
    assert len(rows.read_rows(RowSelector(labels=())).rows) == 2


def test_a_label_survives_supersession_and_still_finds_the_live_row(labels, terms, rows):
    """The whole reason attachments key on lineage roots. Keyed on the ref, this label would
    detach silently the first time the row it was put on was reworded — which is exactly
    when the person who filed it would want it."""
    _rows(rows, 1)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1"])
    rows.supersede_row(
        "requirements:1",
        RowSubmission(table="requirements", content={"t": "reworded"}, name="row 1b"),
        "the first wording was wrong",
        "supersede-1",
    )
    rows.supersede_row(
        "requirements:2",
        RowSubmission(table="requirements", content={"t": "again"}, name="row 1c"),
        "and again",
        "supersede-2",
    )
    found = [str(r.ref) for r in rows.read_rows(RowSelector(labels=("engine",))).rows]
    assert found == ["requirements:3"], "the live head of the labelled lineage"
    page = rows.read_rows(RowSelector(live_only=True))
    assert page.labels[next(r.ref for r in page.rows)] == ("engine",)


def test_the_filter_composes_with_other_dimensions_and_returns_a_row_once(
    labels, terms, rows
):
    """A join against a one-to-many table duplicates rows, and a row carrying two matching
    attachments is the case that would show it."""
    _rows(rows, 2)
    _rows(rows, 1, table="entities")
    for word in ("engine", "schema"):
        terms.define_term(word, f"what {word} means")
        labels.attach_label(word, ["requirements:1", "entities:1"])

    page = rows.read_rows(RowSelector(labels=("engine", "schema"), table="requirements"))
    assert [str(r.ref) for r in page.rows] == ["requirements:1"]
    assert page.total == 1
    assert len(rows.read_rows(RowSelector(labels=("engine", "schema"))).rows) == 2, (
        "the positive control: without the table dimension both rows come back"
    )


def test_total_and_paging_are_computed_over_the_filtered_set(labels, terms, rows):
    """`total` computed before the filter reports a page count for a different query, and
    `limit` applied before it returns short pages that look like the end of the results. The
    fixture is larger than one page, or it asserts nothing about either."""
    refs = _rows(rows, 7)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", refs[:5])

    first = rows.read_rows(RowSelector(labels=("engine",), limit=2))
    assert first.total == 5 and len(first.rows) == 2 and first.has_more
    second = rows.read_rows(RowSelector(labels=("engine",), limit=2, offset=4))
    assert second.total == 5 and len(second.rows) == 1 and not second.has_more


def test_a_page_over_the_ceiling_is_refused_by_name(rows):
    with pytest.raises(InvalidSelector) as exc:
        rows.read_rows(RowSelector(limit=50_000))
    assert exc.value.detail["field"] == "limit"


# --- the labels on a page ---


def test_a_page_carries_every_row_s_labels_alphabetically(labels, terms, rows):
    _rows(rows, 2)
    for word in ("stage", "engine", "door"):
        terms.define_term(word, f"what {word} means")
        labels.attach_label(word, ["requirements:1"])

    page = rows.read_rows(RowSelector(table="requirements"))
    by_ref = {str(ref): words for ref, words in page.labels.items()}
    assert by_ref["requirements:1"] == ("door", "engine", "stage")


def test_a_row_with_no_labels_is_present_with_an_empty_tuple(labels, terms, rows):
    """If unlabelled rows were absent, a caller could not tell "this row has no labels" from
    "this page did not fetch them", and would write `labels.get(ref, ())` — restoring the
    ambiguity the mapping exists to remove."""
    _rows(rows, 2)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", ["requirements:1"])

    page = rows.read_rows(RowSelector(table="requirements"))
    by_ref = {str(ref): words for ref, words in page.labels.items()}
    assert by_ref == {"requirements:1": ("engine",), "requirements:2": ()}


def test_a_page_of_labelled_rows_issues_one_label_query(labels, terms, rows, store):
    """**One**, not "a fixed number" — a two-query implementation satisfies "fixed" while
    violating the promise. Counted by instrumenting the connection rather than by running
    the code once and writing down what came out, which is a change-detector and not a
    check."""
    refs = _rows(rows, 6)
    terms.define_term("engine", "the planning engine")
    labels.attach_label("engine", refs)

    seen = []
    store.conn.set_trace_callback(seen.append)
    try:
        rows.read_rows(RowSelector(table="requirements"))
    finally:
        store.conn.set_trace_callback(None)

    label_queries = [s for s in seen if "label_attachments" in s]
    assert len(label_queries) == 1, label_queries
    assert len(rows.read_rows(RowSelector(table="requirements")).labels) == 6, (
        "the positive control: the one query really did return every row's labels"
    )


def test_the_report_does_not_query_once_per_glossary_word(labels, terms, rows, store):
    """The same rule one call over, and it was broken when this test was written.

    `unattached_terms` read the attached-word set inside its own comprehension, so
    `labels()` issued one query per term in the glossary — the exact one-query-per-item
    shape the page read spends a recursive CTE avoiding, reintroduced ten lines away in the
    same module. A rule with a mechanism in one place and none in the next is a rule that
    holds until somebody writes the next line.
    """
    _rows(rows, 2)
    for word in ("engine", "schema", "door", "store", "gate", "label"):
        terms.define_term(word, f"what {word} means")
    labels.attach_label("engine", ["requirements:1"])

    seen = []
    store.conn.set_trace_callback(seen.append)
    try:
        report = labels.labels()
    finally:
        store.conn.set_trace_callback(None)

    attached = [s for s in seen if "DISTINCT word" in s]
    assert len(attached) == 1, f"{len(attached)} queries for 6 terms: {attached}"
    assert report.unattached_terms == 5, "the positive control: the count is still right"
