# Scenarios

This page tells ten short stories. Each one follows an invented project from the moment something arrives (a request, an answer, a change, a bug report) to the moment you have what you need. You see what to type, what Sentinel shows, and what it means. Read the one that matches your situation, or read them in order to learn the whole lifecycle.

> [!NOTE]
> Every company, person, number and quote below is invented and marked FICTIONAL SAMPLE. Nothing here is real client data. Every output is shortened from a real run of the current version of Sentinel on that sample.

## How to read these scenarios

Each scenario has the same shape:

- **The situation:** who you are, what arrived, and what you want.
- **Steps:** what you do, what Sentinel shows, and what it means.
- **What you have now:** the files and the state you end with.

A few terms come back often. A **gap** is an open question Sentinel found in your material. The **brief** is the project brief, the document Sentinel compiles from your evidence. **Health** is `CLEAN` when every generated file still matches what it was built from, and `DIRTY` when something needs regenerating. The [glossary](00-user-guide.md#glossary) has the rest.

**Typing a command.** The steps show the chat form, for example `/ingest ACME_PORTAL --source input/portal-request.md`. In a terminal, put `python -m sentinel` in front (`python -m sentinel /ingest ...`). In Codex and with the Claude Code plugin, put `sentinel` in front (`sentinel /ingest ...`). In a Claude Code clone, `/init` and `/doctor` are also Claude Code's own commands; if the wrong one starts, send `/sentinel /init ACME_PORTAL` or `/sentinel /doctor`. You can also just say what you want ("the client answered the gaps in this file; process them") and the agent picks the command. See [Chat commands](11-chat-commands.md).

**Reading the outputs.** Sentinel answers with structured data; in chat the agent summarizes it. The blocks under *Sentinel shows* keep only the lines that matter, as `name: value`. Error messages are quoted as Sentinel prints them.

**Who writes the JSON files.** Several commands read a small JSON or Markdown file that an agent writes for you (`/annotate`, `/challenge`, `/scrutinize`, `/assume`, `/self-review`, `/split --propose`, `/prototype --trace`, `/harvest`, `/implementation-feedback`, `/refine-backlog`, `/sync --analysis`). You ask in plain words; the matching [skill](04-codex-skills-guide.md) writes the file, with exact quotes from your evidence, and runs the command. In a plain terminal you write the file yourself.

**Two rules hold everywhere.**

1. **Generated files change only through commands.** The gaps document, requirements, brief, specs and backlog are written by Sentinel. To change them, give Sentinel new evidence: answers through `/resolve-gaps`, new material through `/sync`. A hand edit is flagged by `/health`.
2. **A refusal is information.** A command that stops says why, usually with a `next step:` line. `/next ACME_PORTAL` prints the next step at any time. Scenario 4 shows every kind of refusal.

### Which scenario is yours?

<!-- Diagram source: user_guide/images/scenario-picker.mmd (re-render with tools/render_doc_diagrams.py) -->
![Which scenario to read: with no project yet, triage a pile of requests or start with scenario 1; with a project, pick scenario 2 to 8 by what happened.](images/scenario-picker.svg)

| Your situation | Scenario |
| --- | --- |
| One clear request, nothing exists yet | [1. A new customer portal](#scenario-1-a-new-customer-portal) |
| The request is one page of adjectives | [2. Thin intake, several answer rounds](#scenario-2-thin-intake-several-answer-rounds) |
| New material arrives while you work (a change request, meeting notes, a new version of a document) | [3. A requirement changes mid-flight](#scenario-3-a-requirement-changes-mid-flight) |
| A command refused | [4. A command refuses, and how to recover](#scenario-4-a-command-refuses-and-how-to-recover) |
| The scope is too big for one release | [5. Splitting a release into r1, r2 and r3](#scenario-5-splitting-a-release-into-r1-r2-and-r3) |
| Design sent a clickable HTML prototype | [6. A prototype arrives](#scenario-6-a-prototype-arrives) |
| The project extends a system that already exists in code | [7. An existing system](#scenario-7-an-existing-system) |
| The team starts building | [8. Building starts](#scenario-8-building-starts) |
| The client changes a rule after the backlog is ready | [9. The client changes scope after the backlog is ready](#scenario-9-the-client-changes-scope-after-the-backlog-is-ready) |
| A developer finds something the backlog does not cover | [10. Development finds a hole](#scenario-10-development-finds-a-hole) |
| Something small: triage, domain teams, exports, the portfolio page | [Smaller situations](#smaller-situations) |

| Role | Start with |
| --- | --- |
| Business analyst | 1, 2, 3, 9, 4 |
| Product manager | 1, 5, 6, 9, and the readiness view in 1 |
| Developer | 8, 10, 4 |

For one procedure per situation, without the story, see [Workflows](03-workflows.md).

---

## Scenario 1: A new customer portal

### The situation

You are the business analyst for ACME, an insurer. ACME wants a portal where policyholders sign in, file a claim and follow it. Nothing exists yet. You received one short email, saved as `input/client_requirement/portal-request.md`. You want a brief, a PRD, a backlog and a checked workspace that a team can build from.

```text
# ACME Claims Portal: initial request (FICTIONAL SAMPLE)

Policyholders should sign in to a web portal, file a claim with photos and
documents, and follow its status. Claims adjusters review and approve claims.
Large claims need a second approval. The portal must integrate with our policy
system and be secure and compliant. Details to be defined later.
```

The text is vague on purpose. That is normal for a first request, and finding what is missing is Sentinel's first job.

### Steps

1. **Check the installation once.**

   ```text
   /doctor
   ```

   Sentinel shows `verdict: PASS`. A warning about the optional vector memory is fine: Sentinel falls back to a built-in search.

2. **Create the project and load the request.**

   ```text
   /init ACME_PORTAL
   /ingest ACME_PORTAL --source input/client_requirement/portal-request.md
   /status ACME_PORTAL
   ```

   `/init` creates the project folder (the *workspace*). `/ingest` keeps a redacted copy of the email (anything that looks like a password or key is masked; text that reads like an order to the agent is flagged and ignored) and lists what is missing. `/status` shows:

   ```text
   health: DIRTY
   readiness_stage: CLIENT_RESPONSE_NEEDED
   verdict: NOT_READY
   blockers: 3 blocking gap(s) open: GAP-ACCEPTANCE, GAP-SCOPE, GAP-USERS.
   gap_counts: open 28, blocking_open 3
   next_step: This project compiles the brief v2. Confirm its profile and genesis once with /brief; the suggested values come from the raw input, so check them first.
   ```

   **What it means:** a new project always starts `NOT_READY` and `DIRTY`. That is the starting point, not an error. Sentinel found 28 open questions, three of them blocking.

3. **Confirm the brief settings.** The *profile* says what kind of thing you are building; the *genesis* says whether it starts from nothing or from an existing system. Sentinel proposes values from keywords in the email:

   ```text
   /brief ACME_PORTAL
   ```

   ```text
   confirmed: false
   proposal: profiles UI, genesis greenfield, validation_direction to-build
   gap: GAP-BRIEF-PROFILE (critical, blocking) - Confirm the brief profile(s) and genesis
   ```

   Do not accept the proposal blindly; it is a guess from keywords. Here the portal has screens (`UI`), talks to the policy system (`API`) and handles regulated data (`REG`), so you confirm:

   ```text
   /brief ACME_PORTAL --profile UI,API,REG --genesis greenfield --validation-direction to-build
   ```

   Sentinel shows `confirmed: true`. From now on the brief is recompiled every time an answer arrives. Until you confirm, `/maturity` stays `BLOCKED` and `/specs` refuses (scenario 4 shows that refusal).

   <details><summary>The brief settings in detail</summary>

   | Setting | Meaning | Values |
   | --- | --- | --- |
   | `--profile` | What kind of thing this is; it decides which places of the brief apply. Comma-separate several. | `UI` screens, `API`, `BAT` batch jobs, `INT` third-party integration, `MIG` migration, `REG` regulated, `MT` multi-tenant |
   | `--genesis` | Where it starts. `MIG` requires `brownfield-replacement`. | `greenfield`, `brownfield-integration`, `brownfield-extension`, `brownfield-replacement` |
   | `--validation-direction` | Is the brief about something to build, or something already built? | `to-build`, `built` |

   A project created with `/init --brief-version 1` keeps the older brief layout and skips this step.

   </details>

4. **Send the client the questions.**

   ```text
   /gaps ACME_PORTAL
   /export ACME_PORTAL --artifact gaps --format interview
   ```

   `/gaps` rebuilds the gaps document, your working file (`01_discovery/gaps.md`). The export writes the file you send: `08_context_packs/exports/gaps-interview.md`. It holds every open question, blocking ones first, in plain words with empty answer fields:

   ```text
   ## Blocking questions

   ### GAP-USERS
   **1.** Which users, personas, or roles are in scope?
   - Answer:
   - Owner / source:
   - Evidence or reference:
   - Decision status:
   ```

   The file asks the client to keep each reference code (`GAP-USERS`) with the answer. Read it before sending and drop any question that does not fit.

5. **Process the answers.** The client fills in the file. For the question about how to prove the portal works (`GAP-ACCEPTANCE`), the claims director confirms four behaviours, each written as "When ..., the system shall ...":

   ```text
   When a policyholder submits a claim with photos, the system shall register the claim and show its reference number.
   When an adjuster approves a large claim, the system shall route it to a senior adjuster for the second approval.
   While a claim is under review, the system shall show its current status to the policyholder.
   If the policy system is unavailable, then the system shall keep the claim as received and retry the policy lookup.
   ```

   The four sentences go in the answers file, one per bullet under the `GAP-ACCEPTANCE` answer:

   ```markdown
   ### GAP-ACCEPTANCE
   - Answer:
     - When a policyholder submits a claim with photos, the system shall register the claim and show its reference number.
     - When an adjuster approves a large claim, the system shall route it to a senior adjuster for the second approval.
     - While a claim is under review, the system shall show its current status to the policyholder.
     - If the policy system is unavailable, then the system shall keep the claim as received and retry the policy lookup.
   - Owner / source: Claims director, workshop
   - Evidence or reference: workshop minutes, 12 March
   - Decision status: confirmed
   ```

   You process the answers file, then check maturity:

   ```text
   /resolve-gaps ACME_PORTAL --source input/interactions/answered-gaps.md
   /maturity ACME_PORTAL
   ```

   Sentinel shows each gap it closed, then `readiness: READY_FOR_SPECS`. Each behaviour became one testable requirement (`REQ-EARS-001` to `REQ-EARS-004`) and, later, one story.

   **What it means:** a gap closes only when the answer is substantive **and** its decision status is confirmed (or not applicable). "TBD" or "depends" keeps it open. Every closure needs an `Evidence or reference` line; a closure without one is listed as a finding. Each "When ..., the system shall ..." sentence in a confirmed answer becomes its own requirement, so one answer can carry several behaviours. Answer each question once: if a file has two sections for the same question, Sentinel merges them and says so.

   <details><summary>For the technical reader</summary>

   The result lists `closed`, `partially_closed`, `open`, `closure_findings` and `knowledge_metabolism` (assumptions validated, artifacts now stale). In a brief v2 project `brief_v2.rewritten_places` lists the places each answer filled. The behaviours are normalized into the EARS table of `02_requirements/requirements.md`.

   </details>

6. **Close what is left, then generate the PRD, specs and backlog.** `/status` now says *No blocking gap is open. Close the remaining ones if you can, or move on: run /brief, then /specs.* Two small brief questions are left (`GAP-BRIEF-S7`, `GAP-BRIEF-S9`); you answer them in a second round, then generate:

   ```text
   /resolve-gaps ACME_PORTAL --source input/interactions/answered-gaps-2.md
   /specs ACME_PORTAL
   /backlog ACME_PORTAL
   /quality ACME_PORTAL
   ```

   ```text
   /backlog   story_count: 4, epic_count: 1
   /quality   count: 4, verdict: PARTIAL
   ```

   `/specs` writes the PRD (`03_specs/prd.md`), a compact index (`03_specs/specs.md`) and one unit per behaviour (`03_specs/units/SPEC-U-001.md` ...). `/backlog` writes an epic, one story per unit (`04_backlog/US-001.md` ...), a slice plan and the packs an implementation agent reads. `/quality` writes one test case per story and an audit; `PARTIAL` means some stories still miss Definition-of-Ready items, listed in `05_quality/backlog_readiness_audit.md`.

7. **Check everything before anyone builds.**

   ```text
   /trace ACME_PORTAL
   /health ACME_PORTAL
   /validate ACME_PORTAL
   /status ACME_PORTAL
   /next ACME_PORTAL
   ```

   ```text
   /health    verdict: CLEAN
   /validate  verdict: VALID
   /status    verdict: READY_WITH_WARNINGS
   /next      Validate and hand off: The backlog and its quality check are done. Run /validate, export what you hand off with /export, and track each story with /story-status.
   ```

   `/validate` may also print advisory warnings about thin content; they do not change the verdict. The two brief questions from step 6 can show as open again after the recompile; they are not blocking and do not stop the verdict.

8. **Show it to a manager or the client.**

   ```text
   /view ACME_PORTAL --artifact readiness
   /view ACME_PORTAL --artifact prd
   ```

   Each writes a read-only HTML page under `08_context_packs/views/` (add `--open` to open it in the browser). The readiness view answers "what is still missing, and from whom?". A recipient shown as unassigned means no stakeholder is registered for that area (scenario 2 adds them).

### What you have now

A confirmed brief, a PRD with four spec units, a backlog of four stories with test cases, health `CLEAN`, `/validate` `VALID` and a `READY_WITH_WARNINGS` verdict. Next: scenario 8 when the team starts building.

**Decision points.** The profile and genesis are a business decision: if the portal extended an existing system, the genesis would be `brownfield-extension` and scenario 7 would apply. When the client cannot answer a gap, you can leave it open, ask a domain team (scenario 7), or proceed on a recorded assumption (scenario 2). If `/specs` says the maturity is `BLOCKED`, go back to step 5; there is no way around it.

---

## Scenario 2: Thin intake, several answer rounds

### The situation

ACME's finance team wants an internal expenses tool (`ACME_EXPENSES`). Their note is one paragraph of adjectives. You want to find what is missing, send each question to the right person, and run short answer rounds until a team could start.

```text
# Expenses tool (FICTIONAL SAMPLE)

We need an internal tool where employees submit expenses and a manager approves
them. Big expenses need an extra approval. Finance exports everything. It has to
integrate with our HR system. Obviously it must be secure and compliant.
```

### Steps

1. **Create the project and confirm the settings.**

   ```text
   /init ACME_EXPENSES
   /ingest ACME_EXPENSES --source input/client_requirement/expenses-note.md
   /brief ACME_EXPENSES --profile UI,INT --genesis greenfield --validation-direction to-build
   /status ACME_EXPENSES
   ```

   ```text
   verdict: NOT_READY
   blockers: 4 blocking gap(s) open: GAP-ACCEPTANCE, GAP-OBJECTIVE, GAP-SCOPE, GAP-USERS.
   gap_counts: open 33, blocking_open 4
   next_step: Send the client the interview script (/export --artifact gaps --format interview) and run /resolve-gaps when answers return.
   ```

2. **Ask the agent to read for what the checklist missed.** In chat:

   > Read the raw requirement for ACME_EXPENSES and add the gaps the checklist missed, quoting the exact text for each. Then run a pre-mortem.

   The agent writes two small files and runs:

   ```text
   /annotate ACME_EXPENSES --source input/interactions/analysis.json
   /challenge ACME_EXPENSES --source input/interactions/findings.json
   ```

   ```text
   /annotate   merged: GAP-EXPENSE-THRESHOLD, GAP-HR-DIRECTION, GAP-FINANCE-EXPORT-FORMAT
   /challenge  merged: GAP-AUDIT-TRAIL
   ```

   Each new gap quotes the note word for word ("Big expenses need an extra approval"); a quote that is not in the note is refused. These commands only add questions; none of them closes one.

3. **Record your decision on each gap the agent raised.**

   ```text
   /gaps ACME_EXPENSES --id GAP-EXPENSE-THRESHOLD --disposition accepted
   /gaps ACME_EXPENSES --id GAP-FINANCE-EXPORT-FORMAT --disposition irrelevant --reason "Finance confirmed the export is out of the MVP"
   ```

   A disposition (`accepted`, `rejected`, `irrelevant`) records what you think of a gap an agent raised, so the false-alarm rate stays visible. Two things to know:

   - `rejected` and `irrelevant` need `--reason`. Without it Sentinel says: *--disposition irrelevant needs --reason: say why it was a false alarm.*
   - A disposition does not close the gap; only an answer does. And it works only on gaps an agent raised. On a checklist gap such as `GAP-TECH-NFR` Sentinel refuses: *GAP-TECH-NFR has origin 'checklist'; a disposition applies only to gaps an agentic channel raised (agent, challenge, scrutiny, ...).*

4. **Register who answers what.**

   ```text
   /stakeholders ACME_EXPENSES --add --name "Finance Controller" --domain business --topic "approval thresholds"
   /stakeholders ACME_EXPENSES --add --name "HR Systems Lead" --domain technical --topic "HR integration"
   /stakeholders ACME_EXPENSES
   ```

   Sentinel gives each person an id (`STK-001`, `STK-002`). From now on the interview script groups questions by person. Sentinel never invents an owner: a question with no matching person stays under *Questions with no contact named yet*.

5. **Plan round 1: the five questions that matter most.**

   ```text
   /gaps ACME_EXPENSES --top 5
   ```

   Sentinel writes `01_discovery/gap_round.md`:

   ```text
   5 of 37 open gaps. One decision per question; the recommended option is an inference and never applies by itself.

   ## 1. GAP-SCOPE (client, critical)
   ## 2. GAP-EXPENSE-THRESHOLD (synthesis, high)
      - A. Confirm `Big expenses need an extra approval` is in scope and answer the missing detail. (recommended, inferred)
      - B. Confirm it is context-only, out of scope, or pending, and state the boundary.
      - Leave pending
   ## 3. GAP-OBJECTIVE (client, high)
   ...
   ```

   Ask these five in the meeting. For a written round, the interview script works too:

   ```text
   /export ACME_EXPENSES --artifact gaps --format interview
   ```

   The script holds **every** open question, not only the five of the round, grouped by person:

   ```text
   ## Blocking questions
   **Questions for Finance Controller**
   ### GAP-EXPENSE-THRESHOLD
   **Questions for HR Systems Lead**
   ### GAP-HR-DIRECTION
   **Questions with no contact named yet**
   ### GAP-SCOPE
   ```

6. **Process round 1.**

   ```text
   /resolve-gaps ACME_EXPENSES --source input/interactions/round1-answers.md
   ```

   Sentinel shows the five gaps it closed and `gap_counts: open 32, closed 5, blocking_open 3`. Each closure needs an `Evidence or reference` line. Brief questions (`GAP-BRIEF-S3` and similar) are answered one line per place, starting with its number: `3.1: ... 3.2: ...`.

7. **Record an assumption when the team must move on.** The threshold for the extra approval is still unknown, but the team wants to start. In chat:

   > We proceed assuming one manager approves every expense for now. Register it for ACME_EXPENSES as a BA-owned assumption, high risk, citing the note.

   ```text
   /assume ACME_EXPENSES --source input/interactions/assumptions.json
   ```

   ```text
   accepted: ASM-SINGLE-APPROVER
   test_before_advancing_ids: ASM-SINGLE-APPROVER
   ```

   An assumption needs a human owner ("AI" is not one), a risk and an exact quote. It stays visible as an assumption, never as a fact. `/status` now warns *Test before advancing (high risk, high uncertainty): ASM-SINGLE-APPROVER.* That is a signal, not a block. Scenario 9 shows what happens when the client later contradicts an assumption.

8. **Round 2, then check whether a team could start.**

   ```text
   /gaps ACME_EXPENSES --top 5
   /resolve-gaps ACME_EXPENSES --source input/interactions/round2-answers.md
   /self-review ACME_EXPENSES --sufficiency --source input/interactions/sufficiency.json
   /maturity ACME_EXPENSES
   ```

   The sufficiency check is an independent read of the brief alone. For each place it says covered, missing, ambiguous or contradictory, and opens one `GAP-SUF-...` question per problem:

   ```text
   /self-review  counts: covered 1, missing 1; sufficient: false; gaps_opened: GAP-SUF-C41CF46B
   /maturity     readiness: BLOCKED; blocking_gaps: GAP-ACCEPTANCE, GAP-HR-DIRECTION, GAP-AUDIT-TRAIL
   ```

   **What it means:** three blocking questions are still open. Run another round with the people they belong to.

### What you have now

A project whose questions are routed to named people, two answer rounds on record, one visible assumption, and a clear list of the three blocking questions left. When `/maturity` says `READY_FOR_SPECS` and a sufficiency round reports nothing missing, continue with scenario 1, step 6.

**Decision points.** One `/annotate` pass is the floor; add `/challenge` when the request looks complete but untested; add `/scrutinize` when the project has domain context (scenario 7). Ask in rounds of about five: a wall of questions gets shallow answers. Assume only when you decide to, and write down who owns the risk.

---

## Scenario 3: A requirement changes mid-flight

### The situation

`ACME_PORTAL` from scenario 1 has a brief, specs and a backlog. Now three things arrive in one week: a change request (policyholders must sign in through ACME's identity provider), the notes of a steering meeting, and a new version of ACME's data-handling rules. You want to absorb all of it without silent scope creep.

### Steps

1. **Register the change request.**

   ```text
   /sync ACME_PORTAL --source input/interactions/change-sso.md --note "client adds SSO"
   ```

   ```text
   source_id: F-04
   merged_gaps: []
   Prose is stored and indexed, not interpreted: 2 line(s) changed nothing. Rewrite them as gap answers (### GAP-...) or pass a cited analysis with /sync --source NOTE --analysis FILE.
   ```

   **What it means:** `/sync` registered the note as source `F-04` (every file Sentinel has read so far has its own number) and wrote an impact report next to the stored copy (`07_changes/00_client_responses/change-sso_impact_report.md`). It opened no new question: a question that quotes a word from the file (such as "auth" or "batch process") opens only when the new file itself says that word without its detail, and this note does not. It did **not** rewrite the brief from the prose: Sentinel never guesses what a sentence changes. The report's *Closed Gaps Detected Again* section says *Nothing is reopened here; a change reopens a gap only through a cited analysis.* To change something already confirmed, the agent writes a cited analysis and you confirm it; scenario 9 shows that path.

2. **See what is now out of date.**

   ```text
   /health ACME_PORTAL
   /backlog ACME_PORTAL
   ```

   ```text
   /health   verdict: DIRTY
             Knowledge changed after downstream artifacts were generated; refresh affected brief/PRD/spec/backlog before implementation handoff.
   /backlog  sentinel error: Cannot run /backlog while project health is DIRTY: knowledge changed after project-brief.md, prd.md, specs.md, BACKLOG.md, implementation_readiness.json were generated. Run /brief, then /specs, then /backlog.
             next step: Run /brief, then /specs, then /backlog.
   ```

   **What it means:** the backlog was built before the change. Sentinel names the files that are out of date and the commands that rebuild them, in order. You will do that in step 5, after the open questions are answered.

3. **Digest the meeting notes.** A transcript or a long mail mixes answers, decisions and small talk. The digest sorts it:

   ```text
   /sync ACME_PORTAL --source input/interactions/steering-meeting.md --digest
   ```

   Sentinel writes `07_changes/01_meetings/steering-meeting_interaction_digest.md` with six sections: candidate answers to open gaps, decision candidates, new gaps, assumption contradictions, an impact matrix, and possible changes to what was confirmed. Its first line says *This digest proposes and routes; it never applies.* For these notes every section says *None*: the scan found no line shaped like an answer. You (or the agent) turn what matters into gap answers. Before you confirm an answer, check who said it: a detected line can be a passing remark, not the owner's answer.

4. **Say which version of a document governs.** The data-handling rules arrived as v1 and then v2 under the same file name:

   ```text
   /sync ACME_PORTAL --source input/client_requirement/compliance-policy.md --note "compliance rules v1"
   /sync ACME_PORTAL --source input/client_requirement/compliance-policy.md --note "compliance rules v2"
   /sources ACME_PORTAL
   ```

   ```text
   unconfirmed_versions: F-07 version_of F-06
   F-07 ... candidate new version of F-06, not confirmed
   ```

   Sentinel noticed a known file with new content and opened a new row, but **it never assumes the newest version governs**. You decide and record it:

   ```text
   /sources ACME_PORTAL --id F-06 --superseded-by F-07
   ```

   Sentinel shows `superseded: 1` and no unconfirmed versions. When two sources disagree on a topic, ask `/sources ACME_PORTAL --precedence compliance --between F-06,F-07`. Here the answer is `status: unresolved`: no recorded rule decides between two client documents, so you take the question back to the client.

5. **Answer the open questions, then regenerate upstream first.**

   ```text
   /resolve-gaps ACME_PORTAL --source input/interactions/sso-answers.md
   /brief ACME_PORTAL
   /specs ACME_PORTAL
   /backlog ACME_PORTAL
   /quality ACME_PORTAL
   /health ACME_PORTAL
   ```

   After the answers, `/backlog` would say *Run /specs, then /backlog.*: the brief was already recompiled by the answers, so the list got shorter. Once the commands have run in order, `/health` is `CLEAN` again.

   Read the change records in `07_changes/04_regeneration/`: here one for the spec units, one for `specs.md` and one for the epic. If stories were already Ready, read `04_backlog/acceptance_criteria_deltas.md` before anyone builds: acceptance criteria that changed after they were frozen are marked `ADDED`, `MODIFIED` or `REMOVED`.

   <details><summary>For the technical reader</summary>

   `/specs` and `/backlog` print `foundation_warnings`. They are checked after the command has run, so they list only what is still out of date (*Foundation for /backlog may be STALE: `specs` was generated before its source(s) changed ...*), never the file the command just rewrote. In this order of commands the list is empty.

   </details>

6. **Pull focused context when a question comes up.**

   ```text
   /retrieve ACME_PORTAL --query "single sign-on identity provider" --workflow sync --write-pack
   ```

   Sentinel saves a small context pack (`08_context_packs/sync.json`) with the passages that match, instead of loading the whole workspace. Without `--write-pack` the matches print to the screen.

### What you have now

Every new document registered as a numbered source, the governing version recorded, the new questions answered, and the brief, specs and backlog regenerated with health `CLEAN`.

**Decision points.** Answers to existing gaps go through `/resolve-gaps`; new or unmapped information goes through `/sync`. Which version governs is always a person's call. Regenerate only what the refusal or `/health` names. In a release series (scenario 5), `/split --move` moves a unit between releases.

---

## Scenario 4: A command refuses, and how to recover

### The situation

You typed a command and it stopped. This scenario shows each kind of refusal as Sentinel prints it, what it means, and the one thing to do. The project is `ACME_PORTAL`.

Three commands always help:

```text
/next ACME_PORTAL
/status ACME_PORTAL
/status ACME_PORTAL --full
```

`/next` prints the one next step with its command. `/status` leads with the verdict and what blocks it; `--full` adds the details.

### 4a. The project or its first source is missing

```text
sentinel error: Workspace not found: ACME_PORTAL. Run /init ACME_PORTAL first.
```

```text
sentinel error: Cannot generate downstream artifacts before /ingest creates discovery artifacts.
next step: Run /ingest first.
```

Do what the message says: `/init`, then `/ingest` with the first file.

### 4b. `/specs` refuses because questions are still blocking

```text
/specs ACME_PORTAL
```

```text
sentinel error: Cannot generate specs while requirement maturity is BLOCKED.
```

A blocking gap is open. Ask `/next`. If the brief settings were never confirmed, it says *Confirm the brief settings* and suggests a command with values guessed from the request; check them, then run it:

```text
/brief ACME_PORTAL --profile UI,API --genesis greenfield
```

If `/specs` still refuses, `/next` now says *Waiting for client answers: Send the client the interview script (/export --artifact gaps --format interview) and run /resolve-gaps when answers return.* Do that (scenario 1, steps 4 and 5).

### 4c. `/backlog`, `/quality` or `/refine-backlog` refuses because health is `DIRTY`

These three commands refuse while health is `DIRTY`. The message says why and what to do. There are three forms:

- **Something changed upstream.** The message names the out-of-date files and the commands that rebuild them, in order:

  ```text
  sentinel error: Cannot run /backlog while project health is DIRTY: knowledge changed after project-brief.md, prd.md, specs.md, BACKLOG.md, implementation_readiness.json were generated. Run /brief, then /specs, then /backlog.
  ```

  Run exactly those commands, in that order. `/quality` and `/refine-backlog` wait until `/backlog` has run (their list ends `... then /backlog, then /quality.`).

- **Something else keeps health `DIRTY`.** The message quotes the first finding:

  ```text
  sentinel error: Cannot run /backlog while project health is DIRTY: Backlog contains Stale stories after source changes: US-001, US-002, US-004. Run /health to see every finding, fix them, then run /backlog again.
  ```

  Run `/health ACME_PORTAL`, read every finding, and fix each with the command that owns it:

  | Finding | Fix |
  | --- | --- |
  | `Blocking gaps remain open.` | Answer them with `/resolve-gaps`, or decide a late change with `/gaps --id GAP-CHG-... --disposition` (scenario 9). |
  | `Backlog contains Stale stories after source changes: US-001.` | Review each story and move it back with `/story-status ... --set Ready` (or `Draft`). Regenerating the backlog does not clear it. |
  | `Open implementation feedback blocks DoD for US-003 (2).` | Resolve the findings with a new `/implementation-feedback` file (scenario 10). This blocks `/backlog`, `/quality` and `/refine-backlog` on purpose. |
  | `CHG-007 is not indexed in memory.` (or `EV-001 ...`) | Run `/reindex ACME_PORTAL`, then `/health` again. |

- **Health was set `DIRTY` and nothing explains it any more:** *Run /health to recompute project health, then run /backlog again.*

Never edit a file to silence a finding.

### 4d. `/quality` before any story

```text
sentinel error: Cannot generate quality artifacts without backlog user stories.
```

Run `/backlog` first.

### 4e. `/story-status` refuses a move

```text
sentinel error: Illegal story transition: Draft -> Done.
```

Stories move one step at a time:

| From | Allowed next |
| --- | --- |
| Draft | Ready, Blocked, Stale |
| Ready | Draft, In Progress, Blocked, Stale |
| In Progress | In Review, Blocked, Stale |
| In Review | In Progress, Done, Blocked, Stale |
| Done | Stale |
| Blocked | Draft, Ready, In Progress, Stale |
| Stale | Draft, Ready, Blocked |

By default a move to Ready or Done that misses Definition-of-Ready or Definition-of-Done items goes through with warnings (`DoR missing: ...`). If the project's `sentinel.config.yaml` sets `backlog_gate: strict: true`, the move is refused instead:

```text
sentinel error: DoR gate blocks Ready: Acceptance criteria must include fail-to-pass, pass-to-pass, and evidence classifications.; Implementation readiness must be Ready With Domain Evidence and score >= 1.00; current score is 0.40.; Assign a human owner with /story-status --owner before treating the story as Ready.
```

Fix the missing items upstream (usually a gap or missing domain context), regenerate the backlog if needed, then move the story again.

### 4f. A file the agent wrote was rejected

```text
sentinel error: GAP-PHOTO-SIZE: the evidence quote is not found verbatim in the raw input. An agent must cite real text, never invent it.
```

```text
sentinel error: the trace was refused (1 finding(s)); nothing was stored: [quote_mismatch] elements[1] S2-E07: element_quote must be the literal text of S2-E07: 'The email or the password is not right.'
```

Every reason is listed and nothing was stored. Fix all of them and submit again. Never paraphrase a quote to get past the check: shorten it to the exact words in the source, or drop the finding.

### 4g. A prerequisite is missing

```text
sentinel error: /split --confirm needs a stored proposal; run /split --propose first
sentinel error: /prototype --trace needs --source TRACE.json (written with the sentinel-prototype-trace skill)
sentinel error: /view diagrams needs the brief: workspaces/ACME_PORTAL/02_requirements/project-brief.md does not exist.
next step: Run /brief ACME_PORTAL first.
sentinel error: --source must be a file, not a folder: input
next step: Pass one file at a time, or run /sync without --source to scan the input and context folders for new or modified files.
```

Run the step the message names.

### 4h. `/validate` or `/doctor` is not green

```text
/validate ACME_PORTAL
```

```text
verdict: INVALID
findings: Backlog exists without backlog_readiness_audit.
```

`INVALID` is a structural problem; here `/quality` was never run. Fix each finding with the owning command and run `/validate` again. Advisory warnings about thin content do not change the verdict. If you decide to go ahead despite a finding, `--override PATH` takes a file of cited `DEC-*` decisions and records your reasons; it does not turn the verdict green. For `/doctor`, fix what it lists; a missing optional extra is only a `WARN` and keeps `PASS`.

### 4i. The workspace is busy

Only one command runs at a time per workspace. A second one waits (10 seconds by default) and then stops with a message naming the command that holds the workspace. Nothing was changed. Wait and retry.

<details><summary>For the technical reader: exit codes</summary>

| Exit | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Unexpected error with a traceback: a bug, report it |
| 2 | Wrong usage: a mistyped command or flag (`unrecognized arguments: ...`) |
| 3 | Invalid input: a malformed or missing file, an illegal story move, a rejected proposal, a missing `--reason` or `--source` |
| 4 | Gate refusal: a missing prerequisite or the project's state (phase, health, maturity) |
| 5 | Unfavourable verdict: `/validate` not `VALID`, `/doctor` not `PASS` |
| 6 | Workspace busy (the wait is set by `SENTINEL_LOCK_TIMEOUT`) |

In a terminal, read it with `echo $?` (Unix shells) or `$LASTEXITCODE` (PowerShell).

</details>

**Decision point.** Do not retry a command hoping for a different answer. Every refusal names a missing step; do that step.

---

## Scenario 5: Splitting a release into r1, r2 and r3

### The situation

A claims programme (`ACME_CLAIMS`) has a confirmed brief: file a claim, approve it, pay it. The payment provider's contract will arrive months after the rest. You want to deliver in releases, each one usable on its own.

### Steps

1. **Ask whether to split.**

   ```text
   /split ACME_CLAIMS --assess
   ```

   ```text
   recommendation: no_split
   why: no split signal lit; 3 build items in 9.1 fit one session
   ```

   Sentinel writes `01_discovery/split_assessment.md` with each signal and the brief place it comes from. The assessment never splits anything; it informs your decision. Here it says the scope fits one release, but the team knows something the brief does not yet say: payment depends on a contract that comes later. You decide to propose a series anyway. (On `cannot_decide`, settle the conflicting signals with the team first.)

2. **Have the agent write the proposal.** In chat:

   > Propose a release series for ACME_CLAIMS. Write the cut criteria first, then the releases, contracts and what stays in the shared base, quoting the brief for every anchor.

   The `sentinel-release-split` skill writes the file and runs:

   ```text
   /split ACME_CLAIMS --propose --source input/series/proposal.json
   ```

   ```text
   status: proposal
   partition_preview: valid: true, codes: []
   ```

   A stored proposal is still only a proposal. `partition_preview` lists what `--confirm` would still refuse; here nothing. A refused proposal lists every finding with a code (for example `layer_cut`, `empty_release`, `criterion_not_written`).

3. **Confirm with the people who own the cut.** These names are theirs, not the agent's.

   ```text
   /split ACME_CLAIMS --confirm --ba "Ana Ruiz" --tech "Platform Team"
   ```

   ```text
   status: confirmed
   client_confirmation_gap: GAP-SPLIT-CLIENT
   releases: r1, r2, r3
   waves: 0: r1, 1: r2, 2: r3
   ```

   Sentinel compiles the series: an index (`02_requirements/series/index.md`) and one brief per release (`02_requirements/r1/project-brief.md` ...). The client's own confirmation stays open as `GAP-SPLIT-CLIENT` on purpose. A release brief is never edited by hand; the series recompiles whenever the whole brief changes.

4. **Build each release's documents.** `--release rN` makes a command work on one release:

   ```text
   /specs ACME_CLAIMS --release r1
   /backlog ACME_CLAIMS --release r1
   /quality ACME_CLAIMS --release r1
   /trace ACME_CLAIMS --release r1
   /validate ACME_CLAIMS --release r1
   /status ACME_CLAIMS --release r2
   ```

   r1's documents land under `03_specs/r1/`, `04_backlog/r1/`, `05_quality/r1/` and so on; `/validate --release r1` says `VALID`. After building r2's documents the same way, `/status --release r2` explains why r2 waits:

   ```text
   verdict: NOT_READY
   blockers: NOT READY by inheritance: r2 depends hard on r1, which is not closed (/split --close r1).
   ```

   Before `--confirm`, any `--release` command says *--release needs a confirmed release series; run /split --confirm first*. A release that is not in the series: *r9 is not a release of the confirmed series*.

5. **The cut changes: move one unit.** The team wants payment (item `C-02`) earlier:

   ```text
   /split ACME_CLAIMS --move --unit C-02 --from r3 --to r2 --reason "payments need the vendor contract first" --ba "Ana Ruiz" --tech "Platform Team"
   ```

   ```text
   status: moved
   releases_changed: r1, r2, r3
   stale_derivations: r1, r2
   next: run /specs, /backlog and /quality with --release for each release in stale_derivations
   ```

   Every move is dated in `02_requirements/series/scope_changes.md`. Moving the unit straight back is refused until a written criterion decides it:

   ```text
   sentinel error: round trip: C-02 already went r3 → r2; a cut criterion is not written [A42]. GAP-SPLIT-CRITERION is open: name the written criterion that decides it with --criterion Cn (written in the proposal and used by r3)
   ```

   Adding `--criterion C1` (a criterion written in the proposal) lets the move through. `--unit` also takes a screen id or an exact quote, and `--to sketch:<name>` sends a unit outside the plan; moving to a sketch closes no gap.

6. **Close r1 when it is done.**

   ```text
   /split ACME_CLAIMS --close r1 --evidence input/interactions/r1-closing-check.md --ba "Ana Ruiz" --tech "Platform Team"
   ```

   With a story still open, Sentinel refuses: *r1 cannot close: stories not Done: US-001 (/story-status --release r1)*. After `US-001` moves through Ready, In Progress, In Review and Done (`/story-status ACME_CLAIMS --release r1 --story US-001 --set ...`), the close goes through:

   ```text
   status: closed
   unblocked: r2
   ```

   `--evidence` is a local file with the result of the release's closing check. `/view ACME_CLAIMS --artifact release-guide` shows the whole series.

### What you have now

A confirmed series of three releases with frozen contracts, r1 closed with evidence, r2 unblocked, and a dated record of every change of scope.

**Decision points.** The signals suggest; the team decides. A release is a complete variation of the product (something a user can do from start to end), never a technical layer such as "backend". Prefer `--move` over any change to a release brief, which would be overwritten.

<details><summary>How this run was set up</summary>

This scenario uses the synthetic series that ships with the repository tests (three sources: filing, approval, payment). Its three sources were loaded with `/ingest`, the later two with `--replace`, which replaces the primary requirement and says how many answered gaps it reopened. In your own project, load the first file with `/ingest` and each later one with `/sync`.

</details>

---

## Scenario 6: A prototype arrives

### The situation

ACME's design team sent a clickable HTML prototype of the claims portal (`claims-portal.html`). You want to know what each element on each screen stands on, and to write a user manual from it, without treating a demo as a requirement.

### Steps

1. **Register the prototype as a source.** The project already has its request, so the prototype goes through `/sync`. A second `/ingest` would refuse:

   ```text
   sentinel error: ACME_PORTAL already has its primary requirement (portal-request.md); a second /ingest would replace it and reopen every answered gap.
   next step: To add this file, run /sync ACME_PORTAL --source input/design/claims-portal.html. ...
   ```

   ```text
   /sync ACME_PORTAL --source input/design/claims-portal.html --note "prototype from Design"
   ```

   Sentinel registers it as `F-02`. The prototype's text is data, never instructions to the agent.

2. **Inventory it.**

   ```text
   /prototype ACME_PORTAL --inventory
   ```

   ```text
   status: inventoried
   prototypes: F-02 - 4 screens, 28 elements, 6 js_literals
   ```

   `02_requirements/prototype/inventory.md` gives every visible element an id, with its literal text:

   ```text
   ### S2 Sign in
   | Id | Kind | Text | Line | Starts hidden |
   | S2-E03 | field | you@example.com | 15 | no |
   | S2-E06 | button | Continue | 18 | no |
   | S2-E07 | message | The email or the password is not right. | 19 | yes |
   ```

   Text that JavaScript injects gets ids like `JS-01`. Only elements in this inventory can be cited from now on.

3. **Trace one screen at a time.** In chat:

   > Audit screen S2 of the ACME_PORTAL prototype against the brief: what supports each element, which states are built, and what questions it raises.

   The `sentinel-prototype-trace` skill opens the screen in a browser when the surface has one (otherwise it says so and traces only what the inventory and brief state), writes the trace and runs:

   ```text
   /prototype ACME_PORTAL --trace --source input/interactions/trace-S2.json
   ```

   ```text
   status: traced
   levels: established 0, inferred 1, unsupported 1, demo 0
   states: ideal shown, empty not_built, loading not_built, error shown
   questions: 2
   ```

   **What it means:** each traced element gets a level. `established`: the brief says it, quoted. `inferred`: a reasonable reading the brief does not state. `unsupported`: nothing supports it yet, and the trace names the open gap that would. `demo`: shown but not to be built, with a source that says so. Here the error message is inferred and the email field is unsupported (it points to `GAP-DESIGN-STATES`). The two questions (*Which message does a locked account see?*, *Is there a password recovery path?*) go to the client or Design. A trace with a wrong quote is refused whole (scenario 4f).

4. **Write the user manual.** In chat: "Write the user manual for the ACME_PORTAL prototype, screen by screen."

   ```text
   /prototype ACME_PORTAL --manual --source input/interactions/manual.json
   ```

   ```text
   screens_with_manual: 1
   screens_without_manual: 3
   ```

   The manual cites elements as placeholders (`{{S2-E06}}`) and Sentinel fills in the interface's real words, so the manual cannot drift from the screen:

   ```text
   ### S2 Sign in
   1. Type your email in **"you@example.com"**.
   2. Type your password in **"Password"** and press **"Continue"**.

   ### S3 My claims
   > **Hole:** this screen has no manual yet.
   ```

   Each submission replaces the screens it brings and keeps the rest.

5. **Read the results.**

   ```text
   /view ACME_PORTAL --artifact prototype
   /view ACME_PORTAL --artifact prototype-trace
   /view ACME_PORTAL --artifact prototype-manual
   ```

   A hole is the honest result for a screen nobody has described yet; do not fill it with generic prose.

### What you have now

An inventory of every screen element, a trace of screen S2 with two questions for the client, and a manual for S2 with three screens marked as holes.

**Decision points.** An `unsupported` element is a question for the client or Design, not a defect to hide. A prototype is evidence of intent, not of requirements: the brief and its gaps still decide what is built.

---

## Scenario 7: An existing system

### The situation

ACME wants customers to pay invoices in instalments (`ACME_BILLING`). The billing system already exists in code, on your machine. Before the brief says anything about the current architecture, you want what the code actually does, as cited evidence rather than recollection.

### Steps

1. **Start the project and tell the brief it extends an existing system.**

   ```text
   /init ACME_BILLING
   /ingest ACME_BILLING --source input/client_requirement/billing-extension.md
   /brief ACME_BILLING --profile INT,UI --genesis brownfield-extension --validation-direction to-build
   ```

   Sentinel shows `confirmed: true`. Settings that contradict each other are not confirmed: `--profile MIG --genesis greenfield` shows `confirmed: false` and *contradiction: profile MIG implies genesis brownfield-replacement, declared greenfield*. Use `--validation-direction built` when the brief documents something already built; then differences between code and brief are reported, not treated as work to do.

2. **Have the agent harvest the code.** In chat:

   > Harvest the billing system at ../billing-api for ACME_BILLING. Read the code block by block and tag every claim.

   The `sentinel-brownfield-harvest` skill reads the code locally and writes a Markdown file in blocks: B0 inventory, B1 architecture, B2 data, B3 integrations, B4 security and constraints, B5 operations. Every claim carries a tag:

   ```text
   ## B0 Inventory
   - repo: billing-api - services/billing-api

   ## B1 Architecture and components
   - [FACT billing-api:src/app.py] The billing API is a Flask app with an invoices blueprint.
   - [INFERRED] Invoices are issued by a nightly job, because its scheduler entry is named nightly-invoices.

   ## B3 Integrations
   - [NOT FOUND billing-api:src/clients/] No client for the bank is present.
   - [OUT OF CODE owners] Who owns the payment reconciliation process.
   - [DIVERGENCE billing-api:README.md] The README documents partial payments; the code rejects any amount below the invoice total.
   ```

   | Tag | Meaning |
   | --- | --- |
   | `[FACT repo:file]` | Read in that file |
   | `[INFERRED]` | A deduction the code does not state |
   | `[NOT FOUND where]` | Looked for and not there |
   | `[OUT OF CODE topic]` | Only a person can say. The topic is one of `owners`, `sla`, `volume`, `purpose_and_retention`, `regulation`, `negotiability`, `role_administration`, `flag_removal_date`, `latency_targets`, `why_without_adr`. |
   | `[DIVERGENCE repo:file]` | The documentation and the code disagree |

   The Spanish tags (`[HECHO]`, `[INFERIDO]`, `[NO ENCONTRADO]`, `[FUERA DEL CÓDIGO]`, `[DIVERGENCIA]`) work too. The code never leaves your machine; only structure and behaviour are recorded.

3. **Register the harvest.**

   ```text
   /harvest ACME_BILLING --source input/harvest/billing-harvest.md
   ```

   ```text
   source_id: F-02
   repos: billing-api
   coverage: fact 2, inferred 1, not_found 1, out_of_code 1, divergence 1
   gaps_opened: GAP-HRV-18FF4AD1, GAP-HRV-A337BA02
   ```

   **What it means:** the out-of-code topic became a low-severity question for a person; the divergence became a high-severity question for you (*Which governs: what is documented or what is built?*). A line without a tag is skipped. One badly tagged line rejects the whole file, with every reason:

   ```text
   sentinel error: Harvest rejected:
   - line 8: [fact] needs `repo:file`
   ```

   You can deliver one block at a time; each run adds its blocks, and a block delivered again replaces only that block. The first file must list the repositories in B0.

4. **Recompile the brief.**

   ```text
   /brief ACME_BILLING
   ```

   The technical places now cite the harvest:

   ```text
   - The billing API is a Flask app with an invoices blueprint. (billing-api:src/app.py) [[sources § ... # F-02 ...]]
   - (inferred) Invoices are issued by a nightly job, because its scheduler entry is named nightly-invoices. (harvest B1)
   - Harvest coverage: facts 2 · inferred 1 · not found 1 · out of code 1 · divergences 1
   ```

5. **Check the request against the code.** Instalments are partial payments, and the code rejects them. Ask the agent for a technical scrutiny pass; it quotes the harvest and runs:

   ```text
   /scrutinize ACME_BILLING --lens technical --source input/interactions/scrutiny.json
   ```

   Sentinel shows `merged: GAP-SCRUTINY-PARTIAL-PAYMENT`. Scrutiny reads the project's domain context (the harvest is part of it) and proposes questions; it never closes one. To check that the brief's own sentences hold against their sources, ask for an anchor review (`/scrutinize ACME_BILLING --mode anchors --source ...`): each line is graded holds, says less or says the opposite, and failures open `GAP-ANC-...` questions.

6. **Ask the technology team for what only they know.**

   ```text
   /context-request ACME_BILLING --domain technology
   /context-request ACME_BILLING --id CTX-001 --status answered
   /context-request ACME_BILLING --id CTX-001 --status closed --reason "technology pack delivered and synced"
   ```

   The first command writes `08_context_packs/requests/technology_context_request.md`, a cited request that tells the team what to document (owners, SLAs, volumes). It does not do their analysis. The request moves from active to answered to closed; closing without `--reason` is refused (*--status closed needs --reason.*). Bring their delivery in with `/sync --source FILE`.

### What you have now

A brief whose technical places cite the code, two questions from the harvest (one for a person, one for you), a scrutiny question about partial payments, and a tracked request to the technology team.

**Decision points.** When the documentation and the code disagree, you decide which governs and record it by answering the gap. Never ask the code what only a person knows; route it to an owner (scenario 2, step 4). For a greenfield project there is nothing to harvest.

---

## Scenario 8: Building starts

### The situation

`ACME_PORTAL` has four stories (`US-001` to `US-004`) and the team starts its first sprint. You are the product owner. You want to refine one story before it starts, move stories through their lifecycle, and keep the board honest.

### Steps

1. **Look at the board.**

   ```text
   /backlog-status ACME_PORTAL
   ```

   ```text
   stories_total: 4; Draft: 4; ready_percent: 0.0; avg_readiness_score: 0.6
   ```

   Sentinel rebuilds `04_backlog/BACKLOG.md`, the board by epic and status. It changes no status.

2. **Refine a story that is too big.** US-002 mixes routing a large claim and the senior adjuster's decision. In chat: "US-002 is too big; propose a split, citing the spec unit." The `sentinel-backlog-refine` skill writes the proposal and runs:

   ```text
   /refine-backlog ACME_PORTAL --source input/interactions/backlog-refinement.json
   ```

   ```text
   accepted: BREF-001
   rejected: []
   ```

   The proposal (`split-story` here; also `reslice`, `merge-stories`, `missing-story`, `enabler-candidate`) must quote the specs word for word. Sentinel adds it to an *Agent Backlog Refinements* section in `EPIC-001.md` and in `US-002.md`, for your review. It rewrites no story: if you agree, the change reaches the backlog through the specs and `/backlog`. A story still marked as pending input cannot be refined.

3. **Move the sprint's stories to Ready.**

   ```text
   /story-status ACME_PORTAL --story US-001 --set Ready --owner "Delivery Lead"
   ```

   ```text
   status: Ready
   owner: Delivery Lead
   warnings: DoR missing: Implementation readiness must be Ready With Domain Evidence and score >= 1.00; current score is 0.60.
   ```

   Moving to Ready checks the Definition of Ready and **freezes a dated copy of the story's acceptance criteria**, so later changes show up as differences. The missing items are warnings by default; with a strict gate the move is refused (scenario 4e). You do the same for US-002, US-003 and US-004. A jump straight to Done is refused: *Illegal story transition: Draft -> Done.*

   Only `/story-status` changes a story's status or owner; never edit `US-NNN.md` or `BACKLOG.md`.

4. **Rebuild the search index after status moves.** `/health` now says:

   ```text
   verdict: DIRTY
   findings: CHG-003 is not indexed in memory.
   ```

   The status change was recorded but not yet added to the search index. Run:

   ```text
   /reindex ACME_PORTAL
   /health ACME_PORTAL
   ```

   Health is `CLEAN` again. Do this before `/backlog`, `/quality` or `/refine-backlog`, which refuse while health is `DIRTY`.

5. **Start work, and confirm the stories that were not touched.**

   ```text
   /story-status ACME_PORTAL --story US-001 --set "In Progress"
   /health ACME_PORTAL
   ```

   ```text
   verdict: DIRTY
   findings: Backlog contains Stale stories after source changes: US-002, US-003, US-004.
   ```

   **What it means:** when a story moves ahead, Sentinel marks the stories of the same area that are behind it as Stale, so someone checks that they still hold. This happens again at each forward move (In Progress, In Review, Done). Review them, and move each one back:

   ```text
   /story-status ACME_PORTAL --story US-002 --set Ready
   /story-status ACME_PORTAL --story US-003 --set Ready
   /story-status ACME_PORTAL --story US-004 --set Ready
   ```

   Regenerating the backlog does not clear a Stale story; only `/story-status` does.

6. **Finish the story with its acceptance evidence.**

   ```text
   /story-status ACME_PORTAL --story US-001 --set "In Review"
   /story-status ACME_PORTAL --story US-001 --set Done --evidence input/interactions/us-001-acceptance.md
   ```

   ```text
   status: Done
   evidence: 04_backlog/acceptance_evidence/US-001-us-001-acceptance.md
   warnings: DoD missing: DoR must pass before DoD can pass.
   ```

   The evidence file (here the notes of a demo) is copied into the workspace and traced to the story. Done is checked against the Definition of Done; by default a missing item is a warning, with a strict gate the move is refused. Open implementation feedback on the story is one of those items (scenario 10).

7. **Leave the board clean, and report.** The move to Done marked the other three stories Stale again; you move them back to Ready as in step 5, then:

   ```text
   /reindex ACME_PORTAL
   /health ACME_PORTAL
   /backlog-status ACME_PORTAL
   /dashboard
   ```

   ```text
   /health          verdict: CLEAN
   /backlog-status  Ready: 3; Done: 1; done_percent: 0.25
   ```

   `/dashboard` writes `dashboard.html` in the folder you run it from: a read-only page over every workspace (in a clone, the repository root, where it is git-ignored).

### What you have now

One story Done with traced evidence, three stories Ready with frozen acceptance criteria, a refinement proposal on record, and health `CLEAN`.

**Decision points.** The agent proposes refinements; you decide. If a story turns out to be the wrong shape because the scope changed, treat it as a change (scenario 9). When a developer finds something the backlog does not cover, register it as feedback (scenario 10).

---

## Scenario 9: The client changes scope after the backlog is ready

### The situation

`ACME_PORTAL` is ready to build: four stories, health `CLEAN`. The client never said where "large claims" start, so early on you recorded an assumption to keep the team moving: *Only claims above 5,000 euros need a second approval; smaller claims need one* (`ASM-SECOND-APPROVAL-LARGE-ONLY`, owner BA, high risk). It stands in for the open question about business rules (`GAP-BUSINESS-RULES`).

Then the claims director writes:

```text
From: Ana (ACME claims director)
Subject: Approvals (FICTIONAL SAMPLE)

After the audit last week, every claim needs a second approval from a senior adjuster,
whatever the amount. Please update the plan.
```

You want the plan to follow the new rule, with a record of what changed and why.

### Steps

1. **Register the email with a cited analysis.** In chat:

   > The client sent this email; it contradicts our approval assumption. Register it for ACME_PORTAL.

   The `sentinel-sync` skill reads the email and the assumption, writes a small analysis that quotes both, and runs:

   ```text
   /sync ACME_PORTAL --source input/interactions/email-approvals.md --note "approval rule changed" --analysis input/interactions/change-analysis.json
   ```

   ```text
   source_id: F-08
   change_analysis: opened GAP-CHG-FDC2C6
   next: Ask the BA to confirm each one: /gaps ACME_PORTAL --id GAP-CHG-x --disposition accepted|rejected
   ```

   **What it means:** Sentinel does not decide on its own that the email overrides the assumption. It opened one blocking question for you, `GAP-CHG-FDC2C6`, that quotes both sides:

   ```text
   Late change on ASM-SECOND-APPROVAL-LARGE-ONLY (invalidate_assumption): CHG-007: "every claim needs a second approval from a senior adjuster, whatever the amount"; ASM-SECOND-APPROVAL-LARGE-ONLY: "Only claims above 5,000 euros need a second approval"
   Does the change in CHG-007 replace what ASM-SECOND-APPROVAL-LARGE-ONLY says? (accepting invalidates ASM-SECOND-APPROVAL-LARGE-ONLY and reopens the gap it holds; reject it if it does not.)
   ```

   Without the analysis, `/sync` would only store the email: *Prose is stored and indexed, not interpreted*. A quote that is not word for word in the email or the assumption makes the whole analysis refused, with nothing written.

2. **Sentinel holds the backlog until you decide.**

   ```text
   /backlog ACME_PORTAL
   /next ACME_PORTAL
   ```

   ```text
   /backlog  sentinel error: Cannot run /backlog while project health is DIRTY: Blocking gaps remain open. (1 more finding(s)) Run /health to see every finding, fix them, then run /backlog again.
   /next     Confirm a late change: A late change waits for your decision: GAP-CHG-FDC2C6. Read each one in gaps.md (the note and the item it changes are both quoted), then accept it to apply the change or reject it as a false alarm.
   ```

3. **Accept the change.** You agree the email replaces the assumption:

   ```text
   /gaps ACME_PORTAL --id GAP-CHG-FDC2C6 --disposition accepted
   ```

   ```text
   applied: kind invalidate_assumption, target ASM-SECOND-APPROVAL-LARGE-ONLY
   invalidated_assumptions: ASM-SECOND-APPROVAL-LARGE-ONLY
   ```

   The assumption is now marked `INVALIDATED` in `01_discovery/assumptions.md` (it is kept, not deleted), and the brief, PRD, specs and backlog built on it are out of date. Had you rejected the change (`--disposition rejected --reason "..."`), nothing else would move.

4. **Sentinel tells you what to rebuild.**

   ```text
   /backlog ACME_PORTAL
   ```

   ```text
   sentinel error: Cannot run /backlog while project health is DIRTY: knowledge changed after project-brief.md, prd.md, specs.md, BACKLOG.md, implementation_readiness.json were generated. Run /brief, then /specs, then /backlog.
   next step: Run /brief, then /specs, then /backlog.
   ```

5. **Record the new rule as the answer, then rebuild in order.** The question the assumption stood in for (`GAP-BUSINESS-RULES`) is still open. Answer it with the client's words:

   ```text
   ### GAP-BUSINESS-RULES
   - Answer: Every claim needs a second approval from a senior adjuster, whatever the amount (email of 14 March).
   - Owner / source: Ana, ACME claims director
   - Evidence or reference: workshop minutes, 12 March
   - Decision status: confirmed
   ```

   ```text
   /resolve-gaps ACME_PORTAL --source input/interactions/approval-answer.md
   /brief ACME_PORTAL
   /specs ACME_PORTAL
   /backlog ACME_PORTAL
   /quality ACME_PORTAL
   /health ACME_PORTAL
   /status ACME_PORTAL
   ```

   ```text
   /resolve-gaps  closed: GAP-BUSINESS-RULES
   /backlog       story_count: 4
   /health        verdict: CLEAN
   /status        verdict: READY_WITH_WARNINGS
   ```

   The brief now says *Every claim needs a second approval from a senior adjuster, whatever the amount (email of 14 March).*, cited to the answer file. `07_changes/04_regeneration/` holds one change record per regenerated file (spec units, PRD, specs, epic).

### What you have now

The new rule in the brief, specs and backlog; the old assumption kept and marked invalidated; the email registered as a source; your decision on record as a closed `GAP-CHG`; and health `CLEAN`. If stories had already been Ready, `04_backlog/acceptance_criteria_deltas.md` would list each acceptance criterion that changed after it was frozen.

**Decision points.** The agent proposes the change; you decide. If the email only answered an open question, you would not need the analysis: answer the gap with `/resolve-gaps` (scenario 3). If it contradicted a confirmed answer instead of an assumption, the analysis would use `reopen_gap`, and accepting it reopens that gap with its previous answer kept on record.

---

## Scenario 10: Development finds a hole

### The situation

`ACME_PORTAL`'s four stories are Ready. A developer picks up US-003 (*While a claim is under review, the system shall show its current status to the policyholder*) and finds two problems: the policy system has no call that returns a claim's status, and the upload gateway rejects photos larger than 10 MB. You want both on record, the backlog held until they are settled, and a clean state once they are.

### Steps

1. **Register the findings.** In chat, the developer (or you) says:

   > While preparing US-003 we found two problems; register them as implementation feedback with their evidence.

   The `sentinel-implementation-feedback` skill writes each finding with its evidence (a file, a contract, an error; never a guess) and runs:

   ```text
   /implementation-feedback ACME_PORTAL --source input/interactions/feedback-us003.json
   ```

   ```text
   accepted: IFB-001, IFB-002
   rejected: []
   ```

   Each finding has a type: `gap` (a question someone must answer), `ac-challenge` (an acceptance criterion that cannot hold), `new-dependency` or `surface-not-covered`. The `gap` finding opened `GAP-FEEDBACK-001` in `01_discovery/implementation_feedback_gaps.md`:

   ```text
   | `GAP-FEEDBACK-001` | `US-003` | gap | OPEN | The claim status shown to the policyholder must come from somewhere; the policy system has no claim-status call. |
   ```

   The report is in `07_changes/05_implementation_feedback/feedback_report.md`. Reporting is not rewriting: the backlog is untouched. A finding without evidence is rejected (*evidence is required; implementation feedback cannot be anonymous*).

2. **Sentinel holds the backlog on purpose.**

   ```text
   /health ACME_PORTAL
   /backlog ACME_PORTAL
   /refine-backlog ACME_PORTAL --source input/interactions/backlog-refinement.json
   ```

   ```text
   /health          verdict: DIRTY
                    findings: Open implementation feedback blocks DoD for US-003 (2).
   /backlog         sentinel error: Cannot run /backlog while project health is DIRTY: Open implementation feedback blocks DoD for US-003 (2). Run /health to see every finding, fix them, then run /backlog again.
   /refine-backlog  sentinel error: Cannot run /refine-backlog while project health is DIRTY: Open implementation feedback blocks DoD for US-003 (2). ...
   ```

   **What it means:** while feedback is open, `/backlog`, `/quality` and `/refine-backlog` refuse by design, so nobody rebuilds or reshapes the backlog on top of an unsettled problem. US-003 can still move, but Done reports *DoD missing: Resolve open implementation feedback before treating the story as Done.*

3. **Settle each finding.** This is the BA's call:

   - The status question needs the client. You ask, and on 20 March ACME agrees the status comes from the claims database. (`GAP-FEEDBACK-001` is not in the gaps document, so `/resolve-gaps` does not know it; it is closed through feedback, below.)
   - The upload limit is a platform fix: the infrastructure team raises it to 25 MB.

   You record both as resolved in a new feedback file. It repeats each finding's id, and for the `gap` finding its gap id:

   ```json
   {"findings": [
     {"id": "IFB-001", "gap_id": "GAP-FEEDBACK-001", "type": "gap", "story": "US-003", "status": "resolved",
      "summary": "Claim status comes from the claims database, not the policy system; agreed with the client on 20 March.",
      "evidence": "meeting minutes, 20 March (FICTIONAL SAMPLE)"},
     {"id": "IFB-002", "type": "ac-challenge", "story": "US-003", "status": "resolved",
      "summary": "The upload limit is raised to 25 MB at the gateway.",
      "evidence": "infra change ticket INF-12 (FICTIONAL SAMPLE)"}
   ]}
   ```

   ```text
   /implementation-feedback ACME_PORTAL --source input/interactions/feedback-us003-resolved.json
   ```

   ```text
   accepted: IFB-001, IFB-002
   | `GAP-FEEDBACK-001` | `US-003` | gap | RESOLVED | Claim status comes from the claims database, not the policy system; agreed with the client on 20 March. |
   ```

4. **Health comes back by itself.**

   ```text
   /status ACME_PORTAL
   ```

   ```text
   health: CLEAN
   ```

   Once no feedback is open, Sentinel recomputes health; you do not need to run `/health`. If something else were still wrong, health would stay `DIRTY` and `/health` would name it.

5. **Act on what you learned.** The status needs a story that reads it from the claims database. Now that health is `CLEAN`, the agent's proposal is accepted:

   ```text
   /refine-backlog ACME_PORTAL --source input/interactions/backlog-refinement.json
   /backlog ACME_PORTAL
   /quality ACME_PORTAL
   ```

   ```text
   /refine-backlog  accepted: BREF-001
   /backlog         story_count: 4
   /quality         verdict: PARTIAL
   ```

   The `missing-story` proposal is on record for review. If the client's answer changes the scope, carry it in as a change: answer or sync it, then regenerate (scenarios 3 and 9).

6. **Later findings add up.** A week later, US-004 hits a missing message queue:

   ```text
   /implementation-feedback ACME_PORTAL --source input/interactions/feedback-us004.json
   ```

   ```text
   accepted: IFB-003
   | `GAP-FEEDBACK-001` | `US-003` | gap | RESOLVED | ... |
   | `GAP-FEEDBACK-002` | `US-004` | gap | OPEN | Retrying the policy lookup needs a message queue the platform does not have yet. |
   ```

   Numbering continues (`IFB-003`, `GAP-FEEDBACK-002`) and earlier rows are kept. Health is `DIRTY` again (*Open implementation feedback blocks DoD for US-004 (1).*) until this one is settled.

### What you have now

Both problems from US-003 on record with their evidence and resolution, the backlog rebuilt once they were settled, a proposal for the missing story, and a running history of findings in which a new one picks up the next number.

**Decision points.** The developer reports; the BA decides. If the developer cannot point to evidence, it is a conversation, not a finding. A finding can also ask Sentinel to send the stories of the spec units it affects back for review; Sentinel then marks only those stories Stale.

---

## Smaller situations

Short recipes that do not need a full story.

**A pile of unstructured requests before any project exists.** Ask the agent to triage them ("group these requests by theme with a quote for each, and tell me whether this is one project or several"). The `sentinel-intake-triage` skill numbers the items (`R1`, `R2` ...), proposes themes and a one-or-several recommendation, and lists noise and out-of-scope asks with the reason. It creates nothing. After you confirm, run `/init` and `/ingest` per project for its first file, and `/sync --source` for each further file.

**Design or Technology must deepen the analysis.**

```text
/context-request ACME_PORTAL --domain design
/context-request ACME_PORTAL --id CTX-001 --status answered
/context-request ACME_PORTAL --id CTX-001 --status closed --reason "design pack delivered and synced"
```

Domains are `technology`, `design`, `quality`, `frontend` and `backend`. A request moves from active to answered to closed, or to obsolete; closing needs a reason. Bring the team's delivery in with `/sync --source FILE`, so it is registered, redacted and checked for contradictions.

**You cloned or moved a workspace and search looks empty, or `/health` says something "is not indexed in memory".** The local search index is not versioned. Rebuild it:

```text
/reindex ACME_PORTAL
/health ACME_PORTAL
```

`/reindex` refreshes only the search index; it never changes a governed file.

**You need focused context for one topic.**

```text
/retrieve ACME_PORTAL --query "claim rejection rules" --workflow discovery --write-pack
```

With `--write-pack` a context pack is saved (`08_context_packs/discovery.json`); without it, the matches print to the screen.

**The PRD is accurate but thin.** In chat: "Improve the wording of the PRD overview with paragraphs that each cite local evidence." The agent writes the blocks and runs `/compose ACME_PORTAL --source input/interactions/composition.json`. Citations must be exact. A block aimed at a section that still has pending input is refused: *COMP-001: section 1 still contains pending input; resolve the feeding gap before composing narrative.* Never change `prd.md` by hand.

**Check that the brief's parts agree.** `/self-review ACME_PORTAL --crosses --source input/interactions/crosses.json` looks for two places of the brief that cannot both be true, or a need with no counterpart (for example an in-scope item with no screen). Each finding opens a `GAP-XRV-...` question.

**A skeptical pass over the PRD before handoff.** `/self-review ACME_PORTAL --source input/interactions/self-review.json` registers cited skeptical findings as gaps and hard-to-reverse decisions as `DEC-...` entries in `03_specs/self_review/decision_register.md`. It rewrites nothing.

**Hand a draft to a stakeholder.**

```text
/export ACME_PORTAL --artifact brief --format md
/export ACME_PORTAL --artifact prd --format md --final
```

An export that still has pending marks is stamped as a draft. `--final` refuses until none remain: */export --final refused: 17 pending marks remain in the prd. Close them (or export without --final to get a marked draft).* The artifacts are `brief`, `prd`, `gaps` and `context-request` (which needs `--domain`). The formats are `md`; `mdx` (PRD only); and `interview` and `faq` (gaps only; `faq` writes the confirmed answers as an FAQ).

**See every project at once.** `/dashboard` (optionally `--open` and `--theme NAME_OR_PATH`) writes `dashboard.html` in the folder you run it from: a read-only page over every workspace. See [Dashboard](14-dashboard.md) and [Themes](17-themes.md).

**Developers need sample data.** Ask for synthetic data from the specs. The `sentinel-handoff-datasets` skill writes disposable CSV, JSON or SQL under `08_context_packs/synthetic/`, marked as synthetic and git-ignored. It is never evidence and never cited; `/validate` flags any citation to it. There is no command for it.

---

## Choosing between `/resolve-gaps` and `/sync`

Use `/resolve-gaps` when the file has `### GAP-...` sections that someone answered: the goal is to close known questions.

Use `/sync` when the information is new or not tied to a question: a meeting note, an email, a new document version, a prototype. The goal is to register it and see its impact. Prose is stored, not interpreted; to change something already confirmed, add a cited analysis (`--analysis`, scenario 9).

Often you use both: `/resolve-gaps` for the answers, then `/sync` for what goes beyond them.

<details><summary>Command coverage map</summary>

Where each of the 37 commands appears. "S" is the smaller situations. For flags, gates and outputs see the [command reference](01-command-reference.md).

| Command | Scenario | Command | Scenario |
| --- | --- | --- | --- |
| `/doctor` | 1, 4 | `/stakeholders` | 2 |
| `/init` | 1, 2, 4, 7 | `/sources` | 3 |
| `/ingest` | 1, 2, 6, 7 | `/context-request` | 7, S |
| `/gaps` | 1, 2, 9 | `/export` | 1, 2, S |
| `/annotate` | 2, 4 | `/specs` | 1, 3, 4, 5, 9 |
| `/challenge` | 2 | `/compose` | S |
| `/scrutinize` | 7 | `/self-review` | 2, S |
| `/assume` | 2 | `/backlog` | 1, 3, 4, 5, 9, 10 |
| `/resolve-gaps` | 1, 2, 3, 9 | `/refine-backlog` | 8, 10 |
| `/maturity` | 1, 2 | `/backlog-status` | 8 |
| `/brief` | 1, 2, 3, 4, 7, 9 | `/story-status` | 4, 5, 8, 10 |
| `/harvest` | 7 | `/implementation-feedback` | 10 |
| `/split` | 5 | `/quality` | 1, 3, 5, 9 |
| `/prototype` | 6 | `/trace` | 1, 5 |
| `/sync` | 3, 6, 9 | `/health` | 1, 3, 4, 8, 9, 10 |
| `/retrieve` | 3, S | `/validate` | 1, 4, 5 |
| `/reindex` | 8, S | `/status` | 1, 2, 4, 5, 9 |
| `/view` | 1, 5, 6 | `/next` | 1, 4, 9, 10 |
| `/dashboard` | 8, S | | |

Modes and flags, and where they appear: `/gaps --top` and `--disposition` (2, 9); `/scrutinize --lens` and `--mode anchors` (7); `/self-review --sufficiency` (2) and `--crosses` (S); `/sync --digest` (3) and `--analysis` (9); `/export --format interview` (1, 2) and `--final` (S); `--release rN` (5); `/prototype --inventory|--trace|--manual` (6); `/split --assess|--propose|--confirm|--move|--close` (5); `/context-request --id --status` (7, S); `/ingest --replace` (5).

</details>

## Next

- The concepts behind these scenarios, and the glossary: [Start here](00-user-guide.md).
- One procedure per situation: [Workflows](03-workflows.md).
- When something went wrong: [Recovery](21-recovery.md).
- Every command, flag and gate: [Command reference](01-command-reference.md).
- What each file is and who may edit it: [Artifact reference](02-artifact-reference.md).
- What the agent does behind a request: [Skills catalog](04-codex-skills-guide.md).
- Setup per surface: [Claude Code](13-claude-adapter.md), [Codex](08-codex-adapter.md), [Kilo Code](07-kilo-code-adapter.md).
