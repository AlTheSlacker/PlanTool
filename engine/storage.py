"""storage-engine (components:1).

Sole owner of persistence. Every other component reaches the database through the typed
operations here; none of them holds a connection or emits SQL.

Contracts implemented: contracts:1 init_plan, contracts:2 write_atomic, contracts:5
integrity_check, contracts:6 recover, contracts:7 snapshot_version, contracts:8 migrate.

**There is no writer lock, deliberately.** An earlier design claimed a lease row before
writing and let a second session take it over once the first had been silent ten minutes.
That protected against two planning sessions interleaving changes — a situation this tool
does not have. Planning is one person in one session, and the owner ruled the scenario out
of scope on 2026-07-22. SQLite already locks the file for the duration of a write, so the
file cannot be corrupted mid-write without it. Removing the lease also removed the last
place where elapsed time decided who owned the data, which was the real cost of keeping it:
a ten-minute silence is a guess about whether a process is dead, and a wrong guess is an
intermittent, unreproducible failure. Do not reintroduce it.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from engine import schema
from engine.clock import now
from engine.errors import (
    MigrationFailed,
    NoGoodVersion,
    PlanAlreadyExists,
    StorageUnavailable,
)

#: dep_failure_modes:2 — how long a write may wait for the database before the attempt is
#: treated as unavailability. Handed to sqlite3.connect(), so it expires *before* anything
#: commits: the caller is told the write did not happen, and it did not.
WRITE_BUDGET_SECONDS = 30.0

PLAN_FILENAME = "plan.db"

#: `terms` exactly as schema 4 created it, frozen here for the 3 -> 4 migration step.
#:
#: **A migration is a point-in-time step and must name a point-in-time text.** That branch
#: read `schema.TERMS_DDL` until v3 change 4, which was right for as long as the table never
#: changed shape: `schema.py` says in its own words that two copies of a `CREATE TABLE` is a
#: schema that drifts between the stores that were migrated and the stores that were born.
#: Change 4 drops six of those columns. Left sharing the constant, a store climbing from 3
#: would be handed the *five*-column table of 2026-08-03 and would then reach the 10 -> 11
#: step and be asked to drop `superseded_at`, a column it never had — failing inside the one
#: migration that discards data.
#:
#: So this is not a second spelling of the live table; it is what schema 4 actually produced,
#: and it is inert. It lives here rather than in `engine/schema.py` because
#: `tests/test_schema_vocabulary.py` regexes every `CREATE TABLE IF NOT EXISTS` out of that
#: file and would read these eleven columns as live schema — the same reason the retained
#: per-version fixtures live under `tests/fixtures/`.
_TERMS_DDL_AT_4 = """
CREATE TABLE IF NOT EXISTS terms (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    term          TEXT    NOT NULL,
    definition    TEXT    NOT NULL,
    approved_at   TEXT,
    names_ref     TEXT,
    ban_scope     TEXT,
    ban_reason    TEXT,
    use_instead   TEXT,
    superseded_at TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_terms_live ON terms (term)
    WHERE superseded_at IS NULL;
"""


@dataclass(frozen=True, slots=True)
class FromOp:
    """A value borrowed from an earlier op's result, resolved at apply time.

    Needed because an id assigned by an INSERT is only known mid-transaction, while a
    batch's values are fixed before it starts. Without this, a parent row and its child
    rows cannot be written in one transaction — and splitting them across two means a
    crash in between leaves a parent with no children, which for conflict_refs would be
    an open conflict that silently blocks nothing.
    """

    index: int
    field: str = "id"


@dataclass(slots=True)
class Op:
    """One journal entry inside a batch.

    Deliberately SQL-free so the storage interface stays backend-neutral, as
    components:1 requires ("a backend-neutral storage interface (SQLite as the only v1
    backend)").
    """

    kind: Literal["insert", "update", "insert_row"]
    table: str
    values: dict[str, Any]
    where: dict[str, Any] | None = None
    #: Set by storage after an insert, so callers can learn assigned ids.
    result: dict[str, Any] | None = field(default=None, compare=False)


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    """contracts:5 — names exactly which rows are unreadable and which survive."""

    readable: tuple[str, ...]
    unreadable: tuple[str, ...]
    dangling_links: tuple[tuple[str, str], ...]
    opened: bool = True

    @property
    def ok(self) -> bool:
        return not self.unreadable and not self.dangling_links


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """contracts:6 — what was restored/salvaged/cleared. Never silent repair."""

    strategy: str
    restored_version: int | None = None
    salvaged: tuple[str, ...] = ()
    lost: tuple[str, ...] = ()
    regapped: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MigrationReport:
    """contracts:8 — states exactly what changed."""

    from_version: int
    to_version: int
    steps: tuple[str, ...]
    snapshot_id: int


class Storage:
    """A plan store rooted at a workspace directory.

    requirements:49 — all plan state lives in files inside the workspace; no
    state is written outside it.
    """

    def __init__(self, workspace: Path | str):
        self.workspace = Path(workspace)
        self.path = self.workspace / PLAN_FILENAME
        self._conn: sqlite3.Connection | None = None

    # --- connection ---

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            try:
                self._conn = sqlite3.connect(self.path, timeout=WRITE_BUDGET_SECONDS)
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA foreign_keys = ON")
                self._conn.execute("PRAGMA synchronous = FULL")
            except sqlite3.Error as exc:
                raise StorageUnavailable(
                    "cannot open the plan store", path=str(self.path), cause=str(exc)
                ) from exc
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Storage:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def exists(self) -> bool:
        return self.path.exists()

    # --- contracts:1 ---

    def init_plan(self, name: str, tier: str) -> dict[str, Any]:
        """Initialize a plan in this workspace.

        requirements:8 — the workspace itself is never created or managed by us.
        """
        if not self.workspace.is_dir():
            raise StorageUnavailable(
                "workspace directory does not exist; the tool never creates it "
                "(requirements:8)",
                workspace=str(self.workspace),
            )
        if self.exists() and self._plan_row() is not None:
            existing = self._plan_row()
            raise PlanAlreadyExists(
                "a plan already exists in this workspace; resume it, or start fresh "
                "with explicit owner confirmation (requirements:9)",
                name=existing["name"],
                state=existing["state"],
                version=existing["version"],
            )
        try:
            self.conn.executescript(schema.DDL)
            try:
                self.conn.executescript(schema.FTS_DDL)
            except sqlite3.OperationalError:
                pass  # FTS5 unavailable; search degrades, the store still works.
            self.conn.execute(
                "INSERT INTO plan (guard, name, tier, state, version, schema_version, "
                "created_at) VALUES (1, ?, ?, 'draft', 1, ?, ?)",
                (name, tier, schema.SCHEMA_VERSION, now()),
            )
            self.conn.commit()
        except sqlite3.Error as exc:
            raise StorageUnavailable(
                "plan initialization failed", cause=str(exc)
            ) from exc
        return dict(self._plan_row())

    def _plan_row(self) -> sqlite3.Row | None:
        try:
            return self.conn.execute("SELECT * FROM plan WHERE guard = 1").fetchone()
        except sqlite3.Error:
            return None

    def plan_handle(self) -> dict[str, Any]:
        row = self._plan_row()
        if row is None:
            raise StorageUnavailable("no plan in this workspace", path=str(self.path))
        return dict(row)

    # --- contracts:2 ---

    def write_atomic(
        self,
        batch: list[Op],
        idempotency_key: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply a batch atomically.

        requirements:6 — a failed write leaves no partial state.
        decisions:43 — a replayed idempotency_key returns the original receipt and
        never duplicates.

        `meta` is caller-owned data stored verbatim in the receipt. Callers that derive
        a richer result than op outputs — row-service's per-row verdicts, for instance
        — put it here so a replay can return the original answer rather than
        recomputing one against a batch that may not even match.
        """
        replay = self.conn.execute(
            "SELECT receipt FROM idempotency WHERE key = ?", (idempotency_key,)
        ).fetchone()
        if replay is not None:
            receipt = json.loads(replay["receipt"])
            receipt["replayed"] = True
            return receipt

        try:
            with self._immediate():
                for op in batch:
                    self._apply(op, batch)
                self._record_changes(batch)
                receipt = {
                    "idempotency_key": idempotency_key,
                    "written_at": now(),
                    "ops": len(batch),
                    "results": [op.result for op in batch],
                    "meta": meta or {},
                    "replayed": False,
                }
                self.conn.execute(
                    "INSERT INTO idempotency (key, receipt, created_at) VALUES (?,?,?)",
                    (idempotency_key, json.dumps(receipt), now()),
                )
        except sqlite3.Error as exc:
            raise StorageUnavailable("atomic write failed", cause=str(exc)) from exc

        # A budget check stood here, timing the write and raising StorageUnavailable if it
        # took longer than WRITE_BUDGET_SECONDS. It ran *after* the transaction committed,
        # so a slow-but-successful write reported failure for data that was already on
        # disk. Deleted 2026-07-22. The case it was meant to catch — a write blocked
        # waiting on the database — is caught by the same budget passed to
        # sqlite3.connect() above, which gives up *before* committing and so reports a
        # failure that is true.
        return receipt

    def replay(self, idempotency_key: str) -> dict[str, Any] | None:
        """The receipt stored against a key, or None if the key is new."""
        row = self.conn.execute(
            "SELECT receipt FROM idempotency WHERE key = ?", (idempotency_key,)
        ).fetchone()
        if row is None:
            return None
        receipt = json.loads(row["receipt"])
        receipt.setdefault("meta", {})
        receipt["replayed"] = True
        return receipt

    def annotate(self, idempotency_key: str, meta: dict[str, Any]) -> None:
        """Merge caller-owned data into an existing receipt.

        Used where the richer result is only known after the write lands — row-service
        cannot know assigned refs until its ops have executed.
        """
        row = self.conn.execute(
            "SELECT receipt FROM idempotency WHERE key = ?", (idempotency_key,)
        ).fetchone()
        if row is None:
            return
        receipt = json.loads(row["receipt"])
        receipt.setdefault("meta", {}).update(meta)
        with self._immediate():
            self.conn.execute(
                "UPDATE idempotency SET receipt = ? WHERE key = ?",
                (json.dumps(receipt), idempotency_key),
            )

    @staticmethod
    def _resolve(values: dict[str, Any], batch: list[Op]) -> dict[str, Any]:
        if not any(isinstance(v, FromOp) for v in values.values()):
            return values
        resolved = {}
        for key, value in values.items():
            if not isinstance(value, FromOp):
                resolved[key] = value
                continue
            source = batch[value.index]
            if source.result is None or value.field not in source.result:
                raise ValueError(
                    f"op {value.index} produced no {value.field!r} to borrow"
                )
            resolved[key] = source.result[value.field]
        return resolved

    def _apply(self, op: Op, batch: list[Op] | None = None) -> None:
        # Values are resolved into a local: `op` itself must stay the caller's object,
        # since callers read the assigned ref back off op.result.
        op_values = self._resolve(op.values, batch or [op])
        if op.kind == "insert_row":
            # Ordinals are per-table and must be assigned inside the transaction, or
            # two concurrent submissions race for the same ref.
            table_name = op_values["table_name"]
            ordinal = self.conn.execute(
                "SELECT COALESCE(MAX(ordinal), 0) + 1 AS n FROM plan_rows "
                "WHERE table_name = ?",
                (table_name,),
            ).fetchone()["n"]
            values = {**op_values, "ordinal": ordinal}
            cols = ", ".join(values)
            marks = ", ".join("?" for _ in values)
            self.conn.execute(
                f"INSERT INTO plan_rows ({cols}) VALUES ({marks})",  # noqa: S608
                tuple(values.values()),
            )
            op.result = {"ref": f"{table_name}:{ordinal}", "ordinal": ordinal}
        elif op.kind == "insert":
            cols = ", ".join(op_values)
            marks = ", ".join("?" for _ in op_values)
            cur = self.conn.execute(
                f"INSERT INTO {op.table} ({cols}) VALUES ({marks})",  # noqa: S608
                tuple(op_values.values()),
            )
            op.result = {"id": cur.lastrowid}
        elif op.kind == "update":
            if not op.where:
                raise ValueError("update op requires a where clause")
            sets = ", ".join(f"{k} = ?" for k in op_values)
            conds = " AND ".join(f"{k} = ?" for k in op.where)
            cur = self.conn.execute(
                f"UPDATE {op.table} SET {sets} WHERE {conds}",  # noqa: S608
                (*op_values.values(), *op.where.values()),
            )
            op.result = {"rows": cur.rowcount}
        else:
            raise ValueError(f"unknown op kind {op.kind!r}")

    # --- change_log (DEVIATIONS.md D28): the GUI's polling feed ---

    def _record_changes(self, batch: list[Op]) -> None:
        """Append one change_log row per mutation, for the GUI's polling feed (D28).

        Called inside write_atomic's transaction, after every op has applied — so it commits
        atomically with the writes, a rolled-back batch records nothing, and an idempotent
        replay (which returns before the transaction opens) records nothing either. `op_type`
        is inferred from the columns each op touched; schema.CHANGE_LOG_DDL explains why that
        is a hint the GUI confirms against the row, never a lie. Deduped by (ref, op_type)
        within the batch, because a plan_rows supersession stamps the old row twice — state
        first (no pointer yet), pointer second — and that is one change to announce, not two.
        The two are merged rather than first-wins, so the pointer op's `replaced_by` is the one
        kept: dropping it would strip a supersession of the very ref that names its replacement.
        """
        replaced: dict[tuple[str, str], str | None] = {}
        order: list[tuple[str, str]] = []
        for op in batch:
            change = self._classify_change(op, batch)
            if change is None:
                continue
            ref, op_type, replaced_by = change
            key = (ref, op_type)
            if key not in replaced:
                order.append(key)
                replaced[key] = replaced_by
            elif replaced_by is not None:
                replaced[key] = replaced_by  # a later op carries the pointer the first lacked
        for ref, op_type in order:
            self.conn.execute(
                "INSERT INTO change_log (op_type, ref, replaced_by, created_at) "
                "VALUES (?, ?, ?, ?)",
                (op_type, ref, replaced[(ref, op_type)], now()),
            )

    def _classify_change(
        self, op: Op, batch: list[Op]
    ) -> tuple[str, str, str | None] | None:
        """(ref, op_type, replaced_by) for one op, or None if it announces nothing.

        The op-type is read off the columns the write touches — the four that make up this
        schema's universal lifecycle vocabulary — in priority order: a supersession pointer
        wins over a retirement stamp, which wins over a bare state move, and a write touching
        none of them is a plain in-place update.
        """
        if op.kind == "insert_row":
            return (op.result["ref"], "create", None)
        if op.kind == "insert":
            return (f"{op.table}:{op.result['id']}", "create", None)
        if op.kind == "update":
            # An update that matched no row changed nothing: no phantom change is announced.
            if not op.result or op.result.get("rows", 0) == 0:
                return None
            values = self._resolve(op.values, batch)
            ref = self._ref_of_update(op)
            if "superseded_by" in values or "superseded_at" in values:
                return (ref, "supersede",
                        self._as_ref(op.table, values.get("superseded_by")))
            if "retired_at" in values:
                return (ref, "retire", None)
            if "state" in values:
                return (ref, "state_change", None)
            return (ref, "update", None)
        return None

    @staticmethod
    def _as_ref(table: str, pointer: Any) -> str | None:
        """A supersession pointer rendered as a `table:key` ref, matching change_log.ref.

        `plan_rows` already stores it as `table:ordinal`; the same-table id pointer
        (`briefs`) stores a bare id naming a row in the op's own table.
        """
        if pointer is None:
            return None
        text = str(pointer)
        return text if ":" in text else f"{table}:{text}"

    @staticmethod
    def _ref_of_update(op: Op) -> str:
        """The `table:key` ref an update addresses, derived from its where clause.

        Covers every shape the services use: plan_rows' (table_name, ordinal), the common
        single `id`, the `plan` singleton's `guard`, `gap_key`, and the two compound keys
        (task_deps, claim_tracks) — the last joined, having no single-column id.
        """
        where = op.where or {}
        if "table_name" in where and "ordinal" in where:
            return f"{where['table_name']}:{where['ordinal']}"
        if "id" in where:
            return f"{op.table}:{where['id']}"
        if where:
            return f"{op.table}:" + ":".join(str(v) for v in where.values())
        return op.table

    def _emit_resync(self) -> None:
        """Append a single `resync` marker: the GUI's cursor is void, full-reload (D28).

        The honest signal after a wholesale rewrite that bypasses the write choke point —
        restore, recover, a failed migration's rollback. Guarded, because a store older than
        schema 7 has no change_log, and rewinding one must not fail for lack of a feed it never
        had.
        """
        try:
            self.conn.execute(
                "INSERT INTO change_log (op_type, ref, replaced_by, created_at) "
                "VALUES ('resync', NULL, NULL, ?)",
                (now(),),
            )
        except sqlite3.Error:
            pass

    def _immediate(self):
        """A BEGIN IMMEDIATE transaction: the write lock is taken up front, so lease
        validation and application cannot be interleaved by another writer."""
        return _Immediate(self.conn)

    # --- reads used by other components (no SQL leaves this module) ---

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Internal read helper. Only engine persistence-aware modules call this, and
        only through the service functions they expose."""
        try:
            return self.conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise StorageUnavailable("read failed", cause=str(exc)) from exc

    # --- contracts:5 ---

    def integrity_check(self) -> IntegrityReport:
        try:
            self.conn.execute("SELECT 1 FROM plan LIMIT 1")
        except sqlite3.Error as exc:
            raise StorageUnavailable(
                "the store itself cannot be opened", cause=str(exc)
            ) from exc

        readable: list[str] = []
        unreadable: list[str] = []
        for row in self.query("SELECT table_name, ordinal, content FROM plan_rows"):
            ref = f"{row['table_name']}:{row['ordinal']}"
            try:
                json.loads(row["content"])
                readable.append(ref)
            except (json.JSONDecodeError, TypeError):
                unreadable.append(ref)

        live = set(readable) | set(unreadable)
        dangling = [
            (r["source_ref"], r["target_ref"])
            for r in self.query("SELECT source_ref, target_ref FROM links")
            if r["target_ref"] not in live or r["source_ref"] not in live
        ]
        return IntegrityReport(tuple(readable), tuple(unreadable), tuple(dangling))

    # --- contracts:7 ---

    def snapshot_version(self, reason: str) -> int:
        """An immutable snapshot (entities:11). Atomic: no partial snapshot survives."""
        tables = (
            "plan", "plan_rows", "links", "source_texts", "source_sections",
            # M3: overlays and ledgers that are not derivable from the rows. A snapshot
            # that dropped these would silently unblock gates on restore (open conflicts
            # gone) and re-surface dismissals the owner had already answered.
            "gap_overlay", "conflicts", "conflict_refs", "warnings",
            # v3 change 4. An overlay keyed on lineage roots, the same primitive as
            # gap_overlay, holding judgments that cannot be recomputed from the rows.
            # Outside the set, `restore_snapshot` on an abandoned revision would rewind
            # `plan_rows` and strand attachments on roots that no longer exist, and
            # `recover('restart')` would orphan every one of them — neither column carries
            # a foreign key that would catch it, and `remove_term`'s refusal would then
            # count rows that are not there. `terms` itself stays out: it is not derived
            # from the plan and a revision does not rewind it, but the attachment of a
            # word to a row is a judgment *about* the plan.
            "label_attachments",
        )
        # source_fts is a derived index, rebuilt from source_texts on restore.
        #
        # **A table the store does not have yet is skipped, and that is a migration
        # requirement rather than defensiveness.** `migrate` snapshots *before* it applies
        # any step (decisions:45), so the moment a schema change adds a table to this set,
        # every store below that version snapshots a table it is about to be given.
        # `label_attachments` is the first: without this, `migrate(11)` on the one real
        # database fails on its own safety snapshot, before touching anything. A store that
        # predates the table genuinely has no rows in it, and `_restore_payload` writes only
        # the tables the payload names, so a rewind of that snapshot leaves it alone.
        present = {
            r["name"] for r in self.query(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        payload = {
            t: [dict(r) for r in self.query(f"SELECT * FROM {t}")]  # noqa: S608
            for t in tables
            if t in present
        }
        version = self.plan_handle()["version"]
        try:
            with self._immediate():
                cur = self.conn.execute(
                    "INSERT INTO plan_versions (version, reason, payload, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (version, reason, json.dumps(payload), now()),
                )
                snapshot_id = cur.lastrowid
        except sqlite3.Error as exc:
            raise StorageUnavailable("snapshot failed", cause=str(exc)) from exc
        return snapshot_id

    def restore_snapshot(self, snapshot_id: int) -> int:
        """Rewind the store to a specific snapshot (entities:11) — revision-service's abandon.

        Distinct from `recover('restore')`, which always takes the *latest* snapshot: a
        revision rewinds to the snapshot it took when it opened, named by id, whatever has
        happened since. Only the tables the snapshot covers are touched, so the revision and
        its repercussions — stored outside it — survive the rewind (requirements:72).
        """
        snap = self.conn.execute(
            "SELECT version, payload FROM plan_versions WHERE id = ?", (snapshot_id,)
        ).fetchone()
        if snap is None:
            raise NoGoodVersion("no such snapshot to rewind to", snapshot=snapshot_id)
        self._restore_payload(json.loads(snap["payload"]))
        return snap["version"]

    def _latest_snapshot(self) -> sqlite3.Row | None:
        rows = self.query(
            "SELECT * FROM plan_versions ORDER BY id DESC LIMIT 1"
        )
        return rows[0] if rows else None

    # --- contracts:6 ---

    def recover(self, strategy: Literal["restore", "salvage", "restart"]) -> RecoveryReport:
        report = self.integrity_check()
        if strategy == "restore":
            snap = self._latest_snapshot()
            if snap is None:
                raise NoGoodVersion(
                    "no readable PlanVersion snapshot exists; salvage and restart "
                    "remain available"
                )
            self._restore_payload(json.loads(snap["payload"]))
            return RecoveryReport("restore", restored_version=snap["version"])

        if strategy == "salvage":
            # requirements:11 — lost areas are re-flagged as gaps for re-elicitation;
            # the gap rows themselves are gap-engine's job (M2), so we name them here.
            with self._immediate():
                for ref in report.unreadable:
                    table, ordinal = ref.split(":")
                    self.conn.execute(
                        "DELETE FROM plan_rows WHERE table_name = ? AND ordinal = ?",
                        (table, int(ordinal)),
                    )
                self._emit_resync()  # rows vanished outside _apply; GUI must reload (D28)
            return RecoveryReport(
                "salvage",
                salvaged=report.readable,
                lost=report.unreadable,
                regapped=report.unreadable,
            )

        if strategy == "restart":
            with self._immediate():
                # The ledgers go too: a conflict contesting a row that no longer exists
                # would block gates forever with a reason nobody can act on, and a
                # dismissal keyed to a deleted lineage root can never be reopened.
                for t in ("plan_rows", "links", "source_texts", "source_sections",
                          "gap_overlay", "conflicts", "conflict_refs", "warnings"):
                    self.conn.execute(f"DELETE FROM {t}")  # noqa: S608
                self._emit_resync()  # everything cleared outside _apply; GUI must reload (D28)
            return RecoveryReport("restart", lost=report.readable + report.unreadable)

        raise ValueError(f"unknown strategy {strategy!r}")

    def _restore_payload(self, payload: dict[str, list[dict]]) -> None:
        with self._immediate():
            for table, rows in payload.items():
                self.conn.execute(f"DELETE FROM {table}")  # noqa: S608
                for row in rows:
                    cols = ", ".join(row)
                    marks = ", ".join("?" for _ in row)
                    self.conn.execute(
                        f"INSERT INTO {table} ({cols}) VALUES ({marks})",  # noqa: S608
                        tuple(row.values()),
                    )
            # A wholesale rewrite bypasses _apply, so nothing above fed the change_log. One
            # resync marker tells a watching GUI to full-reload, instead of a per-row flood
            # for a replace it never drove (D28). change_log is not a payload table, so the
            # feed's own history survives the rewind.
            self._emit_resync()

    # --- contracts:8 ---

    def migrate(self, target_schema_version: int) -> MigrationReport:
        """decisions:45 — a snapshot is taken before any migration, and a failure
        restores it. Silent migration is forbidden.

        **A multi-version target is walked one hop at a time.** `_migration_steps` only
        knows adjacent pairs, and its docstring has claimed since schema 8 that `migrate`
        chains — it did not, and v3 change 2 is the first change where that mattered: the
        retained schema-7 fixture now has two hops to cross, and `migrate(9)` on it would
        have raised "no migration path from 7 to 9" on a path that exists twice over. The
        hops are collected before anything is written and applied inside the one
        transaction, so a failure at the second hop leaves the store at neither.
        """
        current = self.plan_handle()["schema_version"]
        if target_schema_version == current:
            return MigrationReport(current, current, (), self.snapshot_version(
                "pre-migration (no-op)"
            ))
        snapshot_id = self.snapshot_version(
            f"pre-migration {current} -> {target_schema_version}"
        )
        try:
            steps = self._chained_steps(current, target_schema_version)
            with self._immediate():
                for sql in steps:
                    self.conn.execute(sql)
                self.conn.execute(
                    "UPDATE plan SET schema_version = ? WHERE guard = 1",
                    (target_schema_version,),
                )
        except (sqlite3.Error, ValueError) as exc:
            snap = self.conn.execute(
                "SELECT payload FROM plan_versions WHERE id = ?", (snapshot_id,)
            ).fetchone()
            self._restore_payload(json.loads(snap["payload"]))
            raise MigrationFailed(
                "migration failed; the pre-migration snapshot was restored",
                from_version=current,
                to_version=target_schema_version,
                cause=str(exc),
            ) from exc
        return MigrationReport(
            current, target_schema_version, tuple(steps), snapshot_id
        )

    def _chained_steps(self, current: int, target: int) -> list[str]:
        """Every adjacent hop from `current` to `target`, in order.

        A downgrade is handed to `_migration_steps` unchanged so that it raises rather than
        returning an empty list: `range(current, target)` is empty when the target is lower,
        and an empty step list applied to a store would be exactly the silent no-op
        decisions:45 forbids — it would stamp the lower version and change nothing.
        """
        if target < current:
            return self._migration_steps(current, target)
        steps: list[str] = []
        for version in range(current, target):
            steps.extend(self._migration_steps(version, version + 1))
        return steps

    def _migration_steps(self, current: int, target: int) -> list[str]:
        """The SQL that moves the store from one schema version to the next.

        Eight paths exist. Seven of them pass the same test — the migrated value is a truth
        the old store already implied, never one invented to satisfy a NOT NULL — and the
        eighth, 10 -> 11, is the first that **discards** something, which it says out loud
        below rather than leaving to be discovered by its absence:

          **3 -> 4** adds the glossary. A plan that predates it genuinely has an empty one.
          (A `2 -> 3` step is *absent* on purpose: it would have to invent a name for every
          finding, which is precisely what that column exists to prevent.)

          **4 -> 5** adds `findings.resolve_by` (D15). Before D15 the only gate that blocked
          on an open finding was finalization, so every finding was implicitly "resolve by
          finalization" — the DEFAULT below states that, it does not manufacture it. The
          literal is the terminal package of the shipped standard methodology; a migration
          is a point-in-time step and is allowed to name it.

          **5 -> 6** adds the revision tables (M7). They start empty; a plan that predates
          revision-service genuinely has no revisions, so nothing is invented.

          **6 -> 7** adds the GUI's `change_log` (D28). Same shape: a plan written before the
          feed existed has no change history, the table starts empty, and a watching GUI
          cold-loads the current state rather than being handed a backfilled past.

          **7 -> 8** is v3 change 1, and it is the first step that *removes* rather than adds:
          the build grouping and the sub-task level go, `obligation` becomes `behaviour`, and
          the planning-sense `package` becomes `stage`. Where the old store holds something
          the new shape cannot express, it is refused rather than resolved — see
          `_guard_7_to_8`. Only adjacent pairs are handled here, so a store at 7 reaching 11
          is migrated one step at a time by `migrate`.

          **8 -> 9** is v3 change 2: `plan_rows` gains `grounds`, `alternatives` and
          `supersede_reason`, and `findings.rationale` takes the name `findings.reason`. It
          backfills nothing, and that is the same test the others pass rather than an
          exception to it: no truth in the old store says what any row's argument was, and
          a manufactured one would read as though somebody had checked. The columns arrive
          NULL and the gap engine reports them on the next derive.

          **9 -> 10** is v3 change 3, the catalogue. Both tables start empty and it
          backfills nothing, which is the glossary's test again rather than an exception to
          it: a plan written before the catalogue existed has no catalogue, and there is no
          truth in the old store from which a set of function names could be derived. The
          one place such a truth exists is the *tree*, and deriving the catalogue from a
          tree is the design `FUNCTION_CATALOGUE.md` §7 rejects, for dragging
          language-specific declaration-finding into the engine.

          Neither does it join the snapshot table set, which reverses the instinct for a
          mechanical reason: `snapshot_version` carries nine tables and `tasks` is not among
          them — the whole execution layer sits outside snapshots. A `catalogue` inside the
          set would be rewound while the `tasks` rows its `task_id` references were not,
          leaving entries and tasks describing two different plans with nothing complaining.
          Both stay out, together. The inherited consequence is named rather than fixed:
          `recover('restart')` clears eight tables and leaves `terms`, `findings` and the
          execution layer standing, so the catalogue joins that set and a restart leaves a
          catalogue of a plan that no longer exists. That is v2's behaviour for every table
          outside the eight, and fixing it would be a change about recovery.

          **10 -> 11** is v3 change 4, and it is the first step in this engine that **loses
          data**. `terms` drops `approved_at`, `names_ref`, `ban_scope`, `ban_reason`,
          `use_instead` and `superseded_at`, so the ban metadata on an existing plan and
          every superseded definition go with them; the words and their live meanings
          survive. Nothing is invented — a record is dropped on the owner's explicit
          instruction, which is the difference between this and `_guard_7_to_8`'s refusals:
          there, collapsing several declared groupings would have manufactured a claim about
          the owner's grouping, and here he has said what to discard. `label_attachments` is
          created empty, which is the glossary's own test again.

          It reduces `terms` **in place**, with `ALTER TABLE ... DROP COLUMN`, and that was
          settled by probe rather than by argument: the draft asserted a table rebuild was
          required. `DROP COLUMN` has existed since SQLite 3.35 and this engine runs 3.49.1.
          Probed on 2026-07-30 against a v10 `terms` holding a redefined word and a banned
          one — the drops and the index swap work inside `BEGIN IMMEDIATE`, `sqlite_sequence`
          is preserved so ids are never reused, and forcing a failure on the last step rolls
          back to all eleven columns with every row intact. A rebuild would have needed a
          second `CREATE TABLE terms` written here, which `schema.py` forbids in as many
          words.

        Anything else is an error and never a silent no-op (decisions:45) — including a
        downgrade, which would have to drop rows to succeed.
        """
        if (current, target) == (10, 11):
            return self._steps_10_to_11()
        if (current, target) == (9, 10):
            # v3 change 3. Both tables are created from `CATALOGUE_DDL` rather than from SQL
            # restated here, which is what three of the four older branches do (3 -> 4, 5 -> 6,
            # 6 -> 7). The rule the four share is not "always call `statements()`" — 4 -> 5 is
            # the mixed case and issues an ALTER of its own — but this: *a whole table is
            # created from the one text; a column added to an existing table is an ALTER the
            # DDL also carries.* This change is purely the first kind.
            return schema.statements(schema.CATALOGUE_DDL)
        if (current, target) == (8, 9):
            # The three ADD COLUMNs are in the order `schema.DDL` declares them, and the
            # DDL declares them last. `ADD COLUMN` appends, so any other pairing gives a
            # migrated store the same columns at different `cid`s and fails schema parity.
            return [
                "ALTER TABLE plan_rows ADD COLUMN grounds TEXT",
                "ALTER TABLE plan_rows ADD COLUMN alternatives TEXT",
                "ALTER TABLE plan_rows ADD COLUMN supersede_reason TEXT",
                "ALTER TABLE findings RENAME COLUMN rationale TO reason",
            ]
        if (current, target) == (7, 8):
            self._guard_7_to_8()
            return self._steps_7_to_8()
        if (current, target) == (3, 4):
            # The frozen text, not `schema.TERMS_DDL` — see `_TERMS_DDL_AT_4` above. This
            # step creates the table schema 4 had, and the 10 -> 11 step below is what
            # reduces it, exactly as it does for a store that was born at 4.
            return schema.statements(_TERMS_DDL_AT_4)
        if (current, target) == (4, 5):
            return [
                "ALTER TABLE findings ADD COLUMN resolve_by INTEGER NOT NULL DEFAULT 8",
                *schema.statements(schema.REALLOCATIONS_DDL),
            ]
        if (current, target) == (5, 6):
            # M7 adds the revision tables. A plan that predates them genuinely has no
            # revisions — the new tables start empty, inventing nothing (M7_PLAN.md).
            return schema.statements(schema.REVISIONS_DDL)
        if (current, target) == (6, 7):
            # D28 adds the GUI's change_log. A plan written before the feed existed has no
            # change history — the table starts empty and a watching GUI cold-loads, so
            # nothing is invented.
            return schema.statements(schema.CHANGE_LOG_DDL)
        raise ValueError(
            f"no migration path from schema version {current} to {target}"
        )

    def _steps_10_to_11(self) -> list[str]:
        """v3 change 4: the glossary reduces, and labels arrive.

        **The order is not stylistic. Two of its three dependencies were probed and both
        bite**, and they bite inside the step that is discarding data:

        - The `DELETE` runs **first**, because after the drops there is no `superseded_at`
          left to filter on. Under the old schema a redefinition wrote a new row and stamped
          the old one, so a word that has ever been redefined has several rows and one live.
          The new `UNIQUE (term)` is total, so keeping them all makes the index creation
          fail — and a copy written to tolerate that would keep an arbitrary definition.
        - `DROP INDEX idx_terms_live` precedes the column drops. Dropping `superseded_at`
          while that partial index still names it fails with *"error in index idx_terms_live
          after drop column: no such column: superseded_at"*: SQLite validates the surviving
          indexes against the reduced table.

        The retired-word warnings are settled rather than left standing, and that is not
        tidying. `RETIRED_TERM` leaves `SETTLEABLE_KINDS` in this change, so from here
        neither `WarningService._reconcile` nor the gate's settling pass would ever touch
        such a row again: it would sit `active` forever, with nothing able to produce it and
        nothing able to settle it — a permanent nag, in the digest that exists to de-noise,
        about a rule that no longer exists. Suppressed ones are settled too, since a
        suppression resurfaces at every critical point.
        """
        stamp = now()
        settled = (
            "the retired-word scan was removed at schema 11 (v3 change 4): the glossary no "
            "longer holds a banned list, so nothing can raise or clear this warning"
        )
        return [
            # Only live terms survive: the lineage is what this change deletes.
            "DELETE FROM terms WHERE superseded_at IS NOT NULL",
            "DROP INDEX idx_terms_live",
            "ALTER TABLE terms DROP COLUMN approved_at",
            "ALTER TABLE terms DROP COLUMN names_ref",
            "ALTER TABLE terms DROP COLUMN ban_scope",
            "ALTER TABLE terms DROP COLUMN ban_reason",
            "ALTER TABLE terms DROP COLUMN use_instead",
            "ALTER TABLE terms DROP COLUMN superseded_at",
            "CREATE UNIQUE INDEX idx_terms_word ON terms (term)",
            *schema.statements(schema.LABELS_DDL),
            f"UPDATE warnings SET state = 'resolved', reason = '{settled}', "
            f"updated_at = '{stamp}' "
            "WHERE kind = 'retired_term' AND state <> 'resolved'",
        ]

    def _guard_7_to_8(self) -> None:
        """Refuse, before any write, what schema 8 cannot express without inventing a truth.

        The standing migration rule is that a migrated value must be something the old store
        already implied, never something manufactured to satisfy the new shape. Two cases
        fail it, and both are refusals rather than resolutions:

        **More than one live declared package.** Collapsing several of the owner's declared
        groupings into nothing invents the claim that his grouping meant nothing. One live
        package migrates in silence — that grouping *is* the whole plan, which the old store
        already implied. Two or more is his call: retire the ones he does not want, then
        migrate. Refusing costs almost nothing, because exactly one such database exists.

        **Two live sub-tasks sharing a contract.** Schema 8 makes `tasks.contract_ref`
        unique, which is only correct because splitting dies with the level. A store still
        holding a split would have its second task silently rejected by the new index, so it
        is named here instead.

        Raised as ValueError inside `migrate`'s try, so the pre-migration snapshot is
        restored and the caller is told the store did not move.
        """
        live_packages = self.query(
            "SELECT id, name FROM packages WHERE superseded_at IS NULL ORDER BY id"
        )
        if len(live_packages) > 1:
            named = ", ".join(f"packages:{r['id']} ({r['name']})" for r in live_packages)
            raise ValueError(
                "schema 8 removes the declared build grouping, and this plan has "
                f"{len(live_packages)} live packages: {named}. Retire the ones you do not "
                "want kept before migrating — collapsing them here would record that the "
                "grouping never meant anything, which is not something the old store said."
            )

        shared = self.query(
            "SELECT contract_ref, GROUP_CONCAT(id) AS ids FROM subtasks "
            "WHERE superseded_by IS NULL GROUP BY contract_ref HAVING COUNT(*) > 1"
        )
        if shared:
            named = "; ".join(
                f"{r['contract_ref']} is implemented by "
                + ", ".join(f"subtasks:{i}" for i in r["ids"].split(","))
                for r in shared
            )
            raise ValueError(
                "schema 8 makes a task's contract unique, and this plan holds a split: "
                f"{named}. Splitting is removed with the sub-task level, so decide which "
                "one survives before migrating."
            )

    def _steps_7_to_8(self) -> list[str]:
        """v3 change 1: the levels, the rename, and the planning-sense word.

        Order is load-bearing in three places. The two column drops precede `DROP TABLE
        tasks`, or the foreign key is violated. `packages` drops after `tasks`, which
        references it. And `subtasks` takes the name `tasks` only once the old table of that
        name is gone.

        Every index is named explicitly, because renaming a table carries its indexes across
        under their *old* names — probed, `01-vocabulary-and-levels.md` §4.5 — and an index
        called `idx_subtasks_state` sitting on `tasks` is the retired word surviving in the
        place nobody looks.

        Each rename here has a matching edit in `schema.DDL`, and `test_schema_parity` is
        what holds the two together: a migrated store and a fresh one must end structurally
        identical, or the stores that were born and the stores that were migrated drift.
        """
        stamp = now()
        widened = (
            "the build grouping was removed in schema 8; this attachment was at that "
            "level and has been widened rather than dropped"
        )
        return [
            # --- the planning-sense word: the interview step that produced a row ---
            "ALTER TABLE plan_rows RENAME COLUMN package TO stage",
            "DROP INDEX idx_rows_package",
            "CREATE INDEX idx_rows_stage ON plan_rows (stage)",
            "ALTER TABLE gate_runs RENAME COLUMN package TO stage",
            "DROP INDEX idx_gate_runs_package",
            "CREATE INDEX idx_gate_runs_stage ON gate_runs (stage, id)",
            "ALTER TABLE journal_notes RENAME COLUMN package TO stage",
            "DROP INDEX idx_journal_package",
            "CREATE INDEX idx_journal_stage ON journal_notes (stage, id)",
            "ALTER TABLE finding_reallocations RENAME COLUMN from_package TO from_stage",
            "ALTER TABLE finding_reallocations RENAME COLUMN to_package TO to_stage",

            # --- the dying levels ---
            "ALTER TABLE subtasks DROP COLUMN task_id",       # FK to the dying middle level
            "ALTER TABLE subtasks DROP COLUMN superseded_by",  # split lineage
            "DROP TABLE tasks",                                # takes idx_tasks_package
            "DROP TABLE packages",                             # takes idx_packages_live

            # --- obligation -> behaviour ---
            "ALTER TABLE obligations RENAME TO behaviours",
            "ALTER TABLE obligation_ownership RENAME TO behaviour_ownership",
            "ALTER TABLE obligation_amendments RENAME TO behaviour_amendments",
            "ALTER TABLE behaviour_ownership RENAME COLUMN obligation_id TO behaviour_id",
            "ALTER TABLE behaviour_ownership RENAME COLUMN subtask_id TO task_id",
            "ALTER TABLE behaviour_amendments RENAME COLUMN obligation_id TO behaviour_id",
            "DROP INDEX idx_obligations_contract",
            "CREATE INDEX idx_behaviours_contract ON behaviours (contract_ref, retired_at)",
            "DROP INDEX idx_obligation_live_owner",
            "CREATE UNIQUE INDEX idx_behaviour_live_owner ON behaviour_ownership "
            "(behaviour_id) WHERE superseded_at IS NULL",
            "DROP INDEX idx_obligation_owner_subtask",
            "CREATE INDEX idx_behaviour_owner_task ON behaviour_ownership "
            "(task_id, superseded_at)",
            # Data, not structure: one word may not mean two things. A row of kind
            # 'behaviour' whose ref reads `contracts:40#behaviour` is the disease this
            # change is spending 710 lines to remove.
            "UPDATE behaviours SET kind = 'effect' WHERE kind = 'behaviour'",
            "UPDATE behaviours SET key = 'effect' WHERE key = 'behaviour'",
            # The generated key for the second and later entries of a bare string list was
            # `o1`, `o2` — an `o` for a word that no longer exists. `enumerate_from_row` now
            # generates `b1`, `b2`, so the stored ones move with it; leaving them would have
            # the store and the code disagreeing about the key of the same behaviour, which
            # is what UNIQUE (contract_ref, key) is there to make impossible.
            "UPDATE behaviours SET key = 'b' || substr(key, 2) WHERE key GLOB 'o[0-9]*'",
            # The `obligations` array inside contract rows' free-form JSON content.
            # `enumerate_from_row` reads it by that key and the stage-6 script instructs the
            # planner to write it by that key, so the key moves and the value does not.
            "UPDATE plan_rows SET content = json_remove("
            "json_set(content, '$.behaviours', json_extract(content, '$.obligations')), "
            "'$.obligations') WHERE table_name = 'contracts' "
            "AND json_extract(content, '$.obligations') IS NOT NULL",

            # --- the sub-task level moves down, and the name moves with it ---
            "ALTER TABLE subtask_deps RENAME TO task_deps",
            "ALTER TABLE task_deps RENAME COLUMN subtask_id TO task_id",
            "ALTER TABLE subtask_verifications RENAME TO task_verifications",
            "ALTER TABLE task_verifications RENAME COLUMN subtask_id TO task_id",
            "DROP INDEX idx_subtask_deps_on",
            "CREATE INDEX idx_task_deps_on ON task_deps (depends_on)",
            "DROP INDEX idx_verifications_subtask",
            "CREATE INDEX idx_verifications_task ON task_verifications "
            "(task_id, serve_epoch)",
            # The two columns naming the level from outside it. Renaming a parameter against
            # a column that was not renamed is a join that matches nothing, which is the
            # F20/F24 failure this schema already carries scars from.
            "ALTER TABLE briefs RENAME COLUMN subtask_id TO task_id",
            "DROP INDEX idx_briefs_subtask",
            "CREATE INDEX idx_briefs_task ON briefs (task_id, superseded_by)",
            "ALTER TABLE workspace_fingerprints RENAME COLUMN subtask_id TO task_id",
            "ALTER TABLE subtasks RENAME TO tasks",            # the name is free now
            "DROP INDEX idx_subtasks_state",
            "CREATE INDEX idx_tasks_state ON tasks (state)",
            "CREATE UNIQUE INDEX idx_tasks_contract ON tasks (contract_ref)",

            # --- the attachment scope collapse (task 1A.3) ---
            # Two of the four levels lose their anchor, not one: `packages` is dropped and so
            # is the old middle `tasks` that `task` scope keyed. Each live row at either is
            # superseded and *replaced* at plan scope rather than updated in place — the
            # schema states "a target has exactly one live placement" and `idx_attachments_
            # live` is a lookup index, not a unique one, so a bulk UPDATE would leave a
            # target that had one attachment at each level holding two live placements and
            # the invariant false with no error anywhere. Where several widened rows land on
            # one target, the earliest becomes the survivor and the rest are superseded
            # without a replacement.
            #
            # `promoted_from` and the reason are `PromotionNeedsReason`'s friction, honoured
            # rather than walked through: broadening a scope is the free direction and the
            # one that silently bloats context, so a migration that promotes in bulk says so
            # in the owner's own review surface. D8 recorded that forcing subsystem-wide
            # attachments to plan scope is a silent "too high" failure; this does it
            # deliberately, and 1D.3 records what it costs.
            "INSERT INTO scope_attachments (scope_level, scope_key, target_root, reason, "
            "promoted_from, superseded_at, created_at) "
            f"SELECT 'plan', '', a.target_root, '{widened}', a.scope_level, NULL, "
            f"'{stamp}' FROM scope_attachments a WHERE a.superseded_at IS NULL "
            "AND a.scope_level IN ('package', 'task') "
            "AND a.id = (SELECT MIN(b.id) FROM scope_attachments b "
            "WHERE b.target_root = a.target_root AND b.superseded_at IS NULL "
            "AND b.scope_level IN ('package', 'task')) "
            "AND NOT EXISTS (SELECT 1 FROM scope_attachments c "
            "WHERE c.target_root = a.target_root AND c.superseded_at IS NULL "
            "AND c.scope_level = 'plan')",
            f"UPDATE scope_attachments SET superseded_at = '{stamp}' "
            "WHERE superseded_at IS NULL AND scope_level IN ('package', 'task')",
            # `subtask` scope keeps its anchor and only loses its name: the id it holds is a
            # row in the table that has just become `tasks`. So this one is a rename, on
            # every row including the superseded ones — the placements are the same
            # placements, spelled with the surviving word. The two levels that ceased to
            # exist are left spelled as they were on superseded rows, because rewriting them
            # would claim a placement that never happened.
            "UPDATE scope_attachments SET scope_level = 'task' WHERE scope_level = 'subtask'",
            "UPDATE scope_attachments SET promoted_from = 'task' "
            "WHERE promoted_from = 'subtask'",
        ]


class _Immediate:
    """BEGIN IMMEDIATE ... COMMIT / ROLLBACK."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False
