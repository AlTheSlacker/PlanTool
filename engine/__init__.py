"""PlanTool v2 engine.

Built from the frozen plan at spec/v2/plan.md. That plan is read-only and is the
specification; departures from it are logged in spec/v2/DEVIATIONS.md, and places
where it proved insufficient are logged in spec/v2/DEFECTS.md.

Layering (frozen plan, decisions:50) — foundation, planning, surface. v2 inserts a
service layer beneath the surface so MCP is the first adapter rather than the only
possible consumer; see DEVIATIONS.md entry D2.
"""

__version__ = "2.0.0"
