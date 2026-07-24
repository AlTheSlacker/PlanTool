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

        `plan_rows` already stores it as `table:ordinal`; the same-table id pointers
        (`subtasks`, `briefs`) store a bare id naming a row in the op's own table.
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
        (subtask_deps, claim_tracks) — the last joined, having no single-column id.
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
        )
        # source_fts is a derived index, rebuilt from source_texts on restore.
        payload = {
            t: [dict(r) for r in self.query(f"SELECT * FROM {t}")]  # noqa: S608
            for t in tables
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
        restores it. Silent migration is forbidden."""
        current = self.plan_handle()["schema_version"]
        if target_schema_version == current:
            return MigrationReport(current, current, (), self.snapshot_version(
                "pre-migration (no-op)"
            ))
        snapshot_id = self.snapshot_version(
            f"pre-migration {current} -> {target_schema_version}"
        )
        try:
            steps = self._migration_steps(current, target_schema_version)
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

    def _migration_steps(self, current: int, target: int) -> list[str]:
        """The SQL that moves the store from one schema version to the next.

        Two paths exist, and both pass the same test — the migrated value is a truth the
        old store already implied, never one invented to satisfy a NOT NULL:

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

        Anything else is an error and never a silent no-op (decisions:45) — including a
        downgrade, which would have to drop rows to succeed.
        """
        if (current, target) == (3, 4):
            return schema.statements(schema.TERMS_DDL)
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
