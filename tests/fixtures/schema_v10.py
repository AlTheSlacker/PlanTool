"""The schema exactly as version 10 created it, retained as a migration fixture.

`test_schema_parity` builds a version-10 database from this text, migrates it to 11, and
compares it against a freshly-initialised 11. Without a retained copy there is nothing to
migrate *from* once `engine/schema.py` has been edited in place.

It lives here and **not** in `engine/schema.py`, for the same reason `schema_v7`,
`schema_v8` and `schema_v9` do. `tests/test_schema_vocabulary.py` regexes every `CREATE
TABLE IF NOT EXISTS` out of that whole file, so a retained older DDL sitting there would be
phantom schema for every one of its checks. v3 change 4 is the sharpest case yet: it drops
six columns from `terms` and adds a reverse check that every declared role still has a
column, so a v10 `terms` inside `schema.py` would keep `approved_at` and `ban_reason` alive
for exactly the checks written to notice that they died.

Generated from the live `engine/schema.py` at schema 10 rather than hand-copied — a
hand-copy is a second source of truth for a text whose whole job is to be the first one.
"""

DDL_V10 = """
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
-- `name` and `named_for` implement M6_PLAN.md §6: a row is addressed as `table:ordinal`,
-- and an address alone forces the reader to go and look it up. Every row therefore carries
-- a short name, supplied at creation, and the tool never emits the address without it.
--
-- The name is a real column and is NOT derived from `content`. D12 settled that nothing an
-- accounting depends on may be inferred from `content`, because it is free-form JSON with
-- no per-table schema; a display name is the same case, and a truncated first sentence is
-- not a name.
--
-- `named_for` is the fingerprint of the content the name was given for. A name that was
-- accurate when written stops being true when the content moves, so a write that changes
-- content cannot carry the old name forward silently — it must be supplied again. Passing
-- the same name a second time is a deliberate act; silence is not. See rows.py.
--
-- `grounds` and `alternatives` are the decision context (v3 D11): why this row's content is
-- what it is, and what else was considered and why it lost. They attach to the row, not to a
-- transition — a row has grounds from the moment it exists. The reason an *act* was
-- performed is a different thing with a different word, and is prefixed by the act, as in
-- `retire_reason` and `supersede_reason`. A new justification column belongs to one of those
-- two roles; there is not a third, and `tests/test_schema_vocabulary.py` refuses a second
-- spelling of either.
--
-- All three are nullable, deliberately. `NOT NULL DEFAULT ''` would have every row satisfy
-- the column while satisfying nothing; absence is countable and is reported as a gap.
--
-- They are declared **last, in the order the 8 -> 9 migration adds them**, and that is
-- load-bearing rather than cosmetic: `ALTER TABLE ... ADD COLUMN` appends, so declaring
-- `grounds` next to `retire_reason` — where it reads more naturally — would give a fresh
-- database and a migrated one the same columns at different `cid`s, and
-- `tests/test_schema_parity.py` compares raw pragma output.
CREATE TABLE IF NOT EXISTS plan_rows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name      TEXT    NOT NULL,
    ordinal         INTEGER NOT NULL,
    name            TEXT    NOT NULL,
    named_for       TEXT    NOT NULL,          -- content fingerprint at naming time
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
    grounds          TEXT,                     -- why this row's content is what it is
    alternatives     TEXT,                     -- what was considered, and why it lost
    supersede_reason TEXT,                     -- why the old row was abandoned
    UNIQUE (table_name, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_rows_table  ON plan_rows (table_name);
CREATE INDEX IF NOT EXISTS idx_rows_live   ON plan_rows (superseded_by, state);

-- Two live rows in one table may not share a name (M6_PLAN.md §6.5). This is the clause
-- that makes naming a mechanism rather than a convention: a duplicate is a signal every
-- time — either the same thing has been filed twice, or there are two things and nobody
-- has distinguished them. That is the collision this build hit three times (`part` vs
-- `component`, eight spellings of `created_at`, `_age` duplicated as `_age_seconds`),
-- caught at the moment of typing instead of a week later. No judgment is exercised, so
-- `decisions:12` is respected.
--
-- Scoped to live rows so a superseded row's name is free for its replacement to reuse —
-- which is exactly the *redefinition* case (same thing, sharpened) and is correctly
-- distinguished from *replacement* (different thing, different name) by whether the
-- replacement changed the name. The `terms` design (M6_PLAN.md §3.1) needed that same
-- distinction and had to build it by hand; here the general layer gets it for free.
-- `state` carries the exclusion as well as `superseded_by`, because supersession sets the
-- state first and the pointer afterwards: the replacement has to be inserted before its ref
-- exists to point at. Keying on the pointer alone would leave the old row in the index for
-- the one statement in between, and reject a replacement that legitimately keeps its name.
CREATE UNIQUE INDEX IF NOT EXISTS idx_rows_live_name ON plan_rows (table_name, name)
    WHERE superseded_by IS NULL AND state NOT IN ('retired', 'superseded');
-- `stage` is the ordinal of the interview step that produced the row (1..8 under the
-- methodology shipped today). It was called `package` until schema 8, alongside a
-- `packages` table holding the owner's declared build groupings — one word for two things,
-- which is the disease this schema exists to catch. The build grouping is gone (v3 D7) and
-- the surviving meaning takes the word the interview's steps already use.
CREATE INDEX IF NOT EXISTS idx_rows_stage ON plan_rows (stage);
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
    created_at   TEXT    NOT NULL
);

-- decisions:43 — a replayed idempotency_key returns the original receipt.
CREATE TABLE IF NOT EXISTS idempotency (
    key        TEXT PRIMARY KEY,
    receipt    TEXT NOT NULL,                  -- JSON
    created_at TEXT NOT NULL
);

-- A `writer_lease` table stood here until 2026-07-22. It backed a writer lock for
-- concurrent planning sessions, which this tool does not have. Removed with the lock;
-- see engine/storage.py's module docstring. Plans created before that date still carry
-- the table, unused and harmless.

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
    created_at    TEXT NOT NULL
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
    rule_key    TEXT NOT NULL,
    root_ref   TEXT,
    state      TEXT NOT NULL,            -- dismissed | resolved
    reason     TEXT NOT NULL,
    created_at TEXT NOT NULL,            -- when this gap was first dismissed or resolved
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
    created_at    TEXT    NOT NULL,
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
    -- What was found when the claim was tested. Not a justification, and deliberately not
    -- renamed to `reason` in schema 9: it was the *parameter* `fence_claim(rationale)` that
    -- was misspelt, and it now takes the column's word.
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
    created_at TEXT    NOT NULL,        -- when this track was opened
    updated_at TEXT    NOT NULL,
    UNIQUE (claim_id, track)
);

-- A red-team result filed against specific rows (entities:7, state_machines:7).
-- A finding lives here and NOT in plan_rows, and the difference is not storage taste
-- (DEVIATIONS.md D22). A plan row is write-once — content is never edited and changing your
-- mind writes a successor (requirements:61) — while a finding *moves*: filed, then addressed
-- or accepted-as-risk or withdrawn, with a reason attached at the transition. Putting it
-- in plan_rows would mean either a supersession per disposition, so every finding leaves a
-- two-row lineage recording nothing but its own paperwork, or mutable columns on plan_rows,
-- which ends requirements:61 for one table. A finding is also *about* the plan rather than
-- part of it; served through read_rows it would reach every brief and every render as though
-- it were plan content.
--
-- `name` is here for the same reason plan_rows has one: a finding is addressed as
-- `findings:N` and that address reaches readers, so it may never travel alone (D19). It is
-- NOT NULL at creation and never derived from `description` — a name guessed from content is
-- the failure D12 argued out of the row schema and F32 then found three copies of.
--
-- `resolve_by` is the D15 hard-lock (M6_PLAN.md §2.6). A finding is an outstanding item,
-- and every outstanding item is allocated to the stage gate that must not pass while it
-- is still open. The column keeps its name deliberately: it carries no retired word, only
-- its *meaning* is a stage ordinal, and a migration to improve a comment is not a trade
-- this change makes. It is NOT NULL and supplied at filing: an item with no gate to answer to
-- is one that only finalization catches, which is the pile-up D15 exists to break up. The
-- two exits are `resolve_finding` (contracts:73) and a *recorded* reallocation to a later
-- gate — the deferral costs a reason the owner reads (finding_reallocations), which is what
-- keeps it from being silent procrastination. Gaps are deliberately outside this scheme:
-- they are closable by the agent now, so a deferred gap is procrastination with no cost.
CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,       -- what this finding says, in a few words
    description TEXT    NOT NULL,
    severity    TEXT    NOT NULL,
    state       TEXT    NOT NULL,       -- filed | disputed | addressed | accepted_risk
    outcome     TEXT,                   -- addressed | accepted_risk | withdrawn
    -- Why the finding was closed the way it was: for accepted_risk, the owner's acceptance;
    -- for a dispute upheld, why it stands. It was `rationale` until schema 9, which was a
    -- second spelling of the word this schema already uses for why an act was performed
    -- (v3 change 2 §2). One column written by two acts is correct here — both close the
    -- finding — and it is role 1, not the row-level `grounds` that `plan_rows` carries.
    reason      TEXT,
    dispute     TEXT,                   -- the standing argument against the finding
    resolve_by  INTEGER NOT NULL,       -- D15: the stage gate that locks until resolved
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

-- A `packages` table stood here until schema 8, holding the owner's declared build
-- groupings (DEVIATIONS.md D13), and above it a `tasks` table that was the execution
-- layer's *middle* level. Both are gone, with the level itself: v3 D7 removed the build
-- grouping, and D5 moved the name `tasks` down onto the unit a builder is actually handed.
-- Filtering a review list is what the grouping was really used for, and labels (v3 change
-- 4) do that without a level. What is given up is recorded in 1D.3 of
-- `spec/v3/builds/01-vocabulary-and-levels.md`: a subsystem-wide attachment has nowhere
-- between plan and task to sit, so it sits at plan scope and is served to every task.

-- A node in the implementation task graph (entities:9, state_machines:9). One task is the
-- implementation unit of exactly one contract, and — from v3 D5 — one externally-callable
-- function plus the private helpers serving only it.
--
-- `state` deliberately omits `ready`. Under DEVIATIONS.md D10 readiness is a *predicate*
-- over dependency state, recomputed on demand, not an edge event that is fired once and
-- stored. Storing it would be a second source of truth for a fact the deps already
-- determine, and the two would drift precisely when the graph is revised. `ready` is
-- therefore derived (see tasks.readiness_of) and never written here.
--
-- `serve_epoch` counts how many times a brief has been served for this task. It is what
-- scopes a verification verdict to the serving episode that produced it: a verdict
-- recorded under an earlier epoch cannot satisfy a later completion. See DEFECTS.md F19(b).
--
-- `contract_ref` is unique (idx_tasks_contract), reversing D12. It was left non-unique so
-- that the products of a split could share a contract; splitting is gone with the sub-task
-- level, one task *is* one contract, and the constraint states that rather than leaving it
-- an invariant somebody has to remember. It constrains non-null values only — SQLite treats
-- two NULLs in a unique index as distinct — so it says "no two tasks share a contract", not
-- "every task has one".
CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_ref  TEXT    NOT NULL,          -- the contract this implements
    title         TEXT    NOT NULL,
    state         TEXT    NOT NULL,          -- pending | in_progress | blocked | done
                                             -- | rework_flagged  (never 'ready')
    serve_epoch   INTEGER NOT NULL DEFAULT 0,
    detail        TEXT,                      -- last status note; never completion evidence
    block_reason  TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks (state);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_contract ON tasks (contract_ref);

-- The behaviour surface (DEVIATIONS.md D12, fixing DEFECTS.md F23). Called `obligations`
-- until schema 8; same machinery, plainer word (v3 D16).
--
-- A behaviour is one dischargeable commitment of a contract: the main effect of its
-- signature, or one of its enumerated error conditions. It is the denominator F23 found
-- missing.
--
-- Enumerated by the *planning session* and frozen at finalization. The two rejected sources
-- are recorded in D12: the tool deriving it from the contract's prose is the tool exercising
-- judgment (`decisions:12`), and the session declaring it at the moment it is measured hands
-- the denominator to the party being audited — which is exactly how `findings:18` was gamed.
--
-- Frozen does not mean unchangeable: a correction is legitimate but is a recorded,
-- owner-visible act (`behaviour_amendments`), the same friction shape as requirements:79's
-- waiver log and D8's promotion reason. The accounting can change, but not silently.
--
-- `kind` is `effect | error` and `key` is `effect` for the main one. Both said `behaviour`
-- until schema 8, which would have left a `Behaviour` row whose kind is "behaviour" and
-- whose ref reads `contracts:40#behaviour` — one word for two things, which is the same
-- disease as two words for one. `effect`/`error` is the pair INTERVIEW.md §4 already uses.
CREATE TABLE IF NOT EXISTS behaviours (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_ref TEXT    NOT NULL,      -- the contract this commitment belongs to
    key          TEXT    NOT NULL,      -- stable id within the contract, e.g. 'effect'
                                        -- or the error name ('CycleDetected')
    kind         TEXT    NOT NULL,      -- effect | error
    statement    TEXT    NOT NULL,      -- what discharging it means
    retired_at   TEXT,                  -- null == live; set only by a recorded amendment
    created_at    TEXT    NOT NULL,
    UNIQUE (contract_ref, key)
);

CREATE INDEX IF NOT EXISTS idx_behaviours_contract ON behaviours (contract_ref, retired_at);

-- Who owes what, now. Coverage is enforced here as a database invariant rather than as a
-- procedural comparison of contract refs: the partial unique index makes "every behaviour is
-- owned by exactly one live task" impossible to violate, which is what D12 buys over
-- re-checking it at each call site.
--
-- Supersession rather than update, because the ownership history IS the audit trail of the
-- act being audited — the same reasoning as scope_attachments' promotion history. Nothing
-- supersedes an ownership row now that splitting is gone, so `superseded_at` is always null
-- and the partial predicate is always true; both stay, because the column is what makes the
-- *amendment* path — retiring a behaviour and vesting a replacement — expressible without a
-- second mechanism, and the unique index is what states "nothing is owed twice" as a
-- constraint rather than a convention.
CREATE TABLE IF NOT EXISTS behaviour_ownership (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    behaviour_id  INTEGER NOT NULL REFERENCES behaviours (id),
    task_id       INTEGER NOT NULL REFERENCES tasks (id),
    superseded_at TEXT,                 -- null == the live ownership
    created_at    TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_behaviour_live_owner
    ON behaviour_ownership (behaviour_id) WHERE superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_behaviour_owner_task
    ON behaviour_ownership (task_id, superseded_at);

-- Changing a frozen enumeration. D12: legitimate, never silent. Gaming the accounting should
-- require lying in a log the owner reads.
CREATE TABLE IF NOT EXISTS behaviour_amendments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    behaviour_id  INTEGER REFERENCES behaviours (id),   -- null for an addition, until written
    contract_ref  TEXT    NOT NULL,
    action        TEXT    NOT NULL,     -- added | retired | restated
    reason        TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

-- Graph edges: this task cannot start until `depends_on` is done.
-- Derived at finalization from `depends_on`-typed links between contract rows
-- (DEVIATIONS.md D11), never from untyped traceability links.
CREATE TABLE IF NOT EXISTS task_deps (
    task_id    INTEGER NOT NULL,
    depends_on INTEGER NOT NULL,
    PRIMARY KEY (task_id, depends_on)
);

CREATE INDEX IF NOT EXISTS idx_task_deps_on ON task_deps (depends_on);

-- Delivery verification (contracts:62). A passing verdict is the sole enabler of the
-- in_progress -> done transition; report_status (contracts:60) refuses `done` without one.
CREATE TABLE IF NOT EXISTS task_verifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER NOT NULL,
    serve_epoch  INTEGER NOT NULL,      -- the episode this verdict belongs to (F19b)
    verdict      TEXT    NOT NULL,      -- pass | fail
    evidence     TEXT    NOT NULL,      -- JSON: contract ref -> concrete artifact
    unaccounted  TEXT,                  -- JSON list of contracts with no evidence, on fail
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_verifications_task
    ON task_verifications (task_id, serve_epoch);

-- The composed brief (entities:13, contracts:68). Immutable by design, so defect forensics
-- can always answer "what exactly did the engine see". There is no lifecycle and no update
-- path: regeneration writes a *new* brief that supersedes the old by reference, and the old
-- stays frozen (requirements:61's bidirectional lineage, applied to a non-row entity).
--
-- `serve_epoch` records which serving episode the brief was composed for, so a brief is
-- forensically attributable to the delivery it drove — the same scoping verify_completion
-- verdicts use (DEFECTS.md F19b).
CREATE TABLE IF NOT EXISTS briefs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER NOT NULL REFERENCES tasks (id),
    serve_epoch   INTEGER NOT NULL,
    goal          TEXT    NOT NULL,     -- the task goal (requirements:36)
    is_draft      INTEGER NOT NULL DEFAULT 0,  -- requirements:40 watermark
    supersedes    INTEGER REFERENCES briefs (id),
    superseded_by INTEGER REFERENCES briefs (id),
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_briefs_task ON briefs (task_id, superseded_by);

-- The frozen candidate closure, one row per candidate with its disposition. This table is
-- DEFECTS.md F26's fix and the reason it exists at all.
--
-- `contracts:41` audits "brief contents against the task's link-graph closure". Computed
-- at audit time that closure has moved — `decisions:3` makes the plan a living source of
-- truth — so a brief that passed 100% accounting at composition reports as incomplete later
-- purely because the plan grew, and "the composer skipped a row" becomes indistinguishable
-- from "the plan changed afterwards". requirements:44's meter would drift on its own.
--
-- So the denominator is frozen here with the brief. audit_brief accounts against *this* set,
-- which is what requirements:44 measures, and reports drift against the current closure as a
-- separate, non-failing observation. Two numbers, because they are two different facts.
--
-- `origin` distinguishes a row reached by link-graph traversal (requirements:36) from one
-- present because a planning session allocated it to an enclosing scope (D8). Both are
-- candidates and both are subject to 100% accounting: an allocated row omitted with a reason
-- is how the "too high" attachment failure becomes visible in a log the owner reads.
CREATE TABLE IF NOT EXISTS brief_rows (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    brief_id    INTEGER NOT NULL REFERENCES briefs (id),
    target_ref  TEXT    NOT NULL,
    origin      TEXT    NOT NULL,       -- closure | allocation
    disposition TEXT    NOT NULL,       -- included | omitted
    reason      TEXT    NOT NULL DEFAULT '',  -- required on omitted (requirements:79)
    UNIQUE (brief_id, target_ref)
);

CREATE INDEX IF NOT EXISTS idx_brief_rows_disposition
    ON brief_rows (brief_id, disposition);

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
-- stays live and the target remains in every task forever, which is precisely the
-- "too high" failure the friction exists to prevent, made unfixable by the free
-- direction. Superseded placements are stamped rather than deleted, because the
-- promotion history IS the owner's review surface.
-- Two levels since schema 8, not four. `package` and the old middle `task` both lost their
-- anchor when the build grouping and the middle level went (v3 D5/D7), so every attachment
-- at either was widened to `plan` — superseded and replaced, with `promoted_from` and the
-- migration's own reason, because a bulk update would leave two live placements on a target
-- that had one at each level and quietly falsify the invariant above.
CREATE TABLE IF NOT EXISTS scope_attachments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_level   TEXT    NOT NULL,     -- plan | task
    scope_key     TEXT    NOT NULL,     -- '' at plan level; else the task *id* — never a
                                        -- name (a name-keyed scope is empty on a typo)
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
    task_id      INTEGER,               -- set for brief_issue
    fingerprint  TEXT    NOT NULL,      -- JSON
    created_at  TEXT    NOT NULL
);

-- requirements:10 / uc_steps:5 — gate history, which a resuming planner is owed and which
-- nothing recorded until M6 (DEFECTS.md F30): run_gate computed a verdict and returned it.
-- The verdict is stored; the holes are not, because re-running the gate re-derives them
-- mechanically and history's job is to say what happened, not to answer what is true now.
CREATE TABLE IF NOT EXISTS gate_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    stage         INTEGER NOT NULL,
    passed        INTEGER NOT NULL,
    hole_count    INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gate_runs_stage ON gate_runs (stage, id);

-- contracts:48 — an informal learning that is not a formal plan row (requirements:57),
-- written durably the moment it arises and never batched to session end (requirements:56).
-- `stage` is the interview stage current when the note was recorded: it is what bounds the
-- digest to the working set (requirements:62) rather than to the whole life of the plan.
CREATE TABLE IF NOT EXISTS journal_notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    stage      INTEGER NOT NULL,
    note       TEXT    NOT NULL,
    task_ref   TEXT,                    -- the task the learning arose from, if any
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_journal_stage ON journal_notes (stage, id);

-- contracts:49 — the next intended action, which is the resume point a fresh planner is
-- given (requirements:58). Append-only: the newest row is live, and the older ones are the
-- record of what successive planners meant to do next.
CREATE TABLE IF NOT EXISTS checkpoints (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    intent     TEXT    NOT NULL,
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS terms (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    term          TEXT    NOT NULL,
    definition    TEXT    NOT NULL,
    approved_at   TEXT,                    -- null == the planner proposed it, owner has
                                           -- not answered yet
    names_ref     TEXT,                    -- the row this word names, if any
    ban_scope     TEXT,                    -- null == in use; prose | identifier | both
    ban_reason    TEXT,
    use_instead   TEXT,                    -- retired: the word to say instead
    superseded_at TEXT,                    -- null == the live entry for this word
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_terms_live ON terms (term)
    WHERE superseded_at IS NULL;

CREATE TABLE IF NOT EXISTS finding_reallocations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id   INTEGER NOT NULL,
    from_stage   INTEGER NOT NULL,
    to_stage     INTEGER NOT NULL,
    reason       TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_findings_resolve_by
    ON findings (resolve_by, state);
CREATE INDEX IF NOT EXISTS idx_reallocations_finding
    ON finding_reallocations (finding_id, id);

CREATE TABLE IF NOT EXISTS revisions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    intent       TEXT    NOT NULL,
    snapshot_id  INTEGER NOT NULL,
    from_version INTEGER NOT NULL,
    to_version   INTEGER NOT NULL,
    state        TEXT    NOT NULL,
    cursor       INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL,
    resolved_at  TEXT
);

-- One row per repercussion, enumerated once at open time (the frozen denominator, F26) and
-- never recomputed. `kind` is target | affected | accepted_risk | suppressed_warning. The
-- adjudication is recorded in place: `disposition` stays null until the owner decides, and a
-- `modify` that clears the conflict check records the superseding row in `applied_ref`.
CREATE TABLE IF NOT EXISTS repercussions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id    INTEGER NOT NULL,
    position       INTEGER NOT NULL,
    kind           TEXT    NOT NULL,
    row_ref        TEXT,
    finding_ref    TEXT,
    warning_id     INTEGER,
    advice         TEXT    NOT NULL,
    disposition    TEXT,
    owner_words    TEXT,
    applied_ref    TEXT,
    created_at     TEXT    NOT NULL,
    resolved_at    TEXT,
    UNIQUE (revision_id, position)
);

CREATE INDEX IF NOT EXISTS idx_repercussions_revision
    ON repercussions (revision_id, position);

-- At most one revision may be open (not applied/abandoned) at a time (contracts:42). A partial
-- unique index enforces it in the store, not only in the service.
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_revision
    ON revisions (state) WHERE state = 'walkthrough';

CREATE TABLE IF NOT EXISTS change_log (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    op_type     TEXT    NOT NULL,   -- create|supersede|retire|state_change|update|resync
    ref         TEXT,               -- table:key of the changed row; null for a resync marker
    replaced_by TEXT,               -- the new ref on a pointer-carrying supersede; else null
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS catalogue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    container_id  INTEGER REFERENCES catalogue (id),  -- the object holding it; null at
                                                      -- module level. Not a path: location
                                                      -- is never identity.
    kind          TEXT    NOT NULL,
    visibility    TEXT    NOT NULL,
    purpose       TEXT    NOT NULL,      -- verb, object, qualifier; the whole of the search
    task_id       INTEGER REFERENCES tasks (id),      -- a function's owner
    component_ref TEXT,                                -- an object's owner
    retired_at    TEXT,                  -- null == live, and the only field that says so
    retire_reason TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL,
    CHECK (kind IN ('object', 'function')),
    CHECK (visibility IN ('public', 'private')),
    -- Both value sets are constrained because both appear in idx_catalogue_task_entry's
    -- predicate below, where a typo does not fail: it drops the row out of the invariant.
    -- Write 'Public' and the task quietly acquires a second entry point with nothing red.
    -- This schema's habit is to enumerate in a comment and not constrain (subtasks.state
    -- did), so the narrower rule is the one that applies: a value appearing in an index
    -- predicate must be constrained.
    CHECK ((task_id IS NULL) != (component_ref IS NULL)),
    CHECK (CASE kind WHEN 'function' THEN task_id IS NOT NULL
                     ELSE component_ref IS NOT NULL END)
    -- ...and a function owned by a component would pass the line above while escaping
    -- idx_catalogue_task_entry entirely. Same NULL escape, one index later.
);

-- Identity is (name, container), at most one live entry per pair — and the obvious index
-- for it silently does not work. With container_id nullable for a module-level entry,
-- `ON catalogue (name, container_id)` accepts two live module-level entries with the same
-- name, because SQL compares NULLs as distinct. Probed at SQLite 3.49.1 under Python
-- 3.12.10: the second insert is accepted. That is not a corner case. Measured over v2's
-- own engine, the identity collides eleven times and **every one of them is a
-- module-level object** (PlanUnreadable in four modules, RefNotFound in three, ...), so
-- the naive index catches precisely nothing this table exists to catch. Index the
-- expression, not the column. `PRAGMA index_list` reports the two forms identically, so
-- the parity check cannot tell them apart and tests/test_catalogue_store.py asserts the
-- behaviour instead.
CREATE UNIQUE INDEX IF NOT EXISTS idx_catalogue_live_name
    ON catalogue (name, COALESCE(container_id, 0)) WHERE retired_at IS NULL;

-- D6 as a database invariant rather than something a service remembers to check — the same
-- move idx_obligation_live_owner makes for behaviour ownership. A task is one
-- externally-callable function, so a second live public entry means either the task is two
-- tasks or the name is wrong. The "at least one" half is a gap and belongs to change 5,
-- where tasks and pseudocode arrive together.
CREATE UNIQUE INDEX IF NOT EXISTS idx_catalogue_task_entry
    ON catalogue (task_id)
    WHERE kind = 'function' AND visibility = 'public' AND retired_at IS NULL;

-- Read by the ContainerNotEmpty check and by every container name -> id resolution.
CREATE INDEX IF NOT EXISTS idx_catalogue_container
    ON catalogue (container_id, retired_at);

-- One judgment about one candidate: what the relationship is, and why. The negatives are
-- recorded too — if only merges were written down, the next planner runs the same search,
-- sees the same candidate, and decides again, possibly the other way.
--
-- `proposed` is a name and not a ref, deliberately: a comparison whose verdict is `same` or
-- `contains` produces no entry, so there is nothing to point at, and the record has to
-- carry the name that was refused or it says nothing to the next planner. `entry_id` is
-- null in exactly those cases and is the field that distinguishes them.
--
-- No `updated_at`: an immutable audit record, like finding_reallocations and
-- behaviour_amendments. `catalogue` has one because an entry is mutable in two ways — its
-- purpose can be restated and it can be retired.
CREATE TABLE IF NOT EXISTS catalogue_comparisons (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    proposed     TEXT    NOT NULL,      -- the name that was being registered
    container_id INTEGER REFERENCES catalogue (id),
    matched_id   INTEGER NOT NULL REFERENCES catalogue (id),
    entry_id     INTEGER REFERENCES catalogue (id),  -- the entry written, if one was
    relationship TEXT    NOT NULL,
    reason       TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    CHECK (relationship IN ('same', 'contains', 'contained_by',
                            'partially_overlaps', 'unrelated'))
    -- Constrained because a misspelling takes the branch that writes the entry: the typo
    -- does not fail, it inverts the refusal. `same` and `contains` are the two verdicts a
    -- planner reaches for when the match is real, and they are the two that stop the write.
);
"""
