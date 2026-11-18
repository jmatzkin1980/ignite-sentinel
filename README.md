# Ignite Sentinel

Ignite Sentinel helps you turn a client's raw request (a note, an email, meeting minutes, a prototype) into a project brief, a PRD, a backlog and test cases. It does not write requirements up for you: it finds what is missing, turns it into questions for the right person, and only builds on answers someone has confirmed. Everything it writes says where it came from.

It is for **business analysts and product managers** working on real client projects, and for the developers who receive their work. You use it from the AI assistant you already have (Claude Code, Codex or Kilo Code) or from a plain terminal.

**What you get:** a list of open questions you can send to the client, a brief that cites every answer, a clear "what is still missing and from whom", a readiness verdict you can defend, and stories with acceptance criteria and test cases, each traced back to its source.

**Your client's data.** Sentinel runs on your machine and makes no network calls: every file it writes stays in your project folder. Your AI assistant, though, reads the client's documents and Sentinel's files in order to help you, so that content goes to the assistant's model provider, under your organization's agreement with it. When that is not allowed, run Sentinel from a plain terminal, and nothing leaves your machine. Details in [Privacy](user_guide/00-user-guide.md#privacy).

Version 0.16.1 · [What changed](CHANGELOG.md) · New words are explained in the [glossary](user_guide/00-user-guide.md#glossary).

## Get started in 10 minutes

You need **Python 3.10 or newer** and nothing else. Check with `python --version`.

### 1. Pick your tool

| You use | Install, in one step | Then type commands as |
|---|---|---|
| Claude Code, least setup | Add the plugin: `/plugin marketplace add jmatzkin1980/ignite-sentinel#stable`, then `/plugin install ignite-sentinel@ignite-sentinel` ([Path A](user_guide/06-installation-vscode.md#path-a-claude-code-plugin-from-the-marketplace)) | `sentinel /init ACME_PORTAL` |
| Claude Code, with every command as `/command` | Copy the repository: `git clone https://github.com/jmatzkin1980/ignite-sentinel.git` and open the folder ([Path B](user_guide/06-installation-vscode.md#path-b-claude-code-clone)) | `/init ACME_PORTAL` |
| Codex | Copy the repository and open the folder in Codex ([Path C](user_guide/06-installation-vscode.md#path-c-codex-clone)) | `sentinel /init ACME_PORTAL` |
| Kilo Code (VS Code) | Copy the repository and open the folder in VS Code ([Path D](user_guide/06-installation-vscode.md#path-d-kilo-code-clone)) | `/init ACME_PORTAL` |
| A terminal only | Copy the repository, or install the package file from a release ([Path E](user_guide/06-installation-vscode.md#path-e-terminal-only-no-agent)) | `python -m sentinel /init ACME_PORTAL` |

No git, a locked-down machine or no internet? Every path, step by step, is in **[Install: choose your path](user_guide/06-installation-vscode.md)** and [Secure environments](user_guide/09-secure-environments.md).

The rest of this page shows commands in chat form (`/init ...`). Add the prefix from the last column of the table for your tool. You can also ask in plain words, for example: *"Create a Sentinel project ACME_PORTAL from input/acme-request.md and tell me what is missing."*

### 2. Try it on a sample request

In the folder you run Sentinel from, create a folder `input/` and save this made-up request as `input/acme-request.md`:

```markdown
# ACME customer portal

ACME wants a web portal where account holders see their open invoices.
They log in with their customer number and download each invoice as a PDF.
Overdue invoices should stand out. Payments stay out of this first version.
The billing team owns the invoice data; it comes from the current billing system.
Go-live is wanted before the end of the quarter.
```

Then run these five commands, one at a time:

```text
/doctor
/init ACME_PORTAL
/ingest ACME_PORTAL --source input/acme-request.md
/brief ACME_PORTAL --profile UI --genesis greenfield
/next ACME_PORTAL
```

1. `/doctor` checks your setup. You see the verdict `PASS`.
2. `/init` creates the project folder `workspaces/ACME_PORTAL/`. You see its path. The project starts with health `DIRTY`, which is normal: nothing is known yet.
3. `/ingest` reads the request and writes the list of open questions to `workspaces/ACME_PORTAL/01_discovery/gaps.md`. Open it: each question says why it matters and has an answer form.
4. `/brief` tells Sentinel, once, what kind of system this is: a user interface (`UI`) on a new build (`greenfield`). You see the path of the project brief, with a pending mark wherever an answer is missing. ([What these values mean](user_guide/00-user-guide.md#the-brief).)
5. `/next` tells you what to do now: *Waiting for client answers.* Send the client the interview script, which you create with `/export ACME_PORTAL --artifact gaps --format interview`.

> [!NOTE]
> In a Claude Code clone, `/init` and `/doctor` can start Claude Code's own built-in commands instead of Sentinel's. If that happens, send `/sentinel /init ACME_PORTAL` or `/sentinel /doctor`. With the plugin, always type `sentinel /doctor`.

When the client's answers come back, `/resolve-gaps ACME_PORTAL --source input/acme-answers.md` reads them. The [first run end to end](user_guide/00-user-guide.md#first-run-end-to-end) walks the whole project from here to test cases, with what you see at each step.

## How it works

<!-- Diagram source: user_guide/images/readme-how-it-works.mmd (re-render with tools/render_doc_diagrams.py) -->
![How Sentinel works: intake and brief settings produce gaps, answers go through a maturity check that loops back to the gaps until it is ready, then come the PRD and specs, the backlog and the test cases; changes, prototypes and release splits feed in on the side.](user_guide/images/readme-how-it-works.svg)

1. **You load what the client gave you.** Sentinel keeps a copy in the project folder, masks anything that looks like a password or key, and lists every missing or unclear point as a question, called a **gap**.
2. **You confirm what kind of system it is**, once: its profile (screens, API, batch, ...) and whether it is new or changes an existing system. Sentinel proposes the values; you decide.
3. **You send the questions to the client** as an interview script. Each answer comes back under its question.
4. **Sentinel reads the answers.** Only a confirmed answer closes a question. Each one fills its place in the project brief; whatever is still unknown stays visible as a pending mark, never a guess.
5. **Sentinel checks maturity.** When no blocking question is left, the requirement is ready for specs. If not, you plan another round of questions.
6. **Sentinel writes the PRD, the backlog and the test cases**, each linked back to the answers and sources it came from.
7. **Changes keep coming.** A meeting note or an email goes through `/sync`, which records it as a change and shows what it affects, instead of silent scope creep. A project too big for one delivery can be split into releases.

At every point, `/next` tells you the one thing to do, and a command that cannot run yet says why and what to run first.

## Commands at a glance

| To... | Run |
|---|---|
| Check that Sentinel works | `/doctor` |
| Start a project | `/init ACME_PORTAL` |
| Load the client's request | `/ingest ACME_PORTAL --source input/acme-request.md` |
| Confirm what kind of system it is (once) | `/brief ACME_PORTAL --profile UI --genesis greenfield` |
| Know what to do next | `/next ACME_PORTAL` |
| Get the questions to send to the client | `/export ACME_PORTAL --artifact gaps --format interview` |
| Process the client's answers | `/resolve-gaps ACME_PORTAL --source input/acme-answers.md` |
| Bring in a meeting note, an email or a new document version | `/sync ACME_PORTAL --source input/meeting-notes.md` |
| Check whether it is ready for specs | `/maturity ACME_PORTAL` |
| Write the PRD, the backlog and the test cases | `/specs ACME_PORTAL`, then `/backlog ACME_PORTAL`, then `/quality ACME_PORTAL` |
| See where the project stands | `/status ACME_PORTAL` |
| Review a document in your browser | `/view ACME_PORTAL --artifact brief` |
| See all projects of this client | `/dashboard` |

Every command, with its options and what it refuses, is in the [command reference](user_guide/01-command-reference.md). What to do in each situation (the client answered, a change arrived, a command refused) is in [Workflows](user_guide/03-workflows.md), and complete examples are in [Scenarios](user_guide/12-scenarios.md).

## Good to know

- **One folder per client, one workspace per project.** The folder you open is the root; each `/init` adds a project under its `workspaces/` folder, and `/dashboard` shows every project of that root. See [organizing folders](user_guide/00-user-guide.md#organizing-folders-one-per-client-one-workspace-per-project).
- **Do not edit Sentinel's documents by hand.** The brief, the gaps list, the specs and the backlog change only through their command; fix the answer or the evidence instead. See [what you may edit](user_guide/00-user-guide.md#what-you-may-edit).
- **Updates.** With the plugin, a new release arrives through **Update marketplace** in `/plugin`; see [updating the plugin](user_guide/18-claude-plugin.md#updating-the-plugin).
- **The assistant closes with a choice.** When something waits on you, it ends with one question and a few options, the recommended one first. Pick one or answer in your own words; picking never closes a gap for you.
- **Something went wrong?** A wrong file, a wrong answer, a refusal you do not understand: see [When something went wrong](user_guide/21-recovery.md) and [a gate refused](user_guide/03-workflows.md#a-gate-refused).

## Learn more

| Page | For |
|---|---|
| [00 Start here](user_guide/00-user-guide.md) | Concepts, first run end to end, glossary |
| [03 Workflows](user_guide/03-workflows.md) | What to do in each situation |
| [12 Scenarios](user_guide/12-scenarios.md) | Worked examples |
| [11 Chat and MCP](user_guide/11-chat-commands.md) | Driving Sentinel from chat; plain words to commands |
| [14 Dashboard](user_guide/14-dashboard.md) · [15 Artifact views](user_guide/15-artifact-views.md) · [17 Themes](user_guide/17-themes.md) | HTML pages to review with the client and the team |
| [21 When something went wrong](user_guide/21-recovery.md) | Wrong file or answer, hand edits, lost or damaged files, refusals |
| [06 Install](user_guide/06-installation-vscode.md) | Choose your path |
| [07 Kilo Code](user_guide/07-kilo-code-adapter.md) · [08 Codex](user_guide/08-codex-adapter.md) · [13 Claude Code](user_guide/13-claude-adapter.md) · [18 Claude Code plugin](user_guide/18-claude-plugin.md) | Using Sentinel in that tool |
| [01 Command reference](user_guide/01-command-reference.md) | Every command: options, outputs, refusals, exit codes |
| [02 Artifact reference](user_guide/02-artifact-reference.md) | Every file Sentinel writes and who may change it |
| [04 Skills catalog](user_guide/04-codex-skills-guide.md) | The 27 assistant skills |
| [05 Traceability and memory](user_guide/05-traceability-and-memory.md) | Links between items, search, context packs |
| [10 Versioning workspaces](user_guide/10-repo-and-branching-strategy.md) | Keeping your projects in git |

## For IT and security

- [Secure environments](user_guide/09-secure-environments.md): offline machines, virtual desktops, approved installs, optional extras.
- [Portability](user_guide/16-portability.md): modes without install, the single-file `.pyz`, and [a note for IT](user_guide/16-portability.md#a-note-for-it). An older note in Spanish: [PORTABILITY.md](PORTABILITY.md).
- [Threat model](user_guide/19-threat-model.md): assets, threats, controls and how to verify each.
- [Admin guide](user_guide/20-admin-guide.md): managed settings, version pinning, retention, audit trail.
- [Security policy](SECURITY.md): how to report a vulnerability, supported versions.

Contributing to the framework itself? See [MAINTAINERS.md](MAINTAINERS.md). Release history: [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE) © 2026 jmatzkin1980
