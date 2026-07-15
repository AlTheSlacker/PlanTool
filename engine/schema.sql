-- plantool schema v1 (stage 1 build, spec rev 2).
--
-- Migrations are DROP TABLE until the first real plan freezes; the
-- plan.yaml round-trip (export -> recreate DB -> reimport) is the escape
-- hatch protecting live plans across schema churn (spec section 4).
--
-- Claim tables (rows asserting a planning fact) all carry:
--   plan_id, plan_version_added, provenance, assumption_kind, spike_id,
--   links (JSON array of "table:id" refs), created_at.
-- Provenance rules (enforced here and at write time):
--   * assumed rows must carry assumption_kind (world|intent)
--   * verified rows must carry spike_id (only a spike upgrades to verified)
-- Bookkeeping tables (questions, conflicts, spikes, findings, gate_results)
-- record process, not plan facts, and skip provenance.

PRAGMA foreign_keys = ON;

CREATE TABLE plans (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    tier          TEXT NOT NULL DEFAULT 'standard',
    current_stage INTEGER NOT NULL DEFAULT 1 CHECK (current_stage BETWEEN 1 AND 8),
    version       INTEGER NOT NULL DEFAULT 1,
    state         TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'frozen')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Bookkeeping: experiments that verify world-assumptions. Defined first
-- because claim tables' spike_id references it.
CREATE TABLE spikes (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    question           TEXT NOT NULL,
    hypothesis         TEXT,
    method             TEXT,
    budget             TEXT,
    verdict            TEXT CHECK (verdict IN ('confirmed', 'refuted', 'inconclusive')),
    evidence_summary   TEXT,
    evidence_path      TEXT,
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE use_cases (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    title              TEXT NOT NULL,
    actor              TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

CREATE TABLE uc_steps (
    id                  INTEGER PRIMARY KEY,
    plan_id             INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added  INTEGER NOT NULL,
    use_case_id         INTEGER NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
    step_no             INTEGER NOT NULL,
    text                TEXT NOT NULL,
    -- Queryable home of "this step can't fail because..." for the stage-2 gate.
    no_extension_reason TEXT,
    provenance          TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind     TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id            INTEGER REFERENCES spikes(id),
    links               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (use_case_id, step_no),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

CREATE TABLE uc_extensions (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    step_id            INTEGER NOT NULL REFERENCES uc_steps(id) ON DELETE CASCADE,
    description        TEXT NOT NULL,
    in_scope           INTEGER NOT NULL DEFAULT 1 CHECK (in_scope IN (0, 1)),
    handling           TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

-- EARS-typed requirements. Typed slots per ears_type; the engine assembles
-- the canonical sentence from slots -- prose is never regex-parsed.
-- Slot requirements (validated at write time, engine/submits.py):
--   ubiquitous: system_response
--   event:      trigger + system_response
--   state:      precondition + system_response
--   unwanted:   trigger (the unwanted condition) + system_response
--   optional:   feature + system_response
CREATE TABLE requirements (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    ears_type          TEXT NOT NULL CHECK (ears_type IN ('ubiquitous', 'event', 'state', 'unwanted', 'optional')),
    trigger_text       TEXT,   -- tool-facing field name: "trigger" (SQL keyword)
    precondition       TEXT,
    feature            TEXT,
    system_response    TEXT,
    is_nfr             INTEGER NOT NULL DEFAULT 0 CHECK (is_nfr IN (0, 1)),
    planguage_scale    TEXT,
    planguage_meter    TEXT,
    planguage_target   TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

CREATE TABLE entities (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    name               TEXT NOT NULL,
    description        TEXT,
    has_lifecycle      INTEGER NOT NULL CHECK (has_lifecycle IN (0, 1)),
    -- state machine required iff has_lifecycle; a false needs justification
    lifecycle_reason   TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (has_lifecycle = 1 OR lifecycle_reason IS NOT NULL),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

CREATE TABLE crud_grid (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    entity_id          INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    op                 TEXT NOT NULL CHECK (op IN ('C', 'R', 'U', 'D')),
    actor              TEXT,   -- responsible actor/component
    na                 INTEGER NOT NULL DEFAULT 0 CHECK (na IN (0, 1)),
    na_reason          TEXT,
    children_on_delete TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (entity_id, op),
    CHECK ((na = 1 AND na_reason IS NOT NULL) OR (na = 0 AND actor IS NOT NULL)),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

CREATE TABLE state_machines (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    entity_id          INTEGER NOT NULL UNIQUE REFERENCES entities(id) ON DELETE CASCADE,
    states             TEXT NOT NULL,  -- JSON array of state names
    events             TEXT NOT NULL,  -- JSON array of event names
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

-- Each state x event cell: a transition or an explicit impossible + reason.
CREATE TABLE sm_cells (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    machine_id         INTEGER NOT NULL REFERENCES state_machines(id) ON DELETE CASCADE,
    state              TEXT NOT NULL,
    event              TEXT NOT NULL,
    transition_to      TEXT,
    impossible         INTEGER NOT NULL DEFAULT 0 CHECK (impossible IN (0, 1)),
    impossible_reason  TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (machine_id, state, event),
    CHECK ((impossible = 1 AND impossible_reason IS NOT NULL) OR (impossible = 0 AND transition_to IS NOT NULL)),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

CREATE TABLE components (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    name               TEXT NOT NULL,
    responsibility     TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

-- Structured signatures, never prose. Type expressions are free text in the
-- target stack's notation -- recorded, never compiled (language-neutral).
CREATE TABLE contracts (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    component_id       INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
    name               TEXT NOT NULL,
    kind               TEXT NOT NULL CHECK (kind IN ('api', 'function', 'schema', 'file', 'event')),
    params             TEXT,   -- JSON array: [{name, type_expr, required}]
    returns            TEXT,   -- type_expr
    errors             TEXT,   -- JSON array: [{name, semantics}]
    cannot_fail        INTEGER NOT NULL DEFAULT 0 CHECK (cannot_fail IN (0, 1)),
    cannot_fail_reason TEXT,
    is_external        INTEGER NOT NULL DEFAULT 0 CHECK (is_external IN (0, 1)),  -- consumed from outside the system
    stale              INTEGER NOT NULL DEFAULT 0 CHECK (stale IN (0, 1)),        -- [S2]
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

-- Dependency edges: consumer contract/component -> provider contract. [S2]
CREATE TABLE contract_deps (
    id                    INTEGER PRIMARY KEY,
    plan_id               INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added    INTEGER NOT NULL,
    consumer_contract_id  INTEGER REFERENCES contracts(id) ON DELETE CASCADE,
    consumer_component_id INTEGER REFERENCES components(id) ON DELETE CASCADE,
    provider_contract_id  INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    provenance            TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind       TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id              INTEGER REFERENCES spikes(id),
    links                 TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (consumer_contract_id IS NOT NULL OR consumer_component_id IS NOT NULL),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

-- External dependency of the planned system (the stage-5 gate object).
CREATE TABLE dependencies (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    name               TEXT NOT NULL,
    kind               TEXT,   -- service / library / api / filesystem / ...
    notes              TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

-- Stage-5 gate: all five mode rows exist per dependency.
CREATE TABLE dep_failure_modes (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    dep_id             INTEGER NOT NULL REFERENCES dependencies(id) ON DELETE CASCADE,
    mode               TEXT NOT NULL CHECK (mode IN ('unavailable', 'slow', 'malformed', 'auth', 'partial')),
    handling           TEXT NOT NULL,
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (dep_id, mode),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

-- ADR-shaped decisions. `significant` is set by heuristic (links touch a
-- component or contract), never by the model.
CREATE TABLE decisions (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    text               TEXT NOT NULL,
    rationale          TEXT,
    alternatives       TEXT,   -- JSON array: [{alternative, rejected_because}]
    challenge          TEXT,   -- JSON: null | {text, outcome: overridden|revised}
    significant        INTEGER NOT NULL DEFAULT 0 CHECK (significant IN (0, 1)),
    provenance         TEXT NOT NULL CHECK (provenance IN ('decided', 'derived', 'assumed', 'verified')),
    assumption_kind    TEXT CHECK (assumption_kind IN ('world', 'intent')),
    spike_id           INTEGER REFERENCES spikes(id),
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (provenance <> 'assumed' OR assumption_kind IS NOT NULL),
    CHECK (provenance <> 'verified' OR spike_id IS NOT NULL)
);

-- Bookkeeping tables (no provenance).

CREATE TABLE open_questions (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    text               TEXT NOT NULL,
    state              TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'resolved', 'deferred')),
    owner              TEXT,
    resolution         TEXT,
    links              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Engine files the mechanically detectable conflicts; the model files the
-- semantic ones it notices. Both drain through next_gap() priority 1.
CREATE TABLE conflicts (
    id                 INTEGER PRIMARY KEY,
    plan_id            INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added INTEGER NOT NULL,
    description        TEXT NOT NULL,
    refs               TEXT,   -- JSON array of "table:id" refs
    source             TEXT NOT NULL CHECK (source IN ('engine', 'model')),
    state              TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'resolved')),
    resolution         TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE findings (
    id                    INTEGER PRIMARY KEY,
    plan_id               INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    plan_version_added    INTEGER NOT NULL,
    source                TEXT NOT NULL CHECK (source IN ('redteam', 'premortem')),
    text                  TEXT NOT NULL,
    disposition           TEXT CHECK (disposition IN ('fixed', 'accepted', 'spiked')),
    disposition_rationale TEXT,
    links                 TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE gate_results (
    id      INTEGER PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    stage   INTEGER NOT NULL CHECK (stage BETWEEN 1 AND 8),
    passed  INTEGER NOT NULL CHECK (passed IN (0, 1)),
    holes   TEXT,   -- JSON array of row-level holes
    run_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- [S2] task-pack manifests: table exists, unused in stage 1.
CREATE TABLE pack_manifests (
    id         INTEGER PRIMARY KEY,
    plan_id    INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    task_key   TEXT NOT NULL,
    manifest   TEXT NOT NULL,   -- JSON
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
