"""Red-team / pre-mortem bookkeeping (spec sections 5 and 8, stage 7).

file_finding records an issue the adversarial pass found; disposition_finding
closes it as fixed / accepted / spiked with the rationale. The stage-7 gate
refuses to pass while any finding is undispositioned — and refuses to pass
vacuously on zero findings, because a red team that finds nothing means the
red-team script is broken, not that the plan is perfect (spec section 11).
"""
from __future__ import annotations

import json

from . import db
from .submits import _clean, _dangling_refs_error, _fmt, _links_error, _strip

SOURCES = ("redteam", "premortem")
DISPOSITIONS = ("fixed", "accepted", "spiked")


def _finding_links(finding: db.Row, extra: list[str] | None) -> list[str]:
    links = json.loads(finding["links"] or "[]")
    for ref in extra or []:
        if ref not in links:
            links.append(ref)
    return links


def file_finding(conn: db.Connection, source: str, text: str,
                 links: list[str] | None = None) -> dict:
    frozen = db.frozen_error(conn)
    if frozen:
        return {"error": frozen}
    args = _clean({"source": source, "text": text, "links": links})
    if args.get("source") not in SOURCES:
        return {"error": (
            f"Rule: source is one of {list(SOURCES)} — 'redteam' for the fresh-session "
            "adversarial pass, 'premortem' for the it-failed-because exercise. "
            f"Offending input: {_fmt(args)}.")}
    if _strip(args.get("text")) is None:
        return {"error": (
            "Rule: a finding states the specific issue found — what is wrong, where, and why "
            f"it matters. Offending input: {_fmt(args)}.")}
    err = _links_error(args) or _dangling_refs_error(conn, args.get("links"), args)
    if err:
        return {"error": err}
    plan = db.get_plan(conn)
    fid = db.insert_row(conn, "findings", {
        "plan_id": plan["id"], "plan_version_added": plan["version"],
        "source": args["source"], "text": _strip(args["text"]),
        "links": json.dumps(args["links"]) if args.get("links") else None})
    conn.commit()
    return {"id": fid,
            "note": ("Filed. The stage-7 gate blocks until every finding is dispositioned "
                     "(disposition_finding: fixed | accepted | spiked, with rationale).")}


def disposition_finding(conn: db.Connection, finding_id, disposition: str,
                        rationale: str, links: list[str] | None = None) -> dict:
    frozen = db.frozen_error(conn)
    if frozen:
        return {"error": frozen}
    finding = None
    if isinstance(finding_id, int) and not isinstance(finding_id, bool):
        finding = conn.execute(
            "SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
    if finding is None:
        open_fs = {r["id"]: r["text"] for r in conn.execute(
            "SELECT id, text FROM findings WHERE disposition IS NULL ORDER BY id")}
        return {"error": (
            "Rule: finding_id must match a filed finding. Undispositioned findings "
            f"(id: text): {_fmt(open_fs)}. Offending input: finding_id={_fmt(finding_id)}.")}
    if finding["disposition"] is not None:
        return {"error": (
            f"Rule: finding #{finding['id']} is already dispositioned "
            f"('{finding['disposition']}': \"{finding['disposition_rationale']}\"). "
            "File a new finding if the issue has resurfaced.")}
    if disposition not in DISPOSITIONS:
        return {"error": (
            f"Rule: disposition is one of {list(DISPOSITIONS)} — 'fixed' (the plan rows were "
            "corrected; link them), 'accepted' (the user accepted the risk knowingly), or "
            "'spiked' (an experiment will settle it; link the spike). "
            f"Offending input: disposition={_fmt(disposition)}.")}
    if _strip(rationale) is None:
        return {"error": (
            "Rule: a disposition records its rationale — what was fixed, why the risk is "
            "acceptable, or what the spike will settle. Offending input: "
            f"{_fmt({'finding_id': finding_id, 'disposition': disposition, 'rationale': rationale})}.")}
    args = _clean({"links": links})
    err = _links_error(args) or _dangling_refs_error(conn, args.get("links"), args)
    if err:
        return {"error": err}
    merged = _finding_links(finding, args.get("links"))
    if disposition == "spiked" and not any(ref.startswith("spikes:") for ref in merged):
        return {"error": (
            "Rule: a 'spiked' disposition links the spike that will settle the finding "
            "(register_spike first, then pass links: [\"spikes:N\"]). Offending input: "
            f"{_fmt({'finding_id': finding_id, 'links': links})}.")}
    conn.execute(
        "UPDATE findings SET disposition = ?, disposition_rationale = ?, links = ? "
        "WHERE id = ?",
        (disposition, _strip(rationale), json.dumps(merged) if merged else None,
         finding["id"]))
    conn.commit()
    return {"id": finding["id"], "disposition": disposition}
