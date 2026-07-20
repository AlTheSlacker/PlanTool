from engine import submits

from conftest import valid_entity, valid_requirement


def test_valid_requirement_batch_lands(conn):
    from conftest import valid_use_case
    submits.submit_use_cases(conn, [valid_use_case()])  # links resolve since Session D
    result = submits.submit_requirements(conn, [
        valid_requirement(),
        valid_requirement(ears_type="state", trigger=None,
                          precondition="the plan is frozen",
                          system_response="reject all submit calls"),
        valid_requirement(ears_type="ubiquitous", trigger=None, is_nfr=True,
                          system_response="serve plan_status quickly",
                          planguage_scale="p95 latency ms",
                          planguage_meter="load test, 100 calls",
                          planguage_target="<= 200",
                          provenance="assumed", assumption_kind="intent",
                          links=["use_cases:1"]),
    ])
    assert result["accepted"] == 3 and result["rejected"] == 0
    rows = conn.execute("SELECT * FROM requirements ORDER BY id").fetchall()
    assert rows[0]["trigger_text"] == "the user submits a valid order"
    assert rows[1]["precondition"] == "the plan is frozen"
    assert rows[2]["is_nfr"] == 1
    assert rows[2]["assumption_kind"] == "intent"
    assert rows[2]["links"] == '["use_cases:1"]'
    assert rows[2]["plan_version_added"] == 1


def test_one_bad_row_never_bounces_the_batch(conn):
    result = submits.submit_requirements(conn, [
        valid_requirement(),
        valid_requirement(trigger=None),  # event without its trigger slot
        valid_requirement(system_response="archive completed orders nightly"),
    ])
    assert result["accepted"] == 2 and result["rejected"] == 1
    verdicts = {v["index"]: v for v in result["results"]}
    assert verdicts[0]["accepted"] and verdicts[2]["accepted"]
    bad = verdicts[1]
    assert not bad["accepted"]
    # Pedagogic: names the rule, shows the offending input and a compliant example.
    assert "WHEN <trigger>" in bad["error"]
    assert "ears_type" in bad["error"]
    assert "Compliant example" in bad["error"]
    assert conn.execute("SELECT count(*) FROM requirements").fetchone()[0] == 2


def test_stray_slot_rejected(conn):
    result = submits.submit_requirements(
        conn, [valid_requirement(ears_type="ubiquitous", trigger="left over")])
    assert result["rejected"] == 1
    assert "does not belong" in result["results"][0]["error"]


def test_assumed_requires_kind_and_verified_is_refused(conn):
    result = submits.submit_requirements(conn, [
        valid_requirement(provenance="assumed"),
        valid_requirement(provenance="verified"),
        valid_requirement(provenance="chosen"),
        valid_requirement(assumption_kind="world"),  # kind without assumed
    ])
    assert result["accepted"] == 0
    errors = [v["error"] for v in result["results"]]
    assert "assumption_kind" in errors[0]
    assert "spike" in errors[1]
    assert "provenance" in errors[2]
    assert "assumption_kind accompanies" in errors[3]


def test_nfr_requires_full_planguage_triad(conn):
    result = submits.submit_requirements(conn, [
        valid_requirement(is_nfr=True, planguage_scale="latency"),
        valid_requirement(planguage_target="<= 200"),  # planguage without is_nfr
    ])
    assert result["accepted"] == 0
    assert "planguage_meter" in result["results"][0]["error"]
    assert "is_nfr" in result["results"][1]["error"]


def test_unknown_field_rejected_pedagogically(conn):
    result = submits.submit_requirements(conn, [valid_requirement(severity="high")])
    assert result["rejected"] == 1
    err = result["results"][0]["error"]
    assert "severity" in err and "Valid fields" in err


def test_entity_lifecycle_judgment_enforced(conn):
    result = submits.submit_entities(conn, [
        valid_entity(),
        valid_entity(name="AuditEntry", has_lifecycle=False),  # no reason
        valid_entity(name="AuditEntry2", has_lifecycle=False,
                     lifecycle_reason="append-only; created once, never mutated"),
        valid_entity(name="Mystery", has_lifecycle=None),
    ])
    assert result["accepted"] == 2
    verdicts = result["results"]
    assert "lifecycle_reason" in verdicts[1]["error"]
    assert "judgment" in verdicts[3]["error"]


def test_duplicate_entity_rejected_within_batch_and_across_calls(conn):
    first = submits.submit_entities(conn, [valid_entity(), valid_entity()])
    assert first["accepted"] == 1 and first["rejected"] == 1
    assert "already exists" in first["results"][1]["error"]
    second = submits.submit_entities(conn, [valid_entity(name="ORDER")])  # case-insensitive
    assert second["rejected"] == 1
