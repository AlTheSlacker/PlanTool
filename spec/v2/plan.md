# Plan: LLM Manager — planning tool for LLM CLI code engines

State: frozen · version 2 · stage 8

## Stage 1 — Context & goals

**Goals**
- Goal: Execution sufficiency — a finished plan lets an executor complete every sub-task without milestone-time re-planning. (`decisions:14` · decided) — Success criterion: on a real project, zero sub-tasks are blocked by missing or ambiguous plan information; mid-execution discoveries arrive as change-orders traceable to genuinely new facts, not planning omissions.
- Goal: Lossless resume — any session can die at any point and a cold session resumes from the database alone. (`decisions:15` · decided) — Success criterion: zero previously-answered questions are ever re-asked across session deaths. Directly counters LLM forgetfulness (problem cause c).
- Goal: Focused context delivery — each execution sub-task receives a context pack containing exactly its linked rows plus the governing big-picture rows. (`decisions:16` · decided) — Success criterion: the executor never has to request missing plan information, and the pack contains no rows lacking a link-path to the task.
- Goal: Enforced rigor — the planning interview cannot silently accept contradictions or invented facts. (`decisions:17` · decided) — Success criterion: mechanical audit shows every row carries provenance and every conflict with an existing row was raised before filing. Counters agreeable transcription and inaccurate assessments (problem cause c).
- Goal: Research red-flag triage — every user-proposed capability is feasibility-classified at the moment it enters the plan: established solution, needs a spike, or research-level with no known solution. Research-level items must be resolved or fenced as an explicit research sub-project with go/no-go criteria before dependent planning continues. (`decisions:18` · decided) — Success criterion: zero research-level unknowns survive into build planning unresolved; research surprises discovered at build time = 0. User's actual words: "if the user proposes something with no known solution, that is a research red flag that needs to be considered immediately and if not solvable defined as a research sub-project in itself before continuing." Directly targets problem cause (b).
- Goal: Frictionless deployment — a gate-passed plan becomes an executing workspace with near-zero ceremony. (`decisions:19` · decided) — Success criterion: from approved plan to an executor working on its first sub-task in a single command, with no manual transcription of plan content. User named deployment friction as the most likely cause of tool abandonment: "the most likely cause of that is it creating too much friction to deploy."
- Goal: Dependency rigor — every external dependency is fully characterised (version, role, integration surface, known failure modes) before build planning completes. (`decisions:20` · derived) — Success criterion: zero mid-build discoveries of missing, incompatible, or misunderstood dependencies. Derived from problem cause (a) "poorly defined dependencies" — the user named it as a leading failure cause but did not state it as a goal; engineer promoted it.

**Non-goals**
- Non-goal: generating production code — the tool plans; the LLM CLI engine executes. (`decisions:9` · decided) — User confirmed: "Totally correct assumptions."
- Non-goal: multi-user project management — no scheduling, Gantt charts, task assignment, or team workflow. (`decisions:10` · decided) — User confirmed the candidate non-goal list in full.
- Non-goal: any hosted or cloud component — fully local operation. (`decisions:11` · decided) — User confirmed the candidate non-goal list in full.
- Non-goal: direct LLM API integration or API-key management. (`decisions:12` · decided) — User confirmed the candidate non-goal list in full; also a founding constraint from the original brief.
- Non-goal: planning non-software projects — this is a software development planning tool only. (`decisions:13` · decided) — User's actual words: "this is a software dev plan tool only."
- Non-goal: public distribution, packaging, or end-user support — personal tool. (`decisions:21` · derived) — Follows from the audience decision (personal tool for the author's own projects).

**Target stack**
- Stack: Python + SQLite (single-file database per plan), delivered as an MCP server over stdio. (`decisions:1` · decided) — User selected "Python + SQLite (Recommended)". Continuity with the author's Python skills; mature Python MCP SDK; SQLite is zero-install, cross-OS, single-file, with real foreign keys — the plan travels with the project folder.

## Stage 2 — Use cases

### Start a plan — actor: LLM planning agent (`use_cases:1` · decided)
1. Owner instructs the agent — already running inside the project workspace it is planning — to begin planning the project. (`uc_steps:1`)
   - if Owner's instruction is ambiguous about project scope. -> Agent asks before initializing when project scope is ambiguous; tier is never asked — v1 has the single tier 'standard', applied by default. (`uc_extensions:50`)
2. Agent initializes a new plan in the existing workspace, recording name and tier. The tool never creates or manages the workspace itself. (`uc_steps:2`)
   - if A plan already exists in this workspace. -> Resume it (UC2) — never overwrite. Starting fresh requires explicit owner confirmation and archives the old plan as a version. (`uc_extensions:2`)
   - if Storage failure during initialization. -> Visible error; initialization is atomic — nothing half-created. (`uc_extensions:3`)
3. Tool returns the engineer's mandate plus the stage-1 script; agent opens the stage-1 interview. (`uc_steps:3`)
   - if Mandate or script unreadable. -> Integrity-error path of UC2: report precisely, never answer from partial state. (`uc_extensions:4`)

### Resume a plan cold — actor: LLM planning agent (fresh session) (`use_cases:2` · decided)
1. Agent calls plan status before responding to the owner. (`uc_steps:4`)
   - if No plan exists in the workspace. -> Tool says so plainly; agent offers to start one (UC1). (`uc_extensions:5`)
2. Tool returns full state: stage, gate history, warnings, mandate, current script, and the readable contents of every recorded row on demand — not just counts. (`uc_steps:5`)
   - if Integrity/corruption error: some rows or tables are unreadable. -> Tool reports exactly which rows are lost and which survive; agent presents a salvage report and the owner chooses: restore from the last good version, salvage readable rows into a new plan version with the lost areas re-flagged as gaps for re-elicitation (owner re-explains what was there), or clear and restart. Never silent repair. (`uc_extensions:6`)
3. Agent fetches next gaps and continues the interview mid-stream. (`uc_steps:6`)
   - if No open gaps. -> Agent proposes running the current stage gate (UC5). (`uc_extensions:7`)

### Conduct a stage interview — actor: LLM planning agent with the product owner (`use_cases:3` · decided)
1. Agent fetches the next gap cluster. (`uc_steps:7`)
   - if Gap engine returns a stale or unresolvable gap. -> Agent can dismiss it with a recorded reason; dismissals are visible and reversible. (`uc_extensions:8`)
2. Agent converses proposal-first — defensible defaults with rationale, asking for objection; blank questions only for genuine intent-unknowns. (`uc_steps:8`)
   - if Owner's answer contradicts a stored row. -> Raise the conflict before filing (UC7). (`uc_extensions:9`)
   - if Owner defers or is unavailable. -> Question parked as an open question; the interview continues elsewhere. (`uc_extensions:10`)
3. Agent batch-submits the accepted facts as rows with provenance. (`uc_steps:9`)
   - if A row is rejected by validation. -> Fix and resubmit only the rejected rows; accepted rows stand. (`uc_extensions:11`)
4. Loop until the agent judges stage coverage complete. (`uc_steps:10`)
   - if The agent's completeness judgment is wrong. -> The stage gate's row-level holes drive the next iteration (UC5). (`uc_extensions:12`)

### Resolve an intent-assumption — actor: Product owner (adjudicates), LLM planning agent (drives) (`use_cases:4` · decided)
1. Gap engine surfaces an assumed intent row with its surrounding context. (`uc_steps:11`)
   - if The surfaced row was already resolved (stale gap). -> Dismiss with recorded reason (UC3 step-1 path). (`uc_extensions:13`)
2. Agent presents the assumption proposal-first with rationale; owner confirms, revises, or rejects. (`uc_steps:12`)
   - if Owner rejects the assumption. -> Row is revised or retired; every dependent row is flagged via the conflict flow (UC7). (`uc_extensions:14`)
3. The row upgrades in place to decided (with the owner's answer quoted); the gap clears immediately. (`uc_steps:13`)
   - if Upgrade fails or the row is missing. -> Visible error — never a silent insert of duplicate rows. (`uc_extensions:15`)

### Run a stage gate — actor: LLM planning agent (`use_cases:5` · decided)
1. Agent runs the stage's self-review checklist and fixes what it finds. (`uc_steps:14`)
   - if A self-review finding needs owner input. -> Interview resumes (UC3) before the gate is invoked. (`uc_extensions:16`)
2. Agent invokes the mechanical gate. (`uc_steps:15`)
   - if Gate fails. -> Row-level holes returned — each naming table, row, problem, and fix; agent addresses them and reruns. (`uc_extensions:17`)
3. On pass the plan advances and the next stage's script is returned; open gaps and unresolved assumptions are listed as explicit warnings, never passed over silently. (`uc_steps:16`)
   - if Warnings are present at pass. -> Agent re-raises them at every subsequent stage open and gate until resolved or the owner explicitly suppresses them. (`uc_extensions:18`)
   - if Owner has suppressed a warning. -> It still resurfaces as a reminder at critical points: finalization, red-team entry, implementation handoff. (`uc_extensions:19`)

### Run a spike — actor: LLM planning agent (`use_cases:6` · decided)
1. Agent registers a spike linked to the world-assumption it will resolve. (`uc_steps:17`)
   - if Spike registered without a linked assumption. -> Rejected — spikes exist to resolve recorded world-assumptions. (`uc_extensions:20`)
2. Agent executes the experiment against the real dependency. (`uc_steps:18`)
   - if Dependency unreachable. -> Spike parked as blocked with the reason; the assumption stays visibly open. (`uc_extensions:21`)
   - if Result contradicts the assumption. -> Assumption resolved false; conflicts raised on every dependent row. (`uc_extensions:22`)
3. Agent records the result; the linked assumption auto-resolves. (`uc_steps:19`)
   - if Result is inconclusive. -> Assumption stays open; the spike records what was learned and what remains unknown. (`uc_extensions:23`)

### Raise and resolve a conflict — actor: LLM planning agent (detects), product owner (adjudicates) (`use_cases:7` · decided)
1. Agent raises the conflict before filing the offending row, presenting both sides with its engineering recommendation. (`uc_steps:20`)
   - if Conflict is between two already-stored rows (found by a gate or red-team), not new input. -> Same flow, entered from the detecting mechanism. (`uc_extensions:24`)
2. Owner adjudicates. (`uc_steps:21`)
   - if Owner defers. -> Conflict stays open and visibly blocks gates that depend on the contested rows. (`uc_extensions:25`)
3. Outcome recorded (overridden or revised) with the challenge attached to the decision; the losing row is updated. (`uc_steps:22`)
   - if Owner overrides the engineering recommendation. -> Allowed — the user always wins — but the override stays permanently visible on the record. (`uc_extensions:26`)

### Red-team the plan — actor: Adversarial LLM agent (fresh context) (`use_cases:8` · decided)
1. Red-team session starts cold and rehydrates the full plan, including row contents (depends on UC2's full-state read). (`uc_steps:23`)
   - if Rehydration is incomplete (row contents unreadable). -> Red-team refuses to certify and files a finding about the unreadable state. (`uc_extensions:27`)
2. It attacks rows: missing failure modes, unspiked assumptions, contradictions, untestable requirements. (`uc_steps:24`)
   - if Attack surface too large for one session. -> Findings are checkpointed; multiple red-team sessions resume losslessly. (`uc_extensions:28`)
3. Findings are filed against specific rows. (`uc_steps:25`)
   - if A finding is disputed. -> Conflict flow (UC7), with the owner adjudicating. (`uc_extensions:29`)
4. The verification gate requires every finding addressed or explicitly accepted. (`uc_steps:26`)
   - if Owner accepts a finding without fixing it. -> Recorded as an accepted risk, visible at implementation handoff. (`uc_extensions:30`)

### Drive implementation via scoped sub-task briefs — actor: LLM code engine (tool orchestrates) (`use_cases:9` · decided)
1. Owner finalizes the plan (all gates passed); the tool derives an implementation task graph from components, contracts, and dependencies, ordered so nothing is built before what it depends on. (`uc_steps:27`)
   - if Engine requests work from an unfinished plan. -> Refused, or served only with an explicit draft watermark and owner consent. (`uc_extensions:31`)
   - if The graph contains a dependency cycle. -> Surfaced to the owner as a design conflict before implementation starts. (`uc_extensions:32`)
2. Engine requests its next sub-task; the tool composes a scoped brief: the sub-task's goal plus the maximum relevant slice — the contracts it implements, entities it touches, requirements binding it, decisions constraining it — and nothing else. Never the whole plan in one prompt. (`uc_steps:28`)
   - if The relevant slice exceeds the engine's context budget. -> Tool splits the sub-task, or ranks slice content by relevance and cuts visibly — the brief states what was omitted and why. (`uc_extensions:33`)
   - if All remaining sub-tasks are blocked by unfinished dependencies. -> Tool reports the blockage rather than serving unbuildable work. (`uc_extensions:34`)
3. Engine implements the sub-task and reports back; the tool records completion and updates the graph. (`uc_steps:29`)
   - if Engine discovers a plan defect while building. -> Conflict/change request filed against the plan; affected briefs are regenerated before dependent sub-tasks are served. (`uc_extensions:35`)
   - if Delivered work deviates from its contract. -> Verification against the contract catches it; the deviation is filed, never silently absorbed. (`uc_extensions:36`)
4. Repeat until the graph is complete; progress is durable and resumable cold across sessions. (`uc_steps:30`)
   - if Implementation stalls mid-graph across sessions. -> Status shows exactly what is built, in-flight, and blocked, so any fresh session resumes precisely. (`uc_extensions:37`)

### Validate a technical approach — actor: LLM planning agent (owner/domain expert adjudicates scientific claims) (`use_cases:10` · decided)
1. A load-bearing technical claim is identified: software feasibility ('can this be coded / does the dependency do X') or scientific appropriateness ('is this theory or method right for this application'). (`uc_steps:31`)
   - if The claim surfaces late, during implementation. -> Same flow, entered from UC9's plan-defect path. (`uc_extensions:38`)
2. Agent classifies the claim: software claims get an executable spike (UC6); scientific claims get research plus adjudication by the owner or a domain expert. (`uc_steps:32`)
   - if The claim is both — a method that must be scientifically right and implementable. -> Both tracks run and are linked; neither alone closes the claim. (`uc_extensions:39`)
3. The validation result is recorded and linked to every decision that rests on it; a failed validation raises conflicts on all dependent rows. (`uc_steps:33`)
   - if The claim cannot be validated cheaply. -> Recorded as an explicit risk requiring owner sign-off, visible at handoff. (`uc_extensions:40`)

### Revise a finalized plan — actor: Product owner (initiates and adjudicates), LLM planning agent (drives analysis) (`use_cases:11` · decided)
1. Owner requests a change to a finalized plan: a new feature, a reversed decision, or a newly discovered constraint. (`uc_steps:34`)
   - if The change is requested mid-implementation with sub-tasks in flight. -> In-flight sub-tasks are flagged and affected briefs frozen until the impact analysis completes. (`uc_extensions:41`)
2. System bumps the plan version and runs a link-graph impact analysis, enumerating every row, brief, and built sub-task transitively affected by the change. (`uc_steps:35`)
   - if The analysis touches an accepted risk or a suppressed warning. -> That item is resurfaced for re-adjudication — revision is a critical point per the warning policy. (`uc_extensions:42`)
   - if The change turns out to be an isolated addition touching nothing. -> Fast path — but the version bump and analysis record are kept all the same. (`uc_extensions:43`)
3. Agent walks the owner through the repercussions one by one, offering advice, options with costs, validation testing or spike needs, and a recommended path. (`uc_steps:36`)
   - if The repercussion set is too large for one session. -> The walkthrough is checkpointed step by step and resumes losslessly (UC13). (`uc_extensions:44`)
4. Owner adjudicates each repercussion; accepted changes update rows with provenance, affected gates re-run, affected briefs regenerate, and built work needing rework is flagged. (`uc_steps:37`)
   - if Owner abandons the change midway through the walkthrough. -> The plan rolls back cleanly to its pre-change version; the analysis is preserved as a record of the considered-and-abandoned change. (`uc_extensions:45`)

### Checkpoint work so an abrupt session end loses nothing — actor: LLM agent (any role); the owner is the beneficiary (`use_cases:12` · decided)
1. During any work — planning, revision, or implementation orchestration — the system durably records each unit of work the moment it completes: row submissions, decisions, briefs served, sub-task status changes, and informal learnings. (`uc_steps:38`)
   - if The unit is an informal insight or lesson, not a formal plan row. -> Recorded as a timestamped work-journal note linked to the task it arose from. (`uc_extensions:46`)
2. The session ends abruptly at an arbitrary instant: token exhaustion, crash, machine sleep or shutdown. (`uc_steps:39`)
   - if Death lands mid-write. -> Atomic writes guarantee no partial state; the last completed unit is the resume point. (`uc_extensions:47`)
3. The next session — possibly the next morning, machine off overnight — resumes from status at the exact progress point: completed steps, accumulated learnings, and the next intended action. (`uc_steps:40`)
   - if The agent never recorded a next-intended-action before dying. -> Status still shows the last completed unit; the resume session re-derives the next action from open gaps. (`uc_extensions:48`)
   - if Days pass and the project changes under the plan (repo drift). -> Resume includes a staleness check that flags drift between plan assumptions and current workspace state. (`uc_extensions:49`)

## Stage 3 — Requirements

- The system shall persist every submitted row with its provenance (decided, derived, or assumed with assumption kind). (`requirements:5` · decided · links: use_cases:3)
- The system shall apply every write atomically, so a failed write leaves no partial state. (`requirements:6` · decided · links: use_cases:1, use_cases:2)
- The system shall expose the full readable contents of every stored row to any session on demand. (`requirements:7` · decided · links: use_cases:2, use_cases:8, decisions:28, decisions:35)
- WHEN the owner instructs the agent to begin planning the project, the system shall initialize a plan in the current project workspace, recording plan name and tier; the workspace itself is never created or managed by the system. (`requirements:8` · decided · links: use_cases:1, decisions:30)
- IF plan initialization is requested in a workspace that already contains a plan, THEN the system shall refuse to overwrite and offer resume; a fresh start requires explicit owner confirmation and archives the existing plan as a version. (`requirements:9` · decided · links: use_cases:1)
- WHEN a session opens in a workspace containing a plan, the system shall return the full plan state: current stage, gate history, outstanding warnings, the engineer's mandate, the current stage script, and row contents on demand. (`requirements:10` · decided · links: use_cases:2)
- IF stored plan state fails an integrity check, THEN the system shall report exactly which rows are unreadable and which survive, and offer restore-from-last-good-version, salvage-into-a-new-version with lost areas re-flagged as gaps for re-elicitation, or clear-and-restart; never repair silently. (`requirements:11` · decided · links: use_cases:2)
- WHILE the current stage has no open gaps, the system shall recommend running the stage gate. (`requirements:12` · decided · links: use_cases:2, use_cases:5)
- WHEN the agent requests open gaps, the system shall return a prioritized cluster of related gaps, each with surrounding row context. (`requirements:13` · decided · links: use_cases:3)
- WHEN a submitted row fails validation, the system shall reject only that row and return a per-row verdict naming the specific problem. (`requirements:14` · decided · links: use_cases:3)
- WHEN the agent dismisses a gap, the system shall record the dismissal reason, stop surfacing the gap, and keep the dismissal reversible. (`requirements:15` · decided · links: use_cases:3, decisions:28)
- WHEN an elicit-mode stage opens, the system shall present divergence prompts — context-free questions and negative-space probes — and solicit owner-generated candidates before agent-authored drafts are presented. (`requirements:16` · derived · links: use_cases:3, decisions:36)
- WHEN an elicit-stage gate is invoked, the system shall run mechanical coverage cross-checks — every recorded actor participates in at least one use case and every goal traces to at least one use case — and report misses as row-level holes. (`requirements:17` · derived · links: use_cases:3, use_cases:5, decisions:36)
- WHEN the owner resolves an intent-assumption, the system shall upgrade the original row in place to decided with the owner's answer quoted, and clear the associated gap immediately. (`requirements:18` · decided · links: use_cases:4, decisions:28)
- IF an assumption upgrade cannot be applied, THEN the system shall return a visible error and create no duplicate rows. (`requirements:19` · decided · links: use_cases:4, decisions:28)
- WHEN a stage gate is invoked, the system shall evaluate only mechanical criteria and return pass or fail with row-level holes, each naming table, row, problem, and fix. (`requirements:20` · decided · links: use_cases:5)
- WHEN a gate passes while open gaps or unresolved assumptions exist, the system shall list each as an explicit warning in the gate result. (`requirements:21` · decided · links: use_cases:5, decisions:31)
- WHILE unresolved warnings exist, the system shall re-present them at every stage open and every gate invocation until resolved or explicitly suppressed by the owner. (`requirements:22` · decided · links: use_cases:5, decisions:31)
- WHILE a warning has been suppressed by the owner, the system shall still re-present it at the critical points: finalization, red-team entry, and implementation handoff. (`requirements:23` · decided · links: use_cases:5, decisions:31)
- WHEN a spike registration is submitted, the system shall require a link to an existing world-assumption and reject registration without one. (`requirements:24` · decided · links: use_cases:6)
- WHEN a spike result is recorded, the system shall resolve the linked assumption according to the outcome: confirmed or refuted closes it; inconclusive keeps it open with the findings attached. (`requirements:25` · decided · links: use_cases:6)
- IF a spike's target dependency is unreachable, THEN the system shall park the spike as blocked with the reason and keep the linked assumption visibly open. (`requirements:26` · decided · links: use_cases:6)
- WHEN new input contradicts a stored row, the system shall require a conflict to be raised and presented before the contradicting row can be filed. (`requirements:27` · decided · links: use_cases:7)
- WHILE a conflict is open, the system shall block gates that depend on the contested rows and display the blockage reason. (`requirements:28` · decided · links: use_cases:7)
- WHEN a conflict is resolved, the system shall record the outcome (overridden or revised) and the challenge text permanently on the decision. (`requirements:29` · decided · links: use_cases:7)
- WHEN a red-team session requests the plan, the system shall serve the complete plan contents; if any row is unreadable, refuse certification and file a finding about the unreadable state. (`requirements:30` · decided · links: use_cases:8, decisions:28)
- WHEN a finding is filed, the system shall link it to the specific row or rows it attacks. (`requirements:31` · decided · links: use_cases:8)
- WHILE any finding is neither addressed nor explicitly accepted by the owner, the system shall fail the verification gate. (`requirements:32` · decided · links: use_cases:8)
- WHEN the owner accepts a finding without a fix, the system shall record it as an accepted risk that remains visible at implementation handoff. (`requirements:33` · decided · links: use_cases:8)
- WHEN the owner finalizes the plan, the system shall derive an implementation task graph from components, contracts, and dependencies, ordered so no sub-task precedes its dependencies. (`requirements:34` · decided · links: use_cases:9, decisions:32)
- IF the derived task graph contains a dependency cycle, THEN the system shall surface it to the owner as a design conflict before implementation starts. (`requirements:35` · decided · links: use_cases:9)
- WHEN the code engine requests its next sub-task, the system shall compose a scoped brief: the sub-task goal plus candidate rows drawn from the plan's link graph (every row reachable from the sub-task's contracts and components via the defined traversal), from which the composing LLM selects task-specifically, recording every candidate row it omits — never the whole plan in one prompt. (`requirements:36` · derived · links: use_cases:9, decisions:32, decisions:34)
- IF a composed brief proves too large for the engine to work from effectively, THEN the system shall split the sub-task into smaller sub-tasks with their own scoped briefs; silent trimming of relevant content is not a remedy. (`requirements:37` · derived · links: use_cases:9, decisions:34)
- WHEN the engine reports a plan defect discovered during implementation, the system shall file it as a conflict or change request against the plan and regenerate affected briefs before dependent sub-tasks are served. (`requirements:38` · decided · links: use_cases:9)
- WHEN the engine reports sub-task completion, the system shall record it and update the task graph durably so any fresh session resumes with the exact build state. (`requirements:39` · decided · links: use_cases:9)
- IF implementation work is requested from a non-finalized plan, THEN the system shall refuse, or serve only with an explicit draft watermark and owner consent. (`requirements:40` · decided · links: use_cases:9)
- WHEN a load-bearing technical claim is recorded, the system shall classify it as software feasibility, scientific appropriateness, or both, and route it: software claims to an executable spike, scientific claims to research plus owner or domain-expert adjudication. (`requirements:41` · decided · links: use_cases:10, decisions:33)
- IF a technical claim cannot be validated at acceptable cost, THEN the system shall record it as an explicit risk requiring owner sign-off, visible at handoff. (`requirements:42` · decided · links: use_cases:10)
- WHEN a technical validation fails, the system shall raise conflicts on every row that depends on the failed claim. (`requirements:43` · decided · links: use_cases:10)
- The system shall account for every brief candidate row: each row in a sub-task's link-graph closure is either included in the brief or recorded as omitted. (`requirements:44` · derived · links: use_cases:9, decisions:34)
  - Planguage — scale: fraction of link-graph candidate rows accounted for (included or recorded-omitted) per composed brief; meter: automated brief audit comparing brief contents against the sub-task's link-graph closure; target: 100%
- The system shall make all stored rows readable to any session. (`requirements:45` · decided · links: use_cases:2, decisions:35)
  - Planguage — scale: fraction of stored rows readable by a fresh session; meter: automated resume audit comparing rows served against database row count; target: 100%
- The system shall produce deterministic gate results. (`requirements:46` · decided · links: use_cases:5)
  - Planguage — scale: consistency of gate results across repeated invocations on identical database state; meter: repeated-invocation test on a frozen database; target: 100% identical results
- The system shall guarantee crash-safe writes. (`requirements:47` · decided · links: use_cases:1, use_cases:2)
  - Planguage — scale: count of partially written rows present after a crash during a batched write; meter: crash-injection test during batched writes; target: 0
- The system shall store every entry with a unique identifier and creation timestamp. (`requirements:48` · decided · links: use_cases:2, use_cases:12, decisions:39)
- The system shall keep all plan state in files inside the project workspace, committable to git; no state outside the workspace. (`requirements:49` · decided · links: use_cases:1, decisions:39, decisions:40)
- WHEN the owner requests a change to a finalized plan, the system shall bump the plan version and run a link-graph impact analysis enumerating every row, brief, and built sub-task transitively affected. (`requirements:50` · decided · links: use_cases:11, decisions:37)
- WHEN the impact analysis completes, the system shall walk the owner through the repercussions, offering advice, options with costs, validation testing or spike needs, and a recommended path. (`requirements:51` · decided · links: use_cases:11, decisions:37)
- WHEN the owner adjudicates a repercussion, the system shall update the affected rows with provenance, re-run affected gates, regenerate affected briefs, and flag built work that needs rework. (`requirements:52` · decided · links: use_cases:11)
- IF a plan revision is requested while sub-tasks are in flight, THEN the system shall flag the in-flight sub-tasks and freeze affected briefs until the impact analysis completes. (`requirements:54` · decided · links: use_cases:11, use_cases:9)
- WHILE a plan revision touches an accepted risk or suppressed warning, the system shall resurface that item for re-adjudication before the revision proceeds. (`requirements:55` · derived · links: use_cases:11, decisions:31)
- WHEN a unit of work completes (row submission, decision, brief served, sub-task status change, or informal learning), the system shall record it durably at that moment — never batched to session end. (`requirements:56` · decided · links: use_cases:12, decisions:41)
- WHEN an informal learning or insight arises that is not a formal plan row, the system shall record it as a timestamped work-journal note linked to the task it arose from. (`requirements:57` · decided · links: use_cases:12, decisions:41)
- WHEN a session opens after an abrupt session end, the system shall present the exact progress point: completed steps, accumulated learnings, and the next intended action (or, absent one, the last completed unit plus open gaps). (`requirements:58` · decided · links: use_cases:12, use_cases:2, decisions:41)
- IF the workspace has drifted since the last session (repo changes under the plan), THEN the system shall flag the drift between plan assumptions and current workspace state during resume. (`requirements:59` · derived · links: use_cases:12, use_cases:2)
- The system shall lose zero completed work units on abrupt session death. (`requirements:60` · decided · links: use_cases:12, decisions:41)
  - Planguage — scale: count of completed work units (rows, journal notes, status changes) missing after an abrupt session kill; meter: kill-injection test: terminate the session at random instants during work, then audit the store against the completed-unit log; target: 0
- WHEN a record is superseded, the system shall stamp the superseded record once with a superseded_by pointer to its replacement and a timestamp, and set the supersedes pointer on the replacement at creation; record content is never edited, and liveness for any reader is the single check that superseded_by is null and the record is not retired. (`requirements:61` · decided · links: decisions:42, use_cases:9, use_cases:11, use_cases:2)
- The system shall serve cold-session rehydration as a compact digest plus targeted row reads, so resume cost scales with the current working set rather than total plan size; a full-plan dump is never the default rehydration path. (`requirements:62` · derived · links: decisions:49, decisions:28, use_cases:2, requirements:7)
  - Planguage — scale: bytes served during a standard cold resume (status digest plus working-set reads) as a fraction of total stored plan bytes, measured on a reference plan at least 10x larger than its current working set; meter: resume audit on a synthetic large plan: execute the standard resume sequence cold and compare bytes served against total database size; target: <=10% of total plan bytes, with zero previously-answered questions re-asked
- WHEN a plan file with an older schema version is opened, the system shall snapshot a PlanVersion before any migration, migrate forward, and report exactly what changed; silent migration is forbidden. (`requirements:65` · derived · links: decisions:45, requirements:11)
- The system shall log every tool call and every failure to an append-only workspace log with the failure mode labeled (unavailable, slow, malformed, auth, or partial), timestamps, and a result summary. (`requirements:66` · derived · links: decisions:46, decisions:56, decisions:40)
- WHILE another session holds the writer lock, the system shall reject writes from other sessions with a visible error naming the holder and lease age, while leaving read access unrestricted via a path that never holds the lock file open (SMB sharing-violation hardening, decisions:58); a lock silent for 10 or more minutes shall be claimable by a new session. (`requirements:67` · derived · links: decisions:44, decisions:35, decisions:58, findings:8)
- WHEN a session's writer-lock lease lapses without renewal and another session claims the lock, the system shall invalidate the original lease atomically so that every subsequent write attempted under it is rejected inside the same transaction that would apply it — no two sessions ever have writes applied under simultaneously valid leases; lease renewal piggybacks on every tool call the holder makes (the surface is a passive callee, dep_failure_modes:12, and shall not require a background heartbeat process). (`requirements:68` · derived · links: decisions:44, decisions:58, dep_failure_modes:12, findings:2, findings:8)
- WHEN a session starts or resumes against a workspace on a network-mounted filesystem, the system shall warn that machine-crash durability is untested on network mounts (spike 1: synchronous=FULL absorbed by client/NAS caching, commit p50 ~0 ms) and that the hardened SMB lock protocol is in effect. (`requirements:69` · derived · links: decisions:58, spikes:1, findings:8)
- IF a checkpoint-class write (work-unit completion, learnings, next-intended-action) is rejected because another session holds the writer lock, THEN the system shall park the write durably in a session-local spill journal outside the locked store and reconcile it into the plan automatically on the session's next successful lock acquisition, preserving original timestamps and order, so the zero-loss checkpoint guarantee (requirements:60) holds under multi-session contention. (`requirements:70` · derived · links: requirements:56, requirements:60, requirements:67, decisions:41, findings:12)
- The system shall ship the planning methodology — stage list, per-stage interview scripts, the engineer's mandate, per-stage mechanical gate criteria, and gap-derivation rules — as versioned content assets carrying a content-revision stamp, and provide an update path that migrates a plan from one methodology revision to the next. (`requirements:71` · decided · links: decisions:61, components:4, components:5, components:6, findings:4)
- IF the owner abandons a plan revision midway, THEN the system shall discard all staged-but-unapplied changes so the plan remains untouched at its pre-change version, while preserving the revision's analysis record — which is stored outside the plan-row snapshot — as a durable record of the abandoned change. (`requirements:72` · decided · links: use_cases:11, findings:5)
- WHEN the plan is finalized or a brief is issued, the system shall capture a minimal workspace fingerprint — workspace path, storage backend and journal mode, methodology content-revision, plan version, and declared toolchain versions — and store it with the frozen plan version or issued brief as the baseline that resume-time drift detection compares the current workspace against. (`requirements:73` · decided · links: requirements:59, uc_extensions:49, findings:10)
- The system shall run on Windows, macOS, and Linux with no OS-specific dependencies or behavior. (`requirements:74` · decided · links: findings:13)
- The system shall interoperate with any MCP-compliant LLM CLI engine without depending on direct LLM API access or API keys. (`requirements:75` · decided · links: findings:13)
- The system shall confine planning-stage spike/proof-of-concept code to a quarantined area that is never included in the final project deliverable. (`requirements:76` · decided · links: findings:13)
- WHEN the user proposes a capability with no established engineering solution, the system shall flag it as research-level immediately and block planning of anything dependent on it until it is resolved by a spike or fenced as a defined research sub-project with explicit go/no-go criteria. (`requirements:77` · decided · links: findings:13)
- The system shall key each computed gap's dismissed/resolved overlay by a stable identity of gap-type plus the lineage root of the target row (the earliest ancestor in the row's supersession chain), so that a dismissal survives gap re-derivation and row supersession without re-surfacing and without silently detaching. (`requirements:78` · decided · links: entities:3, contracts:66, contracts:67, decisions:28, findings:16)
- The system shall require every row of a sub-task's candidate closure to be either cited in the composed brief or explicitly waived with a recorded reason, carry the waiver log as part of the immutable brief, and surface all waivers of decision, requirement, and failure-mode rows to the owner in the finalization and brief-review summaries, so omission is always a visible recorded act and never a silent deprioritization. (`requirements:79` · decided · links: contracts:68, requirements:44, findings:18)
- WHEN the engine reports a sub-task done, the system shall record the done transition only after a passing verification verdict confirms the delivered evidence against every contract in the sub-task's scope. (`requirements:80` · derived · links: dep_failure_modes:10, uc_extensions:36, findings:9)

## Stage 4 — Domain model

### Plan (`entities:1` · decided) — has lifecycle
The root aggregate: one plan per project workspace, carrying stage, version, and lifecycle state.

| op | responsible | ref |
|---|---|---|
| C | LLM planning agent via tool API, on owner instruction | `crud_grid:1` |
| R | Any agent session via tool API | `crud_grid:2` |
| U | System: stage advances, lifecycle transitions, version bumps | `crud_grid:3` |
| D | Product owner, by deleting the project directory outside the tool (children: everything — all plan state lives in the workspace and dies with it (decisions:40)) | `crud_grid:4` |

State machine (`state_machines:1`) — states: draft, finalized, implementing, revising, complete; events: finalize, start_implementation, request_revision, apply_revision, abandon_revision, complete_implementation

| state | event | -> | ref |
|---|---|---|---|
| draft | finalize | finalized | `sm_cells:1` |
| draft | start_implementation | impossible — only finalized plans are implemented | `sm_cells:2` |
| draft | request_revision | impossible — draft plans are edited directly through the normal interview, not revised | `sm_cells:3` |
| draft | apply_revision | impossible — no revision can be open on a draft | `sm_cells:4` |
| draft | abandon_revision | impossible — no revision can be open on a draft | `sm_cells:5` |
| draft | complete_implementation | impossible — nothing is implementing | `sm_cells:6` |
| finalized | finalize | impossible — already finalized | `sm_cells:7` |
| finalized | start_implementation | implementing | `sm_cells:8` |
| finalized | request_revision | revising | `sm_cells:9` |
| finalized | apply_revision | impossible — no revision open | `sm_cells:10` |
| finalized | abandon_revision | impossible — no revision open | `sm_cells:11` |
| finalized | complete_implementation | impossible — implementation has not started | `sm_cells:12` |
| implementing | finalize | impossible — already finalized | `sm_cells:13` |
| implementing | start_implementation | impossible — already implementing | `sm_cells:14` |
| implementing | request_revision | revising | `sm_cells:15` |
| implementing | apply_revision | impossible — no revision open | `sm_cells:16` |
| implementing | abandon_revision | impossible — no revision open | `sm_cells:17` |
| implementing | complete_implementation | complete | `sm_cells:18` |
| revising | finalize | impossible — the open revision must be applied or abandoned first | `sm_cells:19` |
| revising | request_revision | impossible — one revision at a time | `sm_cells:21` |
| revising | apply_revision | finalized | `sm_cells:22` |
| revising | abandon_revision | finalized | `sm_cells:23` |
| complete | finalize | impossible — already finalized and complete | `sm_cells:25` |
| complete | start_implementation | impossible — already complete; a revision reopens work | `sm_cells:26` |
| complete | request_revision | revising | `sm_cells:27` |
| complete | apply_revision | impossible — no revision open | `sm_cells:28` |
| complete | abandon_revision | impossible — no revision open | `sm_cells:29` |
| complete | complete_implementation | impossible — already complete | `sm_cells:30` |
| revising | start_implementation | revising | `sm_cells:186` |
| revising | complete_implementation | revising | `sm_cells:187` |

### PlanRow (`entities:2` · decided) — has lifecycle
Any content row of the plan (use case, step, extension, requirement, entity, decision, question): shared identity, provenance, timestamps, and a shared confirmation/supersession lifecycle.

| op | responsible | ref |
|---|---|---|
| C | LLM agent via batched submissions with provenance | `crud_grid:5` |
| R | Any agent session; full readability per NFR | `crud_grid:6` |
| U | LLM agent: confirm/revise/supersede/retire with provenance | `crud_grid:7` |
| D | n/a — No hard delete: rows retire or supersede; the only true delete is directory deletion | `crud_grid:8` |

State machine (`state_machines:2`) — states: assumed, active, superseded, retired; events: confirm, revise, supersede, retire

| state | event | -> | ref |
|---|---|---|---|
| assumed | confirm | active | `sm_cells:31` |
| assumed | revise | active | `sm_cells:32` |
| assumed | supersede | superseded | `sm_cells:33` |
| assumed | retire | retired | `sm_cells:34` |
| active | confirm | impossible — already confirmed | `sm_cells:35` |
| active | revise | active | `sm_cells:36` |
| active | supersede | superseded | `sm_cells:37` |
| active | retire | retired | `sm_cells:38` |
| superseded | confirm | impossible — superseded rows are frozen history | `sm_cells:39` |
| superseded | revise | impossible — superseded rows are frozen history | `sm_cells:40` |
| superseded | supersede | impossible — superseded rows are frozen history | `sm_cells:41` |
| superseded | retire | impossible — superseded rows are frozen history | `sm_cells:42` |
| retired | confirm | impossible — retired rows are frozen history | `sm_cells:43` |
| retired | revise | impossible — retired rows are frozen history | `sm_cells:44` |
| retired | supersede | impossible — retired rows are frozen history | `sm_cells:45` |
| retired | retire | impossible — retired rows are frozen history | `sm_cells:46` |

### Gap (`entities:3` · decided) — has lifecycle
A detected deficiency the interview must address; computed by the gap engine but carrying a stored open/dismissed/resolved overlay.

| op | responsible | ref |
|---|---|---|
| C | System: gap engine derives gaps from plan state | `crud_grid:9` |
| R | Any agent session | `crud_grid:10` |
| U | LLM agent (dismiss/reopen with reason) and system (resolve on underlying fix) | `crud_grid:11` |
| D | n/a — Gaps resolve or stay dismissed; history is retained | `crud_grid:12` |

State machine (`state_machines:3`) — states: open, dismissed, resolved; events: resolve, dismiss, reopen

| state | event | -> | ref |
|---|---|---|---|
| open | resolve | resolved | `sm_cells:47` |
| open | dismiss | dismissed | `sm_cells:48` |
| open | reopen | impossible — already open | `sm_cells:49` |
| dismissed | resolve | resolved | `sm_cells:50` |
| dismissed | dismiss | impossible — already dismissed | `sm_cells:51` |
| dismissed | reopen | open | `sm_cells:52` |
| resolved | resolve | impossible — terminal; a recurring deficiency is a new gap | `sm_cells:53` |
| resolved | dismiss | impossible — terminal; a recurring deficiency is a new gap | `sm_cells:54` |
| resolved | reopen | impossible — terminal; a recurring deficiency is a new gap | `sm_cells:55` |

### Conflict (`entities:4` · decided) — has lifecycle
A recorded contradiction between rows or between new input and a stored row; blocks dependent gates while open.

| op | responsible | ref |
|---|---|---|
| C | LLM agent (raising) or system (engine-detected contradictions) | `crud_grid:13` |
| R | Any agent session | `crud_grid:14` |
| U | LLM agent recording the owner's adjudication | `crud_grid:15` |
| D | n/a — Resolved conflicts are permanent audit records | `crud_grid:16` |

State machine (`state_machines:4`) — states: open, resolved_overridden, resolved_revised; events: resolve_override, resolve_revise

| state | event | -> | ref |
|---|---|---|---|
| open | resolve_override | resolved_overridden | `sm_cells:56` |
| open | resolve_revise | resolved_revised | `sm_cells:57` |
| resolved_overridden | resolve_override | impossible — terminal record; re-contesting is a new conflict | `sm_cells:58` |
| resolved_overridden | resolve_revise | impossible — terminal record; re-contesting is a new conflict | `sm_cells:59` |
| resolved_revised | resolve_override | impossible — terminal record; re-contesting is a new conflict | `sm_cells:60` |
| resolved_revised | resolve_revise | impossible — terminal record; re-contesting is a new conflict | `sm_cells:61` |

### Spike (`entities:5` · decided) — has lifecycle
An executable experiment against a real dependency, linked to the world-assumption it resolves.

| op | responsible | ref |
|---|---|---|
| C | LLM agent, linked to a world-assumption | `crud_grid:17` |
| R | Any agent session | `crud_grid:18` |
| U | LLM agent: start/block/unblock/conclude with results | `crud_grid:19` |
| D | n/a — Concluded spikes are evidence records | `crud_grid:20` |

State machine (`state_machines:5`) — states: registered, executing, blocked, concluded; events: start, block, unblock, conclude

| state | event | -> | ref |
|---|---|---|---|
| registered | start | executing | `sm_cells:62` |
| registered | block | blocked | `sm_cells:63` |
| registered | unblock | impossible — not blocked | `sm_cells:64` |
| registered | conclude | impossible — no result without execution | `sm_cells:65` |
| executing | start | impossible — already executing | `sm_cells:66` |
| executing | block | blocked | `sm_cells:67` |
| executing | unblock | impossible — not blocked | `sm_cells:68` |
| executing | conclude | concluded | `sm_cells:69` |
| blocked | start | impossible — unblock first | `sm_cells:70` |
| blocked | block | impossible — already blocked | `sm_cells:71` |
| blocked | unblock | executing | `sm_cells:72` |
| blocked | conclude | concluded | `sm_cells:73` |
| concluded | start | impossible — terminal; outcome recorded on the row | `sm_cells:74` |
| concluded | block | impossible — terminal; outcome recorded on the row | `sm_cells:75` |
| concluded | unblock | impossible — terminal; outcome recorded on the row | `sm_cells:76` |
| concluded | conclude | impossible — terminal; outcome recorded on the row | `sm_cells:77` |

### Warning (`entities:6` · decided) — has lifecycle
A non-blocking issue surfaced at a gate (open gap, unresolved assumption) governed by the keep-pushing policy: re-presented until resolved or suppressed, and resurfaced at critical points even when suppressed.

| op | responsible | ref |
|---|---|---|
| C | System: gate evaluation raises warnings | `crud_grid:21` |
| R | Any agent session | `crud_grid:22` |
| U | System (resurfacing at critical points) and LLM agent recording owner suppression/resolution | `crud_grid:23` |
| D | n/a — Resolved warnings are retained as audit trail | `crud_grid:24` |

State machine (`state_machines:6`) — states: active, suppressed, resolved; events: suppress, unsuppress, resolve, resurface

| state | event | -> | ref |
|---|---|---|---|
| active | suppress | suppressed | `sm_cells:78` |
| active | unsuppress | impossible — not suppressed | `sm_cells:79` |
| active | resolve | resolved | `sm_cells:80` |
| active | resurface | active | `sm_cells:81` |
| suppressed | suppress | impossible — already suppressed | `sm_cells:82` |
| suppressed | unsuppress | active | `sm_cells:83` |
| suppressed | resolve | resolved | `sm_cells:84` |
| suppressed | resurface | suppressed | `sm_cells:85` |
| resolved | suppress | impossible — terminal | `sm_cells:86` |
| resolved | unsuppress | impossible — terminal | `sm_cells:87` |
| resolved | resolve | impossible — terminal | `sm_cells:88` |
| resolved | resurface | impossible — terminal | `sm_cells:89` |

### Finding (`entities:7` · decided) — has lifecycle
A red-team result filed against specific rows; must end addressed or as a visible accepted risk.

| op | responsible | ref |
|---|---|---|
| C | Red-team agent session | `crud_grid:25` |
| R | Any agent session | `crud_grid:26` |
| U | LLM agent recording dispute/address/acceptance outcomes | `crud_grid:27` |
| D | n/a — Findings are permanent verification records | `crud_grid:28` |

State machine (`state_machines:7`) — states: filed, disputed, addressed, accepted_risk; events: dispute, uphold, withdraw, address, accept_risk

| state | event | -> | ref |
|---|---|---|---|
| filed | dispute | disputed | `sm_cells:90` |
| filed | uphold | impossible — no dispute open | `sm_cells:91` |
| filed | withdraw | impossible — no dispute open | `sm_cells:92` |
| filed | address | addressed | `sm_cells:93` |
| filed | accept_risk | accepted_risk | `sm_cells:94` |
| disputed | dispute | impossible — already disputed | `sm_cells:95` |
| disputed | uphold | filed | `sm_cells:96` |
| disputed | withdraw | addressed | `sm_cells:97` |
| disputed | address | impossible — settle the dispute first | `sm_cells:98` |
| disputed | accept_risk | impossible — settle the dispute first | `sm_cells:99` |
| addressed | dispute | impossible — terminal | `sm_cells:100` |
| addressed | uphold | impossible — terminal | `sm_cells:101` |
| addressed | withdraw | impossible — terminal | `sm_cells:102` |
| addressed | address | impossible — terminal | `sm_cells:103` |
| addressed | accept_risk | impossible — terminal | `sm_cells:104` |
| accepted_risk | dispute | disputed | `sm_cells:105` |
| accepted_risk | uphold | impossible — no dispute open | `sm_cells:106` |
| accepted_risk | withdraw | impossible — no dispute open | `sm_cells:107` |
| accepted_risk | address | addressed | `sm_cells:108` |
| accepted_risk | accept_risk | impossible — already accepted | `sm_cells:109` |

### TechnicalClaim (`entities:8` · decided) — has lifecycle
A load-bearing technical assertion needing validation: software feasibility, scientific appropriateness, or both.

| op | responsible | ref |
|---|---|---|
| C | LLM agent when a load-bearing claim is identified | `crud_grid:29` |
| R | Any agent session | `crud_grid:30` |
| U | LLM agent: routing and validation outcomes | `crud_grid:31` |
| D | n/a — Claims and their outcomes are permanent | `crud_grid:32` |

State machine (`state_machines:8`) — states: identified, validating, validated, failed, risk_accepted; events: route, pass, fail, accept_risk

| state | event | -> | ref |
|---|---|---|---|
| identified | route | validating | `sm_cells:110` |
| identified | pass | impossible — not yet validating | `sm_cells:111` |
| identified | fail | impossible — not yet validating | `sm_cells:112` |
| identified | accept_risk | risk_accepted | `sm_cells:113` |
| validating | route | impossible — already routed | `sm_cells:114` |
| validating | pass | validated | `sm_cells:115` |
| validating | fail | failed | `sm_cells:116` |
| validating | accept_risk | risk_accepted | `sm_cells:117` |
| validated | route | impossible — terminal; a revision re-opens as a new claim | `sm_cells:118` |
| validated | pass | impossible — terminal; a revision re-opens as a new claim | `sm_cells:119` |
| validated | fail | impossible — terminal; a revision re-opens as a new claim | `sm_cells:120` |
| validated | accept_risk | impossible — terminal; a revision re-opens as a new claim | `sm_cells:121` |
| failed | route | impossible — terminal; conflicts raised on dependents | `sm_cells:122` |
| failed | pass | impossible — terminal; conflicts raised on dependents | `sm_cells:123` |
| failed | fail | impossible — terminal; conflicts raised on dependents | `sm_cells:124` |
| failed | accept_risk | impossible — terminal; conflicts raised on dependents | `sm_cells:125` |
| risk_accepted | route | validating | `sm_cells:126` |
| risk_accepted | pass | impossible — not validating | `sm_cells:127` |
| risk_accepted | fail | impossible — not validating | `sm_cells:128` |
| risk_accepted | accept_risk | impossible — already accepted | `sm_cells:129` |

### SubTask (`entities:9` · decided) — has lifecycle
A node in the implementation task graph derived at finalization; the unit a brief is composed for and the code engine executes.

| op | responsible | ref |
|---|---|---|
| C | System: task-graph derivation at finalization and revision regeneration | `crud_grid:33` |
| R | Any agent session; the code engine reads its own sub-tasks | `crud_grid:34` |
| U | System (graph/readiness) and code engine status reports via tool API | `crud_grid:35` |
| D | n/a — Sub-tasks persist as build history; revision supersedes the graph rather than deleting nodes | `crud_grid:36` |

State machine (`state_machines:9`) — states: pending, ready, in_progress, blocked, done, rework_flagged; events: deps_satisfied, serve_brief, complete, block, unblock, flag_rework

| state | event | -> | ref |
|---|---|---|---|
| pending | deps_satisfied | ready | `sm_cells:130` |
| pending | serve_brief | impossible — dependencies unfinished — unbuildable work is never served | `sm_cells:131` |
| pending | complete | impossible — no work served | `sm_cells:132` |
| pending | block | blocked | `sm_cells:133` |
| pending | unblock | impossible — not blocked | `sm_cells:134` |
| pending | flag_rework | impossible — nothing built | `sm_cells:135` |
| ready | deps_satisfied | impossible — already ready | `sm_cells:136` |
| ready | serve_brief | in_progress | `sm_cells:137` |
| ready | complete | impossible — no work in progress | `sm_cells:138` |
| ready | block | blocked | `sm_cells:139` |
| ready | unblock | impossible — not blocked | `sm_cells:140` |
| ready | flag_rework | impossible — nothing built | `sm_cells:141` |
| in_progress | deps_satisfied | impossible — already past readiness | `sm_cells:142` |
| in_progress | serve_brief | in_progress | `sm_cells:143` |
| in_progress | complete | done | `sm_cells:144` |
| in_progress | block | blocked | `sm_cells:145` |
| in_progress | unblock | impossible — not blocked | `sm_cells:146` |
| in_progress | flag_rework | impossible — nothing delivered yet — mid-work defects go through block | `sm_cells:147` |
| blocked | deps_satisfied | impossible — unblock is the only exit | `sm_cells:148` |
| blocked | serve_brief | impossible — unblock first | `sm_cells:149` |
| blocked | complete | impossible — blocked work cannot complete | `sm_cells:150` |
| blocked | block | impossible — already blocked | `sm_cells:151` |
| blocked | unblock | ready | `sm_cells:152` |
| blocked | flag_rework | impossible — nothing delivered | `sm_cells:153` |
| done | deps_satisfied | impossible — already done | `sm_cells:154` |
| done | serve_brief | impossible — already done | `sm_cells:155` |
| done | complete | impossible — already done | `sm_cells:156` |
| done | block | impossible — done work is flagged for rework, not blocked | `sm_cells:157` |
| done | unblock | impossible — not blocked | `sm_cells:158` |
| done | flag_rework | rework_flagged | `sm_cells:159` |
| rework_flagged | deps_satisfied | ready | `sm_cells:160` |
| rework_flagged | serve_brief | impossible — must re-enter readiness first | `sm_cells:161` |
| rework_flagged | complete | impossible — no work served | `sm_cells:162` |
| rework_flagged | block | blocked | `sm_cells:163` |
| rework_flagged | unblock | impossible — not blocked | `sm_cells:164` |
| rework_flagged | flag_rework | impossible — already flagged | `sm_cells:165` |

### Revision (`entities:10` · decided) — has lifecycle
An owner-initiated change to a finalized plan: impact analysis, guided walkthrough, then applied or abandoned with rollback.

| op | responsible | ref |
|---|---|---|
| C | LLM agent on owner request | `crud_grid:37` |
| R | Any agent session | `crud_grid:38` |
| U | LLM agent and system through analysis, walkthrough, apply/abandon | `crud_grid:39` |
| D | n/a — Applied and abandoned revisions are permanent change records | `crud_grid:40` |

State machine (`state_machines:10`) — states: proposed, analyzing, walkthrough, applied, abandoned; events: start_analysis, present_walkthrough, apply, abandon

| state | event | -> | ref |
|---|---|---|---|
| proposed | start_analysis | analyzing | `sm_cells:166` |
| proposed | present_walkthrough | impossible — analysis must run first | `sm_cells:167` |
| proposed | apply | impossible — walkthrough is mandatory before apply | `sm_cells:168` |
| proposed | abandon | abandoned | `sm_cells:169` |
| analyzing | start_analysis | impossible — already analyzing | `sm_cells:170` |
| analyzing | present_walkthrough | walkthrough | `sm_cells:171` |
| analyzing | apply | impossible — walkthrough is mandatory before apply | `sm_cells:172` |
| analyzing | abandon | abandoned | `sm_cells:173` |
| walkthrough | start_analysis | impossible — analysis already done | `sm_cells:174` |
| walkthrough | present_walkthrough | walkthrough | `sm_cells:175` |
| walkthrough | apply | applied | `sm_cells:176` |
| walkthrough | abandon | abandoned | `sm_cells:177` |
| applied | start_analysis | impossible — terminal | `sm_cells:178` |
| applied | present_walkthrough | impossible — terminal | `sm_cells:179` |
| applied | apply | impossible — terminal | `sm_cells:180` |
| applied | abandon | impossible — terminal | `sm_cells:181` |
| abandoned | start_analysis | impossible — terminal; a new attempt is a new revision | `sm_cells:182` |
| abandoned | present_walkthrough | impossible — terminal; a new attempt is a new revision | `sm_cells:183` |
| abandoned | apply | impossible — terminal; a new attempt is a new revision | `sm_cells:184` |
| abandoned | abandon | impossible — terminal; a new attempt is a new revision | `sm_cells:185` |

### PlanVersion (`entities:11` · decided) — no lifecycle — Immutable once written: a snapshot never changes state; new circumstances create a new snapshot.
An immutable snapshot of the plan taken at archive or revision-bump moments.

| op | responsible | ref |
|---|---|---|
| C | System at archive and revision-bump moments | `crud_grid:41` |
| R | Any agent session | `crud_grid:42` |
| U | n/a — Immutable snapshot | `crud_grid:43` |
| D | n/a — Snapshots persist; only directory deletion removes them | `crud_grid:44` |

### GateResult (`entities:12` · decided) — no lifecycle — Immutable audit record; a re-run creates a new result rather than mutating history.
The immutable record of one gate invocation: pass/fail, holes, warnings, timestamp.

| op | responsible | ref |
|---|---|---|
| C | System on gate invocation | `crud_grid:45` |
| R | Any agent session | `crud_grid:46` |
| U | n/a — Immutable audit record; a re-run creates a new result | `crud_grid:47` |
| D | n/a — Permanent audit trail | `crud_grid:48` |

### Brief (`entities:13` · decided) — no lifecycle — Immutable by design so defect forensics can always answer 'what exactly did the engine see'; supersession is a property of the newer brief, not a state change on the old one.
The immutable record of one composed sub-task brief, including its candidate-row omission log; regeneration creates a new brief that supersedes by reference.

| op | responsible | ref |
|---|---|---|
| C | System brief composer, on code-engine request | `crud_grid:49` |
| R | Code engine (its own briefs) and any agent session | `crud_grid:50` |
| U | n/a — Immutable; regeneration creates a superseding brief | `crud_grid:51` |
| D | n/a — Retained for defect forensics — 'what exactly did the engine see' | `crud_grid:52` |

### JournalNote (`entities:14` · decided) — no lifecycle — Append-only: notes are historical record, never edited or transitioned.
A timestamped work-journal entry capturing an informal learning or progress marker, linked to the task it arose from.

| op | responsible | ref |
|---|---|---|
| C | LLM agent at the moment a learning or progress unit completes | `crud_grid:53` |
| R | Any agent session | `crud_grid:54` |
| U | n/a — Append-only journal | `crud_grid:55` |
| D | n/a — Append-only history | `crud_grid:56` |

### Link (`entities:15` · decided) — no lifecycle — Immutable edge owned by its source row; changes happen by superseding the owning row, never by mutating the edge.
A typed graph edge between rows: the substrate for impact analysis, brief candidacy, and provenance tracing.

| op | responsible | ref |
|---|---|---|
| C | LLM agent as part of row submission | `crud_grid:57` |
| R | Any session; powers impact analysis and brief candidacy | `crud_grid:58` |
| U | n/a — Immutable edge; supersede the owning row instead | `crud_grid:59` |
| D | n/a — Edges retire with their owning row's supersession; never deleted directly | `crud_grid:60` |

## Stage 5 — External dependencies & failure modes

### Project workspace filesystem (filesystem) (`dependencies:1` · decided)
Sole home of all plan state (decisions:40); atomic writes and integrity checks are the system's contract with it.

| failure mode | handling | ref |
|---|---|---|
| unavailable | Fail fast with a visible error; never write state anywhere outside the workspace (decisions:40); the session reports and stops rather than operating from memory. | `dep_failure_modes:1` |
| slow | Writes exceeding 5s log a network-drive warning to the owner; exceeding 30s is treated as unavailable (fail fast). Numbers are owner-adjudicated defaults, configurable. | `dep_failure_modes:2` |
| malformed | Corrupted plan files enter the UC2 integrity path: report exactly which rows are unreadable and which survive; offer restore-from-version, salvage-with-re-elicitation, or clear-and-restart; never silent repair (requirements:11). | `dep_failure_modes:3` |
| auth | Permission errors fail fast naming the path and the permission needed; the tool never self-elevates or works around ACLs. | `dep_failure_modes:4` |
| partial | Partial writes are impossible by construction (atomic writes, crash-injection NFR requirements:47); partial state found anyway (external tampering) routes to the integrity path. | `dep_failure_modes:5` |

### LLM code engine (external agent) (`dependencies:2` · decided)
The implementing LLM CLI that consumes briefs and reports sub-task status; outside the system's control once served.

| failure mode | handling | ref |
|---|---|---|
| unavailable | An engine that never picks up or reports leaves its sub-task in_progress; flagged stale after 24h of inactivity and surfaced at every resume; never auto-reassigned (single user, decisions:35). | `dep_failure_modes:6` |
| slow | Long-running sub-tasks are normal (human-in-the-loop); the same 24h inactivity staleness flag is the only timeout — no auto-kill of slow work. | `dep_failure_modes:7` |
| malformed | A status report failing validation is rejected per-row with the specific problem named; sub-task state is unchanged and the engine resubmits. | `dep_failure_modes:8` |
| auth | An engine lacking permission to read its brief or write status gets a visible error naming the required scope; no silent bypass. | `dep_failure_modes:9` |
| partial | Honest half-completion keeps the sub-task in_progress with the partial result and learnings journaled (UC13); nothing counts as done until the contract verification passes. | `dep_failure_modes:10` |

### MCP host/harness (service) (`dependencies:3` · decided)
The runtime hosting the planning agent and transporting tool calls; its death is the abrupt-session-end scenario UC13 exists for.

| failure mode | handling | ref |
|---|---|---|
| unavailable | Host death IS the abrupt-session-end scenario: UC13's zero-loss checkpointing guarantees every completed unit survives; the next session resumes losslessly per UC2. | `dep_failure_modes:11` |
| slow | No active handling: the tool is a passive, durable callee; host throttling delays work but cannot corrupt or lose it. | `dep_failure_modes:12` |
| malformed | A malformed tool call is rejected per-row with a pedagogical error naming the problem (requirements:14); nothing is filed. | `dep_failure_modes:13` |
| auth | Denied tool permissions are owner-visible; the tool documents its required permission list and never routes around a denial. | `dep_failure_modes:14` |
| partial | A batch killed mid-call leaves no partial rows: atomic batch semantics with per-row verdicts; the retried batch is deduplicated by idempotency key (decisions pending this stage). | `dep_failure_modes:15` |

### Research sources (api) (`dependencies:4` · decided)
Web/literature/documentation consulted for scientific-appropriateness validation (UC10).

| failure mode | handling | ref |
|---|---|---|
| unavailable | Scientific validation parks as blocked with the reason; the claim stays visibly open; the owner may accept it as an explicit risk (requirements:44). | `dep_failure_modes:16` |
| slow | Research findings are checkpointed as journal notes so the investigation spans sessions without loss (UC13). | `dep_failure_modes:17` |
| malformed | Contradictory or low-quality sources yield an inconclusive validation: recorded with what was found, the claim stays open. | `dep_failure_modes:18` |
| auth | Paywalled sources are noted; alternates sought; the owner may supply access; the system never bypasses access controls. | `dep_failure_modes:19` |
| partial | Partial literature coverage is recorded with explicit coverage limits; the owner adjudicates whether it suffices or the claim becomes an accepted risk. | `dep_failure_modes:20` |

## Stage 6 — Architecture

### storage-engine (`components:1` · decided)
Responsibility: Sole owner of persistence behind a backend-neutral storage interface (SQLite as the only v1 backend): atomic idempotent writes, unique IDs and timestamps, writer lock with heartbeat, integrity audit, version snapshots, and migration — no other component touches the database.
- **init_plan** (function): (name: str, tier: str) -> PlanHandle (`contracts:1` · decided · links: requirements:8, requirements:9, requirements:49, requirements:74, use_cases:1)
  - error PlanAlreadyExists: refuses to overwrite; caller offers resume; a fresh start requires explicit owner confirmation and archives the existing plan as a PlanVersion (requirements:9)
  - error StorageUnavailable: fail fast with a visible error; no state is ever written outside the workspace (dep_failure_modes:1)
  - consumed by: components:15
- **write_atomic** (function): (batch: WriteBatch, idempotency_key: str) -> BatchReceipt (a replayed idempotency_key returns the original receipt — never duplicates, decisions:43) (`contracts:2` · decided · links: requirements:6, requirements:47, requirements:48, requirements:56, requirements:60, decisions:43, dep_failure_modes:15)
  - error StorageUnavailable: fail fast; writes exceeding 30s are treated as unavailable per dep_failure_modes:2
  - error WriterLockLost: the session's lease expired or was claimed; nothing was written; re-acquire and retry
  - consumed by: components:2, components:14
- **integrity_check** (function): () -> IntegrityReport naming exactly which rows are unreadable and which survive (requirements:11) (`contracts:5` · decided · links: requirements:11, requirements:45)
  - error StorageUnavailable: the store itself cannot be opened; distinct from readable-but-corrupt
  - consumed by: components:14
- **recover** (function): (strategy: Literal['restore','salvage','restart']) -> RecoveryReport — what was restored/salvaged/cleared; salvage re-flags lost areas as gaps for re-elicitation; never silent repair (`contracts:6` · decided · links: requirements:11, uc_extensions:6)
  - error NoGoodVersion: restore requested but no readable PlanVersion snapshot exists; salvage and restart remain available
  - error StorageUnavailable: fail fast, visible error
  - consumed by: components:15
- **snapshot_version** (function): (reason: str) -> PlanVersionId of the immutable snapshot (`contracts:7` · decided · links: decisions:45, entities:11, requirements:50)
  - error StorageUnavailable: fail fast; no partial snapshot is left behind (atomic)
  - consumed by: components:13, contracts:8
- **migrate** (function): (target_schema_version: int) -> MigrationReport stating exactly what changed; a PlanVersion snapshot is taken before any migration (`contracts:8` · decided · links: requirements:65, decisions:45)
  - error MigrationFailed: the pre-migration snapshot is restored and the failure reported; silent migration is forbidden (decisions:45)
  - error StorageUnavailable: fail fast, visible error
  - consumed by: components:15
- **renew_lease** (function): (lease: Lease) -> Lease (renewed) — renewal piggybacks on every tool call the holding session makes; no background heartbeat process exists (dep_failure_modes:12); on network mounts the renewal write retries transient sharing violations (decisions:58) (`contracts:53` · decided · links: requirements:67, requirements:68, decisions:44, decisions:58, findings:2, findings:8)
  - error LeaseLost: the lease was claimed by another session after prolonged silence; enforcement sits at the write boundary — every write validates the lease inside the same transaction that applies it, so the stale holder's next write is rejected atomically ('stop immediately' = 'no further write can land')
  - error StorageUnavailable: fail fast, visible error
  - consumed by: components:15
- **release_writer_lock** (function): (lease: Lease) -> Released — the writer lock is free immediately for the next session; the lease is dead and any later write under it is rejected (`contracts:54` · decided · links: requirements:67, decisions:44, findings:1, use_cases:8)
  - error LeaseLost: the lease was already lost to another claimant — nothing is held; safe to treat as released (idempotent)
  - error StorageUnavailable: fail fast, visible error
  - consumed by: components:15
- **acquire_writer_lock** (function): (session_id: str) -> Lease — claimed via atomic O_EXCL create; on network-mounted workspaces the acquire/claim path retries transient sharing violations (decisions:58) (`contracts:63` · decided · links: requirements:67, decisions:44, decisions:58, findings:8, requirements:70)
  - error LockHeld: another live session holds the lock; error names the holder and lease age; a lock silent 10+ minutes is claimable (decisions:44)
  - error StorageUnavailable: fail fast, visible error
  - consumed by: components:15

### row-service (`components:2` · decided)
Responsibility: Owns the PlanRow lifecycle: provenance-checked batched submission with per-row verdicts, full and targeted readback, in-place assumption upgrade, supersession lineage, and retirement.
- **submit_rows** (function): (batch: list[RowSubmission] (each submission may also carry optional grounds and alternatives: why this content is right, and what was considered and rejected), idempotency_key: str) -> list[RowVerdict] — per-row accept/reject naming the specific problem; accepted rows stand (requirements:14) (`contracts:69` · decided · links: requirements:5, requirements:14, requirements:27, requirements:48, decisions:43, use_cases:3)
  - error ConflictRequired: a submitted row contradicts a stored row; nothing is filed until a conflict is raised and presented (requirements:27)
  - error StorageUnavailable: fail fast; the whole batch is atomic — no partial rows (requirements:6)
  - consumed by: components:15
- **resolve_assumption** (function): (row: RowRef, answer: OwnerAnswer (verbatim quote + resolution: confirm|revise|reject)) -> PlanRow — the SAME row upgraded in place to decided with the owner's answer quoted; the gap clears immediately (requirements:18; fixes friction decisions:28a) (`contracts:70` · decided · links: requirements:18, requirements:19, decisions:28, use_cases:4)
  - error RowNotFound: names the missing ref; nothing written
  - error NotAssumed: row is not an open assumption; no write occurs
  - error UpgradeFailed: upgrade could not be applied; visible error, never a silent duplicate row (requirements:19)
  - error RetireNeedsReason: a rejection retires the row, so it records why; a blank retire_reason is refused rather than replaced by the owner-rejected default
  - consumed by: components:15, components:9
- **supersede_row** (function): (old: RowRef, replacement: RowSubmission, reason: str (why the OLD row was abandoned — what was learned that makes its content wrong, which is a different sentence from the replacement's grounds)) -> SupersessionRecord — replacement created with supersedes pointer; old row stamped once with superseded_by + timestamp; content never edited (requirements:61) (`contracts:71` · decided · links: requirements:61, decisions:42)
  - error RowNotFound: names the missing ref
  - error AlreadySuperseded: old row already has a superseded_by pointer; lineage is write-once — supersede the live replacement instead
  - error SupersedeNeedsReason: the reason is blank; superseding is an act, and an act records why it was performed
  - consumed by: components:13, components:15
- **retire_row** (function): (row: RowRef, reason: str) -> PlanRow in retired state; liveness check for any reader stays the single check of requirements:61 (`contracts:72` · decided · links: entities:2, state_machines:2, requirements:61)
  - error RowNotFound: names the missing ref
  - error AlreadyRetired: no-op refused so the audit trail records exactly one retirement
  - error RetireNeedsReason: the reason is blank; retiring takes a row out of every live read, so a later reader finding it gone needs the sentence, not the timestamp
  - consumed by: components:15
- **read_rows** (function): (selector: RowSelector (by ids | table | stage | provenance | liveness | labels | link-neighborhood; paginated)) -> RowPage — full contents of the selected rows, each row's live labels alongside them, and the page's continuation state; targeted reads so resume cost scales with the working set, never a full-plan dump (requirements:62, decisions:49) (`contracts:74` · decided · links: requirements:7, requirements:30, requirements:45, requirements:62, decisions:49)
  - error UnreadableRows: integrity failure on requested rows; report names unreadable vs surviving rows and routes to recovery (requirements:11)
  - error InvalidSelector: selector malformed; pedagogical error names the invalid field; nothing read
  - consumed by: components:15, components:12, components:5, components:6

### link-graph (`components:3` · decided)
Responsibility: Owns the typed-edge substrate: edge creation with row submission, closure traversal, impact enumeration, and cycle detection.
- **closure** (function): (roots: list[RowRef], spec: TraversalSpec (edge types + direction + depth)) -> Closure — every row reachable from roots via the defined traversal; the brief-candidate set of requirements:36 (`contracts:14` · decided · links: requirements:36, requirements:44)
  - error DanglingRef: a root or traversed edge references a missing row; names the offending ref — signals store inconsistency, routes to integrity check
  - consumed by: components:12
- **impact** (function): (changed: list[RowRef]) -> ImpactReport enumerating every row, brief, and built sub-task transitively affected (requirements:50); a pure read — edges are never mutated (conflicts:4) (`contracts:15` · decided · links: requirements:50, conflicts:4)
  - error DanglingRef: names the offending ref; routes to integrity check
  - consumed by: components:13
- **find_cycles** (function): (scope: GraphScope) -> list[Cycle] — each cycle as an ordered list of refs (`contracts:58` · decided · links: requirements:35, findings:7)
  - error DanglingRef: a traversed edge references a missing row; names the offending ref — signals store inconsistency, routes to integrity check (matches siblings closure/impact)
  - error StorageUnavailable: fail fast, visible error
  - consumed by: components:11

### guidance (`components:4` · decided)
Responsibility: Serves the engineer's mandate and per-stage interview scripts, including the mandatory divergence rounds for elicit stages.
- **get_mandate** (function): () -> MandateText — the engineer's mandate (`contracts:17` · decided · links: requirements:10)
  - error GuidanceUnreadable: mandate content failed integrity; UC2 integrity path — never answer from partial state (uc_extensions:4)
  - consumed by: components:14
- **get_stage_script** (function): (stage: int) -> StageScript — the interview script, including mandatory divergence rounds (context-free questions, negative-space probes, owner-candidates-first) for elicit stages (requirements:16) (`contracts:65` · decided · links: requirements:10, requirements:16, decisions:36, requirements:71)
  - error UnknownStage: stage outside the defined set; names the valid range
  - error GuidanceUnreadable: integrity path; never partial
  - consumed by: components:14

### gap-engine (`components:5` · decided)
Responsibility: Derives prioritized gap clusters with surrounding row context from plan state and owns the dismiss/reopen overlay.
- **next_gaps** (function): (limit: int = 5?) -> GapCluster — prioritized related gaps each with surrounding row context (requirements:13); includes a run-the-gate recommendation when the stage has no open gaps (requirements:12) (`contracts:19` · decided · links: requirements:12, requirements:13, use_cases:3)
  - error PlanUnreadable: underlying rows failed integrity; routes to recovery
  - consumed by: components:15
- **dismiss_gap** (function): (gap_id: int, reason: str) -> Gap in dismissed state; the reason is recorded and the dismissal reversible (requirements:15) (`contracts:66` · decided · links: requirements:15, uc_extensions:8, requirements:78)
  - error GapNotFound: names the missing id
  - error AlreadyResolved: resolved gaps cannot be dismissed; nothing written
  - consumed by: components:15
- **reopen_gap** (function): (gap_id: int, reason: str) -> Gap back in open state with the reopen reason recorded (`contracts:67` · decided · links: requirements:15, requirements:78)
  - error GapNotFound: names the missing id
  - error NotDismissed: only dismissed gaps can be reopened
  - consumed by: components:15

### gate-engine (`components:6` · decided)
Responsibility: Evaluates deterministic, mechanical-only stage gates, reporting row-level holes and raising warnings, including elicit-stage coverage cross-checks.
- **run_gate** (function): (stage: int) -> GateResult — deterministic pass/fail with row-level holes (each naming table, row, problem, fix) and every open gap/unresolved assumption listed as an explicit warning, never passed over silently (requirements:20/21/46); elicit stages include coverage cross-checks (requirements:17) (`contracts:22` · decided · links: requirements:17, requirements:20, requirements:21, requirements:46, use_cases:5)
  - error UnknownStage: names the valid range
  - error BlockedByConflict: an open conflict contests rows this gate depends on; names the conflicts and contested rows (requirements:28)
  - error PlanUnreadable: integrity path; a gate never evaluates partial state
  - consumed by: components:15, components:13

### warning-service (`components:7` · decided)
Responsibility: Owns the warning lifecycle under the keep-pushing policy: re-present until resolved or suppressed, and resurface suppressed warnings at critical points.
- **active_warnings** (function): (context: Optional[CriticalPoint (finalization|red_team_entry|handoff|revision)]?) -> list[Warning] — unresolved warnings; when context is a critical point, suppressed warnings are included as reminders (requirements:23, requirements:55) (`contracts:23` · decided · links: requirements:22, requirements:23, requirements:55, decisions:31)
  - error PlanUnreadable: integrity path
  - consumed by: components:14, components:11, components:13
- **suppress_warning** (function): (warning_id: int, reason: str (the owner's explicit suppression)) -> Warning in suppressed state; still resurfaces at critical points (requirements:23) (`contracts:24` · decided · links: requirements:22, decisions:31)
  - error WarningNotFound: names the missing id
  - error AlreadyResolved: resolved warnings need no suppression; nothing written
  - consumed by: components:15
- **resolve_warning** (function): (warning_id: int, cause: RowRef (the row whose fix resolves it)) -> Warning in resolved state, linked to its resolving row (`contracts:25` · decided · links: requirements:22)
  - error WarningNotFound: names the missing id
  - consumed by: components:6

### conflict-service (`components:8` · decided)
Responsibility: Records contradictions between rows or against new input, blocks dependent gates while open, and captures the owner's adjudication permanently.
- **raise_conflict** (function): (refs: list[RowRef] (the contested rows), description: str, recommendation: str (the engineering recommendation presented with both sides)) -> Conflict in open state; dependent gates block while open (requirements:28) (`contracts:26` · decided · links: requirements:27, requirements:43, use_cases:7)
  - error RefNotFound: a contested ref does not exist; names it; nothing filed
  - consumed by: components:15, components:9, components:11
- **resolve_conflict** (function): (conflict_id: int, outcome: Literal['overridden','revised'], adjudication: str (the owner's decision, quoted)) -> ConflictResolution — outcome and challenge text recorded permanently on the decision (requirements:29) (`contracts:27` · decided · links: requirements:29, use_cases:7)
  - error ConflictNotFound: names the missing id
  - error AlreadyResolved: resolved conflicts are permanent audit records; re-adjudication requires a new conflict
  - consumed by: components:15
- **blocking_conflicts** (function): (scope: GateScope (the rows a gate depends on)) -> list[Conflict] — open conflicts contesting rows in scope, with the blockage reason displayable (requirements:28) (`contracts:28` · decided · links: requirements:28)
  - error PlanUnreadable: integrity path
  - consumed by: components:6

### validation-service (`components:9` · decided)
Responsibility: Resolves uncertainty against external reality: spike registration and resolution for world-assumptions, and classification, routing, and outcomes for technical claims.
- **register_spike** (function): (assumption: RowRef (an assumed/world row), spec: SpikeSpec (question, hypothesis, method against the real dependency, budget)) -> Spike with its quarantine directory — probe code confined to spikes/, never shipped (requirements:3) (`contracts:29` · decided · links: requirements:76, requirements:24, use_cases:6)
  - error AssumptionNotFound: names the missing ref; registration rejected without a linked assumption (requirements:24)
  - error NotWorldAssumption: spikes resolve world-assumptions only; intent-assumptions go to the owner
  - consumed by: components:15
- **record_spike_result** (function): (spike_id: int, outcome: Literal['confirmed','refuted','inconclusive','blocked'], evidence: str (what was observed; for blocked: the unreachable-dependency reason)) -> SpikeResolution — the linked assumption auto-resolves per outcome: confirmed/refuted closes it (refuted raises conflicts on every dependent row), inconclusive keeps it open with findings attached, blocked parks the spike with the assumption visibly open (requirements:25/26) (`contracts:30` · decided · links: requirements:25, requirements:26, requirements:43, use_cases:6)
  - error SpikeNotFound: names the missing id
  - error InvalidTransition: outcome not reachable from the spike's current state (state_machines:5); state unchanged
  - consumed by: components:15
- **file_claim** (function): (text: str, kind: Literal['software','scientific','both'], refs: list[RowRef] (rows resting on the claim)) -> TechnicalClaim routed per kind: software→executable spike, scientific→research + owner/domain-expert adjudication, both→both tracks linked, neither alone closes it (requirements:41); research red flags block dependent planning until resolved or fenced (requirements:4) (`contracts:31` · decided · links: requirements:77, requirements:41, use_cases:10)
  - error RefNotFound: names the missing ref; nothing filed
  - consumed by: components:15
- **record_claim_outcome** (function): (claim_id: int, outcome: ClaimOutcome (validated|failed|risk_accepted), evidence: str) -> ClaimResolution — failed validation raises conflicts on every dependent row (requirements:43); unvalidatable-at-acceptable-cost becomes an owner-signed accepted risk visible at handoff (requirements:42) (`contracts:32` · decided · links: requirements:42, requirements:43, use_cases:10)
  - error ClaimNotFound: names the missing id
  - error InvalidTransition: outcome not reachable from the claim's state (state_machines:8); state unchanged
  - consumed by: components:15

### finding-service (`components:10` · decided)
Responsibility: Owns the red-team finding lifecycle from filing against specific rows through addressed, accepted-risk, or withdrawn outcomes.
- **file_finding** (function): (refs: list[RowRef] (the rows the finding attacks), description: str, severity: str) -> Finding in filed state, linked to the attacked rows (requirements:31); unreadable plan state is itself filed as a finding and certification refused (requirements:30) (`contracts:33` · decided · links: requirements:30, requirements:31, use_cases:8)
  - error RefNotFound: names the missing ref; findings must attack specific rows
  - consumed by: components:15
- **resolve_finding** (function): (finding_id: int, outcome: Literal['addressed','accepted_risk','withdrawn'], reason: str (for accepted_risk: the owner's explicit acceptance)) -> Finding in terminal state; accepted_risk remains visible at implementation handoff (requirements:33); unresolved findings fail the verification gate (requirements:32) (`contracts:73` · decided · links: requirements:32, requirements:33, use_cases:8)
  - error FindingNotFound: names the missing id
  - error InvalidTransition: outcome not reachable from the finding's state (state_machines:7); state unchanged
  - consumed by: components:15

### task-graph (`components:11` · decided)
Responsibility: Derives the dependency-ordered implementation task graph at finalization and maintains build-state truth: readiness, engine status reports, staleness flags, and draft-serving policy.
- **finalize_plan** (function): () -> TaskGraph ordered so no sub-task precedes its dependencies (requirements:34); the result carries resurfaced warnings — finalization is a critical point (requirements:23) (`contracts:35` · decided · links: requirements:34, requirements:35, requirements:32, requirements:23, use_cases:9)
  - error GatesIncomplete: a required stage gate has not passed; names it
  - error CycleDetected: the derived graph contains a dependency cycle; surfaced to the owner as a design conflict before implementation starts (requirements:35)
  - error UnresolvedFindings: findings neither addressed nor explicitly accepted block finalization (requirements:32)
  - consumed by: components:15
- **graph_status** (function): () -> GraphStatus — built, in-flight, blocked, and stale sub-tasks (24h inactivity staleness per dep_failure_modes:6) so any fresh session resumes the build exactly (`contracts:38` · decided · links: requirements:39, dep_failure_modes:6, uc_extensions:37)
  - error PlanUnreadable: integrity path
  - consumed by: components:14, components:15
- **next_subtask** (function): (allow_draft: bool = False (requires recorded owner consent)?) -> SubTaskCandidates — the ready sub-task plus its full candidate closure (every row reachable per requirements:36) for the planning session's LLM to make the BriefSelection from; composing the brief is a separate second call (compose_brief) — or AllBlockedReport naming the blocking dependencies instead of serving unbuildable work (uc_extensions:34) (`contracts:55` · decided · links: requirements:36, requirements:40, use_cases:9, findings:3)
  - error PlanNotFinalized: refused unless allow_draft with recorded owner consent; draft briefs carry an explicit watermark (requirements:40)
  - consumed by: components:15
- **report_status** (function): (subtask_id: int, status: SubTaskStatus (state_machines:9 events), detail: str (partial-progress notes or defect description; NOT completion evidence — 'done' is gated by a passing verify_completion verdict, never by this free string)) -> SubTask with updated state, recorded durably at that moment (requirements:39); the in_progress->done transition requires a recorded passing verify_completion verdict; defect reports file a conflict and freeze dependent briefs before dependent sub-tasks are served (requirements:38) (`contracts:60` · decided · links: requirements:38, requirements:39, use_cases:9, findings:9)
  - error SubTaskNotFound: names the missing id
  - error InvalidTransition: not a legal transition in state_machines:9; state unchanged
  - error VerificationMissing: status 'done' reported without a passing verify_completion verdict for the sub-task; transition refused, state unchanged
  - error MalformedReport: report fails validation; rejected naming the specific problem; sub-task state unchanged, engine resubmits (dep_failure_modes:8)
  - consumed by: components:15
- **verify_completion** (function): (subtask_id: int, evidence: CompletionEvidence — per-contract evidence items mapping each contract in the sub-task's scope to the concrete artifact that demonstrates it (test run, check output, behavior trace)) -> VerificationVerdict — recorded durably with the evidence; a pass is the sole enabler of the in_progress->done transition; a fail names each contract whose evidence is missing or non-verifying (`contracts:62` · decided · links: uc_extensions:36, dep_failure_modes:10, use_cases:9, findings:9, requirements:80)
  - error SubTaskNotFound: names the missing id
  - error EvidenceIncomplete: a contract in the sub-task's scope has no mapped evidence item; verification refused naming the unaccounted contracts, sub-task state unchanged
  - error StorageUnavailable: fail fast, visible error
  - consumed by: components:15, contracts:60

### brief-composer (`components:12` · decided)
Responsibility: Composes immutable, scoped sub-task briefs from link-graph candidate closures with 100% candidate accounting, and splits sub-tasks when a brief proves too large.
- **split_subtask** (function): (subtask_id: int, parts: list[SubTaskSpec]) -> list[SubTask] superseding the original in the graph — the remedy when a brief proves too large; silent trimming is never a remedy (requirements:37) (`contracts:40` · decided · links: requirements:37, uc_extensions:33)
  - error SubTaskNotFound: names the missing id
  - error PartsDontCover: the parts do not jointly cover the original sub-task's contracts; names what is uncovered; nothing written
  - consumed by: components:15
- **audit_brief** (function): (brief_id: int) -> BriefAudit comparing brief contents against the sub-task's link-graph closure — the automated meter for requirements:44's 100% accounting target (`contracts:41` · decided · links: requirements:44)
  - error BriefNotFound: names the missing id
  - consumed by: components:15
- **compose_brief** (function): (subtask_id: int, selection: BriefSelection (the planning-session LLM's picks — made by the session that drives the planning tool and has read the plan, never by the code engine or by the tool itself (decisions:12): included rows + omitted rows each with reason)) -> Brief — immutable record including the omission log; regeneration creates a superseding brief with bidirectional lineage (requirements:61, conflicts:2); old briefs stay frozen for defect forensics (`contracts:68` · decided · links: requirements:36, requirements:44, decisions:34, decisions:52, decisions:12, use_cases:9, findings:3, requirements:79)
  - error SubTaskNotFound: names the missing id
  - error IncompleteAccounting: a candidate row from the link-graph closure is neither included nor recorded-omitted; composition rejected naming the unaccounted rows (requirements:44, decisions:52)
  - error ClosureUnreadable: candidate rows failed integrity; refuses to compose from partial state
  - consumed by: contracts:55

### revision-service (`components:13` · decided)
Responsibility: Drives finalized-plan change orders: snapshot and version bump, link-graph impact walkthrough with owner adjudication, then apply or clean rollback.
- **open_revision** (function): (change: ChangeRequest (what the owner wants changed and why)) -> Revision — snapshots the plan, bumps the version, runs link-graph impact analysis, flags in-flight sub-tasks and freezes affected briefs until analysis completes (requirements:50, requirements:54) (`contracts:42` · decided · links: requirements:50, requirements:54, use_cases:11)
  - error NotFinalized: draft plans are edited directly through the interview; revisions exist for finalized plans
  - error RevisionInProgress: one revision at a time; names the open revision
  - consumed by: components:15
- **next_repercussion** (function): (revision_id: int) -> Repercussion (advice, options with costs, validation/spike needs, recommended path — requirements:51) or WalkthroughComplete; touched accepted-risks and suppressed warnings resurface for re-adjudication (requirements:55); walkthrough position is checkpointed so it resumes losslessly (uc_extensions:44) (`contracts:43` · decided · links: requirements:51, requirements:55, use_cases:11)
  - error RevisionNotFound: names the missing id
  - consumed by: components:15
- **apply_revision** (function): (revision_id: int) -> RevisionResult — revision applied and closed; the plan's new version is live (`contracts:45` · decided · links: requirements:52, use_cases:11)
  - error RevisionNotFound: names the missing id
  - error UnadjudicatedItems: every repercussion must be adjudicated before apply; names the remainder
  - consumed by: components:15
- **abandon_revision** (function): (revision_id: int) -> RollbackReport — plan restored cleanly to its pre-change version; the analysis is preserved as a record of the considered-and-abandoned change (requirements:53) (`contracts:46` · decided · links: requirements:72, use_cases:11)
  - error RevisionNotFound: names the missing id
  - error AlreadyApplied: applied revisions roll forward via a new revision, never backward
  - consumed by: components:15
- **adjudicate_repercussion** (function): (revision_id: int, item_id: int, decision: OwnerDecision (accept|modify|defer, with the owner's words)) -> StagedChange — the owner's adjudication is recorded against the revision; nothing mutates plan rows until apply_revision commits the entire staged change-set atomically (deferred application). Affected gates re-run, affected briefs regenerate, and built work needing rework is flagged at apply time (requirements:52). abandon_revision discards staging with the plan untouched. (`contracts:57` · decided · links: requirements:52, use_cases:11, findings:5)
  - error RevisionNotFound: names the missing id
  - error InvalidState: revision is not in walkthrough state or the item is not the current step; state unchanged
  - consumed by: components:15

### session-service (`components:14` · decided)
Responsibility: Gives any cold session its exact resume point — digest-first status with drift flags — and durably checkpoints journal notes and next-intended-action the moment work completes.
- **journal_note** (function): (text: str, task: Optional[RowRef] (the task the learning arose from)?) -> JournalNote — timestamped, durable the moment the unit completes, never batched to session end (requirements:56/57/60) (`contracts:48` · decided · links: requirements:56, requirements:57, requirements:60, use_cases:12)
  - error StorageUnavailable: fail fast, visible; the note is not silently dropped
  - consumed by: components:15
- **set_next_action** (function): (text: str (the next intended action)) -> Checkpoint — the resume point any fresh session presents (requirements:58); absent one, resume falls back to last completed unit + open gaps (uc_extensions:48) (`contracts:49` · decided · links: requirements:58, use_cases:12)
  - error StorageUnavailable: fail fast, visible error
  - consumed by: components:15
- **plan_status** (function): () -> PlanStatus — compact digest: stage, gate history, active warnings, mandate, current stage script, exact progress point (last completed unit, accumulated learnings, next intended action) and workspace-drift flags computed by comparing the workspace fingerprint stored at finalization and at each brief issue against the current workspace; row contents are fetched separately via targeted selectors, never dumped (requirements:10/58/59/62, decisions:49) (`contracts:64` · decided · links: requirements:10, requirements:58, requirements:59, requirements:62, requirements:73, decisions:49, use_cases:2, use_cases:12, findings:10, requirements:69)
  - error NoPlanFound: no plan in this workspace; stated plainly so the caller can offer to start one (uc_extensions:5)
  - error PlanCorrupt: integrity check failed on open; carries the IntegrityReport and routes to recovery — never answers from partial state (requirements:11)
  - consumed by: components:15

### mcp-surface (`components:15` · decided)
Responsibility: The only externally visible component: an engine-agnostic MCP stdio toolset wrapping every service contract, with per-call validation, pedagogical errors, and the append-only observability log.
- **dispatch** (api): (call: ToolCall (MCP tool name + JSON arguments)) -> ToolResult — engine-agnostic MCP content, strictly protocol-clean with no engine-specific calls or configuration (decisions:4, requirements:2); consumed externally by the LLM planning agent and the LLM code engine (`contracts:50` · decided · links: requirements:74, requirements:75, requirements:14, decisions:4, decisions:44) · external
  - error UnknownTool: names the unknown tool and lists valid ones
  - error MalformedCall: pedagogical rejection naming the specific problem; nothing is filed (dep_failure_modes:13, requirements:14)
  - error NotWriter: a write tool was invoked without holding the writer lease; read tools are unrestricted (decisions:44)
- **append_log** (function): (event: LogEvent (tool call or failure, failure-mode label unavailable|slow|malformed|auth|partial, timestamps, result summary)) -> None — append-only observability log in the workspace (decisions:46) (`contracts:51` · decided · links: requirements:66, decisions:46, decisions:54)
  - error LogWriteError: log unwritable; fail fast and surface — operations are never silently unlogged
  - consumed by: contracts:50

## Stage 7 — Adversarial findings

- [redteam] The writer-lock contract set has no release operation. contracts:3 acquires, contracts:4 heartbeats — nothing ever releases. A session that finishes cleanly leaves its lease held until 10-minute staleness expires (requirements:63). Consequence for the plan's own stage-7 workflow (use_cases:8): the author session is alive-but-idle while a fresh red-team session must WRITE findings; the red team is locked out until staleness, and an author session that heartbeats while waiting locks it out forever. Same deadlock for a code engine reporting status while a planning session idles (dep_failure_modes:6 scenario in reverse). A release_writer_lock (and/or an explicit handoff) contract is a missing row. (`findings:1` · links: contracts:3, contracts:4, requirements:63, decisions:44, use_cases:8, contracts:54) — fixed — Missing release operation added: contracts:54 (release_writer_lock on storage-engine) frees the lock immediately on clean finish instead of waiting out 10-minute staleness; LeaseLost on release is idempotent-safe. The author-idle/red-team-locked-out deadlock in use_cases:8 dissolves — a finishing session releases, and an idle-but-alive session no longer starves writers.
- [redteam] The heartbeat mechanism is unimplementable as specified. dep_failure_modes:12 declares the tool "a passive, durable callee" — it executes only when a tool call arrives — yet requirements:64 demands the original holder "stops writing immediately" when its lease is claimed, and contracts:4 assumes something periodically calls heartbeat_lock. No row says WHO fires the heartbeat or WHEN. In the normal interactive pattern (owner thinking/typing for 10+ minutes between tool calls, the exact scenario decisions:41 describes), a passive callee cannot heartbeat, so a live session loses its lock by design — the spike (spikes:1) already observed live-session lock theft at scaled thresholds. Either the surface heartbeats on a background thread (contradicting 'passive callee', and dying with host suspend/sleep), or lock loss during normal use is accepted; neither is recorded. Also unspecified: the check-lease-then-commit race — 'stops immediately' is only achievable if lease validity is verified atomically inside the same transaction as each write, which no contract states. (`findings:2` · links: requirements:64, contracts:4, dep_failure_modes:12, decisions:44, spikes:1, decisions:41, contracts:53, requirements:68) — fixed — Heartbeat replaced by a passive lease model: renewal piggybacks on every tool call (contracts:53) and enforcement moved to the write boundary — every write validates the lease inside the same transaction that applies it (requirements:68). 'Stops writing immediately' now means 'no further write can land', implementable by a passive callee with no background thread; the check-lease-then-commit race is closed by the same-transaction rule.
- [redteam] Brief composition has a circular actor dependency. contracts:36 (next_subtask) returns "the ready sub-task plus its composed brief" and consumes contracts:39 (compose_brief), but compose_brief requires a BriefSelection argument produced by "the composing LLM" (decisions:52). The tool has no LLM access (non-goal decisions:12), so the selection must come from the caller — but the caller of next_subtask is the code engine, which at that moment has never seen the plan and cannot select from a closure it hasn't read. No row defines the actual call sequence: who receives the candidate closure, who makes the selection, and how next_subtask can return an already-composed brief in one call. As specified, the product's central capability (decisions:32 calls it "highly complex" and core) cannot be executed from these contracts. (`findings:3` · links: contracts:36, contracts:39, requirements:36, decisions:52, decisions:12, decisions:32, decisions:60, contracts:55, contracts:56) — fixed — Call sequence now defined (decisions:60): next_subtask (contracts:55) returns candidates + closure, the planning session's LLM makes the BriefSelection, compose_brief (contracts:56) is the second call. No actor is asked to select from a plan it has not read.
- [redteam] The successor's planning methodology itself has no rows. The plan specifies machinery to SERVE stage scripts (contracts:18), the mandate (contracts:17), gap clusters (contracts:19), and mechanical gates (contracts:22) — but nowhere defines the successor's stage list, the content of any stage script or the mandate, the per-stage mechanical gate criteria (beyond the two elicit cross-checks in requirements:17), or the gap-derivation rules (what deficiency types the gap-engine detects). These are the product's core IP and its hardest design problem. Against goal decisions:14 (execution sufficiency: zero sub-tasks blocked by missing plan information), the executor building guidance/gap-engine/gate-engine would have to invent the entire methodology at build time — the exact milestone-time re-planning failure this tool exists to prevent. (`findings:4` · links: components:4, components:5, components:6, contracts:18, contracts:22, contracts:19, requirements:17, requirements:20, decisions:14, decisions:61, requirements:71) — fixed — Methodology content now has owning rows: decisions:61 vendors PlanTool rev-2 methodology as versioned content assets with a content-revision stamp; requirements:71 makes shipping the assets and the revision-migration path a requirement. The content-revision stamp also pre-answers the fossilization premortem.
- [redteam] Revision rollback contradicts the write-once supersession model. adjudicate_repercussion (contracts:44) applies changes immediately during the walkthrough ("rows updated with provenance, affected gates re-run, affected briefs regenerated"), yet abandon_revision (contracts:46, requirements:53) promises the plan "restored cleanly to its pre-change version". Undoing an applied supersession is impossible under the plan's own rules: superseded rows are frozen history (sm_cells:39-42), superseded_by stamps are write-once (requirements:61, decisions:42), and briefs are immutable. Restoring the pre-change PlanVersion snapshot would work — except requirements:53 also demands the analysis record be PRESERVED, and it lives in the same store being restored. The plan needs either deferred application (nothing mutates until apply_revision) or a defined selective-restore semantics; as written the three rules are jointly unsatisfiable. (`findings:5` · links: requirements:53, contracts:44, contracts:46, requirements:61, decisions:42, state_machines:2, contracts:57, requirements:72) — fixed — Deferred application: contracts:57 stages adjudications and only apply_revision mutates rows; requirements:72 rewords abandon as discarding staged changes, with the analysis record stored outside the plan-row snapshot. The three previously jointly-unsatisfiable rules are now consistent.
- [redteam] The Plan state machine globally freezes implementation during revision, contradicting the freeze-only-affected policy. sm_cells:20 makes start_implementation impossible while revising ("affected briefs are frozen during revision") and sm_cells:24 declares "implementation is paused during revision" — but requirements:54 and uc_extensions:41 freeze only AFFECTED briefs "until the impact analysis completes", implying unaffected sub-tasks keep flowing. Concretely: plan is implementing, owner opens a revision touching one component, and next_subtask (contracts:36) for a completely unrelated ready sub-task now fails PlanNotFinalized because the plan sits in 'revising'. For long walkthroughs (uc_extensions:44 anticipates multi-session ones) the entire build stalls. Either the state machine needs a concurrent implementing+revising composite, or requirements:54's affected-only wording is wrong; the two rows currently disagree. (`findings:6` · links: sm_cells:20, sm_cells:24, requirements:54, uc_extensions:41, contracts:36, state_machines:1, decisions:62, sm_cells:186, sm_cells:187) — fixed — Owner chose affected-only freeze (decisions:62): sm_cells:186/sm_cells:187 make start_implementation/complete_implementation self-transitions in 'revising', so unaffected sub-tasks keep flowing and only the impact set freezes (requirements:54). The state machine and the requirement now agree.
- [redteam] Gamed cannot_fail: contracts:16 (find_cycles) claims "cannot fail: pure computation over edges already validated at write time" — but it must READ those edges from the store, exactly like its siblings closure (contracts:14) and impact (contracts:15), both of which carry DanglingRef errors routing to the integrity check, and every other read path in the system carries StorageUnavailable/PlanUnreadable. A corrupt or unavailable store makes find_cycles fail; the cannot_fail assertion is convenience, not impossibility — the precise escape class the stage-7 standing targets name. (`findings:7` · links: contracts:16, contracts:14, contracts:15, contracts:58) — fixed — contracts:58 drops cannot_fail and declares DanglingRef + StorageUnavailable with the same routing semantics as its siblings contracts:14/15.
- [redteam] Spike 1's design consequences were recorded as a decision but never propagated into the requirements and contracts an executor will actually build from. decisions:58 mandates a hardened lock protocol for network mounts (heartbeat retry-on-sharing-violation, reader access that never holds the lock file open, staleness >> heartbeat interval) plus a resume-time SMB durability warning — yet requirements:63/64 and contracts:3/4 are unchanged and mention none of it, and no requirement exists for the resume-time warning at all. A brief composed for storage-engine or session-service could satisfy 100% candidate accounting while omitting decisions:58 if the composing LLM judges a 'decision about a spike' peripheral. Separately, decisions:58's claim that the production 10-min-vs-30-s ratio "satisfies this" is extrapolation, not observation: even WITH retry the spike's heartbeat age reached 5.45s of a 6s threshold (91%); nothing shows sharing-violation bursts stay bounded at minutes-long scale. (`findings:8` · links: decisions:58, requirements:63, requirements:64, contracts:3, contracts:4, spikes:1, spikes:2, requirements:67, requirements:68, contracts:52, contracts:53, requirements:69, decisions:59) — spiked — d58's hardening now lives in the rows an executor builds from: requirements:67/requirements:68 and contracts:52/contracts:53 carry sharing-violation retry, reader-never-holds-open, and the write-boundary lease check; the missing resume-time SMB warning is requirements:69. The remaining unverified claim — bursts stay bounded at production cadence — is recorded as assumed(world) decisions:59 and will be settled by spikes:2 (registered, method in row; execution pending).
- [redteam] Contract verification of delivered work is asserted but owned by nobody. uc_extensions:36 says deviation from contract is caught by "verification against the contract", and dep_failure_modes:10 says "nothing counts as done until the contract verification passes" — but no component, contract, or requirement defines who runs that verification, what it checks, or what evidence gates the in_progress→done transition. contracts:37 (report_status) accepts "completion evidence" as a free string and applies the transition. As specified, 'done' means 'the engine said so' — the honor system UC9's failure handling explicitly claims not to be. (`findings:9` · links: uc_extensions:36, dep_failure_modes:10, contracts:37, use_cases:9, contracts:59, contracts:60) — fixed — Verification now has an owner: contracts:59 (task-graph) checks delivered evidence against every contract in the sub-task's scope and its passing verdict is the sole enabler of in_progress->done; contracts:60 refuses 'done' without it (VerificationMissing) and demotes the free-string detail to notes.
- [redteam] Workspace-drift detection has no mechanism. requirements:59 and uc_extensions:49 require resume to "flag the drift between plan assumptions and current workspace state", and contracts:47 (plan_status) advertises "workspace-drift flags" — but no entity stores a workspace fingerprint, no row defines which plan assumptions are drift-checkable, and no contract captures workspace state at any earlier moment to compare against. What is compared with what, and when the baseline is taken, is nowhere in the plan; the executor cannot build this flag from the rows provided. (`findings:10` · links: requirements:59, uc_extensions:49, contracts:47, requirements:73, contracts:61) — fixed — Baseline defined: requirements:73 captures a minimal workspace fingerprint at finalization and each brief issue (no new entity — it rides on the plan version/brief); contracts:61 computes drift flags by comparing that stored fingerprint against the current workspace.
- [redteam] Sub-task granularity is undefined. requirements:34 and contracts:35 derive the task graph "from components, contracts, and dependencies" — but no row says what one SubTask node IS (a component? a contract? a contract-plus-its-tests?), what the derivation algorithm produces, or how dependency edges between sub-tasks map from contract_deps. entities:9 defines the SubTask lifecycle in 36 cells yet the entity's unit of granularity — the single most consequential input to brief sizing (decisions:32/34) — is unspecified. Two implementers would derive incompatible graphs from the same plan, and the split_subtask remedy (contracts:40) presumes a divisible unit whose composition rules were never stated. (`findings:11` · links: requirements:34, contracts:35, entities:9, contracts:40, decisions:32, decisions:63) — fixed — decisions:63: one SubTask = one contract implementation unit; edges map from contract_deps; split_subtask divides along the contract's param/error surface. Derivation is now deterministic.
- [redteam] Zero-loss checkpointing collides with single-writer rejection. requirements:56/60 guarantee every completed work unit is durably recorded "at that moment" with a loss target of 0 — but requirements:63 makes any second session's write bounce with a visible error while another holds the lock, for up to 10 minutes (longer, since nothing releases the lock — see the missing-release finding). Concrete scenario: the code engine finishes a sub-task and reports; the planning session holds the lock; the engine's session dies (token exhaustion, the exact decisions:41 scenario) before the lock frees; the completion and its learnings are gone, violating the Planguage target of 0. The plan needs either a write-queue/park mechanism for checkpoint-class writes or an explicit carve-out; currently the two requirements are jointly unsatisfiable under multi-session operation the plan itself schedules (planning + engine + red-team sessions). (`findings:12` · links: requirements:60, requirements:56, requirements:63, decisions:41, dep_failure_modes:6, requirements:70) — fixed — New requirement requirements:70: checkpoint-class writes rejected under lock contention park in a session-local durable spill journal and reconcile automatically on the next lock acquisition — the Planguage loss target of 0 survives a session dying before the lock frees.
- [redteam] Requirements 1-4 carry malformed canonical text: doubled boilerplate ("The system shall The system shall run on Windows...") and doubled terminal punctuation, with requirements:4 reading "...the system shall The system shall flag it...". In a product whose core mechanism is serving stored row text verbatim into scoped briefs (requirements:36), garbled canonical text propagates into every brief that cites these rows — including the foundational portability and MCP-compliance constraints that bind nearly every component. These rows should be superseded with clean text. (`findings:13` · links: requirements:1, requirements:2, requirements:3, requirements:4, requirements:74, requirements:75, requirements:76, requirements:77) — fixed — requirements:1-4 superseded by requirements:74, requirements:75, requirements:76, requirements:77 with the renderer boilerplate and doubled punctuation stripped; briefs citing these rows now serve clean canonical text.
- [redteam] Provenance lineage on the decisions:6 chain never closed: decisions:6 is STILL an active assumed/intent row (provenance 'assumed', superseded_by null, verified via get_rows include_inactive) at stage 7, while decisions:25/26/27 are three near-identical 'decided' rows all quoting the same user answer; decisions:27's rationale says "Supersedes and upgrades the intent-assumption decisions:6" but its supersedes pointer is null — the supersession exists only as prose. decisions:26 and 27 are pure duplicates of 25 adding nothing. This is documented prototype friction (decisions:28a), but the residue is a live plan where an external reader's single liveness check (requirements:61) reports an unconfirmed assumption AND its three confirmations as simultaneously live intent. The successor plan should not ship its own provenance discipline violated in its own store: 6 needs confirming or superseding with real lineage, 26/27 retiring. (`findings:14` · links: decisions:6, decisions:25, decisions:26, decisions:27, decisions:28, requirements:61) — fixed — decisions:6 upgraded assumed(intent)->decided via confirm_assumption quoting the owner's 2026-07-17 answer, with decisions:25's original verbatim condition (behavior-derived requirements must cite the observed friction) folded into the provenance note; duplicate confirmations decisions:25/26/27 retired with owner approval. A liveness check now reports one decided row, no dangling confirmations.
- [redteam] Plan 'tier' is recorded but semantically undefined. uc_steps:2 and requirements:8 record a tier at initialization, and entities:1 carries it as core Plan state — but no row enumerates the valid tiers or defines a single behavioral difference between them (do gates, stages, or gap rules change per tier?). Either tier drives behavior (in which case the behavior matrix is a missing, load-bearing set of rows) or it is inert metadata (in which case requiring it at init is unjustified ceremony). uc_extensions:1 even makes the agent stop and ask the owner for tier before initializing — blocking on a value the plan gives no meaning. (`findings:15` · links: requirements:8, uc_steps:2, entities:1, uc_extensions:1, decisions:64, uc_extensions:50) — fixed — decisions:64: tier is a forward-compat placeholder with exactly one v1 value ('standard'), init never blocks on it; uc_extensions:50 drops the stop-and-ask for tier.
- [redteam] Gap identity across re-derivation is unspecified, and the prototype's stale-gap bug will recur without it. entities:3 says gaps are "computed by the gap engine but carrying a stored open/dismissed/resolved overlay", and contracts:20/21 key dismiss/reopen by gap_id — but no row defines how a computed gap gets a stable identity when the engine re-derives after plan changes. If identity is positional or content-hashed, a superseded row's reworded deficiency becomes a 'new' gap and the recorded dismissal silently detaches — exactly the re-surfacing loop documented as friction in decisions:28(a) ("next_gap kept re-surfacing it"). The overlay needs a defined identity function (e.g., gap-type + target row lineage) or dismissals are not durably meaningful. (`findings:16` · links: entities:3, contracts:20, contracts:21, contracts:19, decisions:28, requirements:78) — fixed — requirements:78 defines the identity function: gap-type + target-row lineage root, supersession-stable by construction (the same principle that keys PlanTool's own gap_dismissals), so dismissals stay attached across re-derivation and rewording via supersede.
- [premortem] It failed because the vendored methodology fossilized: the successor shipped PlanTool rev-2 stage scripts, mandate, gate criteria, and gap rules as static content with no revision identity, so when the methodology improved there was no way to tell which revision a live plan was built under or to migrate it — plans silently mixed old-methodology rows with new-methodology gates until the gates' judgments stopped meaning anything. (`findings:17` · links: components:4, components:5, components:6, decisions:61, requirements:71) — fixed — Pre-answered by the finding-4 fix: decisions:61 vendors the methodology as versioned content assets carrying a content-revision stamp, and requirements:71 mandates an update path migrating a plan from one methodology revision to the next — revision identity and migration are exactly the two failure preconditions this story needs.
- [premortem] It failed because brief candidate accounting was gameable: compose_brief's IncompleteAccounting check counts rows OFFERED, not rows NEEDED — the composing LLM satisfied 100% accounting by marking load-bearing-but-peripheral-looking rows (spike-derived lock-hardening decisions, failure-mode handling) as 'omitted: not relevant', and briefs shipped without the constraints that made sub-tasks correct. Nobody reviewed omissions because they were formally accounted for. (`findings:18` · links: contracts:56, requirements:44, decisions:52, requirements:79) — fixed — requirements:79: cited-or-explicitly-waived for every closure row, waiver log immutable in the brief, and waivers of decision/requirement/failure-mode rows surfaced to the owner at finalization and brief review — gaming the accounting now requires lying in a log the owner reads.

## Decisions

- Stack: Python + SQLite (single-file database per plan), delivered as an MCP server over stdio. (`decisions:1` · decided)
  - rationale: User selected "Python + SQLite (Recommended)". Continuity with the author's Python skills; mature Python MCP SDK; SQLite is zero-install, cross-OS, single-file, with real foreign keys — the plan travels with the project folder.
  - rejected: TypeScript/Node + SQLite — npx gives frictionless distribution, but that matters little for a personal tool and abandons the author's Python fluency
  - rejected: Go single static binary + SQLite — best install story per OS, but irrelevant for a personal tool and the least mature MCP ecosystem
- Audience: a personal tool for the author's own projects. Public packaging, distribution, onboarding, and support are out of scope. (`decisions:2` · decided)
  - rationale: User selected "Personal tool, own projects". Keeps scope on planning quality rather than product polish.
- The plan database remains the living source of truth after execution begins: amendments are first-class change-orders that update rows with provenance and re-validate affected rows. The plan is complete upfront but never frozen. (`decisions:3` · decided)
  - rationale: User selected "Living source of truth (Recommended)". Resolves the tension between "complete and thorough from the start" and reality contradicting the plan during execution: complete ≠ immutable.
  - rejected: Freeze the plan once approved; log deviations only — the database silently diverges from the code mid-project and gets abandoned, leaving the user worse off than markdown
- Engine compatibility policy: the design must contain no Claude Code-specific calls, features, or configuration (strict MCP-protocol-clean); practical testing happens on Claude Code; no formal multi-engine validation matrix is required. (`decisions:4` · decided)
  - rationale: User's actual answer: "I don't need validation, but I want you to avoid any claude code specific calls and we will test on claude code."
- Clean-room redesign: prototype 1's code, schema, and repository must not be examined or used as a design reference. Every design element of the successor must be justified from first principles, never by precedent from prototype 1. (`decisions:5` · decided)
  - rationale: User's actual words: "I specifically do not want you to take anything from the tool you are using now, do not examine its code, do not use it as a reference. Let's try and make something better."
- The prototype's externally visible behavior during this planning session (stage flow, prompts, friction points) may be used as a critique baseline: observed weaknesses become requirements for the successor. (`decisions:6` · decided)
  - rationale: Engineer's interpretation of the clean-room constraint, disclosed to the user: the prototype structures this very conversation and cannot be fully unseen, so its visible behavior is treated as a baseline to beat rather than a template to copy. Pending user objection.
- Working norm: complete mutual honesty. The engineer discloses uncertainty and disagreement openly and marks invented content as assumptions; the user commits to candor about intent and context. (`decisions:7` · decided)
  - rationale: User's actual words: "I want to add complete honesty to this as it is very important that we are BOTH completely honest with each other."
- Problem statement: Large, complex solo projects fail late and expensively due to (a) poorly defined dependencies, (b) research-level technology embedded unnoticed in the plan and discovered unsolvable only at a milestone build after substantial sunk work, and (c) LLM forgetfulness, false assumptions, and inaccurate assessments across sessions. Root cause accepted by the user: insufficient upfront planning and failure-point analysis. The intent is to shift effort heavily toward planning and away from failed implementations. (`decisions:8` · decided)
  - rationale: User's own account of why now: "I often develop large, complex projects that are prone to failure due to poorly defined dependencies, research level tech that then cannot be resolved at a milestone build... LLM forgetfullness/false assumptions/inaccurate assessments... I want to spend far more time planning and less time with failed implementations."
- Non-goal: generating production code — the tool plans; the LLM CLI engine executes. (`decisions:9` · decided)
  - rationale: User confirmed: "Totally correct assumptions."
- Non-goal: multi-user project management — no scheduling, Gantt charts, task assignment, or team workflow. (`decisions:10` · decided)
  - rationale: User confirmed the candidate non-goal list in full.
- Non-goal: any hosted or cloud component — fully local operation. (`decisions:11` · decided)
  - rationale: User confirmed the candidate non-goal list in full.
- Non-goal: direct LLM API integration or API-key management. (`decisions:12` · decided)
  - rationale: User confirmed the candidate non-goal list in full; also a founding constraint from the original brief.
- Non-goal: planning non-software projects — this is a software development planning tool only. (`decisions:13` · decided)
  - rationale: User's actual words: "this is a software dev plan tool only."
- Goal: Execution sufficiency — a finished plan lets an executor complete every sub-task without milestone-time re-planning. (`decisions:14` · decided · links: decisions:8)
  - rationale: Success criterion: on a real project, zero sub-tasks are blocked by missing or ambiguous plan information; mid-execution discoveries arrive as change-orders traceable to genuinely new facts, not planning omissions.
- Goal: Lossless resume — any session can die at any point and a cold session resumes from the database alone. (`decisions:15` · decided · links: decisions:8)
  - rationale: Success criterion: zero previously-answered questions are ever re-asked across session deaths. Directly counters LLM forgetfulness (problem cause c).
- Goal: Focused context delivery — each execution sub-task receives a context pack containing exactly its linked rows plus the governing big-picture rows. (`decisions:16` · decided · links: decisions:8)
  - rationale: Success criterion: the executor never has to request missing plan information, and the pack contains no rows lacking a link-path to the task.
- Goal: Enforced rigor — the planning interview cannot silently accept contradictions or invented facts. (`decisions:17` · decided · links: decisions:8)
  - rationale: Success criterion: mechanical audit shows every row carries provenance and every conflict with an existing row was raised before filing. Counters agreeable transcription and inaccurate assessments (problem cause c).
- Goal: Research red-flag triage — every user-proposed capability is feasibility-classified at the moment it enters the plan: established solution, needs a spike, or research-level with no known solution. Research-level items must be resolved or fenced as an explicit research sub-project with go/no-go criteria before dependent planning continues. (`decisions:18` · decided · links: decisions:8)
  - rationale: Success criterion: zero research-level unknowns survive into build planning unresolved; research surprises discovered at build time = 0. User's actual words: "if the user proposes something with no known solution, that is a research red flag that needs to be considered immediately and if not solvable defined as a research sub-project in itself before continuing." Directly targets problem cause (b).
- Goal: Frictionless deployment — a gate-passed plan becomes an executing workspace with near-zero ceremony. (`decisions:19` · decided · links: decisions:8)
  - rationale: Success criterion: from approved plan to an executor working on its first sub-task in a single command, with no manual transcription of plan content. User named deployment friction as the most likely cause of tool abandonment: "the most likely cause of that is it creating too much friction to deploy."
- Goal: Dependency rigor — every external dependency is fully characterised (version, role, integration surface, known failure modes) before build planning completes. (`decisions:20` · derived · links: decisions:8)
  - rationale: Success criterion: zero mid-build discoveries of missing, incompatible, or misunderstood dependencies. Derived from problem cause (a) "poorly defined dependencies" — the user named it as a leading failure cause but did not state it as a goal; engineer promoted it.
- Non-goal: public distribution, packaging, or end-user support — personal tool. (`decisions:21` · derived · links: decisions:2)
  - rationale: Follows from the audience decision (personal tool for the author's own projects).
- Deployment model: planning happens inside the target project's repository from day 0. The SQLite plan database is versioned in git alongside the code, and a single MCP server exposes both the planning and execution toolsets. "Deploy" is zero-step: when the plan gates pass, the executor is already pointed at the live plan. (`decisions:22` · decided · links: decisions:19)
  - rationale: User selected "Plan lives in project repo (Recommended)". Directly serves the frictionless-deployment goal — deployment friction was named the most likely cause of tool abandonment.
  - rejected: Separate planning workspace, then one-command transplant into the project repo — adds a deploy step and a failure point; git already isolates planning clutter
  - rejected: Export the plan to generated documents (CLAUDE.md/AGENTS.md style) at deploy time — sacrifices live queries, selective context packs, and change-orders — defeats the database's purpose
- Research fence policy: when a research red flag cannot be resolved immediately, the tool presents the blast radius (every dependent row) and the user chooses per-flag between hard-pausing the plan and fencing the item as a research sub-project while independent planning continues. (`decisions:23` · decided · links: decisions:18)
  - rationale: User selected "Ask me each time" over the engineer's recommended automatic fence-and-continue — a deliberate choice of per-case control over automation.
  - rejected: Always block dependents only and continue elsewhere (engineer's recommendation) — user prefers to judge blast radius case by case
  - rejected: Hard pause the entire plan on every flag — wastes time when the flagged item is peripheral
- No sacred workflow constraints exist beyond those already recorded (MCP transport, no API keys, OS-agnostic, fully local): the successor may redesign the planning workflow freely. (`decisions:24` · decided)
  - rationale: User selected "Nothing sacred — redesign freely" when asked what must not change about their current workflow.
- Observed prototype friction (critique baseline): (a) an assumed intent-decision cannot be upgraded to decided in place — three record_decision attempts (decisions:25,26,27) with quoted user answer, matching text, and links all left the original row assumed and next_gap kept re-surfacing it, forcing duplicate rows; (b) plan_status returns row counts but not row contents, so a cold session cannot re-read its own recorded decisions, undercutting the 'lossless resume' claim. (`decisions:28` · derived · links: decisions:27, decisions:25)
  - rationale: Directly observed in this session (2026-07-16) while resolving decisions:6. Recorded under the rule in decisions:27/25 that behavior-derived successor requirements must cite observed friction; this row is the citation source for future requirements about assumption lifecycle and full-state rehydration.
- Use-case scope: all four clusters are in scope — core loop (start plan, cold resume, stage interview, assumption resolution, stage gates), resilience (spikes, conflicts), verification (red-team), and handoff (code engine consumes the plan). (`decisions:29` · decided)
  - rationale: User selected all four proposed clusters: "Core loop: UC1–UC5, Resilience: UC6–UC7, Verification: UC8, Handoff: UC9" (2026-07-16). Handoff noted as arguably the product's whole point.
- Workspace precondition: the planning agent always starts inside the pre-existing project workspace it is planning. The tool initializes plans within that workspace; it never creates or manages workspaces itself. (`decisions:30` · decided · links: decisions:29)
  - rationale: User, verbatim (2026-07-16): "you can assume that the agent starts in the project workspace it is planning. Agent does not create it." Simplifies UC1: plan initialization only, no workspace lifecycle.
- Gate warning policy: gates warn rather than block on open gaps and unresolved assumptions. The agent must keep re-raising warnings at every subsequent stage open and gate until resolved or the owner explicitly suppresses them — and even suppressed warnings resurface as reminders at critical points (finalization, red-team entry, implementation handoff). (`decisions:31` · decided · links: decisions:28)
  - rationale: User, verbatim (2026-07-16): "warns are the default, but you need to keep pushing then unless the users suppresses, and even then offer reminders at critical points." Motivated by observed friction: this prototype's gate passed silently over an open gap (decisions:28).
- Implementation control is a core product capability, not an export feature: the tool decomposes the finished plan into sub-tasks and serves the code engine a scoped brief per sub-task — maximum relevant detail for that sub-task, never one massive prompt of the whole plan. The decomposition and context-slicing logic is acknowledged as highly complex and central to the product's value. (`decisions:32` · decided · links: decisions:29)
  - rationale: User, verbatim (2026-07-16): "remember a key aspect of this too is how it controls implimentation, we do not want to hit the agent with one massive prompt, we want to give it maximum relelvant detail for the sub-task, this is a critical aspect of this tool and highly complex decisions are required to do it right." Replaces the too-simple UC9 export framing.
  - rejected: Plan handoff as a single full-plan export document the engine reads once — Explicitly rejected by the owner: one massive prompt dilutes relevance and wastes the engine's context on irrelevant detail.
- Technical validation is in scope in two flavors: software feasibility ("how do I code that" — resolved by executable spikes) and scientific appropriateness ("is that an appropriate theory to use for this application" — resolved by research plus owner/domain-expert adjudication). (`decisions:33` · decided · links: decisions:29)
  - rationale: User (2026-07-16): "I think we are missing the technical validation point, this can be purely software (how do I code that) or scientific (is that an appropriate theory to use for this application)." Becomes UC10; software track reuses the spike machinery (UC6).
- Brief sizing carries no token quotas: how much plan content goes into a sub-task brief is a task-specific judgment by the composing LLM. Relevance is defined structurally by the plan's link graph (rows reachable from the sub-task's contracts/components are candidates), and the LLM's selection is made auditable — omitted candidate rows are recorded — rather than caged by numbers. (`decisions:34` · decided · links: decisions:32, use_cases:9)
  - rationale: User, verbatim (2026-07-16): "I think this is almost impossible to put numbers to, I never have any idea how many tokens an operation is going to take, and I'm pretty sure neither do you. Talking about 40% also seems meaningless (a massive project with 20 code sessions vs a tiny project with 3 - what is 40%, why is it significant?). This needs to be a task specific judgement by the LLM." The link-graph candidacy + auditable-omission mechanism is the engineer's answer to making that judgment verifiable without quotas.
  - rejected: Fixed absolute token budget per brief — Owner: token counts are unknowable in advance and meaningless as a quality bar.
  - rejected: Percentage of engine context window (e.g. 40%) — Owner: percentage is meaningless across project scales — 'what is 40%, why is it significant?'
- Single-user system: one owner, no concurrent multi-session writes. Every session must have access to 100% of stored rows; the hard problem is selection — which rows belong in context for a given task — not access. (`decisions:35` · decided · links: decisions:28, use_cases:2, use_cases:9)
  - rationale: User (2026-07-16): "single user" and "Surely any session must have access to 100% of the rows, the big questions is which ones *should* it use in context." Access completeness stays an NFR at 100%; selection quality is governed by the brief-composition requirements (link-graph candidacy, auditable omissions).
- Observed prototype friction (critique baseline): the proposal-first interview under-pushed the owner for divergent input — the agent authored all ten use cases and the owner "did not feel pushed that hard to add any", so coverage confidence rests entirely on the agent. Successor countermeasures: (a) elicit-stage scripts must include mandatory divergence rounds — context-free questions, negative-space probes, owner-generated candidates solicited BEFORE agent drafts are shown; (b) elicit-stage gates must run mechanical coverage cross-checks (every actor appears in ≥1 use case, every goal traces to ≥1 use case). Note: the agent could not run those cross-checks mechanically in this session because stage-1 rows are unreadable cold (links decisions:28(b)). (`decisions:36` · decided · links: decisions:28, decisions:25, use_cases:3, use_cases:5)
  - rationale: User, verbatim (2026-07-16): "What I'm seeing from the prototype was you created all of the UCs and I did not feel pushed that hard to add any, how are you sure you have captured all of UCs? I think the discussion aspect needs to be expanded from the prototype." Behavior-derived per the citation rule in decisions:25/27; the specific countermeasures are the engineer's mechanism, presented for objection.
- UC11 scope: revising a finalized plan includes interpreting ALL repercussions of the change via the link graph, then walking the owner through those repercussions offering advice, validation testing, and analysis — not merely applying the edit. (`decisions:37` · decided · links: decisions:32, decisions:33)
  - rationale: User, verbatim (2026-07-16): "we need a mechanism to revise a final plan and that includes interpretting all of the repercussions to a change and walking the user through those changes offering advice, validation testing and analysis."
- Non-goal (parked, not rejected): a GUI for interrogating the plan. The owner absolutely plans one, but it is out of scope for this version; the system must therefore be API/tool-first so a GUI can attach later without rework. (`decisions:38` · decided)
  - rationale: User, verbatim (2026-07-16): "I absolutely plan to have a tool gui to interrogate the plan, but I think we can park that for now, without api calls that is something that is difficult for you to interact with." The API-first consequence is the engineer's derivation from the parking rationale.
- Version control strategy: all plan state lives in files inside the project workspace and is git-committable — git covers the VCS aspect; the tool does not reimplement versioning beyond plan-version bumps. Every stored entry carries a unique ID and creation timestamp. Design constraint carried to stage 4+: the storage format must behave acceptably under git commit (and ideally diff). (`decisions:39` · decided · links: decisions:30)
  - rationale: User, verbatim (2026-07-16): "The plan is git commitable and that covers the VCS aspect, although I'm assumming all of your data entries are uniquely ID'd and date stamped." The unique-ID/timestamp assumption is confirmed as a requirement rather than left implicit.
- Abandoning a plan requires no in-tool mechanism: the owner deletes the project directory. Corollary: no plan state may live outside the project workspace, or deletion would leave orphans. (`decisions:40` · decided · links: decisions:30)
  - rationale: User, verbatim (2026-07-16): "Abandon plan = user deletes project directory." The no-external-state corollary is the engineer's derivation.
- Progress tracking is in scope as a first-class capability: every step of work (row submissions, briefs served, sub-task status, and informal learnings) is durably recorded the moment it completes, so an abrupt session end — token exhaustion, crash, sleep — loses nothing. The owner must never need to leave the machine on overnight to preserve a progress point or accumulated learning. (`decisions:41` · decided · links: decisions:35, use_cases:2)
  - rationale: User, verbatim (2026-07-16): "One thing I would like is to track each step of work so that when I run out of tokens at 11pm I do not need to leave my pc on all night to avoid losing my progress point / learning." Becomes UC13 with a zero-loss NFR.
- Supersession lineage is bidirectional and machine-checkable: a superseding record carries a 'supersedes' pointer set immutably at creation, and the superseded record receives a one-time 'superseded_by' pointer plus timestamp at supersession. External readers determine live intent with a single check: superseded_by is null and the record is not retired. Record content remains immutable — the lineage stamp is a write-once lifecycle annotation, not a content edit. Applies to all supersedable records (Briefs, PlanRows, task-graph generations). (`decisions:42` · decided · links: decisions:39, use_cases:9, use_cases:11)
  - rationale: User (2026-07-16): "Obviously I prefer the idea to create a new updated record, but my concern is how does an external app examining the data know that the record is not live intent, should we add a field to mark entries as superseeded, ideally a field that points to the replacement record?" The bidirectional form (forward pointer too) is the engineer's addition so lineage can be walked in both directions without scans.
  - rejected: Reverse pointer only ('supersedes' on the new record), old record untouched — An external app must scan all newer records to learn a record is stale — exactly the user's concern.
  - rejected: Separate supersession index table, records byte-immutable — Liveness answer lives away from the record itself; an app reading a single file/row gets no signal, and index/record drift becomes a corruption class.
- Idempotency: every submission batch carries an idempotency key (content-hash dedup), so a retried or replayed batch can never create duplicate rows. (`decisions:43` · decided · links: decisions:28, use_cases:3)
  - rationale: Owner approved 2026-07-16 ("file it"). Motivated by lived failure: three upgrade attempts on decisions:6 in this very planning session left duplicate rows (decisions:25-27, documented in decisions:28).
- Concurrency: exactly one active writing session, enforced by an advisory lock with a heartbeat; a lock silent for 10+ minutes is claimable by a new session; read-only sessions are unrestricted. (`decisions:44` · decided · links: decisions:35)
  - rationale: Owner approved 2026-07-16 ("file it"); consistent with single-user scope (decisions:35). 10-minute heartbeat staleness is a configurable engineering default.
  - rejected: No lock — last writer wins — Silent clobbering between an interview session and a red-team session is a corruption class, not a policy.
  - rejected: Full multi-writer merge semantics — Out of scope: single-user system (decisions:35).
- Migration: plan files carry a schema version; before any migration the system snapshots a PlanVersion, then migrates forward and reports exactly what changed. Silent migration is forbidden. (`decisions:45` · decided · links: decisions:39, use_cases:2)
  - rationale: Owner approved 2026-07-16 ("file it"). The snapshot-first rule reuses the PlanVersion entity and honors the restore-from-last-good-version recovery path (requirements:11).
- Observability: every tool call and every failure is logged to a workspace log with the failure mode labeled (unavailable | slow | malformed | auth | partial), timestamps, and a result summary — so the owner can distinguish a hung engine from a corrupt store from a permission denial without reading code. (`decisions:46` · decided · links: decisions:40, use_cases:12)
  - rationale: Owner approved 2026-07-16 ("file it"). Log lives in the workspace (decisions:40) and is append-only, consistent with the JournalNote discipline.
- Git diffability of the plan store is not required: the SQLite plan file is committed to git as a binary artifact. History and audit needs are met by the store's own records — every entry uniquely ID'd, timestamped, documented, with supersession lineage — plus PlanVersion snapshots. No text mirror is generated. (`decisions:47` · decided · links: decisions:39, decisions:1)
  - rationale: User's actual words (2026-07-16): "Doesn't need git diffability, the sqlite data is by its nature historic, dated and documented." Resolves the open adjudication raised from decisions:39's "ideally diff" clause.
  - rejected: Deterministic JSONL text mirror written at snapshot/gate moments for git-diff readability — drift risk between mirror and database becomes a corruption class, and the store's own dated records already answer history questions
- All database access goes through a single backend-neutral storage interface owned by the storage-engine component; SQLite is the only v1 backend, and no other component issues SQL or touches the database file. Migrating to a more rigorous database later therefore touches exactly one component. (`decisions:48` · decided · links: decisions:1, requirements:49)
  - rationale: User's actual words (2026-07-16): "I suggest we have a wrapper for all dataabse calls so that if we need more robustness we can trivially migrate to a more rigorous database." Engineer's elaboration: the wrapper is the storage-engine's contract surface itself — services speak in typed operations (write batch, read selector, snapshot), never SQL.
  - rejected: Services issue SQL directly against SQLite — scatters SQL across every component, making a future database migration a cross-cutting rewrite
  - rejected: Full ORM layer (e.g. SQLAlchemy) — heavyweight dependency for a narrow, fully-known query surface; ORM abstractions still leak on migration and add a failure surface
- Observed prototype friction (critique baseline): a cold resume after a context clear cost 4k+ tokens of rebuilding, including dumping the entire plan database to a text file and parsing it, because plan_status serves only counts and no targeted row-read API exists. Successor countermeasure: status serves a compact digest (stage, gates, warnings, progress point) plus the current working set, and row contents are fetched by targeted selectors; a full-plan dump is never the default rehydration path. (`decisions:49` · decided · links: decisions:25, decisions:28, use_cases:2)
  - rationale: Directly observed in this session (2026-07-16) during the stage-6 resume. User, verbatim: "we just did a recovery from a clear and you used 4k+ tokens to get up to speed, including pulling the whole database into a text file that you obviously parsed, so we need a robust way to get status without ripping through the entire project." Recorded under the citation rule (decisions:25/27); extends the rehydration friction already documented in decisions:28(b).
- Architecture shape: a modular monolith — one Python process hosting one MCP stdio server over one SQLite plan file in the workspace; fifteen components in four layers (foundation: storage-engine, row-service, link-graph; planning: guidance, gap-engine, gate-engine, warning-service, conflict-service, validation-service, finding-service; execution: task-graph, brief-composer, revision-service; surface: session-service, mcp-surface). (`decisions:50` · decided · links: decisions:22, decisions:35, decisions:1, decisions:11)
  - rationale: Single-user system (decisions:35), zero-step deploy into the project repo (decisions:22), fully local (decisions:11): anything more distributed adds failure modes with no consumer. User approved the presented cut 2026-07-16 ("Rest seems good").
  - rejected: Separate planning and execution MCP servers — breaks the zero-step deploy of decisions:22 and doubles the operational surface for a single user
  - rejected: Multi-process service split — adds IPC failure modes with no consumer for the isolation in a single-user local tool
- Gap derivation, gate evaluation, and warning policy are three separate components (gap-engine, gate-engine, warning-service), not one merged quality engine. (`decisions:51` · decided · links: decisions:31, requirements:13, requirements:20, requirements:22)
  - rationale: They change for different reasons: gap clustering drives the interview, gates are deterministic exit criteria, and the warning lifecycle implements the owner's keep-pushing policy (decisions:31) consumed far beyond gate runs — at resume, finalization, red-team entry, handoff, and revision. User approved 2026-07-16.
  - rejected: One merged quality engine — interview drive, exit criteria, and nagging policy change for different reasons — a merge guarantees shotgun changes
  - rejected: Warnings folded into gate-engine — warnings are consumed at resume, finalization, and handoff, well beyond gate invocations
- Brief composition splits responsibility between tool and LLM: the tool computes the deterministic link-graph candidate closure; the composing LLM makes the task-specific selection; the contract mechanically rejects any composition that fails 100% candidate accounting (every candidate row either included or recorded-omitted) with an IncompleteAccounting error. (`decisions:52` · decided · links: decisions:34, requirements:36, requirements:44)
  - rationale: Implements decisions:34 (no token quotas; task-specific LLM judgment) while keeping the judgment auditable per requirements:44. The tool enforces honesty, not relevance. User approved 2026-07-16.
  - rejected: Tool-side relevance ranking or numeric budgets — owner explicitly ruled numeric proxies (tokens, percentages) meaningless in decisions:34
  - rejected: Free-form LLM selection without accounting — silent omission of relevant plan content is exactly the failure mode requirements:44 exists to kill
- Spikes and technical claims share one component (validation-service): spike registration/resolution for world-assumptions and classification/routing/outcomes for technical claims (software feasibility, scientific appropriateness, or both). (`decisions:53` · decided · links: decisions:33, use_cases:6, use_cases:10)
  - rationale: Both resolve uncertainty against external reality, share a register-execute-resolve lifecycle, and share the consequence machinery (refuted/failed outcomes raise conflicts on dependent rows). They would always change together. User approved 2026-07-16.
  - rejected: Separate spike and claim components — identical lifecycle and consequence machinery — two components that always change together for the same reason
- The observability log is owned by mcp-surface: an append-only, failure-mode-labeled (unavailable|slow|malformed|auth|partial) file in the workspace recording every tool call and failure with timestamps and result summaries. (`decisions:54` · decided · links: decisions:46, decisions:40)
  - rationale: mcp-surface is the choke point that sees every call and every failure, so ownership there needs no cross-component plumbing. Implements decisions:46. User approved 2026-07-16.
  - rejected: Standalone observability component — trivial in size and changes only when the tool surface changes — a component with no independent reason to exist
- Storage-layer error shape: every storage-engine error carries a machine-readable failure-mode label (unavailable|slow|malformed|auth|partial) plus mode-specific fields. The auth handling of dep_failure_modes:4 is delivered as StorageUnavailable with mode=auth, naming the path and the permission needed; the observability log records the same label. Self-review correction: contracts 1-8 name StorageUnavailable without spelling out the auth variant; this decision pins that shape rather than duplicating contract rows in a store without contract editing. (`decisions:56` · derived · links: dep_failure_modes:4, decisions:46, decisions:28)
  - rationale: Stage-6 self-review found the error names in storage contracts did not fully match stage-5 failure handling: auth is a distinct labeled mode a caller must distinguish from plain unavailability (fix the ACL vs. check the disk). Labeled variants keep one error name per contract while preserving the stage-5 semantics and the decisions:46 log taxonomy.
  - rejected: Distinct PermissionDenied error on every storage contract — the contract rows are already filed and the prototype has no contract-edit path; duplicating rows to add one error name creates the same duplicate-row mess documented in decisions:28
  - rejected: Leave auth folded into unavailable without a label — the owner must be able to distinguish a permission denial from a dead disk without reading code (decisions:46)
- Observed prototype friction (critique baseline): the stage-6 gate failed four contracts for missing requirement links and instructed "link it to the requirement(s) it satisfies or cut it" — but the toolset offers no way to do either: submit_contracts only creates (an id field is rejected as unknown), and no contract edit, supersede, or retire tool exists. The only sanctioned remedies create duplicate rows that leave the original holes in place. Successor requirement: every row-creating toolset must include a sanctioned amend/supersede path for the same row types, and gate fix instructions must name an operation the toolset can actually perform. (`decisions:57` · decided · links: decisions:25, decisions:28, requirements:67, requirements:68, requirements:65, requirements:66)
  - rationale: Directly observed in this session (2026-07-16) while closing stage-6 gate holes on contracts 3, 4, 8, and 51. Recorded under the citation rule (decisions:25/27); same class as the assumption-upgrade dead-end in decisions:28(a). Disclosed workaround: the four links values were corrected by a surgical, reversible edit of plan.db outside the tool API, with a backup taken first and the exact before/after values recorded here — before: contracts:3 ["decisions:44"], contracts:4 ["decisions:44"], contracts:8 ["decisions:45"], contracts:51 ["decisions:46","decisions:54"]; after: the same plus requirements:63, requirements:64, requirements:65, requirements:66 respectively.
- Verified on a real SMB share (spikes:1, Synology NAS, 2026-07-17): SQLite atomic commits survive process-kill on network-mounted workspaces in both DELETE and WAL journal modes (single client machine), but the naive rename-heartbeat advisory lock (decisions:44) is NOT SMB-safe — the heartbeat rename intermittently fails with a sharing violation when a reader holds the lock file open, silently starving the heartbeat so a live session's lock can be stolen. Consequence: local-disk workspaces are fully supported; network-mounted workspaces require a hardened lock protocol (heartbeat retry-on-sharing-violation, reader access that does not hold the lock file open, staleness threshold much greater than the heartbeat interval — the production 10 min vs ~30 s satisfies this) plus a resume-time warning that SMB carries an untested machine-crash durability caveat (synchronous=FULL was absorbed by client/NAS caching, commit p50 ~0 ms). (`decisions:58` · derived · links: decisions:44, dep_failure_modes:2, dependencies:1, spikes:1)
  - rationale: Spike 1 probe: 12/12 kill-injection rounds clean per journal mode per target, 20/20 O_EXCL claim races single-winner, but heartbeat PermissionError 13 on SMB (0 on local NTFS control); observed heartbeat age reached 6.24 s past the 6 s scaled stale threshold while the holder lived. Full evidence: spikes/001_do_sqlite_atomic_commits_and_an_advisory/RESULTS.md.
- On SMB network mounts, sharing-violation bursts against the writer-lock file remain bounded well within the production staleness margin: a hardened renewing writer (retry-on-sharing-violation) at 30 s renewal cadence never accumulates lease age approaching the 10-minute staleness threshold under sustained reader contention. (`decisions:59` · verified by spikes:2 · links: decisions:58, findings:8, requirements:67)
  - rationale: decisions:58 extrapolated this from spike 1's scaled thresholds — observed heartbeat age reached 5.45 s of a 6 s threshold WITH retry (91% of margin). The production ratio is ~20x larger, but burst clustering at production cadence is unobserved (findings:8). Spike 2 settles it.
- Brief composition is a two-step tool sequence executed by the planning session: (1) next_subtask returns the ready sub-task plus its full candidate closure; (2) the planning session's LLM — the actor that drives the planning tool and has read the plan — makes the BriefSelection and calls compose_brief; the resulting immutable brief is then served to the code engine. The tool itself never selects and the code engine never selects. **[significant]** (`decisions:60` · decided · links: contracts:55, contracts:68, decisions:52, decisions:12, findings:3)
  - rationale: Resolves finding 3's circular actor dependency: the engine cannot select from a closure it has never read, and the tool has no LLM access (non-goal decisions:12); the planning session is the only actor with both plan knowledge and tool access.
  - rejected: next_subtask composes the brief internally in one call — requires LLM access inside the tool — violates non-goal decisions:12
  - rejected: the code engine makes the BriefSelection — the engine has never seen the plan at selection time — circular
- The successor vendors the PlanTool rev-2 methodology content — the stage list, per-stage interview scripts, the engineer's mandate, per-stage mechanical gate criteria, and the gap-derivation rules — as versioned content assets carrying a content-revision stamp and an explicit update path. guidance, gap-engine, and gate-engine serve this vendored content; the executor never invents methodology at build time. **[significant]** (`decisions:61` · decided · links: components:4, components:5, components:6, decisions:14, findings:4)
  - rationale: Finding 4: the machinery to SERVE stage scripts/mandate/gates/gap rules had rows, but the methodology content itself had none — the executor would have had to invent the product's core IP at build time, the exact milestone-time re-planning failure this tool exists to prevent (decisions:14).
  - rejected: executor derives the methodology from first principles at build time — recreates the milestone-time re-planning failure the tool prevents (decisions:14)
  - rejected: hard-code the methodology in engine code — content fossilizes with no versioned update path when the methodology revises
- A revision freezes only the AFFECTED briefs and sub-tasks (the revision's impact set, requirements:54); implementation of unaffected sub-tasks continues while the plan is in 'revising' — start_implementation and complete_implementation are self-transitions in that state, and next_subtask keeps serving sub-tasks outside the impact set. (`decisions:62` · decided · links: sm_cells:186, sm_cells:187, requirements:54, uc_extensions:41, findings:6)
  - rationale: Owner's adjudication of finding 6, verbatim: "if we ever go multi-user in the future this would be essential." A global pause stalls the entire build during long multi-session walkthroughs (uc_extensions:44); affected-only matches requirements:54 and scales to concurrent users.
  - rejected: global implementation pause while any revision is open — stalls unrelated work for the whole walkthrough; loses hard once multi-user
  - rejected: composite implementing+revising state in the machine — state explosion for what self-transitions plus per-brief freeze flags express
- One SubTask is the implementation unit of exactly one contract: task-graph derivation produces one sub-task per contract, dependency edges map directly from contract_deps (the sub-task implementing a consumer depends on the sub-task implementing its provider contract), and split_subtask divides along a contract's declared surface — param subsets or error paths — when a brief proves too large. **[significant]** (`decisions:63` · decided · links: requirements:34, contracts:35, entities:9, contracts:40, decisions:32, findings:11)
  - rationale: Finding 11: granularity was the most consequential unstated input to brief sizing (decisions:32/34) — two implementers would derive incompatible graphs. One-contract-one-sub-task makes derivation deterministic, gives edges a mechanical source (contract_deps), and gives split_subtask a defined axis.
  - rejected: one sub-task per component — a component bundles many contracts — briefs blow past the size targets (decisions:32/34)
  - rejected: leave granularity to the executor — two implementers derive incompatible graphs from the same plan — the finding's exact defect
- v1 has exactly one plan tier, 'standard': the tier field remains on Plan as a forward-compatibility placeholder, drives no behavior in v1 (no gate, stage, or gap rule varies by tier), and initialization must not block on it — 'standard' is applied by default when unspecified. (`decisions:64` · decided · links: requirements:8, entities:1, uc_steps:2, findings:15)
  - rationale: Finding 15: tier was recorded and even stop-and-asked for at init, yet no row gave it a single behavioral meaning — blocking on semantically inert input is unjustified ceremony. Tier semantics are deferred until a second tier exists, at which point the behavior matrix becomes required rows.
  - rejected: define a multi-tier behavior matrix now — inventing distinctions with no current user need — pure speculation
  - rejected: drop the tier field entirely — cheap forward-compat placeholder; removal forces a schema migration later
- Network-mounted (SMB) workspace durability under session interruption remains unverified and will not be spiked further: the owner halted network-filesystem experimentation (2026-07-17). The plan absorbs the risk as already specified: network mounts are supported-with-warning (decisions:58), and requirements:69 surfaces the untested-durability caveat at every resume on a network mount. Local-disk workspaces remain the fully-supported path. (`decisions:65` · decided · links: spikes:3, decisions:58, requirements:69)
  - rationale: Owner, verbatim: "just forget about writing to nas boxes or network addresses and let's move on." Spike 3 closed inconclusive; per the spike rules an inconclusive verdict escalates to the owner as a risk decision — this is that decision.

## Spikes

- Do SQLite atomic commits and an advisory writer-lock heartbeat file behave correctly when the workspace sits on a network-mounted filesystem (SMB share), or must the tool document local-disk-only support? (`spikes:1`) — verdict: refuted
  - hypothesis: Expect partial failure: SQLite WAL mode is documented as unsafe on network filesystems (locking primitives unreliable over SMB/NFS), but journal=DELETE mode plus a separate lock file with atomic-rename claiming may survive. If WAL fails and DELETE-mode survives, the design consequence is a storage-engine backend setting; if both fail, local-disk-only is documented and resume warns on network paths.; method: Probe against a real SMB mount (Windows share mapped from this machine or a NAS path): (1) run concurrent-writer atomic-commit tests in WAL and DELETE journal modes, checking for corruption with PRAGMA integrity_check after kill-injection mid-commit; (2) exercise the advisory-lock claim protocol (create, heartbeat, stale-claim after silence) from two processes on the share, verifying no silent double-claim. No mocks — a local-disk run is the control, not the result.; budget: 2 hours
  - evidence: Probe vs a real Synology SMB share (\\DISKSTATION\homes\Al\plantool_spike), local NTFS as control, 2026-07-17. Observed: (1) atomic commits survived 12/12 random hard-kills in BOTH journal modes (DELETE and WAL) on SMB — integrity_check ok, zero orphan/short batches every round; (2) concurrent two-writer runs clean in both modes; (3) O_EXCL claim race: 20/20 rounds exactly one winner; (4) the rename-based heartbeat FAILED on SMB: os.replace onto the lock file intermittently raises PermissionError 13 (sharing violation) when the polling reader has it open — unhandled, this silently killed the holder's heartbeat and the lock was stolen from a live session (observed heartbeat age 6.24s > 6s stale threshold, claim 0.44s before holder death); with retry, observed age still reached 5.45s/6s. Local disk: zero heartbeat errors. Also observed: SMB WAL commit p50 ~0ms, i.e. synchronous=FULL is absorbed by client/NAS caching — durability vs machine crash untested and presumed weaker than local disk.
- Do SMB sharing-violation bursts on the writer-lock file stay bounded well within the production staleness margin (30 s renewal vs 10 min staleness) under sustained reader contention, or can bursts cluster long enough to starve a hardened retrying renewal? (`spikes:2`) — verdict: confirmed
  - hypothesis: With retry-on-sharing-violation and readers hammering open/read/close, worst-case lease age stays far below the 600 s staleness threshold (expect < 120 s) at production renewal cadence — if bursts cluster beyond that, decisions:58's 'production ratio satisfies this' extrapolation is refuted.; method: Probe against the real Synology SMB share (\\DISKSTATION\homes\Al\plantool_spike), based on spikes/001 probe.py: one writer renews the lock file every 30 s via atomic replace with sharing-violation retry; multiple reader processes hammer open/read/close on the lock file continuously; run >= 30 min wall clock; record every renewal burst (retry count, duration) and the maximum observed lease age; compare against the 600 s staleness threshold. Local NTFS control run for baseline.; budget: 2 hours
  - evidence: 24-min run vs real Synology SMB share (plus local NTFS control), production protocol at real cadence: 30 s renewals via atomic replace with retry-on-sharing-violation, 600 s staleness threshold, 3 hardened readers hammering open/read/close throughout, adversarial 250 ms-dwell reader added for the final 12 min. Observed: 48/48 renewals succeeded, zero give-ups; worst renewal under dweller load took 17 attempts / 7.94 s of continuous sharing violations; max lease age 37.94 s = 6.3% of staleness (hypothesis bound < 120 s). Sampler channel: max unretried violation streak 0.44 s (sampler degraded to ~2 s/cycle by SMB latency under load — renewal channel is authoritative). Local control: phase A spotless (1 attempt, <= 16 ms), worst 0.31 s with dweller. Reads saw 0.33% transient errors. Bursts are contention-driven and bounded ~16x under the margin.
- Does a forced SMB session drop while a SQLite commit is in flight leave a database on the network share consistent and recoverable after reconnect — every interrupted transaction either fully applied or fully rolled back, and no acknowledged commit lost? (`spikes:3`) — verdict: inconclusive
  - hypothesis: Consistency holds but acknowledged-commit durability may not: SQLite's journal protocol should recover an interrupted network write on reconnect (integrity_check ok, no partial batches), while spike 1's untested caveat — client/NAS caching absorbing synchronous=FULL (commit p50 ~0 ms) — predicts that some commits acknowledged to the writer just before the drop may vanish. Falsified on the consistency side by corruption or partial batches; on the durability side by surviving-marker count < acknowledged-commit count.; method: Probe against the real Synology share (\\DISKSTATION\homes\Al\plantool_spike2): a writer loops transactional batches (20 rows + marker, synchronous=FULL) on a DB under the UNC path, logging each acknowledged commit; mid-commit-loop the orchestrator force-drops the client SMB session (net use \\DISKSTATION\... /delete /y), waits, reconnects, then runs PRAGMA integrity_check plus orphan/short-batch queries and compares surviving markers against acknowledged commits. Repeated rounds in journal_mode DELETE and WAL. Run strictly after spike 2 (the drop would sever spike 2's writer).; budget: 90 minutes
  - evidence: Partial execution only: 9 forced-disconnect rounds ran against the real Synology share (6 journal=DELETE, 3 WAL) before the owner halted network-filesystem spiking. Every completed round: tracked connection force-deleted mid-commit-loop, writer blocked in SMB I/O (no clean error — killed after 30 s), share reconnected, and the DB reopened; per-round integrity detail was lost to an orchestrator defect (results truncated to 300 chars, full JSON written only at end of a run that later hung on WAL-mode SMB backoff). No corruption was observed in what was captured, but acknowledged-commit loss — the actual question — was never measured. Budget/authorization ended: inconclusive.

## Conflicts

- [resolved] CRUD cell crud_grid:51 records U on entity 'Brief' as n/a ("Immutable; regeneration creates a superseding brief"), but use-case step uc_steps:35 in 'Revise a finalized plan' ("System bumps the plan version and runs a link-graph impact analysis, enumerating every row, brief, and built sub-task transitively affected by the change.") appears to update it. One of the two is wrong — present both to the user and record the adjudication. (`conflicts:1`, engine-filed, refs: crud_grid:51, uc_steps:35) — Revised (clarification, immutability upheld — owner adjudicated): impact analysis in uc_steps:35 is a pure read of the Link graph; it enumerates affected briefs without mutating them. Effects on briefs are expressed as new superseding briefs with bidirectional lineage pointers per decisions:42 / requirements:61; 'freezing' lives on the SubTask (block transition), never on the Brief.
- [resolved] CRUD cell crud_grid:51 records U on entity 'Brief' as n/a ("Immutable; regeneration creates a superseding brief"), but use-case step uc_steps:37 in 'Revise a finalized plan' ("Owner adjudicates each repercussion; accepted changes update rows with provenance, affected gates re-run, affected briefs regenerate, and built work needing rework is flagged.") appears to update it. One of the two is wrong — present both to the user and record the adjudication. (`conflicts:2`, engine-filed, refs: crud_grid:51, uc_steps:37) — Revised (clarification, immutability upheld — owner adjudicated): 'affected briefs regenerate' in uc_steps:37 means new Brief records are created that supersede the old ones; the old brief is stamped once with superseded_by per decisions:42 (a write-once lifecycle annotation, not a content update). The old brief's content stays frozen for defect forensics.
- [resolved] CRUD cell crud_grid:51 records U on entity 'Brief' as n/a ("Immutable; regeneration creates a superseding brief"), but use-case step uc_steps:38 in 'Checkpoint work so an abrupt session end loses nothing' ("During any work — planning, revision, or implementation orchestration — the system durably records each unit of work the moment it completes: row submissions, decisions, briefs served, sub-task status changes, and informal learnings.") appears to update it. One of the two is wrong — present both to the user and record the adjudication. (`conflicts:3`, engine-filed, refs: crud_grid:51, uc_steps:38) — Revised (clarification, immutability upheld — owner adjudicated): 'records each unit of work ... briefs served' in uc_steps:38 creates a JournalNote/serving record referencing the brief; the Brief itself is not updated.
- [resolved] CRUD cell crud_grid:59 records U on entity 'Link' as n/a ("Immutable edge; supersede the owning row instead"), but use-case step uc_steps:35 in 'Revise a finalized plan' ("System bumps the plan version and runs a link-graph impact analysis, enumerating every row, brief, and built sub-task transitively affected by the change.") appears to update it. One of the two is wrong — present both to the user and record the adjudication. (`conflicts:4`, engine-filed, refs: crud_grid:59, uc_steps:35) — Revised (clarification, immutability upheld — owner adjudicated): impact analysis traverses Link edges read-only; edges are never mutated. Link lineage follows the owning row's supersession per decisions:42 — a superseding row carries its own edges, and the old row's edges stay frozen with it.
- [resolved] Spike #1 refuted its hypothesis ("Expect partial failure: SQLite WAL mode is documented as unsafe on network filesystems (locking primitives unreliable over SMB/NFS), but journal=DELETE mode plus a separate lock file with atomic-rename claiming may survive. If WAL fails and DELETE-mode survives, the design consequence is a storage-engine backend setting; if both fail, local-disk-only is documented and resume warns on network paths.") — linked row decisions:55 records the disproved assumption and needs correcting. (`conflicts:5`, engine-filed, refs: decisions:55, spikes:1) — decisions:55 superseded by decisions:58 — the assumption is replaced by the spike-verified statement: atomic commits hold under process-kill on SMB, the naive rename-heartbeat lock does not; local-disk fully supported, network mounts need a hardened lock protocol and a durability warning. Evidence: spikes/001_.../RESULTS.md.
