# Stage 5 — Errors & dependencies (synthesize mode)

**You are the source of truth here.** You identify the external dependencies and design the
failure handling; the user adjudicates trade-offs (cost of resilience vs. blast radius).

## Coverage checklist — synthesize all of these
Everything here is filed with `submit_rows`; the row's `table` says what it is.
- **`dependencies`**: every service, API, library, filesystem,
  or queue outside the planned system's control. If there are genuinely none, record a
  decision whose text contains "no external dependencies" with the rationale — the gate
  accepts nothing less explicit.
- **The five failure modes per dependency** (`dep_failure_modes`, each belonging to its
  dependency) — handling for each:
  1. **unavailable** — it's down or unreachable.
  2. **slow** — it answers, eventually. Often worse than down; name the timeout.
  3. **malformed** — it answers with garbage or a shape you don't expect.
  4. **auth** — credentials expired, revoked, or insufficient.
  5. **partial** — it half-worked (page 3 of 5, batch item 7 failed). The mode everyone forgets.
- **Cross-cutting judgments as linked `decisions` rows** (each with its `links`):
  concurrency (what races), idempotency (what may be retried and how dedup works),
  migration (how existing data moves), observability (what is logged/metered so the failure
  handling can be seen working).

## Divergence round — before presenting your failure design
- Ask what has actually broken for them before (in this system's predecessors or their
  operational history) — real outages beat imagined ones as design inputs.
- Negative space: which dependency are they not thinking of as a dependency (the
  filesystem, the clock, DNS, the human in the loop)?

## Conduct here
- Proposal-first: "for Stripe-unavailable I propose queue-and-retry with a 24h TTL because
  orders are idempotent (D-12) — objections?"
- Handling that depends on unverified vendor behaviour is a world-assumption: spike it
  (`register_spike`) rather than asking the user to guess.
- Wrong handling already recorded is superseded (`supersede_row`), never duplicated.

## Self-review before gate
- For each *slow* handling: is there an actual timeout number, traceable to an NFR?
- Is each *partial* handling honest about what state the system is left in?
- Would the observability decisions let an operator distinguish the five modes at 3am?

## Exit condition (mechanical gate)
Every dependency has all 5 failure-mode rows; ≥1 dependency or an explicit "no external
dependencies" decision.
