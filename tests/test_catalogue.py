"""The catalogue service: the ranking, the refusals, and the two verdicts that stop a write.

The store's own invariants are asserted separately, in `test_catalogue_store.py`, and that
separation is deliberate rather than tidy — see that module's docstring for the reason.
"""

from __future__ import annotations

import pytest

from engine.catalogue import (
    CatalogueService,
    ComponentNotFound,
    ContainerNotCatalogued,
    ContainerNotEmpty,
    EntryNotFound,
    EntryPointExists,
    NameTaken,
    NearMatchesUnadjudicated,
    PurposeRequired,
    ReasonRequired,
    UnknownRelationship,
    UnknownVisibility,
    rank,
    tied_at_top,
    tokens,
)
from engine.errors import RetireNeedsReason, UnresolvedReference
from engine.models import CatalogueEntry, Comparison, RowSubmission
from engine.tasks import TaskNotFound


@pytest.fixture
def component(rows):
    rows.submit_rows(
        [RowSubmission("components", {"does": "stores plan rows"}, name="row-service")],
        "k-component",
    )
    return "components:1"


@pytest.fixture
def task(store):
    store.conn.execute(
        "INSERT INTO tasks (contract_ref, title, state, created_at, updated_at) "
        "VALUES ('contracts:1', 'compose a brief', 'pending', 'then', 'then')"
    )
    store.conn.commit()
    return 1


def entry(id, name, purpose, container=None):
    """A bare entry for exercising the pure ranking without a store."""
    return CatalogueEntry(
        id=id, name=name, container=container, kind="function", visibility="private",
        purpose=purpose, owner=1,
    )


class TestTheTokeniser:
    def test_identifiers_and_prose_tokenise_the_same_way(self):
        assert tokens("planRowId") == tokens("plan_row_id") == {"plan", "row", "id"}

    def test_a_plural_folds_onto_the_singular_and_keeps_both(self):
        assert tokens("rows") == {"rows", "row"}

    def test_terms_delegates_rather_than_carrying_a_second_copy(self):
        """v3 change 4's ruling, applied here: the catalogue is the second thing to need
        word-splitting, so one copy is canonical and the other is a copy — in the change
        whose own subject is duplication."""
        from engine import terms

        assert terms.TermService._tokens("plan rows", terms.PROSE) == tokens("plan rows")
        assert not hasattr(terms, "WORD"), (
            "the regex moved to engine.catalogue with the tokeniser that reads it"
        )


class TestTheRanking:
    def test_an_entry_sharing_nothing_is_not_a_candidate_at_any_rank(self):
        ranked = rank("Widget", "settle widgets", [entry(1, "Sprocket", "turn gears")])
        assert ranked == ()

    def test_it_reads_the_name_and_the_purpose_both(self):
        """One query answers two questions — a close description under a different name is
        duplication, a close name with a different description is a naming collision — so it
        costs nothing to look for both."""
        by_name = rank("RowService", "xyzzy", [entry(1, "RowStore", "plugh")])
        by_purpose = rank("xyzzy", "store plan rows", [entry(1, "Q", "store plan rows")])
        assert by_name and by_purpose

    def test_a_name_match_outranks_a_purpose_match_at_equal_totals(self):
        candidates = [
            entry(1, "alpha", "shared word here"),
            entry(2, "shared", "alpha word here"),
        ]
        ranked = rank("shared", "shared", candidates)
        assert [c.entry.id for c in ranked] == [2, 1], (
            "at an equal total the entry matching in its *name* ranks first: a name "
            "collision is the defect that bit this build three times in a sitting"
        )

    def test_ties_break_on_the_lower_id_so_the_ranking_is_stable(self):
        """The draft said "older entry first" and meant `created_at`, which is not a
        stability guarantee at all: two entries written in the same clock tick share one.
        An unstable ranking makes the required answer change between the call that showed
        the candidates and the call that answers them."""
        candidates = [entry(7, "alpha", "same words"), entry(3, "alpha", "same words")]
        assert [c.entry.id for c in rank("alpha", "same words", candidates)] == [3, 7]

    def test_a_word_almost_everything_shares_decides_almost_nothing(self):
        """Measured over a real candidate set, the word `the` accounted for 46% of all
        matching and put noise at the top of the list — which is exactly where this change
        makes adjudication mandatory."""
        candidates = [
            entry(1, "a", "the plan"), entry(2, "b", "the plan"), entry(3, "c", "the plan"),
            entry(4, "d", "the supersession"),
        ]
        ranked = rank("x", "the supersession", candidates)
        assert ranked[0].entry.id == 4, (
            "`the` is shared by all four and `supersession` by one, so the rare word has "
            "to decide the order"
        )

    def test_the_limit_is_a_page_size(self):
        candidates = [entry(i, f"n{i}", "shared purpose") for i in range(1, 12)]
        assert len(rank("q", "shared purpose", candidates)) == 5
        assert len(rank("q", "shared purpose", candidates, limit=2)) == 2

    def test_every_candidate_tied_at_the_top_is_marked_not_just_the_first(self):
        """Behaviour 7 makes the ranking stable; it does not make the top of it meaningful
        when several candidates score identically. The `id` tie-break would then decide
        which candidate a planner must write a sentence about, and the equally-ranked
        alternatives would never be adjudicated at all."""
        candidates = [entry(i, f"n{i}", "identical purpose words") for i in (1, 2, 3)]
        ranked = rank("q", "identical purpose words", candidates)
        assert len(tied_at_top(ranked)) == 3

    def test_the_tie_set_is_empty_for_no_candidates(self):
        assert tied_at_top(()) == ()


class TestCatalogueObject:
    def test_it_writes_one_object_owned_by_the_component(self, catalogue, component):
        result = catalogue.catalogue_object(
            "RowService", "store and read plan rows", "public", component, "k1"
        )
        assert result.entry.name == "RowService"
        assert result.entry.kind == "object"
        assert str(result.entry.owner) == component
        assert result.entry.container is None
        assert result.use_instead is None

    def test_a_blank_purpose_is_refused(self, catalogue, component):
        with pytest.raises(PurposeRequired):
            catalogue.catalogue_object("X", "   ", "public", component, "k1")

    def test_a_bad_visibility_is_refused_by_name(self, catalogue, component):
        with pytest.raises(UnknownVisibility):
            catalogue.catalogue_object("X", "do a thing", "Public", component, "k1")

    def test_an_owner_that_is_not_a_component_is_refused(self, catalogue, component, rows):
        """`RowService.get` takes any ref, so without the table check an object owned by a
        requirement is accepted."""
        rows.submit_rows(
            [RowSubmission("requirements", {"text": "must store rows"}, name="storage")],
            "k-req",
        )
        with pytest.raises(ComponentNotFound) as exc:
            catalogue.catalogue_object("X", "do a thing", "public", "requirements:1", "k1")
        assert "not a component" in str(exc.value)

    def test_an_owner_that_names_no_row_is_refused(self, catalogue, component):
        with pytest.raises(ComponentNotFound):
            catalogue.catalogue_object("X", "do a thing", "public", "components:99", "k1")

    def test_an_owner_that_is_not_live_is_refused(self, catalogue, component, rows):
        rows.retire_row(component, "the component was folded into another", "k-retire")
        with pytest.raises(ComponentNotFound) as exc:
            catalogue.catalogue_object("X", "do a thing", "public", component, "k1")
        assert "not live" in str(exc.value)

    def test_an_exact_name_collision_is_nametaken_and_not_an_adjudication(
        self, catalogue, component
    ):
        """The refusal order decides this, and it is a decision two tasks make jointly.
        With the name check *after* the search, an exact collision surfaces as
        `NearMatchesUnadjudicated` — because an exact match ranks first — so the planner is
        told to adjudicate a candidate when what they need to be told is that the name is
        taken."""
        catalogue.catalogue_object("RowService", "store rows", "public", component, "k1")
        with pytest.raises(NameTaken):
            catalogue.catalogue_object(
                "RowService", "something else entirely", "public", component, "k2"
            )

    def test_a_near_match_with_no_comparison_is_refused_naming_every_candidate(
        self, catalogue, component
    ):
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        catalogue.catalogue_object(
            "RowCache", "cache plan rows", "public", component, "k2",
            comparisons=(Comparison("RowService", "unrelated", "storing is not caching"),),
        )
        with pytest.raises(NearMatchesUnadjudicated) as exc:
            catalogue.catalogue_object(
                "RowReader", "read plan rows", "public", component, "k3"
            )
        message = str(exc.value)
        assert "RowService" in message and "RowCache" in message

    def test_the_refusal_tells_the_session_a_shared_word_is_not_a_duplicate(
        self, catalogue, component
    ):
        """The owner's ruling of 2026-07-31 (§13): the refusal is addressed to the planning
        session, which goes and looks and answers, and only escalates what survives the
        looking. Every plan starts with an empty catalogue and eligibility is any shared
        word, so the first registrations in every project are matched against near-nonsense
        — and a tool whose first act on a new plan is to raise a fake duplicate is D7's
        cry-wolf meter.

        So the refusal has to say that `unrelated` is the expected answer to a spurious
        match, and it has to name **the words that actually matched**, which is what makes a
        spurious one disposable at a glance.
        """
        catalogue.catalogue_object("Ledger", "keep a tally", "public", component, "k1")
        with pytest.raises(NearMatchesUnadjudicated) as exc:
            catalogue.catalogue_object(
                "Parser", "read a token", "public", component, "k2"
            )
        message = str(exc.value)
        assert "matched on: a" in message, (
            "the words that matched must be named against the candidate, or the session "
            "has to re-derive why it was stopped"
        )
        assert "shared word is not a duplicate" in message
        assert "unrelated" in message

    def test_a_blank_comparison_reason_is_refused_before_the_database_sees_it(
        self, catalogue, component
    ):
        """A comparison reason is NOT NULL, so without this the honest answer "I have not
        written why" surfaces as an IntegrityError naming a column, on the change's central
        write path."""
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        with pytest.raises(ReasonRequired):
            catalogue.catalogue_object(
                "RowReader", "read plan rows", "public", component, "k2",
                comparisons=(Comparison("RowService", "unrelated", "  "),),
            )

    def test_an_unknown_relationship_is_refused_by_name(self, catalogue, component):
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        with pytest.raises(UnknownRelationship):
            catalogue.catalogue_object(
                "RowReader", "read plan rows", "public", component, "k2",
                comparisons=(Comparison("RowService", "sort_of", "hmm"),),
            )

    @pytest.mark.parametrize("verdict", ["same", "contains"])
    def test_a_refusing_verdict_writes_the_comparison_and_no_entry(
        self, catalogue, component, store, verdict
    ):
        """`same` and `contains` are an outcome, not an exception: the planner did exactly
        the right thing, and an exception path that also commits a write is a shape nothing
        else in this engine has."""
        first = catalogue.catalogue_object(
            "RowService", "store plan rows", "public", component, "k1"
        )
        result = catalogue.catalogue_object(
            "RowReader", "read plan rows", "public", component, "k2",
            comparisons=(Comparison("RowService", verdict, "the same job, one word apart"),),
        )
        assert result.entry is None
        assert result.use_instead.id == first.entry.id
        assert len(store.query("SELECT * FROM catalogue")) == 1
        written = store.query("SELECT * FROM catalogue_comparisons")
        assert len(written) == 1
        assert written[0]["entry_id"] is None
        assert written[0]["proposed"] == "RowReader"

    @pytest.mark.parametrize("verdict", ["contained_by", "partially_overlaps", "unrelated"])
    def test_a_permitting_verdict_writes_both(self, catalogue, component, store, verdict):
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        result = catalogue.catalogue_object(
            "RowReader", "read plan rows", "public", component, "k2",
            comparisons=(Comparison("RowService", verdict, "different enough"),),
        )
        assert result.entry is not None
        written = store.query("SELECT * FROM catalogue_comparisons")
        assert written[0]["entry_id"] == result.entry.id, (
            "FromOp is what lets the comparison borrow the entry's assigned id inside one "
            "transaction"
        )

    def test_a_comparison_naming_nothing_live_is_refused(self, catalogue, component):
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        with pytest.raises(EntryNotFound):
            catalogue.catalogue_object(
                "RowReader", "read plan rows", "public", component, "k2",
                comparisons=(Comparison("NoSuchEntry", "unrelated", "never heard of it"),),
            )

    def test_an_unresolvable_ref_in_the_purpose_is_refused_naming_the_token(
        self, catalogue, component
    ):
        with pytest.raises(UnresolvedReference) as exc:
            catalogue.catalogue_object(
                "X", "serve widgets, see components:99", "public", component, "k1"
            )
        assert "components:99" in str(exc.value)

    def test_a_url_with_a_port_reads_as_an_address_and_the_refusal_says_so(
        self, catalogue, component
    ):
        """Change 2's probe found this trap and left such a token merely rendering oddly.
        Here it refuses the write, so the refusal has to name the token and let the planner
        see it is their `localhost:8080` and not a citation."""
        with pytest.raises(UnresolvedReference) as exc:
            catalogue.catalogue_object(
                "X", "poll localhost:8080 for widgets", "public", component, "k1"
            )
        assert "localhost:8080" in str(exc.value)
        assert "without one" in str(exc.value)

    def test_an_unresolvable_ref_in_a_comparison_reason_is_refused(
        self, catalogue, component
    ):
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        with pytest.raises(UnresolvedReference):
            catalogue.catalogue_object(
                "RowReader", "read plan rows", "public", component, "k2",
                comparisons=(
                    Comparison("RowService", "unrelated", "different, see components:99"),
                ),
            )

    def test_a_replay_of_an_entry_writing_call_hits_nametaken(self, catalogue, component):
        """Every guard runs before `write_atomic`, so a replayed registration that wrote an
        entry never reaches the receipt. That is the correct outcome and it is stated as one
        rather than left as an unreachable behaviour."""
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        with pytest.raises(NameTaken):
            catalogue.catalogue_object(
                "RowService", "store plan rows", "public", component, "k1"
            )

    def test_a_replay_of_a_refusing_verdict_returns_the_first_receipt(
        self, catalogue, component, store
    ):
        """The case where replay does its job: no entry was written, no name is taken, the
        call reaches `write_atomic`, and the receipt suppresses a duplicate comparison."""
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        judgment = (Comparison("RowService", "same", "the same job"),)
        catalogue.catalogue_object(
            "RowReader", "read plan rows", "public", component, "k2", comparisons=judgment
        )
        catalogue.catalogue_object(
            "RowReader", "read plan rows", "public", component, "k2", comparisons=judgment
        )
        assert len(store.query("SELECT * FROM catalogue_comparisons")) == 1


class TestCatalogueFunction:
    def test_a_module_level_function_is_not_an_error(self, catalogue, task):
        result = catalogue.catalogue_function(
            "stored_text", "trim a text value before storing it", "private", task, "k1"
        )
        assert result.entry.container is None

    def test_an_unknown_container_is_refused_and_names_the_call(self, catalogue, task):
        with pytest.raises(ContainerNotCatalogued) as exc:
            catalogue.catalogue_function(
                "_hydrate", "build a row", "private", task, "k1", container="NoSuchClass"
            )
        assert "catalogue_object" in str(exc.value)

    def test_an_unknown_task_is_refused(self, catalogue):
        with pytest.raises(TaskNotFound):
            catalogue.catalogue_function("f", "do a thing", "private", 99, "k1")

    def test_a_task_gets_one_public_entry_point(self, catalogue, task):
        catalogue.catalogue_function("compose", "assemble a brief", "public", task, "k1")
        with pytest.raises(EntryPointExists) as exc:
            catalogue.catalogue_function("build", "make a brief", "public", task, "k2")
        assert "compose" in str(exc.value)

    def test_private_entries_for_the_same_task_are_fine(self, catalogue, task):
        catalogue.catalogue_function("compose", "assemble a brief", "public", task, "k1")
        catalogue.catalogue_function("_gather", "collect every row", "private", task, "k2")
        catalogue.catalogue_function("_sort", "order the sections", "private", task, "k3")

    def test_the_name_check_is_scoped_to_the_container_not_module_level(
        self, catalogue, component, task
    ):
        """A one-word correction with a real consequence. Inherited verbatim from the object
        case, `catalogue_function("_hydrate", container="RowService")` would be refused
        because a module-level `_hydrate` exists — the exact case the whole table's identity
        is designed around."""
        catalogue.catalogue_object("Ledger", "tally sums", "public", component, "k1")
        catalogue.catalogue_function(
            "_hydrate", "build one row from stored columns", "private", task, "k2"
        )
        result = catalogue.catalogue_function(
            "_hydrate", "build one row from stored columns", "private", task, "k3",
            container="Ledger",
            comparisons=(
                Comparison("_hydrate", "unrelated", "the module-level one is a different job"),
            ),
        )
        assert result.entry.container == "Ledger"


class TestRetirement:
    def test_a_blank_reason_is_refused(self, catalogue, component):
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        with pytest.raises(RetireNeedsReason):
            catalogue.retire_catalogue_entry("RowService", "  ", "k2")

    def test_an_unknown_entry_is_refused(self, catalogue):
        with pytest.raises(EntryNotFound):
            catalogue.retire_catalogue_entry("Nothing", "gone", "k1")

    def test_an_object_still_holding_live_entries_is_refused_naming_them(
        self, catalogue, component, task
    ):
        catalogue.catalogue_object("Ledger", "tally sums", "public", component, "k1")
        catalogue.catalogue_function(
            "_hydrate", "build one row from stored columns", "private", task, "k2",
            container="Ledger",
        )
        with pytest.raises(ContainerNotEmpty) as exc:
            catalogue.retire_catalogue_entry("Ledger", "the design changed", "k3")
        assert "_hydrate" in str(exc.value)

    def test_a_retired_entry_is_never_a_search_candidate(self, catalogue, component):
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        catalogue.retire_catalogue_entry("RowService", "folded into the store", "k2")
        assert catalogue.search_catalogue("store plan rows") == ()

    def test_the_name_is_free_again_and_the_reintroduction_is_told_about_it(
        self, catalogue, component
    ):
        """The design's strongest sentence, delivered: a dead function cannot be reused, but
        the thing about to be written may have been removed on purpose, and the planner may
        be undoing somebody's decision without knowing it."""
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        catalogue.retire_catalogue_entry("RowService", "folded into the store", "k2")
        result = catalogue.catalogue_object(
            "RowService", "store plan rows", "public", component, "k3"
        )
        assert result.entry is not None
        assert "folded into the store" in result.note

    def test_a_retirement_surfaces_in_a_later_entrynotfound(self, catalogue, component):
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        catalogue.retire_catalogue_entry("RowService", "folded into the store", "k2")
        with pytest.raises(EntryNotFound) as exc:
            catalogue.restate_purpose("RowService", "store rows", "k3")
        assert "folded into the store" in str(exc.value)


class TestRestatePurpose:
    def test_it_replaces_in_place_and_keeps_the_row(self, catalogue, component):
        first = catalogue.catalogue_object(
            "RowService", "store rows", "public", component, "k1"
        )
        after = catalogue.restate_purpose(
            "RowService", "store, read and retire plan rows", "k2"
        )
        assert after.id == first.entry.id
        assert after.purpose == "store, read and retire plan rows"

    def test_a_blank_purpose_is_refused(self, catalogue, component):
        catalogue.catalogue_object("RowService", "store rows", "public", component, "k1")
        with pytest.raises(PurposeRequired):
            catalogue.restate_purpose("RowService", "  ", "k2")

    def test_an_unresolvable_ref_is_refused(self, catalogue, component):
        catalogue.catalogue_object("RowService", "store rows", "public", component, "k1")
        with pytest.raises(UnresolvedReference):
            catalogue.restate_purpose("RowService", "store rows, see components:99", "k2")

    def test_recorded_comparisons_are_untouched(self, catalogue, component, store):
        """The honest cost: a comparison judged against the old wording is not
        re-adjudicated. Invalidating them would make restating expensive again and re-create
        the problem this call solves."""
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        catalogue.catalogue_object(
            "RowCache", "cache plan rows", "public", component, "k2",
            comparisons=(Comparison("RowService", "unrelated", "storing is not caching"),),
        )
        before = store.query("SELECT * FROM catalogue_comparisons")
        catalogue.restate_purpose("RowCache", "hold plan rows in memory briefly", "k3")
        after = store.query("SELECT * FROM catalogue_comparisons")
        assert [dict(r) for r in before] == [dict(r) for r in after]


class TestTheSearchAndTheReport:
    def test_a_query_matching_nothing_returns_empty_and_is_not_an_error(
        self, catalogue, component
    ):
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        assert catalogue.search_catalogue("quantum widget telemetry") == ()

    def test_a_candidate_carries_its_container_name_and_never_a_bare_id(
        self, catalogue, component, task
    ):
        catalogue.catalogue_object("Ledger", "tally sums", "public", component, "k1")
        catalogue.catalogue_function(
            "_hydrate", "build one plan row from stored columns", "private", task, "k2",
            container="Ledger",
        )
        found = catalogue.search_catalogue("plan row")
        containers = {c.entry.container for c in found}
        assert "Ledger" in containers, (
            "a caller reading a result must be able to pass it back to catalogue_function, "
            "which takes a container name"
        )

    def test_two_entries_in_one_container_still_cluster(self, catalogue, component, task):
        """The draft grouped entries "whose containers differ" while module-level entries
        "share the empty container", so no two module-level entries could ever cluster —
        blind to 56 module-level functions and all 204 objects. And the positive case is
        `RowService.get_row` beside `RowService.fetch_row`, which is duplication of exactly
        the kind this table exists to catch."""
        catalogue.catalogue_object("Ledger", "tally sums", "public", component, "k1")
        catalogue.catalogue_function(
            "get_row", "fetch one plan row by address", "public", task, "k2",
            container="Ledger",
        )
        catalogue.catalogue_function(
            "fetch_row", "fetch one plan row by address", "private", task, "k3",
            container="Ledger",
            comparisons=(
                Comparison("get_row", "partially_overlaps", "both fetch; different callers",
                           container="Ledger"),
            ),
        )
        clusters = catalogue.catalogue_clusters()
        members = {frozenset(e.name for e in c.members) for c in clusters}
        assert any({"get_row", "fetch_row"} <= m for m in members)

    def test_module_level_entries_participate_on_the_same_terms(
        self, catalogue, component, task
    ):
        catalogue.catalogue_object("RowStore", "hold plan rows on disk", "public", component, "k1")
        catalogue.catalogue_function(
            "hold_rows", "hold plan rows on disk", "public", task, "k2",
            comparisons=(
                Comparison("RowStore", "unrelated", "one is the class, one the helper"),
            ),
        )
        clusters = catalogue.catalogue_clusters()
        assert any(
            {"RowStore", "hold_rows"} <= {e.name for e in c.members} for c in clusters
        )

    def test_a_stop_word_cluster_sinks_below_a_real_one(self, catalogue, component):
        """The second site of the same escape, found by the owner asking where else it was
        relied on (§13.6). The ranking got a rarity weight and the report got none — and the
        report needed it more: ordered by count of shared words, stop words win outright,
        because they are common *and* they travel together, so they form both the widest
        clusters and the longest shared lists.

        Measured over these ten before the fix, the top six were `the` (all ten), `a`
        (nine), `from`, `of` — with `record`, the one grouping worth reading, sitting sixth.
        """
        purposes = [
            ("Ledger", "keep a tally of the entries"),
            ("Parser", "read a token from the stream"),
            ("Writer", "write a record to the store"),
            ("Reader", "read a record from the store"),
            ("Cache", "hold a copy of the record"),
            ("Clock", "give the current time"),
            ("Router", "send a request to the handler"),
            ("Logger", "append a line to the log"),
            ("Sorter", "order a list of the results"),
            ("Filter", "remove a row from the results"),
        ]
        for i, (name, purpose) in enumerate(purposes):
            shown = catalogue.search_catalogue(f"{name} {purpose}")
            catalogue.catalogue_object(
                name, purpose, "public", component, f"k{i + 1}",
                comparisons=tuple(
                    Comparison(c.entry.name, "unrelated", "different job",
                               c.entry.container)
                    for c in shown
                ),
            )

        report = catalogue.catalogue_clusters()
        top = report[0]
        assert set(top.shared) == {"result", "results"}, (
            f"the report's first cluster is {list(top.shared)}; a grouping resting on a "
            f"word most entries share must not outrank one resting on a word two share"
        )

        placing = {
            word: i
            for i, cluster in enumerate(report)
            for word in cluster.shared
        }
        assert placing["record"] < placing["a"] < placing["the"], (
            "the entries all handling a *record* are the grouping worth reading; `a` and "
            "`the` are noise and must sort below it"
        )

        # Nothing is excluded, because exclusion would be a stop-word list and a stop-word
        # list is an opinion about which words do not matter, frozen where review cannot
        # see it. The junk is still in the report; it is merely last.
        assert "the" in placing

    def test_a_cluster_names_the_words_it_is_grouped_on(self, catalogue, component, task):
        catalogue.catalogue_object("RowStore", "hold plan rows on disk", "public", component, "k1")
        catalogue.catalogue_function(
            "hold_rows", "hold plan rows on disk", "public", task, "k2",
            comparisons=(Comparison("RowStore", "unrelated", "class versus helper"),),
        )
        clusters = catalogue.catalogue_clusters()
        assert clusters and all(c.shared for c in clusters)
        assert "plan" in set(clusters[0].shared)


class TestTheSurfaceAndTheCrossTaskBehaviours:
    """3E.2 — the assertions no single task would fail on its own."""

    def test_the_planning_registry_holds_57_tools_and_added_holds_16(self):
        """Stated because a coverage test asserting a number nobody wrote down cements
        whichever number the builder guessed — and the draft's number was wrong at both
        ends. 51 today (54 in v2, minus change 1's four, plus change 2's one), plus six."""
        from engine.surface import ADDED, REGISTRY

        assert len(REGISTRY) == 57
        assert len(ADDED) == 16

    def test_the_six_are_deviations_and_each_says_why(self):
        from engine.surface import ADDED, DEVIATION, REGISTRY

        ours = (
            "catalogue_object", "catalogue_function", "retire_catalogue_entry",
            "restate_purpose", "search_catalogue", "catalogue_clusters",
        )
        reasons = {a.call: a.reason for a in ADDED}
        for name in ours:
            assert REGISTRY[name].contract == DEVIATION
            assert reasons[name].strip()

    def test_four_write_and_two_read(self):
        from engine.surface import REGISTRY

        writes = {
            n for n in (
                "catalogue_object", "catalogue_function", "retire_catalogue_entry",
                "restate_purpose", "search_catalogue", "catalogue_clusters",
            )
            if REGISTRY[n].writes
        }
        assert writes == {
            "catalogue_object", "catalogue_function", "retire_catalogue_entry",
            "restate_purpose",
        }

    def test_the_ranking_a_registration_adjudicates_is_the_one_the_search_returns(
        self, catalogue, component
    ):
        """The one a builder would skip, because each half looks covered by a unit test of
        its own. It is what makes "one ranking function" a mechanism rather than a sentence:
        two rankings would let a planner be shown one candidate and required to adjudicate
        another, and every individual test would still pass."""
        catalogue.catalogue_object("RowService", "store plan rows", "public", component, "k1")
        catalogue.catalogue_object(
            "RowCache", "cache plan rows briefly", "public", component, "k2",
            comparisons=(Comparison("RowService", "unrelated", "storing is not caching"),),
        )
        catalogue.catalogue_object(
            "RowIndex", "index plan rows for lookup", "public", component, "k3",
            comparisons=(
                Comparison("RowService", "unrelated", "indexing is not storing"),
                Comparison("RowCache", "unrelated", "indexing is not caching"),
            ),
        )

        shown = [c.entry.name for c in catalogue.search_catalogue("read plan rows")]
        with pytest.raises(NearMatchesUnadjudicated) as exc:
            catalogue.catalogue_object(
                "RowReader", "read plan rows", "public", component, "k4"
            )
        message = str(exc.value)
        assert shown, "the fixture must actually produce candidates or this proves nothing"
        for name in shown:
            assert name in message
        assert message.index(shown[0]) == min(message.index(n) for n in shown), (
            "the registration must present the same order the search returned"
        )

    def test_a_refusal_naming_a_call_survives_the_door(self, tmp_path):
        """The landing-order inversion made into an assertion. `ContainerNotCatalogued`
        names a call, so the refusal only survives the door if the registry rows exist.
        Asserting that the refusal *renders* — rather than that it is raised — is what
        catches the ordering being undone later; the standing evidence is that a missing
        route reports a refusal reading like the caller's mistake (F39)."""
        from engine.storage import Storage
        from engine.surface import Surface, ToolCall

        with Storage(tmp_path) as store:
            store.init_plan("p", "standard")
            store.conn.execute(
                "INSERT INTO tasks (contract_ref, title, state, created_at, updated_at) "
                "VALUES ('contracts:1', 't', 'pending', 'then', 'then')"
            )
            store.conn.commit()
            surface = Surface(store)
            result = surface.dispatch(ToolCall("catalogue_function", {
                "name": "_hydrate", "purpose": "build a row", "visibility": "private",
                "task_id": 1, "idempotency_key": "k1", "container": "NoSuchClass",
            }))
            assert result.ok is False
            assert "catalogue_object" in result.problem
            assert result.error == "ContainerNotCatalogued"

    def test_the_whole_registry_still_advertises_over_mcp(self):
        """F46's shape: `engine/mcp.py` is the transport every client hits first, and a new
        parameter kind with no JSON-Schema entry there kills `tools/list` for the whole
        surface rather than for the one tool that introduced it."""
        from engine.mcp import tool_list

        advertised = {t["name"]: t for t in tool_list()}
        assert len(advertised) == 57
        schema = advertised["catalogue_object"]["inputSchema"]
        assert schema["properties"]["comparisons"]["type"] == "array"
        assert set(schema["required"]) == {
            "name", "purpose", "visibility", "component_ref", "idempotency_key",
        }
