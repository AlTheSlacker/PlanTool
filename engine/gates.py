"""Stage gates 1-6 (spec section 8): one function per gate, pure SQL/queries
over the plan DB, no LLM anywhere. A gate returns row-level holes — each hole
names its table, row, problem, and what compliance looks like. run_gate()
records the result in gate_results and, on a pass at the plan's current
stage, advances the stage (the server attaches the next stage's script).

Most structural rules are also enforced at write time (engine/submits.py);
the gates re-check them in SQL anyway because the plan.yaml reimport path
bypasses submit validation — a gate that trusts the writer passes vacuously
on imported data.

Stage-1 recording conventions (the queryable shape of "goals / non-goals /
target stack", taught by the stage-1 script and by these holes' fix texts):
each is a decision whose text starts 'Goal:', 'Non-goal:', or 'Stack:'
(or 'Target stack:'); a goal's measurable success criterion lives in its
rationale. Stage 5's "no external dependencies" escape is a decision whose
text contains that phrase.
"""
from __future__ import annotations

import json

from . import db

FAILURE_MODES = ("unavailable", "slow", "malformed", "auth", "partial")
CRUD_OPS = ("C", "R", "U", "D")

GOAL_WHERE = "lower(ltrim(text)) LIKE 'goal:%'"
NON_GOAL_WHERE = "lower(ltrim(text)) LIKE 'non-goal:%'"
STACK_WHERE = "(lower(ltrim(text)) LIKE 'stack:%' OR lower(ltrim(text)) LIKE 'target stack:%')"
NO_DEPS_WHERE = "lower(text) LIKE '%no external dep%'"


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params)]


def _hole(table: str, problem: str, fix: str, *, row_id: int | None = None,
          entity: str | None = None) -> dict:
    return {"table": table, "row_id": row_id, "entity": entity,
            "problem": problem, "fix": fix}


def goal_decisions(conn) -> list[dict]:
    return _rows(conn, f"SELECT * FROM decisions WHERE {GOAL_WHERE} AND {db.ACTIVE} ORDER BY id")


def non_goal_decisions(conn) -> list[dict]:
    return _rows(conn, f"SELECT * FROM decisions WHERE {NON_GOAL_WHERE} AND {db.ACTIVE} ORDER BY id")


def stack_decisions(conn) -> list[dict]:
    return _rows(conn, f"SELECT * FROM decisions WHERE {STACK_WHERE} AND {db.ACTIVE} ORDER BY id")


def no_deps_decisions(conn) -> list[dict]:
    return _rows(conn, f"SELECT * FROM decisions WHERE {NO_DEPS_WHERE} AND {db.ACTIVE} ORDER BY id")


# --- stage 1: context & goals --------------------------------------------------

def gate_stage1(conn) -> list[dict]:
    holes = []
    goals = goal_decisions(conn)
    if not goals:
        holes.append(_hole(
            "decisions", "no goals recorded",
            "record each goal as a decision whose text starts 'Goal:', with the measurable "
            "success criterion in rationale"))
    for g in goals:
        if not (g["rationale"] or "").strip():
            holes.append(_hole(
                "decisions", f"goal decisions:{g['id']} (\"{g['text']}\") has no success criterion",
                "a goal's rationale carries the measurable success criterion an acceptance test "
                f"could check — supersede_row(\"decisions\", {g['id']}, {{\"rationale\": "
                "\"...\"}}, reason) adds it", row_id=g["id"]))
    if not non_goal_decisions(conn):
        holes.append(_hole(
            "decisions", "no non-goals recorded",
            "record each explicit exclusion as a decision whose text starts 'Non-goal:' — "
            "the gate requires at least one real exclusion"))
    if not stack_decisions(conn):
        holes.append(_hole(
            "decisions", "target stack not recorded",
            "record the language/platform/runtime as a decision whose text starts 'Stack:' "
            "(planning data, never tool configuration)"))
    return holes


# --- stage 2: use cases --------------------------------------------------------

def gate_stage2(conn) -> list[dict]:
    holes = []
    if not _rows(conn, f"SELECT id FROM use_cases WHERE {db.ACTIVE} LIMIT 1"):
        holes.append(_hole(
            "use_cases", "no use cases recorded",
            "elicit them Cockburn-style with submit_use_cases: primary actor, numbered main "
            "scenario, extensions per step"))
    for s in _rows(conn, f"""
        SELECT s.id, s.step_no, s.text, u.title
        FROM uc_steps s JOIN use_cases u ON u.id = s.use_case_id
        WHERE s.no_extension_reason IS NULL AND {db.active('s')} AND {db.active('u')}
          AND NOT EXISTS (SELECT 1 FROM uc_extensions e
                          WHERE e.step_id = s.id AND {db.active('e')})
        ORDER BY u.id, s.step_no"""):
        holes.append(_hole(
            "uc_steps",
            f"step {s['step_no']} of '{s['title']}' (uc_steps:{s['id']} — \"{s['text']}\") has "
            "no extensions and no no_extension_reason",
            "add what can fail or vary here with submit_uc_extensions, or record why genuinely "
            f"nothing can (supersede_row(\"uc_steps\", {s['id']}, "
            "{\"no_extension_reason\": \"...\"}, reason))",
            row_id=s["id"], entity=s["title"]))
    return holes


# --- stage 3: requirements -----------------------------------------------------

_SLOT_HOLES_SQL = f"""
    SELECT id, ears_type FROM requirements WHERE {db.ACTIVE} AND (
        (ears_type = 'ubiquitous' AND system_response IS NULL)
     OR (ears_type IN ('event', 'unwanted') AND (trigger_text IS NULL OR system_response IS NULL))
     OR (ears_type = 'state' AND (precondition IS NULL OR system_response IS NULL))
     OR (ears_type = 'optional' AND (feature IS NULL OR system_response IS NULL)))
    ORDER BY id"""


def gate_stage3(conn) -> list[dict]:
    holes = []
    if not _rows(conn, f"SELECT id FROM requirements WHERE {db.ACTIVE} LIMIT 1"):
        holes.append(_hole(
            "requirements", "no requirements recorded",
            "derive EARS-typed requirements from the use cases with submit_requirements, "
            "linking each to its use case"))
    for r in _rows(conn, _SLOT_HOLES_SQL):
        holes.append(_hole(
            "requirements",
            f"requirements:{r['id']} does not satisfy its ears_type '{r['ears_type']}' slots",
            "every requirement is slot-structured — fill the type's required slots "
            "(free prose is never accepted)", row_id=r["id"]))
    for r in _rows(conn, f"""
        SELECT id FROM requirements WHERE is_nfr = 1 AND {db.ACTIVE}
            AND (planguage_scale IS NULL
                 OR planguage_meter IS NULL OR planguage_target IS NULL) ORDER BY id"""):
        holes.append(_hole(
            "requirements", f"NFR requirements:{r['id']} lacks a full Planguage triad",
            "quantify every NFR with planguage_scale, planguage_meter, and planguage_target",
            row_id=r["id"]))
    for u in _rows(conn, f"""
        SELECT u.id, u.title FROM use_cases u
        WHERE {db.active('u')}
          AND NOT EXISTS (SELECT 1 FROM requirements r
                          WHERE r.links LIKE '%"use_cases:' || u.id || '"%'
                            AND {db.active('r')})
        ORDER BY u.id"""):
        holes.append(_hole(
            "use_cases", f"use case '{u['title']}' (use_cases:{u['id']}) traces to no requirement",
            f"derive its requirements and link them (links: [\"use_cases:{u['id']}\"])",
            row_id=u["id"], entity=u["title"]))
    return holes


# --- stage 4: domain -----------------------------------------------------------

def gate_stage4(conn) -> list[dict]:
    holes = []
    entities = _rows(conn, f"SELECT * FROM entities WHERE {db.ACTIVE} ORDER BY id")
    if not entities:
        holes.append(_hole(
            "entities", "no domain entities recorded",
            "synthesize mode: propose the domain model (entities with lifecycle judgments) "
            "with submit_entities and let the user adjudicate"))
    for e in entities:
        ops = {r["op"] for r in _rows(
            conn, f"SELECT op FROM crud_grid WHERE entity_id = ? AND {db.ACTIVE}", (e["id"],))}
        missing = [op for op in CRUD_OPS if op not in ops]
        if missing:
            holes.append(_hole(
                "crud_grid",
                f"entity '{e['name']}' (entities:{e['id']}) has empty CRUD cell(s) {missing}",
                "every cell names the responsible actor/component or is an explicit n/a + reason "
                "(children_on_delete on D)", row_id=e["id"], entity=e["name"]))
        if not e["has_lifecycle"]:
            if not (e["lifecycle_reason"] or "").strip():
                holes.append(_hole(
                    "entities",
                    f"entity '{e['name']}' (entities:{e['id']}) has has_lifecycle=false "
                    "without a recorded justification",
                    "record why this entity has no lifecycle worth modelling "
                    "(lifecycle_reason)", row_id=e["id"], entity=e["name"]))
            continue
        machines = _rows(conn, f"SELECT * FROM state_machines WHERE entity_id = ? AND {db.ACTIVE}",
                         (e["id"],))
        if not machines:
            holes.append(_hole(
                "state_machines",
                f"lifecycle entity '{e['name']}' (entities:{e['id']}) has no state machine",
                "propose states and events with submit_states; every state x event cell is a "
                "transition or an explicit impossible + reason",
                row_id=e["id"], entity=e["name"]))
            continue
        m = machines[0]
        states, events = json.loads(m["states"]), json.loads(m["events"])
        have = {(c["state"], c["event"]) for c in _rows(
            conn, f"SELECT state, event FROM sm_cells WHERE machine_id = ? AND {db.ACTIVE}",
            (m["id"],))}
        undefined = [[s, ev] for s in states for ev in events if (s, ev) not in have]
        if undefined:
            holes.append(_hole(
                "sm_cells",
                f"state machine for '{e['name']}' (state_machines:{m['id']}) has "
                f"{len(undefined)} undefined state x event cell(s): {undefined}",
                "fill each with submit_state_cells — a transition_to or an explicit "
                "impossible + reason", row_id=m["id"], entity=e["name"]))
    return holes


# --- stage 5: errors & dependencies --------------------------------------------

def gate_stage5(conn) -> list[dict]:
    holes = []
    deps = _rows(conn, f"SELECT * FROM dependencies WHERE {db.ACTIVE} ORDER BY id")
    if not deps and not no_deps_decisions(conn):
        holes.append(_hole(
            "dependencies",
            "no external dependencies registered and no explicit 'no external dependencies' "
            "decision",
            "register each dependency with submit_dependencies, or record a decision stating "
            "the system has no external dependencies (text containing 'no external "
            "dependencies') with the rationale"))
    for d in deps:
        modes = {r["mode"] for r in _rows(
            conn, f"SELECT mode FROM dep_failure_modes WHERE dep_id = ? AND {db.ACTIVE}",
            (d["id"],))}
        missing = [m for m in FAILURE_MODES if m not in modes]
        if missing:
            holes.append(_hole(
                "dep_failure_modes",
                f"dependency '{d['name']}' (dependencies:{d['id']}) is missing failure-mode "
                f"handling for {missing}",
                "submit_dep_failure_modes — all five of unavailable/slow/malformed/auth/partial "
                "per dependency", row_id=d["id"], entity=d["name"]))
    return holes


# --- stage 6: architecture -------------------------------------------------------

def gate_stage6(conn) -> list[dict]:
    holes = []
    if not _rows(conn, f"SELECT id FROM components WHERE {db.ACTIVE} LIMIT 1"):
        holes.append(_hole(
            "components", "no components recorded",
            "synthesize mode: design the component cut with submit_components and contracts "
            "to structured-signature level; the user adjudicates"))
    for c in _rows(conn, f"""
        SELECT c.id, c.name FROM components c
        WHERE {db.active('c')}
          AND NOT EXISTS (SELECT 1 FROM contracts k
                          WHERE k.component_id = c.id AND {db.active('k')})
        ORDER BY c.id"""):
        holes.append(_hole(
            "components", f"component '{c['name']}' (components:{c['id']}) has no contract",
            "every deliverable component gets >=1 contract via submit_contracts",
            row_id=c["id"], entity=c["name"]))
    for k in _rows(conn, f"""
        SELECT k.id, k.name, c.name AS component FROM contracts k
        JOIN components c ON c.id = k.component_id
        WHERE {db.active('k')}
          AND (k.params IS NULL OR k.returns IS NULL
               OR (k.cannot_fail = 1 AND k.cannot_fail_reason IS NULL)
               OR (k.cannot_fail = 0 AND (k.errors IS NULL OR k.errors = '[]')))
        ORDER BY k.id"""):
        holes.append(_hole(
            "contracts",
            f"contract '{k['name']}' (contracts:{k['id']}) on '{k['component']}' is "
            "structurally incomplete",
            "supersede it with the completed signature (supersede_row) — params typed (or "
            "explicitly []), a return type_expr, and >=1 named error with semantics or "
            "cannot_fail + reason", row_id=k["id"], entity=k["component"]))
    for k in _rows(conn, f"""
        SELECT k.id, k.name, c.name AS component FROM contracts k
        JOIN components c ON c.id = k.component_id
        WHERE k.is_external = 0 AND {db.active('k')}
          AND NOT EXISTS (SELECT 1 FROM contract_deps d
                          WHERE d.provider_contract_id = k.id AND {db.active('d')})
        ORDER BY k.id"""):
        holes.append(_hole(
            "contracts",
            f"contract '{k['name']}' (contracts:{k['id']}) has no consumer and is not marked "
            "external — an untraceable contract is invented scope",
            "record its consumer edge with submit_contract_deps, mark it external "
            f"(supersede_row(\"contracts\", {k['id']}, {{\"is_external\": true}}, reason)), or "
            f"cut it (retire_row(\"contracts\", {k['id']}, reason))",
            row_id=k["id"], entity=k["component"]))
    for k in _rows(conn, f"""
        SELECT k.id, k.name FROM contracts k
        WHERE k.provenance = 'assumed' AND k.assumption_kind = 'world' AND {db.active('k')}
          AND NOT EXISTS (SELECT 1 FROM spikes s
                          WHERE s.links LIKE '%"contracts:' || k.id || '"%')
          AND NOT EXISTS (SELECT 1 FROM decisions d
                          WHERE d.links LIKE '%"contracts:' || k.id || '"%'
                            AND {db.active('d')})
        ORDER BY k.id"""):
        holes.append(_hole(
            "contracts",
            f"contract '{k['name']}' (contracts:{k['id']}) rests on an unverified "
            "world-assumption",
            "spike it against the real dependency (register_spike with links to this contract), "
            "or record a user-accepted-risk decision linking it", row_id=k["id"]))
    for r in _rows(conn, f"""
        SELECT r.id FROM requirements r
        WHERE {db.active('r')}
          AND NOT EXISTS (SELECT 1 FROM contracts k
                          WHERE k.links LIKE '%"requirements:' || r.id || '"%'
                            AND {db.active('k')})
          AND NOT EXISTS (SELECT 1 FROM decisions d
                          WHERE d.links LIKE '%"requirements:' || r.id || '"%'
                            AND {db.active('d')})
        ORDER BY r.id"""):
        holes.append(_hole(
            "requirements",
            f"requirements:{r['id']} traces to no contract and is not explicitly deferred",
            "link a contract to it (supersede_row the contract adding links: "
            f"[\"requirements:{r['id']}\"]), record a deferral decision linking it with the "
            f"rationale, or retire_row(\"requirements\", {r['id']}, reason) if it no longer "
            "stands", row_id=r["id"]))
    for k in _rows(conn, f"""
        SELECT k.id, k.name FROM contracts k
        WHERE (k.links IS NULL OR k.links NOT LIKE '%"requirements:%') AND {db.active('k')}
        ORDER BY k.id"""):
        holes.append(_hole(
            "contracts",
            f"contract '{k['name']}' (contracts:{k['id']}) traces to no requirement — "
            "invented scope",
            f"link it to the requirement(s) it satisfies (supersede_row(\"contracts\", "
            f"{k['id']}, {{\"links\": [\"requirements:N\"]}}, reason)) or cut it "
            f"(retire_row(\"contracts\", {k['id']}, reason))",
            row_id=k["id"]))
    return holes


GATES = {1: gate_stage1, 2: gate_stage2, 3: gate_stage3,
         4: gate_stage4, 5: gate_stage5, 6: gate_stage6}


def run_gate(conn: db.Connection, stage) -> dict:
    """Evaluate a stage gate, record the result, advance the plan on a pass
    at its current stage. Returns pass/fail with the specific row-level holes."""
    if isinstance(stage, bool) or not isinstance(stage, int) or not 1 <= stage <= 8:
        return {"error": f"Rule: stage is an integer 1-8. Offending input: stage={stage!r}."}
    if stage not in GATES:
        return {"error": (
            "Rule: the stage-7 (adversarial) and stage-8 (freeze) gates arrive in a later "
            f"build session; gates 1-6 are live. Offending input: stage={stage}.")}
    holes = GATES[stage](conn)
    passed = not holes
    plan = db.get_plan(conn)
    db.insert_row(conn, "gate_results", {
        "plan_id": plan["id"], "stage": stage,
        "passed": 1 if passed else 0, "holes": json.dumps(holes)})
    out = {"stage": stage, "passed": passed, "holes": holes,
           "current_stage": plan["current_stage"]}
    if passed and plan["current_stage"] == stage and stage < 8:
        conn.execute("UPDATE plans SET current_stage = ?", (stage + 1,))
        out["advanced_to"] = stage + 1
        out["current_stage"] = stage + 1
    conn.commit()
    return out
