"""Session C done-when: a populated DB survives export -> drop -> reimport.
Plus the escape-hatch behaviours: refusing to clobber, rejecting foreign
files, and reporting dropped columns on schema churn."""
import pytest
import yaml

from engine import db, gates, render, spikes, submits

from conftest import populate_full_plan


def populated_conn(tmp_path):
    conn = db.create_plan_db(tmp_path / "plan.db", "roundtrip-plan")
    populate_full_plan(conn)
    submits.file_question(conn, "Which currency rounding rule applies?", owner="user")
    spikes.register_spike(conn, tmp_path / "spikes", "does the sandbox rate-limit?",
                          "60 rpm", "hammer the real sandbox", "1h",
                          links=["contracts:1"])
    gates.run_gate(conn, 1)  # a gate_results row rides along
    return conn


def all_tables(conn):
    return {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")]
            for t in render.TABLE_ORDER}


def test_export_drop_reimport_is_lossless(tmp_path):
    conn = populated_conn(tmp_path)
    before = all_tables(conn)
    out = render.export_yaml(conn, tmp_path / "plan.yaml")
    conn.close()
    (tmp_path / "plan.db").unlink()  # the "drop"

    assert out["rows"]["plans"] == 1 and out["rows"]["requirements"] >= 1
    render.import_yaml(tmp_path / "plan.yaml", tmp_path / "plan.db")

    conn2 = db.connect(tmp_path / "plan.db")
    try:
        assert all_tables(conn2) == before
    finally:
        conn2.close()


def test_reimported_plan_keeps_working(tmp_path):
    conn = populated_conn(tmp_path)
    render.export_yaml(conn, tmp_path / "plan.yaml")
    conn.close()
    render.import_yaml(tmp_path / "plan.yaml", tmp_path / "plan2.db")
    conn2 = db.connect(tmp_path / "plan2.db")
    try:
        # Gates run on reimported data, ids keep resolving, and new writes land.
        assert gates.run_gate(conn2, 6)["passed"] is True
        out = submits.file_question(conn2, "post-reimport question", links=["contracts:1"])
        assert out["id"] == 2
    finally:
        conn2.close()


def test_import_refuses_existing_target(tmp_path):
    conn = populated_conn(tmp_path)
    render.export_yaml(conn, tmp_path / "plan.yaml")
    conn.close()
    with pytest.raises(FileExistsError, match="deliberately"):
        render.import_yaml(tmp_path / "plan.yaml", tmp_path / "plan.db")


def test_import_rejects_foreign_yaml(tmp_path):
    (tmp_path / "notaplan.yaml").write_text("just: some yaml\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a plantool export"):
        render.import_yaml(tmp_path / "notaplan.yaml", tmp_path / "new.db")


def test_import_drops_and_reports_unknown_columns(tmp_path):
    conn = populated_conn(tmp_path)
    data = render.export_data(conn)
    conn.close()
    for row in data["tables"]["requirements"]:
        row["retired_column"] = "value from an older schema"
    conn2 = db.create_db(tmp_path / "new.db")
    try:
        out = render.import_data(conn2, data)
        assert out["dropped_columns"] == {"requirements": ["retired_column"]}
        assert conn2.execute("SELECT count(*) FROM requirements").fetchone()[0] \
            == out["rows"]["requirements"]
    finally:
        conn2.close()


def test_export_yaml_is_plain_safe_yaml(tmp_path):
    conn = populated_conn(tmp_path)
    render.export_yaml(conn, tmp_path / "plan.yaml")
    conn.close()
    data = yaml.safe_load((tmp_path / "plan.yaml").read_text(encoding="utf-8"))
    assert data["plantool_export"] == render.EXPORT_FORMAT
    assert data["plan_name"] == "roundtrip-plan"


# --- plan.md / plan packs (Session E) ------------------------------------------


def test_full_markdown_carries_every_section_with_refs(tmp_path):
    conn = populated_conn(tmp_path)
    try:
        md = render.render_markdown(conn)
    finally:
        conn.close()
    assert md.startswith("# Plan: roundtrip-plan")
    # The EARS sentence is assembled from slots, never stored.
    assert ("WHEN the user submits a valid order, the system shall persist the order "
            "and emit OrderPlaced.") in md
    for expected in (
            "Goal: customers place orders online",          # stage 1
            "Place an order — actor: Customer",             # stage 2
            "### Order (`entities:1`", "| C | OrderService", # stage 4 grid
            "| draft | place | placed |",                    # stage 4 machine
            "### Stripe API (api)", "| unavailable |",       # stage 5
            "**place_order** (function): (draft: OrderDraft) -> OrderId",  # stage 6
            "error ValidationError",
            "does the sandbox rate-limit?",                  # spikes
            "Which currency rounding rule applies?",         # questions
            "`requirements:1`", "`contracts:1`"):            # refs for the red team
        assert expected in md, expected


def test_stage_pack_scopes_to_one_stage(tmp_path):
    conn = populated_conn(tmp_path)
    try:
        pack = render.plan_pack(conn, "stage:3")
        assert pack["scope"] == "stage:3"
        assert "the system shall persist the order" in pack["markdown"]
        assert "Stripe API" not in pack["markdown"]
    finally:
        conn.close()


def test_component_pack_carries_contracts_and_linked_decisions(tmp_path):
    conn = populated_conn(tmp_path)
    try:
        submits.record_decision(
            conn, "place_order is synchronous", "decided",
            rationale="callers need the OrderId immediately", links=["contracts:1"],
            alternatives=[{"alternative": "async job + callback",
                           "rejected_because": "no consumer can use it"}])
        by_name = render.plan_pack(conn, "component:orderservice")
        assert by_name["scope"] == "component:OrderService"
        assert "place_order" in by_name["markdown"]
        assert "place_order is synchronous" in by_name["markdown"]
        assert "rejected: async job + callback" in by_name["markdown"]
        assert render.plan_pack(conn, "component:1")["markdown"] == by_name["markdown"]
    finally:
        conn.close()


def test_plan_pack_rejects_bad_scopes(tmp_path):
    conn = populated_conn(tmp_path)
    try:
        assert "\"stage:N\"" in render.plan_pack(conn, "everything")["error"]
        assert "freeze procedure" in render.plan_pack(conn, "stage:8")["error"]
        unknown = render.plan_pack(conn, "component:NoSuch")["error"]
        assert "matches none" in unknown and "OrderService" in unknown
    finally:
        conn.close()


def test_export_plan_writes_both_files(tmp_path):
    conn = populated_conn(tmp_path)
    try:
        out = render.export_plan(conn, tmp_path)
    finally:
        conn.close()
    md = (tmp_path / "plan.md").read_text(encoding="utf-8")
    assert "# Plan: roundtrip-plan" in md
    assert out["plan_md"]["chars"] == len(md)
    assert out["plan_yaml"]["rows"]["plans"] == 1
    (tmp_path / "plan.db").unlink()
    render.import_yaml(tmp_path / "plan.yaml", tmp_path / "plan.db")  # still a real bundle


def test_roundtrip_check_is_clean_on_a_real_plan(tmp_path):
    conn = populated_conn(tmp_path)
    try:
        assert render.roundtrip_check(conn) == []
    finally:
        conn.close()
