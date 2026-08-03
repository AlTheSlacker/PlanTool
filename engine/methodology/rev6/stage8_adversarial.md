# Stage 8 — Adversarial (verify mode)

The plan now gets attacked before it gets frozen. Two passes, both filed through
`file_finding`, both drained through `resolve_finding`. **You do not defend the plan
here** — a finding that turns out wrong is resolved on the record, never argued out of
existence before it is filed.

## Pass 1 — the red team (a fresh session, not you)

Your context authored this plan; it cannot see the plan's blind spots because they are its
own. Ask the user to **start a fresh session in this workspace** and tell it to red-team
the plan. That session will call `get_auxiliary("redteam")` for its own script, read the
plan through `read_rows`, and file findings with `file_finding(source="redteam", ...)`. Do
not brief it beyond that —
a red team that inherits your framing inherits your blind spots.

While it runs: nothing. Your part resumes when findings exist.

## Pass 2 — the pre-mortem (you, with the user)

Assume it is a year from now and the implemented system failed **because of a planning
error**. Ask the user for the failure story first (owner-generated candidates), then write
your own: for each, name the plan row(s) that caused it. File each credible story as
`file_finding(source="premortem", text, links)` — linked to the rows it implicates, not to
vibes. Standing targets you must check explicitly (they are prompt-enforced rules the
engine cannot see, spec 5.1):

- `assumed→decided` upgrades whose `provenance_note` quote doesn't read like the user's words.
- Spike methods that touched a mock or a stand-in but recorded `confirmed`.
- Significant decisions whose `alternatives` are strawmen (technically present, never live options).

## Dispositioning — with the user, every finding

Each finding is closed with `resolve_finding`, which takes exactly one outcome:
- **addressed** — the plan rows were corrected (supersede_row / retire_row / new submits);
  the reason names them.
- **accepted_risk** — the user heard the risk and kept the plan; the reason quotes their
  call. This one stays visible at implementation handoff, which is the point of it.
- **withdrawn** — the finding was wrong. Only reachable after a recorded dispute.

Where an experiment will settle it, `register_spike` first and say so in the reason.

Dismissing a finding as "not really a problem" is spelled **accepted_risk**, with the user's
words in the reason. The gate checks both halves — an outcome and a reason — because a
finding closed without one is indistinguishable at handoff from one somebody forgot about.

## Self-review before gate

- Did the red team run in a genuinely fresh session? Findings authored by this session
  under `source="redteam"` are self-review wearing a costume.
- Is any disposition reason a restatement of the finding rather than an answer to it?
- Zero findings overall? The gate will refuse — and it is right: a red team that finds
  nothing means the script is broken, not that the plan is perfect.

## Exit condition (mechanical gate)

At least one finding exists, and every finding has both an outcome and a reason.
