# Workflows

This page tells you what to do in each situation you meet on a real project, from the first request to the handoff and after it. It is written for business analysts and product managers. If you have not run Sentinel yet, start with [Start here](00-user-guide.md); for longer worked examples, see [Scenarios](12-scenarios.md).

**How to read a situation.** Each one has the same parts: *When this happens*, *What to do*, *How you know it worked* and *If something goes wrong*. In *What to do*, each step has three lines: what you tell the assistant, what you will see, and what it means. Under each step, a collapsed block called "In a terminal" holds the exact commands for people who work in a terminal; you can skip it.

**How to talk to the assistant.** Write in plain language, as you would to a colleague, one step at a time. The example project is called ACME_PORTAL; use your own project name. Words such as *gap* (an open question), *brief* or *health* are defined in the [glossary](00-user-guide.md#glossary). How the commands are typed in a terminal, in Codex and in the Claude Code plugin is in [Driving Sentinel from chat](11-chat-commands.md).

**When something stops.** The assistant tells you what is wrong and what to do next. If you ask "what should I do next?", it always gives the one step that unblocks the project. The exact messages are in the terminal blocks.

| Situation | Go to |
|---|---|
| A new request arrives | [A new request arrives](#a-new-request-arrives) |
| The request is only a few lines long | [The request is only a few lines long](#the-request-is-only-a-few-lines-long) |
| You prepare a meeting with stakeholders, then process the minutes | [Preparing a meeting and processing the minutes](#preparing-a-meeting-and-processing-the-minutes) |
| The client sent answers | [The client sent answers](#the-client-sent-answers) |
| The client does not answer and you need to move on | [The client does not answer and you need to move on](#the-client-does-not-answer-and-you-need-to-move-on) |
| You want the agent to find what you missed | [You want the agent to find what you missed](#you-want-the-agent-to-find-what-you-missed) |
| A domain team must provide context | [A domain team must provide context](#a-domain-team-must-provide-context) |
| Something changed after a meeting or an email | [Something changed after a meeting or an email](#something-changed-after-a-meeting-or-an-email) |
| Two sources say different things | [Two sources contradict each other](#two-sources-contradict-each-other) |
| A source was wrong or is outdated | [A source was wrong or is outdated](#a-source-was-wrong-or-is-outdated) |
| The scope changes after the backlog exists | [The scope changes after the backlog exists](#the-scope-changes-after-the-backlog-exists) |
| You need what was said about a topic | [Finding what was said about a topic](#finding-what-was-said-about-a-topic) |
| A command refused | [A command refused](#a-command-refused) |
| The scope is too big for one release | [The scope is too big for one release](#the-scope-is-too-big-for-one-release) |
| You have an HTML prototype | [You have an HTML prototype](#you-have-an-html-prototype) |
| The system already exists | [The system already exists](#the-system-already-exists) |
| A change or new feature on something that already exists | [A change on something that already exists](#a-change-on-something-that-already-exists) |
| Stories need reshaping, assigning or moving | [Stories need reshaping or moving](#stories-need-reshaping-or-moving) |
| The development team asks a question or finds a problem | [The development team asks a question or finds a problem](#the-development-team-asks-a-question-or-finds-a-problem) |
| You want to check quality before handing off | [Checking quality before handing off](#checking-quality-before-handing-off) |
| You show progress to the sponsor or the client | [Showing progress to the sponsor or the client](#showing-progress-to-the-sponsor-or-the-client) |
| Time to hand off | [Handing off to the delivery team](#handing-off-to-the-delivery-team) |
| You pick up a project after weeks, or take over from another BA | [Picking up a project after weeks](#picking-up-a-project-after-weeks) |
| You edited a generated file by hand | [You edited a file by hand](#you-edited-a-file-by-hand) |
| Something broke | [Something broke](#something-broke) |
| You run several projects for the same client | [Several projects for the same client](#several-projects-for-the-same-client) |

<a id="new-project"></a>

## A new request arrives

**When this happens.** The first real input arrives: a request, a brief, a guide or a set of notes.

**What to do.** Talk to your assistant in plain language, one step at a time. The commands are only for people who work in a terminal; each step has them in a collapsed block.

1. Create the project and load the request.

   **Tell the assistant:** "We just got a request from ACME for a customer portal. Start a project called ACME_PORTAL and read this request: input/acme-request.md."

   **You'll see:** The assistant confirms that the project is created and that it read the request. It tells you how many open questions (the *gaps*) it found and that it kept a copy of the request with any secrets masked.

   **What it means:** The project now has a place to keep everything, and the questions the request left unanswered are written down so none is forgotten.

   <details><summary>In a terminal</summary>

   ```text
   /init ACME_PORTAL
   /ingest ACME_PORTAL --source input/acme-request.md
   ```

   In a Claude Code clone, if `/init` starts Claude Code's own project setup, send `/sentinel /init ACME_PORTAL` instead.
   </details>

2. Say what kind of system this is, once.

   **Tell the assistant:** "It's a new web portal built from scratch, with a user interface. Write the project brief."

   **You'll see:** The assistant writes the project brief and tells you that some parts are marked as pending, wherever the request does not give an answer yet. If you were not sure what kind of system it is, it first asks you to confirm the settings and proposes values taken from the request.

   **What it means:** The *profile* says what the brief must cover (here, a user interface); the *genesis* says whether you build from scratch or change an existing system. The pending marks are the places the client still has to answer.

   <details><summary>In a terminal</summary>

   ```text
   /brief ACME_PORTAL --profile UI --genesis greenfield
   ```

   If you are not sure of the values, run `/next ACME_PORTAL` first: until you confirm them it answers *Confirm the brief settings* and proposes values from the request.
   </details>

3. Ask what to do next.

   **Tell the assistant:** "What should I do next on ACME_PORTAL?"

   **You'll see:** *Waiting for client answers*. The assistant tells you to send the client the interview script (the list of open questions, ready to send) and to come back when the answers arrive.

   **What it means:** Sentinel has done what it can until the client replies. Go to [The request is only a few lines long](#the-request-is-only-a-few-lines-long) to plan the first round of questions.

   <details><summary>In a terminal</summary>

   ```text
   /next ACME_PORTAL
   ```
   </details>

4. Load every later file (a guide, meeting notes, a prototype) as a new source, never as a second request.

   **Tell the assistant:** "Add this billing guide to the project as a new source: input/billing-guide.md."

   **You'll see:** The assistant confirms the file was added and says what it changed in what the project knows.

   **What it means:** The project learns from the new file without replacing the first request or reopening questions already answered.

   <details><summary>In a terminal</summary>

   ```text
   /sync ACME_PORTAL --source input/billing-guide.md
   ```
   </details>

**How you know it worked.** The assistant can show you a list of open questions for the project. Asking "what next?" no longer asks you to confirm the brief settings. The project brief exists, with pending marks where an answer is missing.

**If something goes wrong.**

- The assistant says it cannot find the file: the path is read from the folder you work in. Check the name and where the file is.
- The assistant refuses to load a second request as the first one: that would replace the original and reopen every answered question. Tell it the file is an additional source instead. If you really want to replace the first request, say so explicitly (see [When something went wrong](21-recovery.md#a-wrong-file-was-ingested)).
- The assistant stops on the kind of system and lists the valid options: pick one of them. You can combine several, for example a user interface and a regulatory one.
- If you skip step 2, the assistant keeps asking for it, and refuses to write the specs or the backlog.

<details><summary>In a terminal</summary>

- `--source file not found`: the path is read from the folder you run Sentinel from.
- A second `/ingest` is refused. Use `/sync` for later files. To replace the first request on purpose, add `--replace`.
- `/brief` with an unknown profile or genesis stops and lists the valid values. Several profiles go together as `--profile UI,REG`.
- Without step 2, `/next` and `/status` keep asking for it, and `/specs` and `/backlog` refuse.

A binary file that is not `.docx` (a PDF, a corrupt Word file) is refused with exit 3; convert it to Markdown. Other UTF-8 text files are stored as Markdown with a warning. A `MIG` profile needs `--genesis brownfield-replacement`; a contradictory pair keeps `GAP-BRIEF-PROFILE` open. Older projects can keep the earlier brief format with `/init ACME_PORTAL --brief-version 1` (11 sections, no pending-mark places).
</details>

<a id="thin-intake"></a>

## The request is only a few lines long

**When this happens.** The request is a paragraph or a vague idea, and the list of open questions comes back long (thirty or more is normal).

**What to do.**

1. Ask for the few questions that matter most now, not all of them.

   **Tell the assistant:** "Give me the five most important open questions for ACME_PORTAL."

   **You'll see:** Five questions, scope first, each with the options Sentinel can cite (always including *Leave pending*). They are also saved as a short document you can read before the meeting.

   **What it means:** A long list gets shallow answers. A round of about five gets real ones.

   <details><summary>In a terminal</summary>

   ```text
   /gaps ACME_PORTAL --top 5
   ```

   The round is written to `01_discovery/gap_round.md`.
   </details>

2. Prepare the questions for the client.

   **Tell the assistant:** "Write the interview script to send to the client."

   **You'll see:** A document with every open question, blocking ones first, each with empty fields for the answer, the owner, the evidence and the decision status. If you registered who answers what, the questions are grouped by person (see the next situation).

   **What it means:** Send this document, not your working list. It holds all open questions, not only the five of the round.

   <details><summary>In a terminal</summary>

   ```text
   /export ACME_PORTAL --artifact gaps --format interview
   ```

   Written to `08_context_packs/exports/gaps-interview.md`; each question starts with a code such as `GAP-SCOPE`. Send this file, not `gaps.md`, which is your working list.
   </details>

3. When the answers come back, go to [The client sent answers](#the-client-sent-answers), then ask for the next round of five.

If you received many unrelated requests at once and are not sure how many projects they are, ask the assistant to group them by theme before you create anything ("triage these requests"). It cites each source and creates nothing.

**How you know it worked.** The round lists at most the number of questions you asked for and says how many remain. The interview script opens with "These are the questions we need answered to complete the requirement, the most urgent first."

**If something goes wrong.** The assistant says it cannot plan a round before the request is loaded: load the request first.

<details><summary>In a terminal</summary>

"Cannot plan a round before /ingest creates 01_discovery/gaps.md." Triage uses the `sentinel-intake-triage` skill before `/init`.
</details>

<a id="preparing-a-meeting-and-processing-the-minutes"></a>

## Preparing a meeting and processing the minutes

**When this happens.** You will meet stakeholders (the sponsor, the billing team, the tech lead) and want each one to get their own questions. After the meeting you have the minutes.

**What to do.**

1. Register who answers for each area.

   **Tell the assistant:** "Add the Head of Billing as the business contact for invoices, the Product Owner for product, and the Tech Lead for technical questions."

   **You'll see:** The assistant confirms each person it registered.

   **What it means:** Questions will be routed to these people. Sentinel never invents an owner: an area nobody covers stays "no contact named yet".

   <details><summary>In a terminal</summary>

   ```text
   /stakeholders ACME_PORTAL --add --name "Head of Billing" --domain business --topic invoices
   /stakeholders ACME_PORTAL --add --name "Product Owner" --domain product
   /stakeholders ACME_PORTAL --add --name "Tech Lead" --domain technical
   ```

   `--domain` must be one of `business`, `product`, `technical`, `design`, `quality`, `compliance` or `delivery` (`technology`, `frontend` and `backend` are saved as `technical`). `/stakeholders ACME_PORTAL` alone lists them.
   </details>

2. Pick the questions for this meeting and write the script.

   **Tell the assistant:** "Pick the five questions for this meeting and write the interview script."

   **You'll see:** The script groups the questions under each person's name, plus a group for questions with no contact yet.

   **What it means:** Each stakeholder gets only their own questions.

   <details><summary>In a terminal</summary>

   ```text
   /gaps ACME_PORTAL --top 5
   /export ACME_PORTAL --artifact gaps --format interview
   ```
   </details>

3. After the meeting, bring the result in. If you have the answered interview script, tell the assistant so; if you have free-text minutes, an email or a call note, give it as a change.

   **Tell the assistant:** "The client answered the interview script: input/answers.md. Process it." Or: "Here are the minutes of the workshop of 14 November: input/minutes.md. Add them to the project."

   **You'll see:** For answers: which questions closed, which closed partly and which were not recognised. For minutes: the change is recorded, checked against the other sources, and its impact is reported. Free text is stored and searchable, but not interpreted; the assistant tells you which lines changed nothing and suggests writing them as answers.

   **What it means:** Only an answer with the decision status "confirmed" closes a question; a "pending" answer is recorded but leaves it open. Minutes can also contain answer blocks, which close questions with the same rules. For a long raw transcript, ask for a digest: it proposes the answers and decisions it can cite and applies nothing.

   <details><summary>In a terminal</summary>

   ```text
   /resolve-gaps ACME_PORTAL --source input/answers.md
   /sync ACME_PORTAL --source input/minutes.md --note "workshop 2026-11-14"
   ```

   Answer blocks are `### GAP-...` sections. `/sync` says: "Prose is stored and indexed, not interpreted: 2 line(s) changed nothing. Rewrite them as gap answers (### GAP-...) or pass a cited analysis with /sync --source NOTE --analysis FILE." For a raw transcript add `--digest`.
   </details>

**How you know it worked.** The script groups questions under each person's name. Questions answered as confirmed show as closed in the open-questions list.

**If something goes wrong.** The assistant refuses a contact area it does not know and lists the valid ones (business, product, technical, design, quality, compliance, delivery): pick the closest and put the detail in the topic. It also asks for the area when you forget it.

<details><summary>In a terminal</summary>

- "Unknown --domain 'operations': it must name a lens, or no gap would ever be routed to this owner. Use one of: business, product, quality, technical, compliance, delivery, design (also accepted: backend = technical, frontend = technical, technology = technical).": use the closest lens and `--topic` for the detail (`--domain business --topic operations`).
- "/stakeholders --add requires --domain: the lens this owner answers for. Use one of: ...": add `--domain`.
- "/stakeholders --id/--name/--domain/--topic/--profile/--notes go with --add": you forgot `--add`.
</details>

<a id="client-answers-arrive"></a>

## The client sent answers

**When this happens.** The client or a domain owner returned the answered interview script.

**What to do.**

1. Load the answers and look at where the project stands.

   **Tell the assistant:** "The client returned the answers in input/acme-answers.md. Process them and tell me what's next."

   **You'll see:** The questions closed, closed partly and not recognised, then the next step. The brief is rewritten in place with the new facts.

   **What it means:** Each pending mark in the brief that matches an answered question is replaced by the answer.

   <details><summary>In a terminal</summary>

   Under each `### GAP-...` heading the client filled `Answer`, `Owner / source`, `Evidence or reference` and `Decision status` (`confirmed`, `pending` or `not applicable`).

   ```text
   /resolve-gaps ACME_PORTAL --source input/acme-answers.md
   /next ACME_PORTAL
   ```

   If the answers came in another shape, the `sentinel-gap-response` skill helps put them in this one.
   </details>

2. Repeat the round until the assistant stops saying it is waiting for the client.

   **Tell the assistant:** "What should I do next on ACME_PORTAL?"

   **You'll see:** Either *Waiting for client answers* with a new round to plan, or "No blocking gap is open. Close the remaining ones if you can, or move on: write the brief, then the specs."

   **What it means:** With no blocking question left, you can go on to the specs.

   <details><summary>In a terminal</summary>

   ```text
   /next ACME_PORTAL
   ```
   </details>

**How you know it worked.** The answered questions show as closed, and the matching pending marks in the brief are replaced by the answer.

**If something goes wrong.**

- An answer did not close its question. The question code does not exist in the project (unknown ones are listed), the decision status is not "confirmed" (unconfirmed answers never close a question, by design), or the answer is vague ("TBD", "later"), in which case it stays partly closed with a note.
- An answer closed its question but the report flags it: there is no evidence line. Add one next time.
- A question asking for rules or acceptance criteria closed with the note "EARS-eligible, not normalized": only answers written as testable sentences, such as "When an account holder opens the invoice screen, the system shall list every open invoice", become stories later. Propose that wording to the client. One answer can hold several such sentences.
- The same question appears twice in the file: Sentinel merges the answers and says so. If one says confirmed and the other pending, the question does not close; send it again with one decision status.
- The answers came as a meeting note or an email: give them as a change instead (see [Preparing a meeting](#preparing-a-meeting-and-processing-the-minutes)).
- A question is irrelevant: answer it as "not applicable" and say why.

<details><summary>In a terminal</summary>

- Unknown codes are listed in the `/resolve-gaps` result. `Decision status` must be `confirmed` (or `not applicable`) to close.
- The note reads "EARS-eligible, not normalized". Sentences can be on one line or one per bullet under `- Answer:`; each becomes its own requirement.
- Duplicate section: "GAP-USERS: answered in 2 sections; the answers were merged into one."
- `/gaps --disposition` is only for questions an agent raised (see [You want the agent to find what you missed](#you-want-the-agent-to-find-what-you-missed)).
</details>

<a id="the-client-does-not-answer-and-you-need-to-move-on"></a>

## The client does not answer and you need to move on

**When this happens.** A question is blocking the project, the client is silent, and the team decides to go ahead on a reasonable guess.

**What to do.**

1. Register the guess as an *assumption*: a statement you proceed on without confirmation, with a human owner, a risk (how bad it is if wrong) and an uncertainty (how likely it is to be wrong), each low, medium or high.

   **Tell the assistant:** "We'll proceed assuming only claims above 5,000 euros need a second approval. Register it as an assumption owned by me, high risk, citing the request."

   **You'll see:** The assistant confirms the assumption is registered and visible. If risk and uncertainty are both high, it flags "test before advancing" and suggests cheap ways to test it.

   **What it means:** The guess stays visible in the brief, the PRD and the readiness report. The assistant must quote, word for word, the evidence it rests on.

   <details><summary>In a terminal</summary>

   ```text
   /assume ACME_PORTAL --source assumptions.json
   ```

   Listed in `01_discovery/assumptions.md` as `ASSUMED`. The advice reads, for example, "Confirm the cited basis directly with the owner or source before advancing". The `sentinel-assume` skill writes the file.
   </details>

2. Understand what an assumption does not do: it never unblocks a blocking question.

   **Tell the assistant:** "What's next on ACME_PORTAL?"

   **You'll see:** The assistant says an assumption is registered for that question, that it keeps the work visible but never unblocks, and that to move on without the client you confirm the answer in your own name.

   **What it means:** Moving on is your decision, taken on the record.

   <details><summary>In a terminal</summary>

   > An assumption is registered for GAP-SCOPE: it keeps the work visible but never unblocks. To move on without the client, confirm the answer in your own name with /resolve-gaps (Decision status: confirmed, Owner / source: you).
   </details>

3. Take the decision in your own name. Save this as input/ba-decision.md:

   ```markdown
   ### GAP-SCOPE
   - Answer: The first version covers open invoices and PDF download; payments stay out.
   - Owner / source: Maria Lopez, BA (decision taken without client answer)
   - Evidence or reference: request of 2026-11-02, line 4
   - Decision status: confirmed
   ```

   **Tell the assistant:** "Process my decision in input/ba-decision.md."

   **You'll see:** The question closes, and an assumption linked to it is marked validated.

   **What it means:** The project moves on, and the record shows who decided.

   <details><summary>In a terminal</summary>

   ```text
   /resolve-gaps ACME_PORTAL --source input/ba-decision.md
   ```
   </details>

4. Later, the assumption is confirmed or proven wrong through the normal channels. If the client answers the linked question as confirmed, the assumption becomes validated. If a note says the assumption is invalid ("ASM-001 is invalidated: ..."), add it as a change: the assumption becomes invalidated, a question it was holding up opens again, and the brief, PRD, specs and backlog are marked out of date. See [The scope changes after the backlog exists](#the-scope-changes-after-the-backlog-exists).

**How you know it worked.** The project status lists the assumption among its warnings, and after your decision the assistant no longer waits for that question.

**If something goes wrong.**

- The assistant refuses the assumption because the quote is not found word for word in a loaded file: it must be exact, otherwise the question stays open.
- It refuses because an assumption needs a human owner, or because risk must be low, medium or high.

<details><summary>In a terminal</summary>

- "justification quote is not found verbatim in local evidence. Assumptions need a cited basis; otherwise keep the gap open."
- "owner is required and must be human-owned."
- "risk must be low, med, or high."
- `/status` warns "Test before advancing (high risk, high uncertainty): ASM-001."
- The JSON holds an `assumptions` array; each item has `id` (`ASM-...`), `lens`, `statement`, `owner`, `risk`, `uncertainty`, `justification` (the verbatim quote), optional `closes_gap` and `risk_category`. `/maturity` may report `READY_WITH_GOVERNED_ASSUMPTIONS` in `development_readiness.json` once no cell is open. Full options: [`assume`](01-command-reference.md#assume).
</details>

<a id="deepen-discovery-with-the-agent"></a>

## You want the agent to find what you missed

**When this happens.** The checklist questions are answered, but you want a deeper look: hidden assumptions, risks, what one lens says against another.

**What to do.**

1. Ask for the kind of review you want.

   **Tell the assistant:** "Read the request again and find the gaps a reassuring word hid." Or: "Run a pre-mortem on ACME_PORTAL." Or: "Scrutinize the project lens by lens against the domain context."

   **You'll see:** The assistant lists the new questions it found and any finding it refused. Every finding must quote a loaded file word for word, or it is refused.

   **What it means:** New questions are added with a mark of where they came from (the agent, the pre-mortem, the scrutiny). None of these closes a question.

   <details><summary>In a terminal</summary>

   The agent writes a file with the matching skill and the command checks and merges it.

   ```text
   /annotate ACME_PORTAL --source analysis.json
   /challenge ACME_PORTAL --source findings.json
   /scrutinize ACME_PORTAL --source scrutiny.json
   ```

   Skills: `sentinel-annotate`, `sentinel-challenge`, `sentinel-scrutiny`.
   </details>

2. See the effect.

   **Tell the assistant:** "How mature is ACME_PORTAL now?"

   **You'll see:** The maturity report, with the new questions counted.

   **What it means:** It shows whether the project is closer to ready for specs.

   <details><summary>In a terminal</summary>

   ```text
   /maturity ACME_PORTAL
   ```
   </details>

3. For each question the agent raised, record your call.

   **Tell the assistant:** "Accept the question about the audit trail. Mark the one about export format as irrelevant: out of scope for this release."

   **You'll see:** The assistant records each judgement.

   **What it means:** This records what you think of the agent's work. It does not close the question: an accepted or irrelevant question stays open until it is answered ("not applicable" for one that does not apply).

   <details><summary>In a terminal</summary>

   ```text
   /gaps ACME_PORTAL --id GAP-X --disposition accepted
   /gaps ACME_PORTAL --id GAP-X --disposition irrelevant --reason "out of scope for this release"
   ```
   </details>

**How you know it worked.** The assistant lists each accepted finding, and the status counts the questions by origin.

**If something goes wrong.**

- The assistant lists every refused finding and why, usually a quote that is not word for word in the source. Nothing was merged; have the agent fix it and run it again.
- It says the request must be loaded first.
- It refuses a judgement on a checklist question: those came from the checklist, not from an agent. Answer them instead.
- Rejecting or calling a question irrelevant needs a reason.

Checks on the brief, the PRD and the specs are in [Checking quality before handing off](#checking-quality-before-handing-off).

<details><summary>In a terminal</summary>

- "Cannot challenge before /ingest creates 01_discovery/gaps.md." The same holds for `/annotate`, `/scrutinize` and `/assume`.
- "GAP-SCOPE has origin 'checklist'; a disposition applies only to gaps an agentic channel raised (...)"
- `--disposition rejected` and `irrelevant` need `--reason`.
</details>

<a id="domain-context-and-context-requests"></a>

## A domain team must provide context

**When this happens.** Technology, Design, Quality, Frontend or Backend must supply what the client cannot: contracts, screen states, a test strategy.

**What to do.**

1. Write a request for that team.

   **Tell the assistant:** "Write a context request for the technology team on ACME_PORTAL."

   **You'll see:** A request for the team, with an id such as CTX-001, listing what they should document. Send it.

   **What it means:** It tells the team what you need; it does not do their analysis.

   <details><summary>In a terminal</summary>

   ```text
   /context-request ACME_PORTAL --domain technology
   ```

   Written to `08_context_packs/requests/technology_context_request.md`.
   </details>

2. When the answer arrives, load it. The answer file should name the request, for example a first line "Answer to CTX-001".

   **Tell the assistant:** "The technology team answered CTX-001: input/tech-answer.md. Add it."

   **You'll see:** The assistant adds the file and lists the request among the answered ones. If the answer arrived some other way, tell it to mark the request answered.

   **What it means:** Only the file's text is read for the request id, not your note.

   <details><summary>In a terminal</summary>

   ```text
   /sync ACME_PORTAL --source input/tech-answer.md --note "technology answer"
   /context-request ACME_PORTAL --id CTX-001 --status answered
   ```

   The second command is for an answer that arrived some other way.
   </details>

3. Close the request.

   **Tell the assistant:** "Close CTX-001: the contract is confirmed."

   **You'll see:** The request shows as closed.

   **What it means:** Closed and obsolete are final and need a reason.

   <details><summary>In a terminal</summary>

   ```text
   /context-request ACME_PORTAL --id CTX-001 --status closed --reason "contract confirmed"
   ```
   </details>

4. Material the team keeps up to date (a design system, an architecture note) can live in the project as *domain context*. Put the file in the matching context folder of the project (technology, business, design or quality) and ask the assistant to pick up new files.

   **Tell the assistant:** "I put the design system in the design context folder of ACME_PORTAL. Pick up the new files."

   **You'll see:** The assistant lists the new or changed files it picked up.

   **What it means:** A file added as a plain change is recorded as a change, not as domain context.

   <details><summary>In a terminal</summary>

   Folders under `workspaces/ACME_PORTAL/00_raw/`: `02_technology_context/` (or `01_business_context`, `03_design_context`, `04_quality_context`).

   ```text
   /sync ACME_PORTAL
   ```

   With no `--source`. A file loaded with `/sync --source` is recorded as a change.
   </details>

**How you know it worked.** The request shows as closed, and the "pending domain" marks in the brief disappear as the context arrives.

**If something goes wrong.**

- Closing needs a reason.
- An active request cannot be closed directly: mark it answered first, or retire it as obsolete.
- Asking for a request for a domain and for an existing request at once, or for neither, is refused.
- A sync after the backlog exists can make health dirty: see [The scope changes after the backlog exists](#the-scope-changes-after-the-backlog-exists).

<details><summary>In a terminal</summary>

- "--status closed needs --reason."
- "CTX-001 is active; it can move to: answered, obsolete."
- `/context-request` with both `--id` and `--domain`, or with neither, is refused.
- The brief marks read `⏳ PENDING DOMAIN (GAP-X)`.
</details>

<a id="requirement-changes"></a>

## Something changed after a meeting or an email

**When this happens.** New information arrives that is not an answered interview script: meeting notes, an email, a chat thread, a late blocker, a new version of a document.

**What to do.**

1. Load it as a traced change.

   **Tell the assistant:** "Add the notes of the steering meeting to ACME_PORTAL: input/meeting-notes.md."

   **You'll see:** What the change may affect, the questions it closed, new questions it opened, and any contradiction with other sources.

   **What it means:** Read the new questions: Sentinel's checklist runs on the note too.

   <details><summary>In a terminal</summary>

   ```text
   /sync ACME_PORTAL --source input/meeting-notes.md --note "steering meeting"
   ```
   </details>

2. **A late change to something already confirmed** (a note that reverses scope, a decision that replaces an assumption) does not reopen anything by itself. Ask the assistant to read the note and prove the change with quotes.

   **Tell the assistant:** "This board note may reverse a decision we already confirmed: input/board-note.md. Analyse it with quotes and register it."

   **You'll see:** For each change the analysis proves, a blocking question quoting both sides, and a request to confirm a late change.

   **What it means:** You decide each one. Accepting applies the change: the confirmed question reopens (its old answer stays on record) or the assumption is invalidated, and the brief and PRD are marked out of date. Rejecting closes it as a false alarm.

   <details><summary>In a terminal</summary>

   ```text
   /sync ACME_PORTAL --source input/board-note.md --analysis change-analysis.json
   /gaps ACME_PORTAL --id GAP-CHG-3F9A1C --disposition accepted
   /gaps ACME_PORTAL --id GAP-CHG-3F9A1C --disposition rejected --reason "restates the old draft"
   ```

   The `sentinel-sync` skill writes the analysis; `/next` answers *Confirm a late change*. Answer the reopened question with `/resolve-gaps`.
   </details>

3. If the file is a new version of an existing document, say which version governs. Sentinel never assumes the newest wins. See [Two sources contradict each other](#two-sources-contradict-each-other).

4. Regenerate what the change touched, in the order the assistant gives, then check.

   **Tell the assistant:** "Rebuild what the change made stale, then check the health of ACME_PORTAL."

   **You'll see:** Each rebuilt document, then a health check.

   **What it means:** Health is clean again once the stale documents are regenerated.

   <details><summary>In a terminal</summary>

   ```text
   /health ACME_PORTAL
   ```

   Regenerate in the order `/next` or the refusal message gives.
   </details>

**How you know it worked.** The change is stored with an impact report, and health is clean again once the stale documents are regenerated.

**If something goes wrong.**

- The assistant says it takes one file at a time, not a folder. To pick up every new or changed file in the input folders, ask it to scan them.
- An analysis whose quotes are not found in the note or the target is refused as a whole; nothing is written.
- Do not fix the brief, specs or backlog by hand. See [You edited a file by hand](#you-edited-a-file-by-hand).
- After the backlog exists, a change usually makes health dirty: see [The scope changes after the backlog exists](#the-scope-changes-after-the-backlog-exists).

<details><summary>In a terminal</summary>

- "--source must be a file, not a folder": pass one file at a time, or run `/sync ACME_PORTAL` with no `--source`.
- The change is stored under `07_changes/`.
</details>

<a id="two-sources-contradict-each-other"></a>

## Two sources contradict each other

**When this happens.** The request says one thing and a later document says another: "The invoice history is 12 months." against "The invoice history is 24 months."

**What to do.**

1. Load the later document as usual.

   **Tell the assistant:** "Add the steering minutes to ACME_PORTAL: input/steering-minutes.md."

   **You'll see:** A blocking question that quotes both lines with their sources and asks which value governs ("Which value governs for 'the invoice history'? Both sources stay anchored until someone decides."). A subject only one source mentions is not a contradiction.

   **What it means:** Sentinel compares short statements by subject across every source. A list of all contradictions is kept for you.

   <details><summary>In a terminal</summary>

   ```text
   /sync ACME_PORTAL --source input/steering-minutes.md --note "steering meeting"
   ```

   The question is `GAP-CTR-...`, quoting `F-01 line 7` and `F-04 line 5`. `01_discovery/contradictions.md` lists every contradiction.
   </details>

2. Ask which source governs on this kind of topic.

   **Tell the assistant:** "Which source wins for business topics between the request and the steering minutes?"

   **You'll see:** The winner (here the minutes) or "unresolved": no rule settles it and a person decides. Asking changes nothing.

   **What it means:** Sentinel applies fixed precedence rules, for example "Minutes govern business." and "A spec governs over an example; an example never closes a rule." They depend on the kind of source, taken from the file's path: a path that says meeting or minutes is meeting minutes, mail or slack is a mail or chat note, and client, response or interaction is a client document. For a file whose path says none of this, the kind stays unset and the assistant tells you so: tell it the kind ("F-04 is meeting minutes") and ask again.

   <details><summary>In a terminal</summary>

   ```text
   /sources ACME_PORTAL
   /sources ACME_PORTAL --precedence business --between F-01,F-04
   /sources ACME_PORTAL --id F-04 --authority minutes
   ```

   Each file is a numbered source (`F-01`, `F-02`, ...). The `/sync` message for an unset kind: "F-04 has no source kind (authority `unclassified`), so no precedence rule can settle a contradiction it takes part in. Set it: /sources ACME_PORTAL --id F-04 --authority KIND (minutes, decision_record, client_document, interaction, tech_lead, spec, ...)."
   </details>

3. Settle it. The contradiction is a question like any other. Save this as input/history-decision.md:

   ```markdown
   ### GAP-CTR-4BA12C
   - Answer: The invoice history is 24 months; the steering meeting of 2026-11-12 replaced the 12 months of the request.
   - Owner / source: Head of Billing
   - Evidence or reference: steering minutes 2026-11-12
   - Decision status: confirmed
   ```

   **Tell the assistant:** "Process the decision in input/history-decision.md."

   **You'll see:** The contradiction question closes, and the assistant no longer waits for it.

   **What it means:** The value that governs and who decided are on record.

   <details><summary>In a terminal</summary>

   ```text
   /resolve-gaps ACME_PORTAL --source input/history-decision.md
   ```
   </details>

4. If the old document is now obsolete as a whole, say so.

   **Tell the assistant:** "The original request is superseded by the steering minutes."

   **You'll see:** The assistant marks the old source as replaced.

   **What it means:** Or retire it (see [A source was wrong or is outdated](#a-source-was-wrong-or-is-outdated)).

   <details><summary>In a terminal</summary>

   ```text
   /sources ACME_PORTAL --id F-01 --superseded-by F-04
   ```
   </details>

**How you know it worked.** The contradiction question shows as closed and the assistant no longer waits for it.

**If something goes wrong.**

- The answer is "unresolved" even though one document is clearly the minutes: its kind is unset or wrong. Check the source list and correct the kind. The contradiction question says the same when one of its sources has no kind.
- Precedence is asked for one of nine topics; any other topic is refused with the list, and the two sources must be named.

<details><summary>In a terminal</summary>

- `--precedence` takes one of `business`, `scope`, `stack_to_be`, `behavior`, `api`, `compliance`, `legacy`, `design`, `rule`; it needs `--between` and takes no other option.
- Authorities: `minutes`, `decision_record`, `tech_lead`, `built`, `prototype`, `prototype_signoff`, `api_contract`, `norm`, `external_review`, `legacy_artifact`, `reconstruction`, `spec`, `example`, `own_artifact`, `client_document`, `interaction`, `unclassified`.
- While a contradiction is open, a resolved precedence gives an interim value marked `⏳` in the brief; an unresolved one gives none. A source that declares itself a draft only adds proposals, never facts. A source that cites a document never delivered opens a `GAP-CND-...` question. Rules: `sentinel/templates/source_routing.json`; options: [`sources`](01-command-reference.md#sources).
</details>

<a id="a-source-was-wrong-or-is-outdated"></a>

## A source was wrong or is outdated

**When this happens.** A loaded document turns out to be wrong, loaded by mistake, or replaced by a newer agreement, and it must stop counting.

**What to do.**

1. Find its number.

   **Tell the assistant:** "List the sources of ACME_PORTAL."

   **You'll see:** Every loaded file with its number, kind and status (current, replaced or retired).

   **What it means:** You need the number to retire the right one.

   <details><summary>In a terminal</summary>

   ```text
   /sources ACME_PORTAL
   ```
   </details>

2. Retire it, with the reason.

   **Tell the assistant:** "Retire the outdated deck F-06: it was replaced by the commercial agreement, F-07."

   **You'll see:** The source shown as retired with your reason, and the list of what was removed from Sentinel's search memory.

   **What it means:** The file stays on disk for audit, but its text no longer comes back in searches or context bundles. Every document gets a pending review item ("Content that relied on F-06") to check. Questions the file opened stay open: answer them ("not applicable" if they no longer apply). Facts already confirmed from it are not undone; if something confirmed was wrong, reopen it as described in [When something went wrong](21-recovery.md#a-wrong-answer-was-applied).

   <details><summary>In a terminal</summary>

   ```text
   /sources ACME_PORTAL --id F-06 --retire --reason "outdated deck, replaced by the commercial agreement" --replacement F-07
   /sources ACME_PORTAL --id F-06 --cell brief/business --mark reviewed --reason "nothing relied on it"
   ```

   `--replacement` is optional. The text leaves the search memory: `/retrieve` and context packs stop returning it, and `/reindex` skips it.
   </details>

3. If you retired the wrong one, bring it back.

   **Tell the assistant:** "Bring F-06 back, I retired it by mistake."

   **You'll see:** The source is current again and the search memory is rebuilt.

   **What it means:** Nothing is lost.

   <details><summary>In a terminal</summary>

   ```text
   /sources ACME_PORTAL --id F-06 --current
   /reindex ACME_PORTAL
   ```
   </details>

**How you know it worked.** The source list shows the row as retired with your reason, and a search for a phrase from that file no longer returns it.

**If something goes wrong.**

- The assistant needs a reason to retire a source, and only one change of validity at a time (replace, retire, expire or restore).
- For a wrong first request, replace it instead: see [When something went wrong](21-recovery.md#a-wrong-file-was-ingested).

<details><summary>In a terminal</summary>

- "--retire needs --reason: say why the source is dead."
- "Pass only one of --superseded-by, --retire, --expire or --current."
- For a wrong first request use `/ingest --replace`.
</details>

<a id="the-scope-changes-after-the-backlog-exists"></a>

## The scope changes after the backlog exists

**When this happens.** The backlog is written, and a decision changes what the project knows: an assumption proven wrong, a new data source, a changed rule.

**What to do.** Tell the assistant about the change, then let it walk you through the steps. It always knows which step is next.

1. Load the decision.

   **Tell the assistant:** "The sponsor sent a note that changes the scope: input/sponsor-note.md. Add it to ACME_PORTAL."

   **You'll see:** The assistant confirms the note was added and warns that the brief, the PRD, the specs and the backlog are now out of date. The project health shows as dirty.

   **What it means:** *Health* is Sentinel's structural check: clean means nothing is out of date or broken. Dirty means the documents no longer match what the project knows, so they must be regenerated.

   <details><summary>In a terminal</summary>

   ```text
   /sync ACME_PORTAL --source input/sponsor-note.md --note "sponsor note"
   ```
   </details>

2. Try to update the backlog.

   **Tell the assistant:** "Update the backlog for ACME_PORTAL."

   **You'll see:** The assistant refuses and explains why: what the project knows changed after the brief, PRD, specs and backlog were generated. It lists the steps to do, in order: the brief, then the specs, then the backlog.

   **What it means:** This is expected, not a failure. Sentinel will not build a backlog on documents that are older than the change.

   <details><summary>In a terminal</summary>

   ```text
   /backlog ACME_PORTAL
   ```

   > sentinel error: Cannot run /backlog while project health is DIRTY: knowledge changed after project-brief.md, prd.md, specs.md, BACKLOG.md, implementation_readiness.json were generated. Run /brief, then /specs, then /backlog.
   </details>

3. Run the steps it named.

   **Tell the assistant:** "Go ahead: regenerate the brief, then the specs, then the backlog."

   **You'll see:** The assistant does each step and reports it. After each one, the list of what is left gets shorter. When the brief and the specs are regenerated, the backlog runs, and regenerating the backlog clears the last finding.

   **What it means:** The documents match the change again. Asking "what next?" at any point gives the same next step.

   <details><summary>In a terminal</summary>

   ```text
   /brief ACME_PORTAL
   /specs ACME_PORTAL
   /backlog ACME_PORTAL
   ```

   `/next` names the same next command at every step.
   </details>

4. Check quality again.

   **Tell the assistant:** "Check the quality of the backlog again."

   **You'll see:** The quality report. If the backlog has not been regenerated yet, the assistant tells you to do that first. The same goes for refining the backlog.

   **What it means:** Quality is only checked on a backlog that is up to date with the change.

   <details><summary>In a terminal</summary>

   ```text
   /quality ACME_PORTAL
   ```

   Until `/backlog` has run, it refuses ("Run /backlog, then /quality."), and so does `/refine-backlog`.
   </details>

5. **Stale stories.** When the change touches a part of the specs, the stories built from it are marked stale, and the assistant refuses to update the backlog until you review them.

   **Tell the assistant:** "Story US-001 is stale after the change. I reviewed it; put it back to draft."

   **You'll see:** The assistant explains that the backlog contains stale stories after the source change (it names them, for example US-001), and that regenerating does not clear them. After your instruction it confirms the story is back to draft.

   **What it means:** A person has to look at each affected story and decide what happens to it. A stale story can go back to draft, to ready or to blocked, never straight to done. Only a real change makes a story stale: moving another story forward never does.

   <details><summary>In a terminal</summary>

   ```text
   /story-status ACME_PORTAL --story US-001 --set Draft
   ```

   The refusal and `/next` give the exact command.
   </details>

6. **A change of meaning.** When the note uses words that signal a change of meaning ("now", "instead", "must not", "replaces", "out of scope", and similar), Sentinel also asks you to check the links between the documents that this change may touch.

   **Tell the assistant:** "I checked with the Product Owner: no story covers document upload, so nothing downstream has to change. Record that review."

   **You'll see:** Before this, the assistant says it cannot update the backlog while a change of meaning is waiting for review, and lists what the change may touch (the questions, decisions, brief, PRD and specs). After your instruction it shows the change, how many links you marked as reviewed, and that the project is clean if nothing else is open.

   **What it means:** You read the change against those documents. If they have to change, regenerating them after the change clears the finding. If nothing has to change, your short reason is recorded instead. A later source without those words does not clear the finding for you.

   <details><summary>In a terminal</summary>

   `/health` and the `/backlog` refusal say:

   > sentinel error: Cannot run /backlog while project health is DIRTY: Semantic change CHG-007 may invalidate downstream trace links (targets: GAP-001, DEC-001, REQ-002, PRD-001, DISC-003, SPEC-001, SPEC-U-001, SPEC-U-002). Review the targets, then run /brief, then /specs, then /backlog. If nothing downstream has to change, record the review instead with /trace ACME_PORTAL --reviewed CHG-007.

   `/next` gives the same text, titled *Review the semantic change*. To record the review:

   ```text
   /trace ACME_PORTAL --reviewed CHG-007 --reason "Checked with the Product Owner: no story covers document upload."
   ```
   </details>

**How you know it worked.** The assistant tells you the project is clean and the quality check runs. Asking "what next?" returns to the normal backlog steps.

**If something goes wrong.**

- The assistant refuses to update the backlog and lists several problems: each comes with its fix, in the order to do them, and it ends by saying to run the backlog again. Do them in that order.
- The assistant refuses because of an open blocking question or open feedback from the development team: deal with that first, as it explains.
- The assistant says the change you named is not the one waiting for review, and gives the right one: use the one it names. If it says no change is waiting for review, there is nothing to record.

<details><summary>In a terminal</summary>

- `/backlog` refuses with several findings: it lists each one with its fix and ends with "Run /backlog again." The `next step:` line chains the same commands.
- `/trace --reviewed` answers "CHG-009 is not the change waiting for review; /health names CHG-007.": use the id `/health` gives. "No semantic change is waiting for review" means there is nothing to record.

The refusal and `/next` use the same list, built from the `/health` findings: `/reindex` for a record not indexed in memory, the `GAP-CHG` decision or `/resolve-gaps` for a blocking question, `/implementation-feedback` for open feedback, `/story-status ... --set Draft` for each `Stale` story, then the regeneration chain (`/brief`, `/specs`, `/backlog`) for a knowledge change or a change of meaning. `/backlog`, `/quality` and `/refine-backlog` check the staleness markers even when `state.json` says `CLEAN`, so a command that set health on its own criteria cannot let them run on specs older than the brief. The review is stored in `state.json#suspicious_trace_links.reviewed` and on each flagged edge of the traceability graph (`review_status: reviewed`).
</details>

<a id="finding-what-was-said-about-a-topic"></a>

## Finding what was said about a topic

**When this happens.** You need to know what the sources and the decisions say about a topic ("invoice history", "login") without reading every file.

**What to do.**

1. Ask.

   **Tell the assistant:** "What do the sources say about invoice history months? Show me the three best passages."

   **You'll see:** The best-matching passages, each with its file, section and line numbers, so you can open the place it came from.

   **What it means:** The files are the source of truth; memory only helps find them. If a passage and the file disagree, the file wins.

   <details><summary>In a terminal</summary>

   ```text
   /retrieve ACME_PORTAL --query "invoice history months" --workflow discovery --limit 3
   ```

   `--workflow` names what you need the context for (`discovery`, `sync`, `specs`, `implementation`, free text).
   </details>

2. To give an agent a focused bundle instead of whole files, ask for one.

   **Tell the assistant:** "Prepare a context bundle about the invoice API contract for the developers."

   **You'll see:** A saved bundle with the matching passages.

   **What it means:** An agent reads a small bundle instead of the whole project.

   <details><summary>In a terminal</summary>

   ```text
   /retrieve ACME_PORTAL --query "invoice API contract" --workflow implementation --write-pack
   ```

   Written under `08_context_packs/` (for example `discovery.json`).
   </details>

3. To see what happened recently, in order, ask for the timeline.

   **Tell the assistant:** "What happened on ACME_PORTAL recently? Last ten events."

   **You'll see:** The recent events in order.

   **What it means:** It is a quick way to catch up.

   <details><summary>In a terminal</summary>

   ```text
   /retrieve ACME_PORTAL --timeline --limit 10
   ```
   </details>

**How you know it worked.** The passages quote the text you were looking for, with the file they come from.

**If something goes wrong.** A retired source is never returned, by design. If results look out of date after many changes, ask the assistant to rebuild the search memory. A search needs to know what the context is for, unless you ask for the timeline.

<details><summary>In a terminal</summary>

- "/retrieve requires --workflow unless --timeline is used"
- Rebuild with `/reindex ACME_PORTAL`.
</details>

<a id="a-gate-refused"></a>

## A command refused

**When this happens.** The assistant stopped and told you it cannot do something.

**What to do.** Read what it says is wrong and the next step it names. Most refusals name the step. If not, ask "what should I do next?": it gives the one step that unblocks the project.

**Tell the assistant:** "What should I do next on ACME_PORTAL?"

**You'll see:** One next step, with the reason.

**What it means:** Refusals are information, not failures. They group into these kinds:

<!-- Diagram source: user_guide/images/gate-refused.mmd (re-render with tools/render_doc_diagrams.py) -->
![What to do for each exit code, from 1 (an unexpected error to report) to 6 (another command holds the workspace, wait and retry).](images/gate-refused.svg)

| What happened | What to do |
|---|---|
| The request was malformed (a missing detail, a value outside the list) | Say it again with the missing detail. |
| The input is wrong (a file that does not exist, is not text, or is a folder; a quote that is not word for word; an illegal story move). Nothing was written. | Fix what the assistant names and try again. |
| A step is missing first (no project yet, no request loaded, the brief settings not confirmed, health dirty, no stories yet, pending marks for a final export) | Do the step it names. After a change, see [The scope changes after the backlog exists](#the-scope-changes-after-the-backlog-exists). |
| A check gave an unfavourable verdict | Read the findings. To go ahead on purpose, record a cited decision: your reason is kept, the verdict is not faked. |
| Another chat or terminal is working on the same project | Wait and try again. |
| An unexpected error | Keep the text it printed and report it. |

**How you know it worked.** The step you retried runs, and the next step moves on.

**If something goes wrong.** If the same refusal comes back after you did the step, ask for the full status and read the question counts: a question you thought closed may only be answered, not confirmed. More cases in plain words: [When something went wrong](21-recovery.md#a-command-refused).

<details><summary>In a terminal</summary>

Read the `sentinel error:` line, then the `next step:` line. `/next ACME_PORTAL` prints the one step that unblocks the project.

| Code | What it means | Common causes | What to do |
|---|---|---|---|
| 2 | The command line is wrong. | A required option is missing (`--source` on most commands, `--artifact`, `--story`, `--set`); a value outside the list; two `/split` or `/prototype` modes at once. | Fix the command; see the [command reference](01-command-reference.md). |
| 3 | The input is wrong. Nothing was written. | A `--source` file that does not exist, or a folder; a file that is not UTF-8 or not a supported format; an invalid project id; an unknown profile or genesis; an agent file with a quote that is not word for word; options that go together used alone (`/gaps --disposition` without `--id`, `/stakeholders` fields without `--add`, `/split --propose` or `/prototype --trace`/`--manual` without `--source`); a disposition on a checklist question; an illegal story move; a damaged `state.json`. | Fix what the message names and run again. A path is read from the folder you run Sentinel from. For `state.json`, see [When something went wrong](21-recovery.md#a-file-was-deleted-or-is-corrupted). |
| 4 | A step is missing first. | No workspace yet; anything before `/ingest`; `/compose` or `/self-review` before `/specs`; `/refine-backlog` or `/implementation-feedback` before `/backlog`; `/self-review --sufficiency`/`--crosses`, `/split` or `/prototype --trace` without a brief; `/view` of a document not generated yet; maturity `BLOCKED` (often the brief settings: see [A new request arrives](#a-new-request-arrives)); health `DIRTY` for `/backlog`, `/quality` or `/refine-backlog`; `/quality` with no stories; `/export --final` with pending marks; a strict gate in `sentinel.config.yaml`. | Do the step the message or `/next` names. |
| 5 | A check gave an unfavourable verdict. | `/validate` is not `VALID`; `/doctor` is not `PASS`. | Read the findings. To go ahead on purpose: `/validate ACME_PORTAL --override decisions.json`. |
| 6 | Another command is working on the same project. | A second chat or terminal runs a command on the same workspace. | Wait and run again (10 seconds); see [the workspace lock](20-admin-guide.md#the-workspace-lock). |
| 1 | An unexpected error. | A genuine bug. | Keep the text and report it. |

If the same refusal returns: `/status ACME_PORTAL --full` and read the gap counts.
</details>

<a id="release-split"></a>

## The scope is too big for one release

**When this happens.** The brief describes more than one release can carry, or the client wants staged delivery.

**What to do.**

1. Ask whether to split.

   **Tell the assistant:** "Should ACME_PORTAL be split into releases?"

   **You'll see:** A recommendation (split, do not split, or cannot decide) with its reasons. Nothing is split yet.

   **What it means:** It informs your decision; the team decides.

   <details><summary>In a terminal</summary>

   ```text
   /split ACME_PORTAL --assess
   ```
   </details>

2. Have the assistant write a proposal.

   **Tell the assistant:** "Propose a release series for ACME_PORTAL, with cut criteria, quoting the brief for each anchor."

   **You'll see:** The proposal stored, with what confirming it would still refuse.

   **What it means:** A stored proposal is still only a proposal.

   <details><summary>In a terminal</summary>

   ```text
   /split ACME_PORTAL --propose --source proposal.json
   ```

   The `sentinel-release-split` skill writes the file.
   </details>

3. When the BA and the technical team agree, confirm with their names. They give the names, not the assistant.

   **Tell the assistant:** "Confirm the release split. The BA is Ana Ruiz and the technical team is Platform Team."

   **You'll see:** A series overview and one brief per release, plus an open question for the client's own confirmation.

   **What it means:** Release briefs are never edited by hand; they are rebuilt whenever the whole brief changes.

   <details><summary>In a terminal</summary>

   ```text
   /split ACME_PORTAL --confirm --ba "BA NAME" --tech "TEAM NAME"
   ```

   Writes `02_requirements/series/index.md` and `02_requirements/r1/project-brief.md`, ...; opens `GAP-SPLIT-CLIENT`.
   </details>

4. Work each release on its own.

   **Tell the assistant:** "Build the specs, backlog and quality check for release r1 only."

   **You'll see:** The documents for r1.

   **What it means:** Each release has its own documents and status. Follow the whole series in its release guide ("show me the release guide").

   <details><summary>In a terminal</summary>

   ```text
   /specs ACME_PORTAL --release r1
   /backlog ACME_PORTAL --release r1
   /quality ACME_PORTAL --release r1
   /status ACME_PORTAL --release r1
   /view ACME_PORTAL --artifact release-guide
   ```
   </details>

5. Move scope between releases with a reason and both names, never by editing.

   **Tell the assistant:** "Move item C-03 from r1 to r2: it depends on the new ledger. Ana Ruiz and Platform Team agree."

   **You'll see:** The move recorded and dated, and which releases must be rebuilt.

   **What it means:** Every move is on record.

   <details><summary>In a terminal</summary>

   ```text
   /split ACME_PORTAL --move --unit C-03 --from r1 --to r2 --reason "depends on the new ledger" --ba "BA NAME" --tech "TEAM NAME"
   ```

   Moves are dated in `02_requirements/series/scope_changes.md`.
   </details>

6. Close a release when every story is Done and its closing check ran.

   **Tell the assistant:** "Close r1. The closing check is in input/r1-closing-check.md. Ana Ruiz and Platform Team confirm."

   **You'll see:** The release closed and the next one unblocked.

   **What it means:** The closing check result is kept as evidence.

   <details><summary>In a terminal</summary>

   ```text
   /split ACME_PORTAL --close r1 --evidence input/r1-closing-check.md --ba "BA NAME" --tech "TEAM NAME"
   ```
   </details>

**How you know it worked.** The proposal result shows what confirming would still refuse. Moves are dated. A check of each release says whether it is valid.

**If something goes wrong.**

- A brief in the older format cannot be split; confirm the brief settings first.
- A refused proposal, partition or move lists every finding; fix them and run again.
- A missing step refuses with a next step: confirming without a stored proposal or after the brief changed, moving or working on a release without a confirmed series, closing while a story is not Done.
- Moving a unit back where it came from is refused and opens a question until you name the written cut criterion.

<details><summary>In a terminal</summary>

- Older-format brief: confirm with `/brief --profile ... --genesis ...`.
- `--confirm` without a stored proposal or after the brief changed; `--move` or `--release` without a confirmed series; `--close` while a story is not `Done`.
- r1 → r2 → r1 is refused and opens `GAP-SPLIT-CRITERION` until you pass `--criterion`.
- `/validate --release r1` checks each release.
</details>

<a id="prototype-available"></a>

## You have an HTML prototype

**When this happens.** Design delivered an HTML prototype and you want to know what each screen element stands on.

**What to do.**

1. Load it like any later file.

   **Tell the assistant:** "Add the prototype from Design: input/acme-prototype.html."

   **You'll see:** The assistant confirms it was added.

   **What it means:** It is a source like any other; its text is data, never instructions.

   <details><summary>In a terminal</summary>

   ```text
   /sync ACME_PORTAL --source input/acme-prototype.html
   ```

   Use `/ingest` if it is the project's first material.
   </details>

2. List its screens and visible elements.

   **Tell the assistant:** "List the screens and elements of the prototype."

   **You'll see:** The screens, with every visible element numbered.

   **What it means:** Only elements in this list can be cited from now on.

   <details><summary>In a terminal</summary>

   ```text
   /prototype ACME_PORTAL --inventory
   ```

   Written to `02_requirements/prototype/inventory.md`, with ids such as `S1-E01`.
   </details>

3. For each screen, ask for a trace: element, then data, then contract, then rule.

   **Tell the assistant:** "Audit screen S1 of the prototype against the brief: what supports each element and what questions it raises."

   **You'll see:** A verdict per screen and at most four questions.

   **What it means:** A trace with a wrong quote is refused whole.

   <details><summary>In a terminal</summary>

   ```text
   /prototype ACME_PORTAL --trace --source trace-s1.json
   ```

   The `sentinel-prototype-trace` skill writes the file.
   </details>

4. Optionally, ask for a user manual.

   **Tell the assistant:** "Write the user manual for the prototype, screen by screen."

   **You'll see:** A manual for the screens described, with the rest marked as holes.

   **What it means:** The manual cannot drift from the screen.

   <details><summary>In a terminal</summary>

   ```text
   /prototype ACME_PORTAL --manual --source manual.json
   ```

   Skill: `sentinel-prototype-manual`.
   </details>

5. Review the results ("show me the prototype trace page").

   <details><summary>In a terminal</summary>

   ```text
   /view ACME_PORTAL --artifact prototype-trace
   ```

   Also `prototype` and `prototype-manual`.
   </details>

**How you know it worked.** The list shows the screens with numbered elements, and each trace has a verdict per screen.

**If something goes wrong.** The assistant says there is no HTML prototype among the sources: load the file first. A trace needs the brief, and a trace or manual needs the inventory first. A refused trace or manual stores nothing and lists every finding.

<details><summary>In a terminal</summary>

"no HTML prototype among the ingested sources"; `--trace` needs the brief; `--trace` and `--manual` need the inventory.
</details>

<a id="existing-system"></a>

## The system already exists

**When this happens.** The project extends, integrates with or replaces a system whose code you have on your machine (*brownfield*).

**What to do.**

1. Say so.

   **Tell the assistant:** "This extends an existing system. Set the brief as an API project, brownfield extension."

   **You'll see:** The brief settings confirmed.

   **What it means:** Add "document what exists" if the brief should describe what is built rather than what will be built.

   <details><summary>In a terminal</summary>

   ```text
   /brief ACME_PORTAL --profile API --genesis brownfield-extension
   ```

   Add `--validation-direction built` for the second case.
   </details>

2. Ask the assistant to read the code.

   **Tell the assistant:** "Harvest the billing code at ../billing-api for ACME_PORTAL, block by block, tagging every claim."

   **You'll see:** A harvest in blocks B0 to B5; each line is tagged as a fact with its file, an inference, not found, out of code, or a divergence.

   **What it means:** The code never leaves your machine.

   <details><summary>In a terminal</summary>

   Skill: `sentinel-brownfield-harvest`.
   </details>

3. Load it.

   **Tell the assistant:** "Register the harvest: input/harvest.md."

   **You'll see:** The coverage per tag and the questions opened.

   **What it means:** Facts feed the technology section of the brief. Topics outside the code become non-blocking domain questions. Each difference between a README and the code opens a high-severity question.

   <details><summary>In a terminal</summary>

   ```text
   /harvest ACME_PORTAL --source harvest.md
   ```
   </details>

**How you know it worked.** The brief shows the harvest coverage per tag.

**If something goes wrong.** The assistant rejects the harvest and lists each bad line, for example a fact without its file, or a repository not declared in the inventory block. One bad line rejects the whole file. You may deliver one block at a time: the first file needs the inventory block, and a block delivered again replaces that block only.

<details><summary>In a terminal</summary>

"Harvest rejected" lists each bad line. The first file needs B0.
</details>

## A change on something that already exists

**When this happens.** The request is a change or a new feature on a system that is already running, and you want it matured on its own, with its own questions, without touching the project's artifacts. A note that only updates what you are already maturing is not this: use [Something changed after a meeting or an email](#something-changed-after-a-meeting-or-an-email).

**What to do.**

1. Open the change.

   **Tell the assistant:** "This is a change on something that already exists. Open it for ACME_PORTAL: input/change-note.md."

   **You'll see:** A change, `CHG-001`, with only the short scope round: objective, users, scope, and what the product does today against what it should do.

   **What it means:** The change matures apart from the project; nothing of the project is rewritten.

   <details><summary>In a terminal</summary>

   ```text
   /ingest ACME_PORTAL --source input/change-note.md --change
   ```
   </details>

2. Load what the system already says, saying what each document is.

   **Tell the assistant:** "Here is the architecture document of the current system: input/sad.md. It is the baseline of CHG-001 for ACME_PORTAL." Other roles: "this is the prototype of the new design" (`diseno_nuevo`), "this is the brief of the previous release" (`plan_previo`).

   **You'll see:** The document registered as a source with its role, and its `F-NN`. If the request cites another version of it, a blocking question opens asking which version governs.

   **What it means:** Only a document registered as the baseline can close a question `by_baseline`; a file copied by hand into `00_raw/` never does. If nothing is built yet, tell the assistant to waive the baseline and give the reason.

   <details><summary>In a terminal</summary>

   ```text
   /sources ACME_PORTAL --load input/sad.md --role linea_de_base --change CHG-001
   /sources ACME_PORTAL --change CHG-001 --no-baseline --reason "nothing is built yet"
   ```

   The second line is the alternative when there is no baseline.
   </details>

3. Answer the scope with a border, then keep answering.

   **Tell the assistant:** "Process the answers in input/scope.md for change CHG-001 of ACME_PORTAL." To get the change's questions again: "Regenerate the questions of CHG-001."

   **You'll see:** With a valid `Borde:` block, the review round opens, scoped to the change and its border.

   **What it means:** One bad border line rejects the whole file and nothing is written. The full walkthrough, with the border format, is [Scenario 11](12-scenarios.md#scenario-11-a-change-on-something-that-already-exists).

   <details><summary>In a terminal</summary>

   ```text
   /resolve-gaps ACME_PORTAL --source input/scope.md --change CHG-001
   /gaps ACME_PORTAL --change CHG-001
   ```
   </details>

4. Cross the request with the existing system, the prototype and itself.

   **Tell the assistant:** "Compare the request of CHG-001 with the existing system" (it reads the code and the baseline), "cross the request with the prototype" and "check whether the request contradicts itself." If there is no prototype, or you read it and found nothing, say so: the cross-read is waived with a reason, or recorded as read with nothing found.

   **You'll see:** For each cross-read, a count per tag: `RESPALDADO` (the design backs it), `SIN RESPALDO EN DISEÑO` (the request asks for it and the design does not show it), `SOLO EN DISEÑO` (the design shows it and the request does not mention it), `DIVERGENCIA`, `CONTRADICCIÓN` or `SIN HALLAZGOS`. Every divergence and contradiction opens a blocking question; the other two flag their element for the extraction. The not-found parts of the harvest come back as candidate new surfaces, and the assistant asks you to accept or decline each.

   **What it means:** Every finding quotes the request and the design word for word, and Sentinel checks each quote against the document. The cross-read goes stale if you load a new request or prototype afterwards. Sentinel asks for all three before it inventories the request.

   <details><summary>In a terminal</summary>

   ```text
   /harvest ACME_PORTAL --source harvest.md --change CHG-001
   /cross ACME_PORTAL --change CHG-001 --kind diseno --claims cruce_diseno.md
   /cross ACME_PORTAL --change CHG-001 --kind contradicciones --skip --reason "the request has no contradictions to cross"
   /cross ACME_PORTAL --change CHG-001 --accept-new NEW-1A2B3C --type pantalla --name "Historial de aprobaciones"
   ```

   The claims file and its tags are in the [`/cross`](01-command-reference.md#cross) entry.
   </details>

5. Extract the request element by element.

   **Tell the assistant:** "Go through everything the request of CHG-001 says and propose what each element becomes."

   **You'll see:** The list of rules, criteria, stories and decisions of the request with the lines of each, a reading plan in batches, a cited proposal for each (with the lines the assistant read) and the coverage (how many are confirmed out of the total).

   **What it means:** Nothing is confirmed on your behalf. You confirm by section, and a section goes into the brief with the literal text of the request. What Sentinel flagged (a contradiction with the baseline, an element the design does not back) you confirm one by one; an element read only in part is not confirmed until the reading is completed ("Completar las lecturas parciales"). To check the work, ask "re-read a sample of what we confirmed": each element that differs goes back to proposed. The change is `done` only with the whole request covered.

   <details><summary>In a terminal</summary>

   ```text
   /extract ACME_PORTAL --change CHG-001
   /extract ACME_PORTAL --change CHG-001 --proposals proposals.md
   /extract ACME_PORTAL --change CHG-001 --confirm all
   /extract ACME_PORTAL --change CHG-001 --confirm-item RN-04
   /extract ACME_PORTAL --change CHG-001 --verify --sample 10
   /extract ACME_PORTAL --change CHG-001 --verify-result verification.md
   ```
   </details>

6. See whether the change is ready, class what is left and export the final brief.

   **Tell the assistant:** "Is CHG-001 ready?" Open questions that do not block are `construccion` by default and hold the change back; if one is not needed to build, say so: "The Purchasing area resolves GAP-SED-1A2B, it does not stop the build." Then: "Export the final brief of CHG-001."

   **You'll see:** A verdict (`READY`, `READY_WITH_WARNINGS` or `NOT_READY`) with what blocks it, and the brief of the change in the format of the project brief, sealed with status, date, verdict, coverage and deferred items. After the export, `/next --change` goes on to the specs.

   **What it means:** The final brief is the milestone before `/specs --change`. If the change changes afterwards, the export is out of date and `/next --change` asks for it again. `/status --change` also tells you why a workspace is not `CLEAN`.

   <details><summary>In a terminal</summary>

   ```text
   /status ACME_PORTAL --change CHG-001
   /gaps ACME_PORTAL --change CHG-001 --id GAP-SED-1A2B --impact operativo --reason "the Purchasing area resolves it"
   /export ACME_PORTAL --artifact brief --change CHG-001 --final
   ```
   </details>

**If something goes wrong.** `/next --change CHG-001` always names the step in progress (`crosses`, `cross_new_surfaces`, `extract_inventory`, ...), and `/status --change CHG-001` shows the cross-reads and the coverage. `/brief --change CHG-001` compiles the change's brief (see [Scenario 11](12-scenarios.md#scenario-11-a-change-on-something-that-already-exists)); the change's specs are built with `/specs --change CHG-001`, and its stories with `/backlog --change CHG-001`: one story per unit under an epic of its own, with the preserved behavior as pass-to-pass criteria. If the project already has stories, the answer of each modified or removed requirement says which ones it affects (`Afecta`); those become `Stale`, or get a change request when they are already implemented. `/backlog` without `--change` is refused in a workspace that only has changes. Once the backlog exists, `/validate --change CHG-001` checks the change against its border (each answer names its surfaces with `Superficie`), and `/next --change CHG-001` tells you the next step of the change, ending in `done`. `/next` and `/status` also warn when the border looks too big for a change (several processes, new roles, a contract third parties use): the warning never blocks, you decide whether to split the change.

<a id="backlog-refinement-and-story-status"></a>

## Stories need reshaping or moving

**When this happens.** The backlog exists, and stories need an owner, a new status, a split or a merge.

**What to do.**

1. Refresh the board.

   **Tell the assistant:** "Refresh the backlog board for ACME_PORTAL."

   **You'll see:** The board by epic and status.

   **What it means:** It changes no status.

   <details><summary>In a terminal</summary>

   ```text
   /backlog-status ACME_PORTAL
   ```

   Writes `04_backlog/BACKLOG.md`.
   </details>

2. Move a story through delivery.

   **Tell the assistant:** "Mark US-001 as ready and assign it to the Delivery Lead." Later: "US-001 is in progress." "US-001 is done; the evidence is input/us-001-evidence.md."

   **You'll see:** The new status and owner, with warnings if the Definition of Ready or Done is not fully met.

   **What it means:** Moves go one step at a time. Allowed moves:

   | From | To |
   |---|---|
   | Draft | Ready, Blocked, Stale |
   | Ready | Draft, In Progress, Blocked, Stale |
   | In Progress | In Review, Blocked, Stale |
   | In Review | In Progress, Done, Blocked, Stale |
   | Done | Stale |
   | Blocked | Draft, Ready, In Progress, Stale |
   | Stale | Draft, Ready, Blocked |

   Marking a story Ready freezes its acceptance criteria: a later backlog run records any change in a separate list instead of replacing them silently.

   <details><summary>In a terminal</summary>

   ```text
   /story-status ACME_PORTAL --story US-001 --set Ready --owner "Delivery Lead"
   /story-status ACME_PORTAL --story US-001 --set "In Progress"
   /story-status ACME_PORTAL --story US-001 --set "In Review"
   /story-status ACME_PORTAL --story US-001 --set Done --evidence input/us-001-evidence.md
   ```

   Changes are recorded in `04_backlog/acceptance_criteria_deltas.md`.
   </details>

3. Reshape with the assistant (split, merge, missing stories, technical enablers).

   **Tell the assistant:** "US-002 is too big; propose a split, citing the spec unit."

   **You'll see:** The accepted proposals, added as an "Agent Backlog Refinements" section to the epic and to the target stories.

   **What it means:** They are proposals for your review; the story text above is not rewritten.

   <details><summary>In a terminal</summary>

   ```text
   /refine-backlog ACME_PORTAL --source refinement.json
   ```

   Skill `sentinel-backlog-refine`; a report is written under `04_backlog/refinements/`.
   </details>

4. Check again ("check the quality and the traceability").

   <details><summary>In a terminal</summary>

   ```text
   /quality ACME_PORTAL
   /trace ACME_PORTAL
   ```
   </details>

**How you know it worked.** The board shows the status and owner of each story. The full status lists what each story still misses to be Ready or Done. Moving one story leaves the others as they were, and health stays clean.

**If something goes wrong.**

- The assistant says the move is not allowed (for example from Stale straight to Done).
- A failed Definition of Ready or Done warns by default and refuses in strict mode. Add what it lists (an owner, evidence) and retry.
- Refining refuses while health is dirty, and before the backlog exists.
- The backlog commands scan for credentials, private addresses and e-mail addresses. In blocking mode, a finding refuses the command until you remove it at its source.

<details><summary>In a terminal</summary>

- "Illegal story transition: Stale -> Done."
- `/refine-backlog` refuses while health is `DIRTY`, and before `/backlog`.
- The scan covers `04_backlog/`; in `block` mode a finding refuses.
</details>

<a id="the-development-team-asks-a-question-or-finds-a-problem"></a>

## The development team asks a question or finds a problem

**When this happens.** Developers start a story and need context, or they find something the backlog did not foresee: a missing dependency, an acceptance criterion that cannot work, a surface nobody covered.

**What to do.**

1. **A question for a domain team** (contracts, design states): use a context request. See [A domain team must provide context](#a-domain-team-must-provide-context).

2. **A problem found while building.**

   **Tell the assistant:** "While building US-001 we found that older PDFs cannot be generated. Register it as implementation feedback with this evidence."

   **You'll see:** Each finding gets an id (IFB-001, then IFB-002 later; ids never restart). A finding that is a question opens one, listed with the feedback questions.

   **What it means:** Reporting is not rewriting: the backlog is untouched.

   <details><summary>In a terminal</summary>

   ```text
   /implementation-feedback ACME_PORTAL --source feedback.json
   ```

   Skill `sentinel-implementation-feedback`. A finding of type `gap` opens `GAP-FEEDBACK-001`, listed in `01_discovery/implementation_feedback_gaps.md`.
   </details>

3. Understand the block. While a finding is open, health is dirty and the assistant says "Open implementation feedback blocks DoD for US-001 (1)." Updating the backlog, the quality check and refinement all refuse, by design: the backlog should not move while the team says a story is wrong.

4. Decide with the product owner, then close the finding. The new feedback repeats the finding's id and says it is resolved.

   **Tell the assistant:** "The Product Owner decided: older PDFs are out of scope; US-001 keeps 12 months. Mail of 2026-11-17. Mark IFB-001 resolved."

   **You'll see:** The feedback question shows as resolved, no new question opens, and when no finding is open any more health is recomputed by itself.

   **What it means:** The finding id is enough to close it.

   <details><summary>In a terminal</summary>

   ```json
   {"findings": [{"id": "IFB-001", "type": "gap", "story": "US-001", "status": "resolved",
                  "summary": "Older PDFs are out of scope; the story keeps 12 months.",
                  "evidence": "Product Owner mail of 2026-11-17"}]}
   ```

   ```text
   /implementation-feedback ACME_PORTAL --source feedback-resolved.json
   ```
   </details>

**How you know it worked.** The health check no longer lists the feedback. If nothing else is stale, it is clean, and the quality check runs.

**If something goes wrong.**

- Answering the feedback question with the usual answers file does not work: it is reported as unknown. Close it with a feedback file, as in step 4.
- The assistant says there is no backlog yet.
- It says no finding was accepted: the feedback report says why for each (a story that does not exist, no evidence, an unknown type).
- If the decision changes the scope, add it as a change too, and follow [The scope changes after the backlog exists](#the-scope-changes-after-the-backlog-exists).

<details><summary>In a terminal</summary>

- `/resolve-gaps` reports `GAP-FEEDBACK-...` as unknown.
- "Cannot process implementation feedback before /backlog creates 04_backlog/EPIC-001."
- "No implementation feedback findings were accepted": see `07_changes/05_implementation_feedback/feedback_report.md`.
- Finding types: `new-dependency`, `gap`, `ac-challenge`, `surface-not-covered`. Each needs `type`, `story`, `summary` and `evidence`; optional `acceptance_criteria`, `status` (`open` or `resolved`), `blocks_dod` (default true) and `mark_stale` with `source_units`. Full options: [`implementation-feedback`](01-command-reference.md#implementation-feedback).
</details>

<a id="checking-quality-before-handing-off"></a>

## Checking quality before handing off

**When this happens.** You are about to hand the brief, PRD or backlog to someone, and you want to catch problems first.

**What to do.** Each check fits a stage. Ask for them in this order:

| Order | Ask for | What it checks | Available from |
|---|---|---|---|
| 1 | A pre-mortem and a lens-by-lens scrutiny | The discovery: what is not said, risks, lenses that disagree with the domain context. | After the request is loaded |
| 2 | A sufficiency check, a cross-section check and an anchor check on the brief | Is the brief enough to start building, do its sections agree, does each quoted passage say what the brief claims. | After the brief |
| 3 | A skeptical self-review | The PRD and specs, read skeptically by the agent. | After the specs |
| 4 | A quality check | Each story against INVEST and its acceptance criteria; writes test cases. | After the backlog |
| 5 | A trace and a validation | The whole chain: every story traces to its source, the structure is sound. | Any time; most useful at the end |

Checks 1 to 3 follow the pattern of [You want the agent to find what you missed](#you-want-the-agent-to-find-what-you-missed): the assistant writes cited findings, and the command merges what is cited. To polish PRD prose with citations after the specs, ask for a composition pass.

Checks 4 and 5 need nothing from the agent.

**Tell the assistant:** "Check the quality of the backlog, trace every story to its source, validate the project and give me the overall status."

**You'll see:** The quality verdict (pass when every story passes, attention when at least one fails, partial otherwise), the validation verdict (valid or not, with warnings worth reading), and the overall verdict: ready, ready with warnings, or not ready with its blockers.

**What it means:** Ready with warnings is a normal place to hand off from, if you understand each warning.

<details><summary>In a terminal</summary>

```text
/quality ACME_PORTAL
/trace ACME_PORTAL
/validate ACME_PORTAL
/status ACME_PORTAL
```

Checks 1 to 3: `/challenge`, `/scrutinize`, `/self-review --sufficiency`, `/self-review --crosses`, `/scrutinize --mode anchors`, `/self-review`, `/compose` (skills `sentinel-challenge`, `sentinel-scrutiny`, `sentinel-self-review`, `sentinel-compose`). `/quality` answers `PASS`, `ATTENTION` (its audit in `05_quality/` names the stories to fix) or `PARTIAL`; `/validate` answers `VALID`, with warnings such as "assumption ASM-001 is not used anywhere in the body"; `/status` answers `READY`, `READY_WITH_WARNINGS` or `NOT_READY`.
</details>

**How you know it worked.** The validation is valid and the overall verdict is ready (or ready with warnings you understand).

**If something goes wrong.**

- The assistant says the PRD review needs the specs first. The sufficiency and cross-section checks only need the brief.
- The composition pass needs the specs too.
- The quality check refuses while health is dirty, and when there are no stories.
- The status says not ready, "The project brief says: Ready to build: no. 8 pending marks block (§7)": questions are still open in the brief. Answer them, or hand off a draft knowingly.

<details><summary>In a terminal</summary>

- "Cannot self-review before /specs creates PRD/spec artifacts."
- "Cannot compose PRD before /specs creates 03_specs/prd.md."
- "Cannot generate quality artifacts without backlog user stories."
</details>

<a id="showing-progress-to-the-sponsor-or-the-client"></a>

## Showing progress to the sponsor or the client

**When this happens.** You have a steering meeting, or the client asks where things stand.

**What to do.**

1. For an overview of every project in your folder, build the dashboard.

   **Tell the assistant:** "Build the dashboard of all my projects and open it."

   **You'll see:** A page with one card per project: its health, open questions, backlog and next step.

   **What it means:** It is a snapshot; ask again to refresh it. See [Dashboard](14-dashboard.md).

   <details><summary>In a terminal</summary>

   ```text
   /dashboard --open
   ```

   Writes `dashboard.html` in the folder you run it from.
   </details>

2. For one document, build its page.

   **Tell the assistant:** "Show me the readiness view of ACME_PORTAL."

   **You'll see:** A page that answers "what is missing, and from whom". Other pages: the questions, brief, PRD, specs, backlog, diagrams, release guide and prototype pages. See [Artifact views](15-artifact-views.md).

   **What it means:** It is read-only and opens offline.

   <details><summary>In a terminal</summary>

   ```text
   /view ACME_PORTAL --artifact readiness --open
   ```
   </details>

3. For something to send, export it.

   **Tell the assistant:** "Export the brief for the client. Also export the confirmed answers as an FAQ."

   **You'll see:** The exported files. A brief, PRD or context request with pending marks is stamped as a draft. The FAQ lists only questions closed with a confirmed answer, quoted; open questions never appear as answered.

   **What it means:** The exports are written for readers outside the team.

   <details><summary>In a terminal</summary>

   ```text
   /export ACME_PORTAL --artifact brief --format md
   /export ACME_PORTAL --artifact gaps --format faq
   ```
   </details>

**What is safe to share.**

| File | Share with the client? |
|---|---|
| Exports (interview script, FAQ, brief, PRD) | Yes. They are written for readers outside the team. Check a draft's pending marks first. |
| A view page | With care. It shows one document of one project, including question text and pending marks. It loads nothing from the internet and has no full paths. |
| The dashboard | Rarely. It covers **every** project under the folder and can embed their documents. Share it only if the folder holds one client's projects, and keep it out of commits. |
| Working files (the questions list, the project state, the memory folders) | No. |

Loaded files are stored with secrets masked, but client names, figures and decisions are kept as written: everything you share is client material.

**How you know it worked.** The page opens offline in your browser. Its provenance block shows the date of the data and the command that rebuilds it.

**If something goes wrong.**

- The assistant says the document has not been generated yet: ask what to do next.
- It says diagrams are drawn from the brief, which does not exist yet.
- The dashboard looks old: it is a snapshot. Ask for it again.
- A final export refuses while pending marks remain: close them, or export a marked draft instead.

<details><summary>In a terminal</summary>

- "Artifact not generated yet for /view: workspaces/ACME_PORTAL/03_specs/prd.md"; the next step says to run `/next ACME_PORTAL`.
- "/view diagrams needs the brief: ... does not exist." with "Run /brief ACME_PORTAL first."
- "/export --final refused: 8 pending marks remain in the brief (36 deferred marks do not block). Close them (or export without --final to get a marked draft)."
- Exports live under `08_context_packs/exports/`; do not share `gaps.md`, `state.json` or `.sentinel/`.
</details>

<a id="handoff-and-export"></a>

## Handing off to the delivery team

**When this happens.** The backlog is checked and you hand the documents to a delivery team, an agent or a stakeholder.

**What to do.**

1. Run the final checks (see [Checking quality before handing off](#checking-quality-before-handing-off)).

   **Tell the assistant:** "We're about to hand off ACME_PORTAL. Run the final checks and tell me what's next."

   **You'll see:** The trace, health, validation and status results, then "The backlog and its quality check are done. Run the validation, export what you hand off, and track each story."

   **What it means:** Hand off when health is clean, validation is valid, and the verdict is ready (or ready with warnings you understand).

   <details><summary>In a terminal</summary>

   ```text
   /trace ACME_PORTAL
   /health ACME_PORTAL
   /validate ACME_PORTAL
   /status ACME_PORTAL
   ```

   `/next` answers *Validate and hand off*.
   </details>

2. Show what is still missing per item and from whom ("show me the readiness view").

   <details><summary>In a terminal</summary>

   ```text
   /view ACME_PORTAL --artifact readiness
   ```
   </details>

3. Export what you hand over.

   **Tell the assistant:** "Export the brief, the PRD and a design context request. They must have no pending marks."

   **You'll see:** The exported files, or a refusal while pending marks remain.

   **What it means:** A final export refuses until the pending marks are gone.

   <details><summary>In a terminal</summary>

   ```text
   /export ACME_PORTAL --artifact brief --format md
   /export ACME_PORTAL --artifact prd --format mdx
   /export ACME_PORTAL --artifact context-request --domain design --format md
   ```

   Add `--final` when the deliverable must have no pending mark.
   </details>

4. Developers who need sample data can ask for synthetic datasets.

   **Tell the assistant:** "Generate synthetic sample data for the developers from the specs."

   **You'll see:** Disposable sample files, marked as synthetic.

   **What it means:** They are kept out of git and are never evidence.

   <details><summary>In a terminal</summary>

   Skill `sentinel-handoff-datasets`; files land in `08_context_packs/synthetic/`. There is no command.
   </details>

5. From now on, track each story, and bring the team's findings back (see [The development team asks a question or finds a problem](#the-development-team-asks-a-question-or-finds-a-problem)).

**How you know it worked.** Health clean, validation valid, verdict ready (or ready with warnings you understand), and every known uncertainty visible as a question or an assumption. For a release series, check each release.

**If something goes wrong.**

- The validation lists structural findings; quality and consistency findings are warnings only.
- Some exports only work for some documents: the interview script and the FAQ only for the questions list, the MDX format only for the PRD, and a context request needs a domain.

<details><summary>In a terminal</summary>

`interview` and `faq` work only with `--artifact gaps`, `mdx` only with `--artifact prd`, `context-request` needs `--domain`. For a series: `/validate --release r1` and `/status --release r1`.
</details>

<a id="picking-up-a-project-after-weeks"></a>

## Picking up a project after weeks

**When this happens.** You come back to a project after a break, or another BA hands it to you.

**What to do.**

1. Ask where it stands.

   **Tell the assistant:** "I'm picking up ACME_PORTAL after three weeks. Where does it stand?"

   **You'll see:** The one next step; the verdict with its blockers and warnings and the open-question counts; and whether anything is stale or was changed by hand.

   **What it means:** The status always answers, even when the verdict is not ready.

   <details><summary>In a terminal</summary>

   ```text
   /next ACME_PORTAL
   /status ACME_PORTAL
   /health ACME_PORTAL
   ```
   </details>

2. For the picture across projects, ask for the dashboard ("build the dashboard and open it").

   <details><summary>In a terminal</summary>

   ```text
   /dashboard --open
   ```
   </details>

3. Ask the assistant to walk you through the project, in this order: the brief (what the project is and what is still pending), the open questions (with who should answer), the assumptions (what the team proceeds on without confirmation), the list of every file loaded with its status, and the log of the last commands.

   <details><summary>In a terminal</summary>

   Files: `02_requirements/project-brief.md`, `01_discovery/gaps.md`, `01_discovery/assumptions.md`, `07_changes/source_log.md`, `06_traceability/command_protocol_log.md`.
   </details>

4. For what was said about a topic, search instead of reading everything: see [Finding what was said about a topic](#finding-what-was-said-about-a-topic).

**How you know it worked.** You can say in one sentence what the project waits for, and the assistant agrees.

**If something goes wrong.**

- Commands refuse on the new machine with a message about the project state: it did not come along. See [When something went wrong](21-recovery.md#a-file-was-deleted-or-is-corrupted).
- The health check warns about hand edits: see [You edited a file by hand](#you-edited-a-file-by-hand).
- Another chat is working on the same project: commands wait 10 seconds, then refuse. Wait for it to finish.

<details><summary>In a terminal</summary>

The project state is `state.json`. `/retrieve ACME_PORTAL --timeline` lists recent events in order.
</details>

<a id="you-edited-a-file-by-hand"></a>

## You edited a file by hand

**When this happens.** You (or a colleague, or a script) changed a file that Sentinel writes, such as the open-questions list, the brief, the specs or a story. These are *governed artifacts*: only the command that owns each one should change it.

**What to do.**

1. See what Sentinel noticed.

   **Tell the assistant:** "Check the health of ACME_PORTAL."

   **You'll see:** A warning that a governed file was edited outside Sentinel, naming it, and telling you to revert the edit or carry it through the owning command or as a change.

   **What it means:** Before the next command that writes files, Sentinel keeps a copy of every hand-edited file. If that command then rewrites the file, it says where the edited text is kept. Your text is never lost.

   <details><summary>In a terminal</summary>

   ```text
   /health ACME_PORTAL
   ```

   "Governed artifact edited outside the CLI: 01_discovery/gaps.md. Its bytes differ from the last command-produced version; revert the edit, or carry the change through the owning Sentinel command or /sync instead of hand-editing."

   > sentinel warning: /gaps changed hand-edited 01_discovery/gaps.md; the edited text is kept in .sentinel/hand_edits/2026-11-18T012830Z-gaps/. Carry the change through the owning command or /sync, then delete the copy.

   The copies live in `.sentinel/`, which is not in git.
   </details>

2. Carry the change through the proper channel, using the text from the file or its kept copy.

   | Your edit was | Tell the assistant |
   |---|---|
   | A client answer | To process it as an answer |
   | New information or a decision | To add it as a change |
   | Better PRD wording | To compose it into the PRD with citations |
   | A backlog change | To refine the backlog, or to move the story |

   Then delete the kept copy. Or, if the edit was a mistake, undo it (from git or your editor's history).

   <details><summary>In a terminal</summary>

   `/resolve-gaps`, `/sync --source`, `/compose`, `/refine-backlog` or `/story-status`.
   </details>

**How you know it worked.** The health check no longer reports the hand edit or a kept copy.

**If something goes wrong.**

- The health check keeps saying the edited text was changed by a later command and is kept somewhere: delete that copy once you carried the change.
- In Claude Code, an agent that tries to edit a governed file is stopped by a hook that names the owning command. That is expected.
- The kept copies exist only on the machine that ran the command.

More detail: [When something went wrong](21-recovery.md#someone-edited-a-generated-file-by-hand).

<details><summary>In a terminal</summary>

`/health` says "Hand edit of 01_discovery/gaps.md was changed by a later command; the edited text is kept at ...".
</details>

<a id="something-broke"></a>

## Something broke

**When this happens.** A wrong file went in, a wrong answer was applied, or a file is missing or damaged.

**What to do.** [When something went wrong](21-recovery.md) covers each case. The three most common:

- **You loaded the wrong file.**

  **Tell the assistant:** "I loaded the wrong first request. Replace it with input/the-right-request.md."

  **You'll see:** The new request replaces the first one; answered questions open again, and the result lists the saved answer files so you can apply them again.

  **What it means:** If the wrong file came later, retire it instead (see [A source was wrong or is outdated](#a-source-was-wrong-or-is-outdated)). [Details](21-recovery.md#a-wrong-file-was-ingested).

  <details><summary>In a terminal</summary>

  ```text
  /ingest ACME_PORTAL --source input/the-right-request.md --replace
  ```
  </details>

- **A wrong answer closed a question.** Do not edit the questions list. Ask the assistant to reopen it.

  **Tell the assistant:** "The answer to the question about users was wrong. Reopen it: the premise was false."

  **You'll see:** The question opens again, and the old closure stays on record.

  **What it means:** [Details](21-recovery.md#a-wrong-answer-was-applied).

  <details><summary>In a terminal</summary>

  Send an answer file for that question with `Decision status: pending` and `Closure reason: reopened_false_premise`, then `/resolve-gaps`.
  </details>

- **A file is missing or damaged.** Ask the assistant to generate it again (the brief or the PRD). The original sources and the project state cannot be regenerated: restore them from git or a backup. [Details](21-recovery.md#a-file-was-deleted-or-is-corrupted).

  <details><summary>In a terminal</summary>

  Run the command that writes it again (`/brief`, `/specs`). Sources are under `00_raw/` and `07_changes/`, plus `state.json`.
  </details>

Then ask for a health check and a validation.

<details><summary>In a terminal</summary>

```text
/health ACME_PORTAL
/validate ACME_PORTAL
```
</details>

**How you know it worked.** The checks no longer report the problem, and the assistant gives a normal next step.

**If something goes wrong.** If a command prints a traceback, that is a bug: keep the text and report it.

<a id="several-projects-for-the-same-client"></a>

## Several projects for the same client

**When this happens.** One client has several projects: a portal, a mobile app, a report.

**What to do.**

1. Keep one folder per client and create one project per piece of work inside it. Work from the client folder.

   **Tell the assistant:** "Create two projects for ACME: ACME_PORTAL and ACME_MOBILE."

   **You'll see:** Two projects, each with its own questions, brief, backlog and traceability.

   **What it means:** A document that serves two projects is loaded in each. Name projects by the work, not the client; see [Organizing folders](00-user-guide.md#organizing-folders-one-per-client-one-workspace-per-project).

   <details><summary>In a terminal</summary>

   ```text
   /init ACME_PORTAL
   /init ACME_MOBILE
   ```

   Each project gets its own folder under `workspaces/`.
   </details>

2. See them side by side.

   **Tell the assistant:** "Build the dashboard of my projects."

   **You'll see:** One card per project.

   **What it means:** It covers every project under the folder you work in.

   <details><summary>In a terminal</summary>

   ```text
   /dashboard --open
   ```

   `--root PATH` builds it for another folder.
   </details>

**How you know it worked.** The dashboard shows one card per project. Each "what's next" answers for its own project only.

**If something goes wrong.**

- The assistant says the name differs only in letter case from an existing project: names are case-sensitive but Windows folders are not. Use the existing name.
- In a clone of the framework, the clone is the folder, so every client would share one dashboard. Keep one clone per client, or use the plugin or the wheel, which run in any folder.

<details><summary>In a terminal</summary>

"differs only in letter case from the existing workspace".
</details>

## Next

- [Scenarios: worked examples](12-scenarios.md)
- [When something went wrong](21-recovery.md)
- [Command reference](01-command-reference.md)
- [Artifact reference](02-artifact-reference.md)
- [Driving Sentinel from chat](11-chat-commands.md)
