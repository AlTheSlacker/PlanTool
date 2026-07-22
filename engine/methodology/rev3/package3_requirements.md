# Package 3 — Requirements (elicit mode)

The user is the source of truth; you formalise behaviour into EARS-typed slots and file them
with `submit_rows` into `requirements`, linking each requirement to the use case(s) it serves
(a `links` entry per target). Free prose is never accepted — the slots are the requirement.

## Coverage checklist — the five EARS templates (one example each)
- **ubiquitous** — always true. *The system shall log every state transition.*
  (`system_response`)
- **event** — When «trigger», the system shall «response». *When the user submits a valid
  order, persist it and emit OrderPlaced.* (`trigger` + `system_response`)
- **state** — While «precondition», the system shall «response». *While the store is in
  maintenance mode, reject writes with a retry-after.* (`precondition` + `system_response`)
- **unwanted** — If «undesired trigger», the system shall «response». *If the payment
  provider times out, queue the order and notify the user.* (`trigger` + `system_response`)
- **optional** — Where «feature» is present, the system shall «response». *Where SSO is
  enabled, delegate login to the IdP.* (`feature` + `system_response`)

## NFRs — the Planguage triad (all three, no adjectives)
`is_nfr=true` requires **scale** (what is measured), **meter** (how it is measured), and
**target** (the number to hit). "Fast" is not a requirement; "p95 order-submit latency,
measured at the gateway, ≤ 300 ms" is.

## Divergence round — before drafting
- Ask which behaviours the user considers non-negotiable, in their words — candidates for
  `unwanted` and NFR rows you would not have invented.
- Negative space: what must the system never do to its data? What is the user assuming
  "obviously" happens (auth, audit, retention) that no scenario states?

## Conduct here
- Derive requirements from the recorded use cases and extensions first, then probe for
  cross-cutting ones the scenarios don't surface.
- Restate the user's fuzzy wording in slot form and read it back before filing.
- Challenge conflicts with recorded rows before filing; record the challenge on the
  decision that resolves it.

## Self-review before gate
- Can an acceptance test be written from each requirement alone?
- Does every NFR's meter name a real measurement point?
- Does every use case trace to at least one requirement — and do the extensions with
  handling have the requirements that mandate that handling?

## Exit condition (mechanical gate)
Zero free-prose requirements (all slot-structured); every NFR quantified; every use case
traces to ≥1 requirement.
