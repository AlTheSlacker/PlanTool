"""row-service (components:2).

Owns the PlanRow lifecycle: provenance-checked batched submission with per-row verdicts,
full and targeted readback, in-place assumption upgrade, supersession lineage, and
retirement.

Contracts: contracts:69 submit_rows, contracts:74 read_rows, contracts:70
resolve_assumption, contracts:71 supersede_row, contracts:72 retire_row.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from engine.door import ADDRESS
from engine.errors import (
    AlreadyRetired,
    AlreadySuperseded,
    ConflictRequired,
    GroundsAlreadyRecorded,
    GroundsNeedBoth,
    InvalidSelector,
    NotAssumed,
    RetireNeedsReason,
    RowNotFound,
    RowNotLive,
    SpikeRequired,
    SupersedeNeedsReason,
    UnresolvedReference,
    UpgradeFailed,
)
from engine.models import (
    EDGE_TYPES,
    BatchReceipt,
    LinkSpec,
    PlanRow,
    Provenance,
    RowPage,
    RowRef,
    RowSelector,
    RowState,
    RowSubmission,
    RowVerdict,
    content_fingerprint,
)
from engine.clock import now
from engine.idempotency import key
from engine.storage import FromOp, Op, Storage
from engine.validation import (
    spike_directory,
    spike_insert_op,
    spike_slug,
    spike_spec_problem,
)

#: The live rows carrying **every** word in a label filter (v3 change 4).
#:
#: **The join it performs has no other primitive.** Attachments key on lineage roots and
#: this is a `WHERE` clause over rows, and the only root primitive in the engine —
#: `lineage_root` — is a Python loop issuing one query per supersession hop. Resolving in
#: Python would break `total` and paging, which both ride in SQL; matching roots against
#: refs directly is correct only for rows that have never been superseded, and so silently
#: drops exactly the lineages root-keying exists to preserve.
#:
#: So it walks the chain the other way: rather than resolving every candidate row *back* to
#: its root, it resolves the small attached set *forward* to its live heads. Probed at
#: SQLite 3.49.1 against a lineage superseded twice and labelled at its root — the live row
#: is still found, and the result is a plain set of refs that composes with every other
#: selector dimension.
#:
#: **`COUNT(DISTINCT word)` and not `COUNT(*)`, and that was probed rather than reasoned.**
#: The live unique index is supposed to guarantee one live attachment per word per target,
#: which would make the two spellings equivalent — but this change measured that the
#: *natural* spelling of that index enforces nothing whatsoever, every row having exactly
#: one NULL among the target columns. So the duplicate the two forms disagree about is
#: reachable in exactly the case where the constraint was got wrong, and `DISTINCT` makes
#: the filter correct independently of it.
#:
#: The AND is the owner's decision of 2026-07-30, taken against the recommendation that one
#: label is enough: he asked for it "for completeness". The `HAVING` is the whole of it.
LABELLED_HEADS = """
    WITH RECURSIVE attached(root) AS (
        SELECT target_root FROM label_attachments
         WHERE word IN ({marks}) AND detached_at IS NULL AND target_root IS NOT NULL
         GROUP BY target_root
        HAVING COUNT(DISTINCT word) = ?
    ),
    chain(root, ref) AS (
        SELECT root, root FROM attached
        UNION ALL
        SELECT c.root, p.superseded_by
          FROM chain c
          JOIN plan_rows p ON p.table_name || ':' || p.ordinal = c.ref
         WHERE p.superseded_by IS NOT NULL
    )
    SELECT DISTINCT ref FROM chain
     WHERE ref IN (SELECT table_name || ':' || ordinal FROM plan_rows
                    WHERE superseded_by IS NULL)
"""

#: The most rows one page may ask for. `read_rows` validated only that `limit` is positive,
#: and both of this change's queries bind one parameter per element — a caller asking for
#: fifty thousand rows would build a fifty-thousand-parameter statement and get a driver
#: error rather than a refusal naming the field. Well above any sensible page and well below
#: SQLite's own default parameter limit.
MAX_PAGE = 1000

#: A contradiction detector: given a candidate submission and the store, return a
#: human-readable description of what stored row it contradicts, or None.
#:
#: contracts:69 mandates a ConflictRequired error but the frozen plan never specifies how
#: contradiction is *determined* (DEFECTS.md F4). conflict-service supplies a real
#: detector in M3; until then no contradiction is detected and the error is unreachable.
ContradictionDetector = Callable[[RowSubmission, "RowService"], str | None]

#: Table names a plan row may not use, each with the refusal the submitter reads.
#:
#: `plan_rows.table` is open — a methodology declares its own row types and the engine knows
#: none of them, which is what keeps `findings:4` from coming true. But open means a name
#: already owned by another store can be claimed by accident, and one already had been:
#: `findings` addresses both the finding service and, in v1's export, a set of plan rows, so
#: a red team filing through `file_finding` wrote where the stage-7 gate did not look
#: (DEFECTS.md F38). Deciding which store owns the word is only half a fix; without this the
#: collision returns as data the first time somebody submits the obvious-looking row.
#:
#: The refusal names the tool to use instead. A closed door with no signpost is how a
#: planner ends up inventing a workaround.
RESERVED_TABLES = {
    "findings": (
        "'findings' is not a plan-row table: a finding moves through states and a plan row "
        "is write-once, so findings have a store of their own. File it with file_finding, "
        "which addresses it as findings:N and links it to the rows it attacks"
    ),
    # The reservation survives v3 change 4; its old reason did not. It argued that the
    # glossary is a real table "because a word being redefined and a word being replaced are
    # two different relations that supersession collapses into one" — and after that change
    # a redefinition is an in-place UPDATE, a replacement is a parameter of the delete, and
    # supersession is gone from this table entirely. The plain reason is the one that holds:
    # a real table owns that name, so plan rows must not be written into it.
    "terms": (
        "'terms' is not a plan-row table: the glossary is a real table of its own, so this "
        "name is taken. Record it with define_term, which takes the word and what it means "
        "here"
    ),
}


def _no_contradictions(submission: RowSubmission, service: RowService) -> str | None:
    return None


def stored_text(value: str | None) -> str | None:
    """Strip on store: a text value is trimmed before it is written, and a value that
    strips to empty is stored NULL, never `''`.

    One function rather than a `.strip()` at each write, because the two answers drift:
    `''` and NULL both read as absent to a person and differently to a gap rule, and the
    rule reads the column raw. `supersede_row` already did this by hand for `name`; the
    decision-context columns are the third and fourth text fields to need it, which is
    when it stops being a habit and becomes a function.
    """
    if value is None:
        return None
    return value.strip() or None


def unresolved_refs(text: str | None, exists: Callable[[RowRef], bool]) -> list[str]:
    """Address tokens in `text` that name no row at all, in the order they appear.

    Uses the door's own `ADDRESS` pattern rather than a second one: the door scans every
    outgoing payload with it, so a token this misses is a token that fails the *render*
    of the row later, when the only repair left is superseding a row whose content is fine.

    Superseded and retired rows resolve — the door renders them with their successor, and
    citing what a decision replaced is exactly what an argument does.
    """
    if not text:
        return []
    return [
        token
        for token in dict.fromkeys(ADDRESS.findall(text))
        if not exists(RowRef.parse(token))
    ]


class RowService:
    def __init__(
        self,
        storage: Storage,
        detector: ContradictionDetector = _no_contradictions,
        containment: dict[str, str] | None = None,
    ):
        self.storage = storage
        self.detect_contradiction = detector
        #: Child row type -> mandatory parent row type, from the methodology revision in
        #: force. The engine holds no opinion about which row types these are; it
        #: enforces the map it is handed. Pass `{}` to disable (used by tests that
        #: submit row types no methodology declares).
        if containment is None:
            from engine.methodology import load

            containment = load().containment
        self.containment = containment

    # --- contracts:69 ---

    def submit_rows(
        self, batch: list[RowSubmission], idempotency_key: str
    ) -> BatchReceipt:
        """Submit a batch of rows.

        requirements:14 — a row failing validation is rejected alone, with a verdict
        naming the specific problem; accepted rows stand.
        requirements:6 — the batch is atomic: no partial rows.
        requirements:27 — a row contradicting a stored row files nothing until a
        conflict is raised.
        """
        replay = self.storage.replay(idempotency_key)
        if replay is not None and "verdicts" in replay["meta"]:
            # decisions:43 — a replayed key returns the ORIGINAL receipt. The batch
            # presented now is not re-evaluated; it may not even be the same batch.
            return BatchReceipt(
                idempotency_key,
                tuple(
                    RowVerdict(
                        v["index"],
                        v["accepted"],
                        RowRef.parse(v["ref"]) if v["ref"] else None,
                        v["problem"],
                        v.get("note"),
                    )
                    for v in replay["meta"]["verdicts"]
                ),
                replay["written_at"],
                replayed=True,
            )

        problems: dict[int, str] = {}
        for index, submission in enumerate(batch):
            problem = self._validate(submission, index, len(batch))
            if problem is None:
                problem = self._containment_problem(submission, batch)
            if problem is None:
                problem = self._duplicate_name_problem(submission, index, batch)
            if problem is None:
                problem = self._spike_problem(submission)
            if problem is not None:
                problems[index] = problem
                continue
            contradiction = self.detect_contradiction(submission, self)
            if contradiction is not None:
                raise ConflictRequired(
                    "a submitted row contradicts a stored row; nothing is filed until "
                    "a conflict is raised and presented (requirements:27)",
                    index=index,
                    contradiction=contradiction,
                )

        # A row whose sibling target was rejected cannot be filed either: dropping the
        # link silently would file a row with less provenance than it declared. Iterate
        # to a fixed point, since a rejection can cascade along a chain of siblings.
        changed = True
        while changed:
            changed = False
            for index, submission in enumerate(batch):
                if index in problems:
                    continue
                for link in submission.links:
                    if link.is_intra_batch and link.target in problems:
                        problems[index] = (
                            f"link target (batch index {link.target}) was rejected: "
                            f"{problems[link.target]}"
                        )
                        changed = True
                        break

        verdicts: list[RowVerdict] = []
        ops: list[Op] = []
        op_index: list[int] = []

        for index, submission in enumerate(batch):
            if index in problems:
                verdicts.append(RowVerdict(index, False, problem=problems[index]))
                continue

            ops.append(
                Op(
                    "insert_row",
                    "plan_rows",
                    {
                        "table_name": submission.table,
                        "content": json.dumps(submission.content),
                        "name": submission.name.strip(),
                        "named_for": content_fingerprint(submission.content),
                        "provenance": str(submission.provenance),
                        "assumption_kind": submission.assumption_kind,
                        "state": str(submission.initial_state()),
                        "stage": submission.stage,
                        "created_at": now(),
                        # v3 D11. Both optional: a submission with neither is accepted, and
                        # the absence is a gap rather than a rejection. Refusing here would
                        # make every synthesize stage a negotiation with the tool and would
                        # buy padding, which is worse than absence because absence counts.
                        "grounds": stored_text(submission.grounds),
                        "alternatives": stored_text(submission.alternatives),
                    },
                )
            )
            op_index.append(index)
            # `note` carries no producer in this module since v3 change 4 deleted the
            # retired-word scan. The field stays: `CatalogueResult.note` documents the same
            # shape for the catalogue's retired namesake, and a verdict is the natural place
            # for advice that rides along with a row that stands. Said here rather than left
            # to be discovered, because a field nothing fills reads as an oversight.
            verdicts.append(RowVerdict(index, True))

        # Links ride in the SAME batch as the rows they belong to.
        #
        # They used to be a second write_atomic, because a link needs its source row's
        # ref and refs are assigned inside the transaction. That was tolerable while a
        # link was optional decoration. It stopped being tolerable when a `belongs_to`
        # edge became mandatory for contained row types (F28): a row write that
        # succeeded followed by a link write that failed left exactly the orphan that
        # submission now refuses to accept — created by the code enforcing the rule.
        #
        # `FromOp` borrows a value from an earlier op in the same batch, resolved by
        # storage as it applies them in order, so the row and its edges commit together
        # or not at all. entities:15 keeps links immutable thereafter.
        op_position = {index: position for position, index in enumerate(op_index)}
        for index in op_index:
            for link in batch[index].links:
                ops.append(
                    Op(
                        "insert",
                        "links",
                        {
                            "source_ref": FromOp(op_position[index], "ref"),
                            "target_ref": (
                                FromOp(op_position[link.target], "ref")
                                if link.is_intra_batch
                                else str(link.target)
                            ),
                            "edge_type": link.edge_type,
                            "created_at": now(),
                        },
                    )
                )

        # D16 — a world-assumption's spike rides the same transaction, so the row and the
        # experiment that will attack it commit together or not at all. Its `assumption`
        # borrows the ref this row insert assigns, exactly as a link does. Spike ops go
        # after every row op so the ref-assignment readback below (which zips results with
        # op_index) still lands on the leading row results. Each is remembered by its
        # position so the quarantine directory can be created once the id is known.
        spike_ops: list[tuple[int, str]] = []
        for index in op_index:
            spec = batch[index].spike
            if spec is not None:
                spike_ops.append((len(ops), spike_slug(spec.question)))
                ops.append(spike_insert_op(FromOp(op_position[index], "ref"), spec))

        receipt = self.storage.write_atomic(ops, idempotency_key)
        self._create_spike_directories(receipt, spike_ops)

        # Read assignments from the receipt, not from the ops: on an idempotent replay
        # the ops were never executed and carry no results, but the stored receipt has
        # the original refs (decisions:43). Only the leading row ops are read; the link
        # ops that follow them carry no ref of their own.
        assigned: dict[int, RowRef] = {}
        for result, index in zip(receipt["results"], op_index, strict=False):
            assigned[index] = RowRef.parse(result["ref"])

        final = tuple(
            RowVerdict(v.index, v.accepted, assigned.get(v.index), v.problem, v.note)
            for v in verdicts
        )
        # Record the verdicts against the key so a replay can return them verbatim.
        self.storage.annotate(
            idempotency_key,
            {
                "verdicts": [
                    {
                        "index": v.index,
                        "accepted": v.accepted,
                        "ref": str(v.ref) if v.ref else None,
                        "problem": v.problem,
                        "note": v.note,
                    }
                    for v in final
                ]
            },
        )
        return BatchReceipt(
            idempotency_key,
            final,
            receipt["written_at"],
            replayed=receipt.get("replayed", False),
        )

    def _create_spike_directories(
        self, receipt: dict[str, Any], spike_ops: list[tuple[int, str]]
    ) -> None:
        """requirements:3 — each new spike's quarantine directory, created the moment the
        spike exists so probe code has exactly one legitimate place to live.

        The ids come from the receipt rather than the ops, so a crash between the write
        and this call is recoverable: a replay returns the stored receipt with the same
        ids, and `mkdir(exist_ok=True)` makes re-creating an existing directory a no-op.
        """
        results = receipt.get("results", [])
        for position, slug in spike_ops:
            result = results[position] if position < len(results) else None
            if result and result.get("id"):
                path = self.storage.workspace / spike_directory(result["id"], slug)
                path.mkdir(parents=True, exist_ok=True)

    def _validate(
        self, submission: RowSubmission, index: int = 0, batch_size: int = 1
    ) -> str | None:
        """requirements:5 — provenance is mandatory, and an assumed row must say what
        kind of assumption it is."""
        if not submission.table or not submission.table.isidentifier():
            return f"table name {submission.table!r} is not a valid identifier"
        if submission.table in RESERVED_TABLES:
            return RESERVED_TABLES[submission.table]
        if not isinstance(submission.content, dict) or not submission.content:
            return "content must be a non-empty object"
        if not submission.name or not submission.name.strip():
            return (
                "every row needs a name: a short phrase saying what this row is. The row "
                "is addressed as table:ordinal, and an address on its own makes the reader "
                "go and look it up — so the name is what gets shown and the address rides "
                "alongside it"
            )
        if submission.provenance is Provenance.ASSUMED and not submission.assumption_kind:
            return (
                "an assumed row must carry an assumption_kind (requirements:5); "
                "world assumptions go to spikes, intent assumptions go to the owner"
            )
        for link in submission.links:
            if link.edge_type not in EDGE_TYPES:
                return (
                    f"unknown edge type {link.edge_type!r}; the vocabulary is closed: "
                    f"{', '.join(sorted(EDGE_TYPES))}. An edge type nothing traverses "
                    "is an invisible relation, not a new kind of one"
                )
            if link.is_intra_batch:
                if not 0 <= link.target < batch_size:
                    return (
                        f"link target index {link.target} is outside this batch "
                        f"(0..{batch_size - 1})"
                    )
                if link.target == index:
                    return "a row cannot link to itself"
            elif self._row(link.target) is None:
                return f"link target {link.target} does not exist"
        return None

    def _spike_problem(self, submission: RowSubmission) -> str | None:
        """D16 — a world-assumption is filed WITH the spike that will attack it.

        The F28 move applied to assumptions: rather than let an unbacked world-assumption
        be written and caught five stages later at the stage-6 gate, the row and its
        first spike are one atomic act, so unbacked is unrepresentable. An assumption made
        in the first hour that turns out false is the milestone-time re-plan this tool
        exists to prevent, reproduced inside the tool — registering a spike is cheap even
        when concluding it is not, which is what makes "as they happen" affordable.

        A spike on anything other than a world-assumption is refused, not ignored: spikes
        resolve world-assumptions only, and a spike attached to a decided row or an
        intent-assumption is a caller mistake worth naming rather than dropping silently.
        `_validate` has already guaranteed that an assumed row carries its kind.
        """
        is_world = (
            submission.provenance is Provenance.ASSUMED
            and (submission.assumption_kind or "").strip().lower() == "world"
        )
        if is_world:
            if submission.spike is None:
                return (
                    "a world-assumption is filed with the spike that will attack it, in "
                    "the same act (D16): pass a spike with its question, hypothesis, "
                    "method against the real dependency, and budget. An unbacked "
                    "world-assumption is the milestone-time surprise this tool exists to "
                    "prevent"
                )
            return spike_spec_problem(submission.spike)
        if submission.spike is not None:
            return (
                "a spike resolves a world-assumption only; this row is not one, so its "
                "spike has nothing to attack. Drop the spike, or file the row as an "
                "assumed/world row if that is what it is"
            )
        return None

    # `_vocabulary_note` stood here until v3 change 4. It ran every submitted row's content
    # past the glossary's retired-word scan and returned what it found as a verdict note —
    # the delivery point aimed at F27's actual cause, since naming happens at the point of
    # least attention and the moment of typing is the only moment at which saying so changes
    # anything.
    #
    # It goes because the scan goes, and the argument is that no scan could ever have worked
    # for the failure it was built for: `part` and `component` share no letters. Something
    # lexical catches a *retired* word being reused and never catches a second word being
    # invented for a thing that already has one, which is what F27 actually was. The
    # glossary's job is now to be in front of the writer at the moment of naming — loaded
    # into the session — and its one mechanical use is that a label must be a live term.

    def _duplicate_name_problem(
        self, submission: RowSubmission, index: int, batch: list[RowSubmission]
    ) -> str | None:
        """No two live rows in one table share a name (M6_PLAN.md §6.5).

        The database enforces this with a partial unique index; this check exists so the
        planner gets told which row it collided with and why, rather than an integrity
        error naming a constraint. A duplicate is a real signal every time — either the
        same thing has been filed twice, or there are two things and nobody has
        distinguished them.

        Checked against the batch as well as the store, because two identically named
        rows arriving together is the same collision and the index would reject the
        second one with no explanation of the first.
        """
        name = submission.name.strip()

        for other_index, other in enumerate(batch):
            if other_index >= index or other.table != submission.table:
                continue
            if other.name.strip().casefold() == name.casefold():
                return (
                    f"another row in this batch (index {other_index}) is already named "
                    f"{other.name.strip()!r} in {submission.table}. Two live rows in a "
                    f"table cannot share a name: either this is the same thing filed "
                    f"twice, or they are two things and need names that tell them apart"
                )

        clash = self._live_name_clash(submission.table, name)
        if clash:
            existing = RowRef(submission.table, clash["ordinal"])
            return (
                f"{clash['name']} ({existing}) already has this name. Two live rows "
                f"in a table cannot share a name: either this is the same thing filed "
                f"twice — supersede it instead — or they are two things and need names "
                f"that tell them apart"
            )
        return None

    def _live_name_clash(
        self, table: str, name: str, exclude_ordinal: int | None = None
    ) -> dict[str, Any] | None:
        """The live row in `table` already holding `name`, if any.

        One owner for the liveness-scoped name lookup, used by submission and by the
        in-place upgrade. Case-insensitive: two rows differing only in capitalisation are
        the collision this exists to catch, not two distinct names.
        """
        found = self.storage.query(
            "SELECT ordinal, name FROM plan_rows WHERE table_name = ? "
            "AND superseded_by IS NULL AND state != 'retired' "
            "AND lower(name) = lower(?)",
            (table, name.strip()),
        )
        for row in found:
            if exclude_ordinal is None or row["ordinal"] != exclude_ordinal:
                return dict(row)
        return None

    def _containment_problem(
        self, submission: RowSubmission, batch: list[RowSubmission]
    ) -> str | None:
        """A child row type must carry exactly one `belongs_to` edge to its parent.

        v1 spelled this as a NOT NULL foreign key and the database refused an orphan.
        The stage-6 flattening kept the rows and dropped the constraint, so an orphan
        `uc_steps` row became writable, invisible and gate-clean. This is the general
        repair for that class; F20 and F24 were the two instances found by accident.

        Checked here rather than at the gate because it is well-formedness, not judgment
        — the row makes no claim without its parent — and because a gate warning arrives
        after the planner has moved on.
        """
        parent = self.containment.get(submission.table)
        if parent is None:
            return None

        owners = [link for link in submission.links if link.edge_type == "belongs_to"]
        if not owners:
            return (
                f"a {submission.table} row must declare its owning {parent} with a "
                f"belongs_to link; without one the row makes no claim, because there "
                f"is nothing for it to be true of"
            )
        if len(owners) > 1:
            return (
                f"a {submission.table} row belongs to exactly one {parent}; "
                f"{len(owners)} belongs_to links were declared"
            )

        # A stored ref names its own table (`table:ordinal`), so no lookup is needed;
        # _validate has already established that the target row exists. `target` may be
        # a RowRef or the string spelling of one — LinkSpec accepts both everywhere else.
        target = owners[0].target
        found = (
            batch[target].table
            if owners[0].is_intra_batch
            else RowRef.coerce(target).table
        )
        if found != parent:
            return (
                f"a {submission.table} row belongs to a {parent}, but its belongs_to "
                f"link points at {found or 'a missing row'}"
            )
        return None

    # --- contracts:74 (contracts:10 until v3 change 4 gave the selector its seventh
    # dimension and put each row's labels on the page) ---

    def read_rows(self, selector: RowSelector) -> RowPage:
        """Targeted reads, so resume cost scales with the working set rather than total
        plan size (requirements:62, decisions:49)."""
        if selector.limit <= 0:
            raise InvalidSelector("limit must be positive", field="limit",
                                  value=selector.limit)
        if selector.limit > MAX_PAGE:
            raise InvalidSelector(
                f"limit may not exceed {MAX_PAGE}: a label filter and the label read both "
                "bind one query parameter per element, so an unbounded page fails as a "
                "driver error rather than as a refusal naming the field. Page through with "
                "offset",
                field="limit", value=selector.limit,
            )
        if selector.offset < 0:
            raise InvalidSelector("offset cannot be negative", field="offset",
                                  value=selector.offset)

        where: list[str] = []
        params: list[Any] = []

        if selector.ids is not None:
            if not selector.ids:
                raise InvalidSelector("ids selector is empty", field="ids")
            marks = ", ".join("?" for _ in selector.ids)
            where.append(f"(table_name || ':' || ordinal) IN ({marks})")
            params.extend(str(RowRef.coerce(r)) for r in selector.ids)
        if selector.table is not None:
            where.append("table_name = ?")
            params.append(selector.table)
        if selector.stage is not None:
            where.append("stage = ?")
            params.append(selector.stage)
        if selector.provenance is not None:
            where.append("provenance = ?")
            params.append(str(selector.provenance))
        if selector.live_only:
            # requirements:61 — liveness is this single check.
            where.append("superseded_by IS NULL AND state != 'retired'")
        if selector.neighbourhood_of is not None:
            ref = str(RowRef.coerce(selector.neighbourhood_of))
            where.append(
                "(table_name || ':' || ordinal) IN ("
                " SELECT target_ref FROM links WHERE source_ref = ?"
                " UNION SELECT source_ref FROM links WHERE target_ref = ?)"
            )
            params.extend([ref, ref])
        if selector.labels:
            words = self._label_words(selector.labels)
            marks = ", ".join("?" for _ in words)
            where.append(
                "(table_name || ':' || ordinal) IN ("
                + LABELLED_HEADS.format(marks=marks)
                + ")"
            )
            params.extend([*words, len(words)])

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        total = self.storage.query(
            f"SELECT COUNT(*) AS n FROM plan_rows {clause}", tuple(params)  # noqa: S608
        )[0]["n"]
        rows = self.storage.query(
            f"SELECT * FROM plan_rows {clause} ORDER BY id LIMIT ? OFFSET ?",  # noqa: S608
            (*params, selector.limit, selector.offset),
        )
        page = tuple(self._hydrate(r) for r in rows)
        return RowPage(
            page, total, selector.offset, selector.limit,
            labels=self._labels_for(page),
        )

    @staticmethod
    def _label_words(labels: Any) -> list[str]:
        """The words a label filter asks for: normalised, deduplicated, order kept.

        **A bare `str` is refused**, and it is the same class of trap as `isinstance(True,
        int)`: a `str` *is* a sequence of `str`, so `labels="engine"` iterates to `'e'`,
        `'n'`, `'g'`, `'i'` — four distinct characters after dedupe — none of which is a
        term, so the page comes back empty and correct-looking. The payload parser is the one
        place allowed to be generous about this; the model stays strict.

        **Deduplicating is not tidying either.** `("engine", "engine")` would set the
        `HAVING` count to two while the query can only ever reach one, so the filter would
        silently match nothing because the caller repeated a word. Normalising first also
        collapses `("Engine", "engine")` rather than guaranteeing an empty page.
        """
        if isinstance(labels, str):
            raise InvalidSelector(
                "labels is a tuple of words, not one word: a bare string is itself a "
                "sequence of characters, so it would filter on its letters and return an "
                "empty page that looks correct. Pass ('engine',)",
                field="labels", value=labels,
            )
        words = list(dict.fromkeys(w.strip().lower() for w in labels))
        if any(not w for w in words):
            raise InvalidSelector(
                "a label is a word; one of these is empty", field="labels", value=labels
            )
        return words

    def _labels_for(self, rows: tuple[PlanRow, ...]) -> dict[RowRef, tuple[str, ...]]:
        """Each row's live labels, in one query, populated whether or not a filter was used.

        Imported inside the call because `engine/labels.py` takes this service as a
        collaborator; the two would otherwise import each other at module level. The service
        is constructed here rather than injected for the reason the reverse would fail:
        `read_rows` is called on a `RowService` built in a dozen tests and in five other
        modules, and a label mapping that is only populated where somebody remembered to
        pass a collaborator is the F50 shape — a value that is true only where refreshed.
        """
        if not rows:
            return {}
        from engine.labels import LabelService
        from engine.terms import TermService

        service = LabelService(self.storage, self, TermService(self.storage))
        return service.labels_for_page([r.ref for r in rows])

    def get(self, ref: RowRef | str) -> PlanRow:
        ref = RowRef.coerce(ref)
        row = self._row(ref)
        if row is None:
            raise RowNotFound("no such row", ref=str(ref))
        return self._hydrate(row)

    def lineage_root(self, ref: RowRef | str) -> RowRef:
        """The earliest ancestor in a row's supersession chain.

        The supersession-stable identity primitive. A record keyed on a row ref detaches
        silently the moment that row is superseded (findings:16); keyed on the lineage
        root it does not, because the root never changes. requirements:78 established
        this for gap dismissals; scope attachments take the same keying (M5_PLAN.md 2.4),
        which makes this the second application and the reason it lives here rather than
        on either caller.
        """
        current = RowRef.coerce(ref)
        seen: set[str] = set()
        while True:
            if str(current) in seen:  # defensive: a cycle in lineage is corruption
                return current
            seen.add(str(current))
            found = self.storage.query(
                "SELECT supersedes FROM plan_rows WHERE table_name = ? AND ordinal = ?",
                (current.table, current.ordinal),
            )
            if not found or not found[0]["supersedes"]:
                return current
            current = RowRef.parse(found[0]["supersedes"])

    def lineage_head(self, ref: RowRef | str) -> RowRef:
        """The live end of a row's supersession chain — `lineage_root`'s mirror.

        The root is the stable *identity* of a thing; the head is its current *state*. Both
        are needed and for opposite reasons: key on the root so a reference never detaches,
        read the head to answer "and where does that stand now".

        This is what serves "I decided something yesterday — what became of it" without a
        stored `updated_at` on an immutable row (see `PlanRow.updated_at`). The question is
        about a lineage, so it is answered by walking one.
        """
        current = RowRef.coerce(ref)
        seen: set[str] = set()
        while True:
            if str(current) in seen:  # defensive: a cycle in lineage is corruption
                return current
            seen.add(str(current))
            found = self.storage.query(
                "SELECT superseded_by FROM plan_rows WHERE table_name = ? AND ordinal = ?",
                (current.table, current.ordinal),
            )
            if not found or not found[0]["superseded_by"]:
                return current
            current = RowRef.parse(found[0]["superseded_by"])

    def history(self, ref: RowRef | str) -> list:
        """Every version of a thing, oldest first, from lineage root to live head.

        `requirements:61`'s lineage made readable. Each row carries its own `created_at`, so
        this answers both halves of the owner's question at once: *when* each version was
        written, and *what it said at the time*.
        """
        rows, current = [], self.lineage_root(ref)
        while True:
            row = self.get(current)
            rows.append(row)
            if row.superseded_by is None:
                return rows
            current = row.superseded_by

    def _row(self, ref: RowRef | str):
        ref = RowRef.coerce(ref)
        rows = self.storage.query(
            "SELECT * FROM plan_rows WHERE table_name = ? AND ordinal = ?",
            (ref.table, ref.ordinal),
        )
        return rows[0] if rows else None

    def _hydrate(self, row) -> PlanRow:
        ref = RowRef(row["table_name"], row["ordinal"])
        links = tuple(
            LinkSpec(RowRef.parse(r["target_ref"]), r["edge_type"])
            for r in self.storage.query(
                "SELECT target_ref, edge_type FROM links WHERE source_ref = ? "
                "ORDER BY id",
                (str(ref),),
            )
        )
        return PlanRow(
            ref=ref,
            content=json.loads(row["content"]),
            name=row["name"],
            provenance=Provenance(row["provenance"]),
            state=RowState(row["state"]),
            created_at=row["created_at"],
            assumption_kind=row["assumption_kind"],
            stage=row["stage"],
            supersedes=RowRef.parse(row["supersedes"]) if row["supersedes"] else None,
            superseded_by=(
                RowRef.parse(row["superseded_by"]) if row["superseded_by"] else None
            ),
            superseded_at=row["superseded_at"],
            retired_at=row["retired_at"],
            retire_reason=row["retire_reason"],
            links=links,
            grounds=row["grounds"],
            alternatives=row["alternatives"],
            supersede_reason=row["supersede_reason"],
        )

    # --- contracts:70 ---

    def resolve_assumption(
        self,
        ref: RowRef | str,
        quote: str,
        resolution: str,
        idempotency_key: str,
        retire_reason: str | None = None,
        name: str | None = None,
    ) -> PlanRow:
        """Upgrade the SAME row in place to decided, with the owner's answer quoted.

        requirements:18/19 — the gap clears immediately and no duplicate row appears.
        This fixes the friction recorded in decisions:28(a), where an assumption could
        only be resolved by creating a second row.

        `retire_reason` overrides the default for a rejection. The owner is not the only
        thing that can settle an assumption: validation-service closes world-assumptions
        from spike evidence (requirements:25), and recording those as "rejected by the
        owner" would put a falsehood in the audit trail. See DEFECTS.md F14.

        `name` is **required when the resolution is `revise`** and optional otherwise
        (M6_PLAN.md §6.6). This is the one write that changes a live row's content in
        place, so it is the one write where a name can quietly stop being true. A
        `confirm` records that the owner agreed and changes no meaning; a `reject` retires
        the row, which takes it out of live reads altogether. Demanding a re-name in
        either case would be friction with nothing behind it, and a check that fires when
        nothing happened is a check people learn to click through.

        Supplying a name on a `confirm` is still allowed — re-affirming deliberately is
        exactly the act this design wants to be possible.
        """
        ref = RowRef.coerce(ref)
        row = self._row(ref)
        if row is None:
            raise RowNotFound("no such row; nothing written", ref=str(ref))
        if row["state"] != RowState.ASSUMED or row["provenance"] != Provenance.ASSUMED:
            raise NotAssumed(
                "row is not an open assumption; no write occurred",
                ref=str(ref),
                state=row["state"],
                provenance=row["provenance"],
            )
        if resolution not in ("confirm", "revise", "reject"):
            raise UpgradeFailed(
                "resolution must be confirm|revise|reject",
                ref=str(ref),
                resolution=resolution,
            )
        if not quote or not quote.strip():
            raise UpgradeFailed(
                "the owner's answer must be quoted verbatim (requirements:18)",
                ref=str(ref),
            )
        # A rejection retires the row, so it is a retirement and costs a reason like any
        # other. Supplying a blank one is refused rather than quietly replaced by the
        # default below: the default says the *owner* rejected it, and validation-service
        # closing a world-assumption from spike evidence would be recording a falsehood
        # (F14). Not supplying one at all is the documented way to take the default.
        if resolution == "reject" and retire_reason is not None and not retire_reason.strip():
            raise RetireNeedsReason(
                f"rejecting {row['name']} ({ref}) retires it, which records why. Pass the "
                f"reason, or omit it entirely to record that the owner rejected it",
                ref=str(ref),
            )

        if resolution == "revise" and (not name or not name.strip()):
            raise UpgradeFailed(
                f"revising {row['name']} ({ref}) changes what the row says, so it needs "
                f"a name for what it says now — pass the same one to keep it "
                f"deliberately, or a new one",
                ref=str(ref),
                resolution=resolution,
            )
        if name and name.strip():
            clash = self._live_name_clash(ref.table, name, exclude_ordinal=ref.ordinal)
            if clash:
                raise UpgradeFailed(
                    f"{clash['name']} ({RowRef(ref.table, clash['ordinal'])}) already "
                    f"has this name; two live rows in a table cannot share one",
                    ref=str(ref),
                )

        content = json.loads(row["content"])
        content["owner_answer"] = {"quote": quote, "resolution": resolution,
                                   "resolved_at": now()}
        target_state = RowState.RETIRED if resolution == "reject" else RowState.ACTIVE
        values: dict[str, Any] = {
            "content": json.dumps(content),
            "name": name.strip() if name and name.strip() else row["name"],
            # Refreshed even on a confirm, which appends the owner's answer to content:
            # leaving the fingerprint stale would make the *next* write look like a
            # change of meaning when the change already happened here.
            "named_for": content_fingerprint(content),
            "provenance": str(Provenance.DECIDED),
            "state": str(target_state),
            "assumption_kind": None,
        }
        if resolution == "reject":
            values["retired_at"] = now()
            values["retire_reason"] = (
                stored_text(retire_reason) or "assumption rejected by the owner"
            )

        op = Op("update", "plan_rows", values,
                where={"table_name": ref.table, "ordinal": ref.ordinal})
        receipt = self.storage.write_atomic([op], idempotency_key)
        result = receipt["results"][0]
        if result is not None and result.get("rows") == 0:
            raise UpgradeFailed("upgrade could not be applied", ref=str(ref))
        return self.get(ref)

    # --- contracts:71 ---

    def supersede_row(
        self,
        old: RowRef | str,
        replacement: RowSubmission,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """requirements:61 — the replacement is created with a supersedes pointer, the
        old row is stamped once with superseded_by and a timestamp, and content is
        never edited.

        `reason` is why the *old* row was abandoned, and it is required (v3 change 2). It
        is a positional parameter with no default on purpose: a default of `""` would leave
        every existing caller compiling and every existing caller wrong, silently.

        It is stamped on the old row, exactly as `retire_reason` is, and it answers a
        different question from the replacement's `grounds`. The grounds say why the new
        content is right; the reason says what was learned that made the old content wrong.
        """
        old = RowRef.coerce(old)
        row = self._row(old)
        if row is None:
            raise RowNotFound("no such row", ref=str(old))
        if row["superseded_by"]:
            raise AlreadySuperseded(
                "lineage is write-once; supersede the live replacement instead",
                ref=str(old),
                superseded_by=row["superseded_by"],
            )
        # After the two lineage guards and before the name check: a blank reason on a ref
        # that does not exist should report the missing row, which is the thing most wrong.
        if not reason or not reason.strip():
            raise SupersedeNeedsReason(
                f"superseding {row['name']} ({old}) records why it was abandoned — what "
                f"was learned that makes the old content wrong. The replacement's own "
                f"grounds say why the new content is right, which is a different sentence",
                ref=str(old),
            )

        if not replacement.name or not replacement.name.strip():
            raise RowNotFound(
                f"the row replacing {row['name']} ({old}) needs a name — pass the same "
                f"one if this sharpens what the row already said, or a new one if it "
                f"says something different",
                ref=str(old),
            )

        # D16 — superseding is the second door that mints a world-assumption (a decided
        # row can be replaced by one), so it carries the same filing lock as submit_rows:
        # a world-assumption replacement is filed with its spike, atomically, and a spike
        # on any other replacement is refused.
        spike_problem = self._spike_problem(replacement)
        if spike_problem is not None:
            raise SpikeRequired(spike_problem, ref=str(old))

        stamp = now()
        insert = Op(
            "insert_row",
            "plan_rows",
            {
                "table_name": replacement.table,
                "content": json.dumps(replacement.content),
                "name": replacement.name.strip(),
                "named_for": content_fingerprint(replacement.content),
                "provenance": str(replacement.provenance),
                "assumption_kind": replacement.assumption_kind,
                "state": str(replacement.initial_state()),
                "stage": replacement.stage,
                "supersedes": str(old),
                "created_at": stamp,
                # The replacement writes its own decision context and inherits none: an
                # argument for the old content attached to new content is worse than an
                # empty field, because it reads as though somebody had checked.
                "grounds": stored_text(replacement.grounds),
                "alternatives": stored_text(replacement.alternatives),
            },
        )
        # All three writes ride one transaction, in this order, and the order is load-
        # bearing. A replacement may keep its original's name — that is the *redefinition*
        # case, the same thing said more sharply — so the old row has to leave the live
        # name index before the replacement enters it. Its state goes first; its
        # superseded_by pointer can only be written once the insert has assigned a ref,
        # which `FromOp` reads back from the earlier op in the same batch.
        #
        # It was two separate write_atomic calls until 2026-07-22, which meant a crash
        # between them left the old row live and unstamped beside its own replacement.
        #
        # `supersede_reason` rides the first op rather than an op of its own: that op
        # already targets the old row, and a stamp in a second write is a stamp a crash can
        # lose — which is the failure this batch was built to close.
        where_old = {"table_name": old.table, "ordinal": old.ordinal}
        batch = [
            Op("update", "plan_rows",
               {"state": str(RowState.SUPERSEDED), "superseded_at": stamp,
                "supersede_reason": stored_text(reason)},
               where=where_old),
            insert,
            Op("update", "plan_rows",
               {"superseded_by": FromOp(1, "ref")},
               where=where_old),
        ]
        # D16 — a world-assumption replacement carries its spike into the same transaction,
        # borrowing the ref the insert (position 1) assigns.
        spike_ops: list[tuple[int, str]] = []
        if replacement.spike is not None:
            spike_ops.append((len(batch), spike_slug(replacement.spike.question)))
            batch.append(spike_insert_op(FromOp(1, "ref"), replacement.spike))

        receipt = self.storage.write_atomic(batch, idempotency_key)
        self._create_spike_directories(receipt, spike_ops)
        new_ref = RowRef.parse(receipt["results"][1]["ref"])
        return {"old": old, "new": new_ref, "superseded_at": stamp}

    # --- contracts:72 ---

    def retire_row(
        self, ref: RowRef | str, reason: str, idempotency_key: str
    ) -> PlanRow:
        ref = RowRef.coerce(ref)
        row = self._row(ref)
        if row is None:
            raise RowNotFound("no such row", ref=str(ref))
        if row["state"] == RowState.RETIRED:
            raise AlreadyRetired(
                "refused so the audit trail records exactly one retirement",
                ref=str(ref),
                retired_at=row["retired_at"],
            )
        if not reason or not reason.strip():
            raise RetireNeedsReason(
                f"retiring {row['name']} ({ref}) takes it out of every live read, so it "
                f"records why — a later reader finding it gone needs the sentence, not "
                f"the timestamp",
                ref=str(ref),
            )
        op = Op(
            "update",
            "plan_rows",
            {"state": str(RowState.RETIRED), "retired_at": now(),
             "retire_reason": stored_text(reason)},
            where={"table_name": ref.table, "ordinal": ref.ordinal},
        )
        self.storage.write_atomic([op], idempotency_key)
        return self.get(ref)

    # --- no contract: v3 D11, and `surface.py`'s ADDED records why ---

    def record_grounds(
        self,
        ref: RowRef | str,
        grounds: str,
        alternatives: str,
        idempotency_key: str,
    ) -> PlanRow:
        """Give an existing row the decision context it was filed without.

        **Why this exists at all.** Every row filed before schema 9 has no recorded
        argument, and content is never edited: `submit_rows` files new rows,
        `supersede_row` replaces one, `retire_row` retires. Without this call the only
        route to closing the first reading would be superseding every row in the plan —
        each needing a full replacement submission and a supersede reason for an
        abandonment that never happened.

        **Write-once per field.** Writing an argument that was never recorded is not
        editing the row's claim; the content is untouched and the field was empty. But if
        an argument can be rewritten, it becomes a place to revise history quietly, which
        this store permits nowhere else — so changing an argument means superseding the
        row, with the audit trail that already exists.

        Per *field* rather than per row, because `submit_rows` makes both optional: a row
        that arrived with grounds and no alternatives must still be able to acquire its
        alternatives, and under a per-row rule the only remedy would be superseding a row
        that nothing is wrong with.
        """
        ref = RowRef.coerce(ref)
        replay = self.storage.replay(idempotency_key)
        if replay is not None:
            # decisions:43 — the key returns the original answer. Checked before the
            # guards, because a replay of a call that succeeded would otherwise refuse
            # with GroundsAlreadyRecorded against the write it made itself.
            return self.get(ref)

        row = self._row(ref)
        if row is None:
            raise RowNotFound("no such row; nothing written", ref=str(ref))
        if row["superseded_by"] or row["state"] in (
            RowState.SUPERSEDED, RowState.RETIRED
        ):
            raise RowNotLive(
                f"{row['name']} ({ref}) is {row['state']}, and a frozen row's argument is "
                f"history — improving it would improve the case for a decision that has "
                f"already been replaced. Record the grounds on the live row instead",
                ref=str(ref),
                state=row["state"],
            )

        values: dict[str, Any] = {}
        for field_name, value in (("grounds", grounds),
                                  ("alternatives", alternatives)):
            clean = stored_text(value)
            if clean and row[field_name]:
                raise GroundsAlreadyRecorded(
                    f"{row['name']} ({ref}) already records its {field_name}, and an "
                    f"argument is write-once. Changing what a row says — or why — is "
                    f"what supersede_row() is for",
                    ref=str(ref),
                    field=field_name,
                )
            if not clean and not row[field_name]:
                raise GroundsNeedBoth(
                    f"{row['name']} ({ref}) needs its {field_name} as well. There is no "
                    f"exemption: a row with no alternative writes so — \"none, this "
                    f"follows directly from the requirement\" is a complete answer when "
                    f"it is true",
                    ref=str(ref),
                    field=field_name,
                )
            if clean:
                unresolved = unresolved_refs(clean, lambda r: self._row(r) is not None)
                if unresolved:
                    raise UnresolvedReference(
                        f"{field_name} cites {', '.join(unresolved)}, which names no row. "
                        f"An argument is written once and every reader of this row renders "
                        f"it, so an address with nothing behind it would fail every read of "
                        f"{row['name']} ({ref}) from here on. Note that a URL with a port "
                        f"reads as an address — write it without one",
                        ref=str(ref),
                        field=field_name,
                        unresolved=unresolved,
                    )
                values[field_name] = clean

        if not values:
            # Both fields are already recorded and the call supplied nothing new. There is
            # no write to make, and reporting success for a call that changed nothing is
            # how a planner comes to believe an argument landed when it did not.
            raise GroundsAlreadyRecorded(
                f"{row['name']} ({ref}) already records its grounds and its alternatives, "
                f"and an argument is write-once. Changing what a row says — or why — is "
                f"what supersede_row() is for",
                ref=str(ref),
                field="grounds and alternatives",
            )

        self.storage.write_atomic(
            [Op("update", "plan_rows", values,
                where={"table_name": ref.table, "ordinal": ref.ordinal})],
            idempotency_key,
        )
        return self.get(ref)
