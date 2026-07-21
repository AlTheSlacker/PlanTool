"""Database schema.

Owned exclusively by storage-engine (components:1): "no other component touches the
database". Every other module reaches persistence through storage.py's typed operations.
"""

SCHEMA_VERSION = 1

DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- The root aggregate (entities:1). Exactly one row; the guard column enforces it.
CREATE TABLE IF NOT EXISTS plan (
    guard          INTEGER PRIMARY KEY CHECK (guard = 1),
    name           TEXT    NOT NULL,
    tier           TEXT    NOT NULL,
    state          TEXT    NOT NULL DEFAULT 'draft',
    version        INTEGER NOT NULL DEFAULT 1,
    schema_version INTEGER NOT NULL,
    created_at     TEXT    NOT NULL
);

-- Any content row (entities:2). Sources and extracts live here too, so they inherit
-- provenance, supersession lineage and link participation for free (DEVIATIONS.md D3).
CREATE TABLE IF NOT EXISTS plan_rows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name      TEXT    NOT NULL,
    ordinal         INTEGER NOT NULL,
    content         TEXT    NOT NULL,          -- JSON
    provenance      TEXT    NOT NULL,
    assumption_kind TEXT,
    state           TEXT    NOT NULL,
    stage           INTEGER,
    supersedes      TEXT,                      -- ref
    superseded_by   TEXT,                      -- ref; null == live (requirements:61)
    superseded_at   TEXT,
    retired_at      TEXT,
    retire_reason   TEXT,
    created_at      TEXT    NOT NULL,
    UNIQUE (table_name, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_rows_table  ON plan_rows (table_name);
CREATE INDEX IF NOT EXISTS idx_rows_live   ON plan_rows (superseded_by, state);
CREATE INDEX IF NOT EXISTS idx_rows_stage  ON plan_rows (stage);
CREATE INDEX IF NOT EXISTS idx_rows_prov   ON plan_rows (provenance);

-- Typed edges (entities:15): immutable, owned by the source row, created with it.
CREATE TABLE IF NOT EXISTS links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source_ref TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    edge_type  TEXT NOT NULL DEFAULT 'links',
    created_at TEXT NOT NULL,
    UNIQUE (source_ref, target_ref, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_links_source ON links (source_ref);
CREATE INDEX IF NOT EXISTS idx_links_target ON links (target_ref);

-- Immutable snapshots (entities:11).
CREATE TABLE IF NOT EXISTS plan_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version    INTEGER NOT NULL,
    reason     TEXT    NOT NULL,
    payload    TEXT    NOT NULL,               -- JSON of every table
    taken_at   TEXT    NOT NULL
);

-- decisions:43 — a replayed idempotency_key returns the original receipt.
CREATE TABLE IF NOT EXISTS idempotency (
    key        TEXT PRIMARY KEY,
    receipt    TEXT NOT NULL,                  -- JSON
    created_at TEXT NOT NULL
);

-- The writer lease (requirements:67/68). DB-authoritative so that a write can validate
-- its lease inside the same transaction that applies it. See DEVIATIONS.md D5.
CREATE TABLE IF NOT EXISTS writer_lease (
    guard       INTEGER PRIMARY KEY CHECK (guard = 1),
    lease_id    TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    renewed_at  TEXT NOT NULL
);

-- Full source text: NOT a plan row. Large, and never loaded into context wholesale.
-- The source's metadata row lives in plan_rows as `sources:n` and carries the hash.
--
-- Keyed by content hash rather than by source ref so that the text can be written in
-- the same atomic batch as the row that cites it (no forward reference to an ordinal
-- that is only assigned mid-transaction). Identical papers deduplicate for free.
CREATE TABLE IF NOT EXISTS source_texts (
    content_hash TEXT PRIMARY KEY,
    text         TEXT NOT NULL,
    char_count   INTEGER NOT NULL,
    stored_at    TEXT NOT NULL
);

-- Structural segmentation of a source, for locators and the coverage meter (M2).
CREATE TABLE IF NOT EXISTS source_sections (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT NOT NULL,
    ordinal      INTEGER NOT NULL,
    heading      TEXT NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset   INTEGER NOT NULL,
    UNIQUE (content_hash, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_sections_hash ON source_sections (content_hash);

-- The dismissed/resolved overlay on computed gaps (entities:3).
--
-- requirements:78 — keyed by gap-type plus the *lineage root* of the target row (the
-- earliest ancestor in its supersession chain), so a dismissal survives both gap
-- re-derivation and row supersession: it neither re-surfaces nor silently detaches.
CREATE TABLE IF NOT EXISTS gap_overlay (
    gap_key    TEXT PRIMARY KEY,
    rule_id    TEXT NOT NULL,
    root_ref   TEXT,
    state      TEXT NOT NULL,            -- dismissed | resolved
    reason     TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Contradictions between rows, or against new input (entities:5, state_machines:4).
--
-- A conflict is a permanent audit record: requirements:29 puts the outcome and the
-- challenge text on the record for good, and contracts:27 refuses re-adjudication.
CREATE TABLE IF NOT EXISTS conflicts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    description    TEXT    NOT NULL,
    recommendation TEXT    NOT NULL,     -- the engineering recommendation, both sides
    state          TEXT    NOT NULL,     -- open | resolved_overridden | resolved_revised
    outcome        TEXT,                 -- overridden | revised
    adjudication   TEXT,                 -- the owner's decision, quoted
    created_at     TEXT    NOT NULL,
    resolved_at    TEXT
);

-- The contested rows. Separate so blocking_conflicts can intersect a gate's scope in
-- one query instead of parsing a JSON blob per conflict.
CREATE TABLE IF NOT EXISTS conflict_refs (
    conflict_id INTEGER NOT NULL,
    ref         TEXT    NOT NULL,
    PRIMARY KEY (conflict_id, ref)
);

CREATE INDEX IF NOT EXISTS idx_conflict_refs_ref ON conflict_refs (ref);

-- The keep-pushing warning ledger (entities:4, state_machines:6, decisions:31).
--
-- Warnings are stored rather than derived because their lifecycle is owner-visible:
-- suppress_warning and resolve_warning take an int id (contracts:24/25), and a
-- suppression must outlive the condition being re-derived. `warning_key` is the stable
-- identity that makes re-raising idempotent — the same deficiency raised at three
-- successive gates is one warning, re-presented, not three.
CREATE TABLE IF NOT EXISTS warnings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    warning_key  TEXT    NOT NULL UNIQUE,
    kind         TEXT    NOT NULL,       -- open_gap | unresolved_assumption | ...
    message      TEXT    NOT NULL,
    source_ref   TEXT,                   -- the row the warning is about, if any
    state        TEXT    NOT NULL,       -- active | suppressed | resolved
    reason       TEXT,                   -- the owner's explicit suppression reason
    resolved_by  TEXT,                   -- ref of the row whose fix resolved it
    raised_at    TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_warnings_state ON warnings (state);

-- An executable experiment against a real dependency (entities:5, state_machines:5).
--
-- requirements:3 confines probe code to a quarantine directory under spikes/ and never
-- ships it. Only the `slug` is stored: the directory is `spikes/{id:03d}_{slug}`, fully
-- determined by the id, so the path can never drift out of step with the record.
CREATE TABLE IF NOT EXISTS spikes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assumption    TEXT    NOT NULL,     -- ref of the world-assumption it resolves
    question      TEXT    NOT NULL,
    hypothesis    TEXT    NOT NULL,
    method        TEXT    NOT NULL,     -- how it probes the real dependency
    budget        TEXT    NOT NULL,
    slug          TEXT    NOT NULL,
    state         TEXT    NOT NULL,     -- registered | executing | blocked | concluded
    outcome       TEXT,                 -- confirmed | refuted | inconclusive | blocked
    evidence      TEXT,                 -- what was observed
    block_reason  TEXT,                 -- requirements:26, the unreachable dependency
    created_at    TEXT    NOT NULL,
    concluded_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_spikes_assumption ON spikes (assumption);
CREATE INDEX IF NOT EXISTS idx_spikes_state      ON spikes (state);

-- A load-bearing technical assertion needing validation (entities:8, state_machines:8).
CREATE TABLE IF NOT EXISTS technical_claims (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    text         TEXT    NOT NULL,
    kind         TEXT    NOT NULL,      -- software | scientific | both
    state        TEXT    NOT NULL,      -- identified | validating | validated | failed
                                        -- | risk_accepted
    outcome      TEXT,                  -- validated | failed | risk_accepted
    evidence     TEXT,
    red_flag     INTEGER NOT NULL DEFAULT 0,   -- requirements:4, blocks dependent planning
    fenced       INTEGER NOT NULL DEFAULT 0,   -- red flag explicitly fenced off
    created_at   TEXT    NOT NULL,
    resolved_at  TEXT
);

-- The rows resting on a claim. Separate table for the same reason conflict_refs is:
-- requirements:43 walks these on failure, and it must be one query.
CREATE TABLE IF NOT EXISTS claim_refs (
    claim_id INTEGER NOT NULL,
    ref      TEXT    NOT NULL,
    PRIMARY KEY (claim_id, ref)
);

CREATE INDEX IF NOT EXISTS idx_claim_refs_ref ON claim_refs (ref);

-- The routing tracks a claim was sent down (requirements:41). `both` opens two rows and
-- neither alone closes the claim, so the tracks are stored rather than derived from kind.
CREATE TABLE IF NOT EXISTS claim_tracks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id   INTEGER NOT NULL,
    track      TEXT    NOT NULL,        -- spike | research
    state      TEXT    NOT NULL,        -- open | satisfied
    detail     TEXT    NOT NULL,
    spike_id   INTEGER,                 -- set when the spike track registers one
    updated_at TEXT    NOT NULL,
    UNIQUE (claim_id, track)
);

-- A red-team result filed against specific rows (entities:7, state_machines:7).
CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT    NOT NULL,
    severity    TEXT    NOT NULL,
    state       TEXT    NOT NULL,       -- filed | disputed | addressed | accepted_risk
    outcome     TEXT,                   -- addressed | accepted_risk | withdrawn
    rationale   TEXT,                   -- for accepted_risk: the owner's acceptance
    dispute     TEXT,                   -- the standing argument against the finding
    created_at  TEXT    NOT NULL,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS finding_refs (
    finding_id INTEGER NOT NULL,
    ref        TEXT    NOT NULL,
    PRIMARY KEY (finding_id, ref)
);

CREATE INDEX IF NOT EXISTS idx_finding_refs_ref ON finding_refs (ref);
CREATE INDEX IF NOT EXISTS idx_findings_state   ON findings (state);

-- Packages (DEVIATIONS.md D13, GLOSSARY.md) — the one *declared* level of the structural
-- hierarchy Plan -> Package -> Task -> Sub-task. A named grouping of tasks: "the GUI", "the
-- controller". Not in the frozen plan; introduced because with only plan/task/sub-task a
-- subsystem is bigger than any task and smaller than the plan, so every subsystem-wide
-- attachment is forced to plan scope — D8 section 2.5's silent "too high" failure, made
-- certain rather than merely possible on a large plan.
--
-- A row with an id, not a free-text label: a name-keyed grouping yields an empty context set
-- on a typo, which is exactly the mistake the retired `milestone` column made.
--
-- Packages do NOT nest. There is deliberately no parent_id: nesting is confusing to users
-- and awkward to draw (owner, 2026-07-21), and it reintroduces an arbitrary depth through
-- the back door when the whole point of scope levels is that the bound is structural.
CREATE TABLE IF NOT EXISTS packages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    intent        TEXT    NOT NULL DEFAULT '',   -- why this grouping exists
    superseded_at TEXT,                          -- null == live
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_packages_live ON packages (superseded_at);

-- Task -> Package membership. Mandatory and exclusive: every task belongs to exactly one
-- package, and finalize_plan refuses a plan with an unpackaged task.
--
-- There is deliberately no default/catch-all package. A catch-all satisfies the invariant
-- while quietly restoring the three-level model, and a grouping nobody chose is a grouping
-- nobody reviews. A one-package plan is fine — declared, not defaulted.
--
-- Which package a task belongs to is a *judgment*, so the tool does not choose it
-- (decisions:12). The tool enforces the invariant; the methodology's architecture-stage
-- script leads the driving session to propose a cut; the owner decides. See D13.
CREATE TABLE IF NOT EXISTS task_packages (
    task_ref   TEXT    NOT NULL PRIMARY KEY,  -- `components:N` — the task
    package_id INTEGER NOT NULL,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_packages_pkg ON task_packages (package_id);

-- A node in the implementation task graph (entities:9, state_machines:9).
--
-- decisions:63 — one SubTask is the implementation unit of exactly one contract.
--
-- `state` deliberately omits `ready`. Under DEVIATIONS.md D10 readiness is a *predicate*
-- over dependency state, recomputed on demand, not an edge event that is fired once and
-- stored. Storing it would be a second source of truth for a fact the deps already
-- determine, and the two would drift precisely when the graph is revised. `ready` is
-- therefore derived (see tasks.readiness_of) and never written here.
--
-- `serve_epoch` counts how many times a brief has been served for this sub-task. It is
-- what scopes a verification verdict to the serving episode that produced it: a verdict
-- recorded under an earlier epoch cannot satisfy a later completion. See DEFECTS.md F19(b).
CREATE TABLE IF NOT EXISTS subtasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_ref  TEXT    NOT NULL UNIQUE,   -- the one contract this implements
    title         TEXT    NOT NULL,
    task_ref      TEXT    NOT NULL DEFAULT '', -- owning task (`components:N`), via
                                               -- belongs_to link (F24 / D13)
    state         TEXT    NOT NULL,          -- pending | in_progress | blocked | done
                                             -- | rework_flagged  (never 'ready')
    serve_epoch   INTEGER NOT NULL DEFAULT 0,
    detail        TEXT,                      -- last status note; never completion evidence
    block_reason  TEXT,
    superseded_by INTEGER,                   -- split_subtask lineage (M5b)
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_subtasks_state ON subtasks (state);

-- Graph edges: this sub-task cannot start until `depends_on` is done.
-- Derived at finalization from `depends_on`-typed links between contract rows
-- (DEVIATIONS.md D11), never from untyped traceability links.
CREATE TABLE IF NOT EXISTS subtask_deps (
    subtask_id INTEGER NOT NULL,
    depends_on INTEGER NOT NULL,
    PRIMARY KEY (subtask_id, depends_on)
);

CREATE INDEX IF NOT EXISTS idx_subtask_deps_on ON subtask_deps (depends_on);

-- Delivery verification (contracts:62). A passing verdict is the sole enabler of the
-- in_progress -> done transition; report_status (contracts:60) refuses `done` without one.
CREATE TABLE IF NOT EXISTS subtask_verifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    subtask_id   INTEGER NOT NULL,
    serve_epoch  INTEGER NOT NULL,      -- the episode this verdict belongs to (F19b)
    verdict      TEXT    NOT NULL,      -- pass | fail
    evidence     TEXT    NOT NULL,      -- JSON: contract ref -> concrete artifact
    unaccounted  TEXT,                  -- JSON list of contracts with no evidence, on fail
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_verifications_subtask
    ON subtask_verifications (subtask_id, serve_epoch);

-- Plan-time context allocation (DEVIATIONS.md D8, M5_PLAN.md section 2).
--
-- M5_PLAN 2.4: keyed on the target row's *lineage root*, not its ref, so an allocation
-- survives supersession instead of silently detaching. Same primitive as requirements:78's
-- gap-dismissal keying; this is its second application.
--
-- `promoted_from` carries M5_PLAN 2.5's asymmetric friction: broadening a scope records
-- the level it came from and demands a reason the owner sees. Narrowing is free.
--
-- A target has exactly one *live* placement. Re-attaching supersedes the previous one
-- rather than adding a second: without that, narrowing is a no-op — the old broader row
-- stays live and the target remains in every sub-task forever, which is precisely the
-- "too high" failure the friction exists to prevent, made unfixable by the free
-- direction. Superseded placements are stamped rather than deleted, because the
-- promotion history IS the owner's review surface.
CREATE TABLE IF NOT EXISTS scope_attachments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_level   TEXT    NOT NULL,     -- plan | package | task | subtask (D13)
    scope_key     TEXT    NOT NULL,     -- '' at plan level; else the package, task or
                                        -- subtask *id* — never a name (GLOSSARY.md)
    target_root   TEXT    NOT NULL,     -- lineage root ref of the attached row
    reason        TEXT    NOT NULL,
    promoted_from TEXT,                 -- prior scope_level, when broadened
    superseded_at TEXT,                 -- null == the live placement
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attachments_live
    ON scope_attachments (target_root, superseded_at);

CREATE INDEX IF NOT EXISTS idx_attachments_scope
    ON scope_attachments (scope_level, scope_key);

-- requirements:73 — the drift baseline. Captured when the plan is finalized and at each
-- brief issue; resume compares the current workspace against the most recent one.
-- Without this nothing ever wrote a baseline and plan_status's drift flags could only
-- ever report "no baseline" (M5_PLAN.md section 1.2).
CREATE TABLE IF NOT EXISTS workspace_fingerprints (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    occasion     TEXT    NOT NULL,      -- finalization | brief_issue
    plan_version INTEGER NOT NULL,
    subtask_id   INTEGER,               -- set for brief_issue
    fingerprint  TEXT    NOT NULL,      -- JSON
    captured_at  TEXT    NOT NULL
);
"""

# Lexical retrieval (V2_BUILD_PLAN.md 5.4). Separate because FTS5 is a compile-time
# option; absence degrades search rather than breaking the store.
FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS source_fts USING fts5(
    content_hash UNINDEXED,
    text
);
"""
