# Covora — Design Specification

- **Date:** 2026-10-17
- **Status:** Approved by the product owner on 2026-10-17, with the sizing and CoALA memory additions
- **Next step after approval:** implementation plan (`superpowers:writing-plans`)

---

## 1. What Covora is, and why

Covora is an autonomous AI sales agent for B2B companies. A user describes the customers they want in plain language (a "vibe prompt"), for example:

> "Find manufacturing companies in the US with 5–25 employees and $5M–$20M in annual revenue. Target people responsible for operations or business partnerships."

Covora's agents then find matching companies, pick the right decision-maker at each one, write personalized cold emails, send them from the user's Gmail, read the replies, hand interested prospects to a salesperson, and learn from the results to run a better next campaign.

**This version is a demo built on simulation.** Companies and people are researched for real, but every email goes only to the team's own test inbox (or, beyond Gmail's daily cap, is delivered inside the app), where a reply simulator plays the prospects. Nothing is ever sent to a real prospect.

It is being built for an AI hackathon. Judges should come away seeing Covora as a go-to sales tool that runs outreach end to end, and then be able to look behind the scenes: every decision the agents made, the evidence behind it, and which NVIDIA Nemotron model handled each step and why. NVIDIA's models and routing technology are central to the product.

**What matters most, in order.** When a design choice trades one of these against polish, these win:

1. A real end-to-end loop that actually works.
2. Transparency: every company and person shown has a reason and a source.
3. A learning loop that makes honest, measurable improvements and never overclaims.

---

## 2. Goals, non-goals, anti-goals

### Goals

1. **End-to-end loop:** vibe prompt → structured ICP → real companies via You.com → decision-makers → personalized drafts → user approves the first batch → sent via Gmail → replies ingested and classified → interested prospects handed to a salesperson → learning agent proposes and runs a measurable improvement.
2. **NVIDIA at the core:** Nemotron Nano and Nemotron Super do all AI work through one shared model gateway, with fixed routing, an optional NeMo Switchyard routing mode, fallback, fixed-model baselines, and full routing observability.
3. **Agent Workflow dashboard:** inspect any run, including stages, tool calls, model calls, routing decisions, tokens, latency, estimated cost, errors, and the evidence behind each output. Runs can be watched live.
4. **Evaluation harness:** measures model and agent quality, compares routing modes against fixed-model baselines, and measures whether the learning loop actually improves results.
5. **Minimal, modern white SaaS UI** with left-hand navigation.
6. **Agents that remember:** CoALA-style memory (working, episodic, semantic, procedural), so agents use past outcomes and the user's corrections. Every memory an agent used is inspectable.
7. **Goal-driven sizing:** the user states the result they want; Covora works out how many prospects to find and what that will cost before it starts.

### Non-goals (this version)

- Sending to real prospects. There is no live mode: every email goes to the test inbox or is delivered in-app.
- Google sign-in, user accounts, multi-tenancy. There is one local workspace.
- Selling to individual consumers (B2C). Covora targets companies and their decision-makers.
- Quoting prices, discount rules, or negotiation. Interested dealers are handed to a salesperson.
- A pre-existing profile dataset. There isn't one: the "20,000" in the original brief described outreach volume, which Covora now computes from the user's goal (§5.2, Campaign sizing).
- Logged-in LinkedIn scraping. People data comes only from public web results via You.com.
- Email open tracking, multi-step follow-up sequences, and calendar integration. Booking happens through each salesperson's own booking link.
- Cloud deployment or production hosting. Covora runs locally.
- A scripted demo. The demo story is explicitly out of scope for this document.

### Anti-goals (a failure even if everything technically works)

- Any invented contact detail or company fact presented as real.
- Any email reaching a real prospect's address.
- Any email sent to a suppressed or unsubscribed prospect.
- The learning agent stating conclusions its data doesn't support.
- API keys, OAuth tokens, or model reasoning text appearing in logs, traces, or the UI.
- Black-box output: a company or person shown without why it was picked and where the information came from.

---

## 3. Decisions

### Made by the product owner

| Topic | Decision |
|---|---|
| Orchestration | LangGraph |
| Frontend | React |
| Backend / DB | Python + FastAPI, PostgreSQL |
| AI models | NVIDIA Nemotron: Nano for light tasks, Super for complex reasoning |
| Routing | Simple fixed routing first; NeMo Switchyard added once the rest works |
| Login | Skip Google sign-in |
| People and company data | Live queries to You.com, generated from the user's requirements |
| Picking prospects | AI decides who the right person is |
| Sending | User approves the first batch of each campaign; after that Covora sends on its own within the daily sending limit |
| Scope | A demo built on simulation: real research, simulated outreach |
| Campaign sizing | Prospects needed = goal ÷ expected reply rate. The owner's example: 10 replies at ~1% → find 1,000 prospects. |
| Agent memory | Follows the CoALA paper (Cognitive Architectures for Language Agents): working, episodic, semantic, and procedural memory (§7.1–7.4) |
| Credentials | NVIDIA and You.com keys go in `.env` |
| Gmail setup | The owner creates a Google Cloud project (Gmail API enabled, OAuth client) and a second Gmail account as the test inbox. Both accounts are regular @gmail.com. |
| Offering type: sales call | The user enters the sales team (name, email, booking link). Interested replies rotate round-robin across reps. Covora replies with that rep's booking link and CCs the rep. |
| Offering type: bulk product to dealers | Interested dealers are handed to the next rep in rotation. Covora never quotes prices. |
| Consumer (B2C) selling | Out of this version; on the "later" list |

### Designer's calls (proposed in conversation, not explicitly confirmed — please review)

| Topic | Call |
|---|---|
| Frontend tooling | React + Vite + TypeScript + Tailwind, as a single-page app. No Next.js, because FastAPI does the server work. |
| How the simulation works | Real Gmail messages, with every prospect address rewritten in code to the test inbox. Research data stays real. |
| Reply simulator | A small agent plays each prospect and replies from the test inbox. Simulated prospects carry hidden preferences so the learning loop can be tested. |
| Mock dataset | A generated dataset with known right answers, used for evaluation and fast simulation, never as the primary data source. |
| Prospect guardrails in code | The suppression list, the "never invent an email address" rule, and "only pick people we actually found" are enforced in code, not left to the AI. |
| One contact per company | One primary contact plus a backup. The backup is contacted only if the primary bounces, says "wrong person", or doesn't reply within a window. |
| Dealer handoff reply | Covora replies to introduce the rep, CCs them, and includes their booking link if they have one. |
| Learning experiments | Concurrent A/B arms inside a new campaign version. Statistics are computed in code, and the AI's claims are checked against them. |
| Background work | One worker process plus a Postgres job table. No Redis or Celery. |
| Live updates | Server-Sent Events (SSE) |
| Tracking | No open tracking; click tracking left out. Positive replies and meetings are the metrics. |
| Sizing defaults | Expected positive reply rate 1%; expected meetings per positive reply 50%. Both are editable, and Covora offers the observed rate once it has enough evidence. |
| Gmail overflow | The first batch and up to the daily Gmail cap go through real Gmail. Beyond the cap, emails are delivered in-app using the same simulator, so a 1,000-prospect campaign doesn't need 10 days. |
| Long-term memory store | Covora's own `memory_item` table with pgvector, not LangGraph's Store, so every memory read and write is traced and embeddings go through the model gateway. |
| Experiment sample sizes | Computed in code from the baseline rate and the smallest lift worth detecting (power calculation). There is no fixed minimum. |

---

## 4. Constraints

- **You.com:** about $100 in credits. Pricing found on 2026-10-17 (verify on you.com's pricing page): Search ≈ $5 per 1,000 calls, Contents ≈ $1 per 1,000 pages. A hard budget cap is enforced (§9.6).
  - Endpoints: `POST https://ydc-index.io/v1/search` (params `query`, `count`; results in `results.web[]` with `url`, `title`, `description`, `snippets`, `page_age`) and `POST https://ydc-index.io/v1/contents` (params `urls`, `formats: ["markdown"]`). Auth header: `X-API-Key`.
- **NVIDIA hosted API:** build.nvidia.com, OpenAI-compatible at `https://integrate.api.nvidia.com/v1`, rate-limited.
  - Model IDs present in the public catalog on 2026-10-17: `nvidia/nemotron-nano-3-30b-a3b` (Nano) and `nvidia/nemotron-3-super-120b-a12b` (Super).
  - The catalog also lists `nvidia/nemotron-3.5-lightning-30b-a3b`, a candidate alternative light model.
  - Model IDs come from env vars, never hard-coded.
- **NeMo Switchyard:** pre-1.0 (`nemo-switchyard` 0.3.0 on PyPI, macOS arm64 wheel available). APIs can change between releases, so pin the version.
- **Gmail:**
  - Two regular @gmail.com accounts: the sender and the test inbox. The OAuth client ID and secret go in `.env`.
  - Consumer sending limits of roughly 500/day.
  - The OAuth app runs in Google's "Testing" status: only listed test users can connect, and refresh tokens expire after 7 days, so reconnecting must be one click.
- **Dev machine:** macOS arm64, Docker (for Postgres), Python 3.10 installed (3.11+ recommended), Node 20.
- **Postgres with pgvector:** for memory retrieval. Use the `pgvector/pgvector:pg16` image.
- **Embeddings:** `nvidia/nemotron-3-embed-1b`, present in the NVIDIA catalog on 2026-10-17.
- **Secrets:** live only in `.env` (gitignored). `.env.example` is committed.

---

## 5. What the user sees

The layout is a left sidebar: Overview · ICP Studio · Prospects · Campaigns · Inbox · Agent Workflow · Settings. The style is white, minimal, and spacious, with clear status badges.

### 5.1 First run: onboarding wizard

1. **Company & product:** company name, website, a description of what they sell and the problem it solves, and key proof points.
2. **Offering type:** `sales_call` (a service or product that needs a call) or `dealer` (a bulk product for distributors or dealers).
3. **Sales team:** one or more reps, each with name, email, and booking link. A booking link is required for `sales_call` and optional for `dealer`.
4. **Goals & limits:** goal type (positive replies or meetings) and target number, expected positive reply rate (default 1%), expected meetings per positive reply (default 50%), daily Gmail send limit, first-batch size, and "no reply" window.
5. **Email:** sender name, title, and signature. Connect the sender Gmail account and the test-inbox account.

Everything entered here can be edited later in Settings.

### 5.2 ICP Studio

- The user types a vibe prompt.
- Nemotron Super turns it into a structured ICP (§9.1). Every field is marked **stated** (the user said it) or **inferred** (the model filled it in), and inferred fields are visually highlighted.
- The ICP includes a **buyer map**: which roles own the problem, who approves spending (by company size), and which titles to skip. It also includes the search queries Covora plans to run.
- The user edits any field and saves. Every save creates a new ICP version, and version history is visible.
- **Launch campaign** creates a campaign from the chosen ICP version. The launch dialog preselects two active templates for the offering type, one per arm; the user can change them. This means even the first campaign produces comparison data for learning.

**Campaign sizing (in the launch dialog):**

- **Prospects needed** = ⌈goal ÷ expected rate⌉.
  - For a replies goal, the rate is the expected positive reply rate.
  - For a meetings goal, it is positive reply rate × meetings per positive reply.
  - Example: 10 positive replies at 1% → **1,000 prospects**. With one contact per company, that is also about 1,000 companies.
- **Observed rate:** once the workspace has its own results, the dialog shows the observed rate with its 95% range next to the assumption. The user picks which to use.
- **Estimate before launch:**
  - companies to find
  - estimated You.com searches and cost
  - estimated model calls
  - how many emails go through Gmail vs in-app delivery
  - whether it fits the remaining You.com budget; if not, the largest campaign that fits
- Per-prospect cost estimates start from config defaults and switch to measured averages after the first campaign.

### 5.3 Prospects

- **Companies tab:** name, domain, fit score, confidence, one-line reason, status, and per-criterion badges (met / not met / unknown).
- **People tab:** name, title, company, role in campaign (primary/backup), pick reason, confidence, email status (verified / unverified / missing), and status.
- **Detail drawer:** every fact with its source link and label (§9.3), plus the agent's reasoning summary (the final explanation only, never raw model reasoning).
- **Exports:** CSV of companies and of people.

### 5.4 Campaigns

- A list of campaigns with their version tree (v1 → v2 → …) and the experiment that created each version.
- **Campaign detail:**
  - A funnel: companies found → qualified → contacts picked → sent → replied → positive → meetings.
  - An arms comparison table (positive reply rate with 95% confidence ranges).
  - Progress toward the meeting goal.
- **Review queue:** the first batch of drafts for the user to read, edit, reject, or approve. Approving releases the batch and switches the campaign to auto-send.
- **Templates tab:** view, create, edit, and deactivate the cold email templates.
- **Experiments tab:** findings, hypotheses, proposed experiments (approve/decline), and results.
- CSV export of campaign results (one row per prospect: status, email sent, reply label, meeting).

### 5.5 Inbox

- All threads, both sent and received, with filters: Needs review · Interested · All.
- Each inbound message shows its classification label and confidence.
- The user can reply inside the portal; the reply is sent in-thread through Gmail and still passes the suppression check and recipient rewrite.
- **Mark meeting booked** button on any thread.
- Every thread shows the intended prospect and a "Simulated: delivered to test inbox" badge.

### 5.6 Agent Workflow

- **Runs list:** kind, campaign, status, duration, model calls, tokens, estimated cost, and errors.
- **Run detail:**
  - A stage timeline that updates live while the run executes.
  - An expandable span tree. Each model call shows task, routing mode, chosen model, routing reason, fallback (if any), tokens, latency, and estimated cost.
  - Each You.com call shows the query, result count, cache hit/miss, and cost.
  - Each stage's outputs, with evidence links.
  - A **working memory panel** for each model call: which memories were loaded (episodic, semantic, procedural), why each was retrieved, and its source.
- **Memory tab:** browse episodic memories (outreach episodes, past picks, the user's corrections) and semantic insights with their evidence levels. You can see what Covora has learned and where each lesson came from.
- **Routing tab:** calls and tokens by model and task, p50/p95 latency, fallback rate, estimated spend, and side-by-side comparison of routing modes.
- **Evaluations tab:** eval runs and their metrics by suite and routing mode (§17).

### 5.7 Overview

- KPIs: sent, positive replies, positive reply rate, meetings vs goal, active campaigns, You.com spend vs budget, and estimated model spend.
- Recent activity feed (live).
- Current experiment status.
- When a reply rate has enough evidence, an estimate of sends still needed to hit the meeting goal, shown as a range.

### 5.8 Settings

- Company profile, offering type, and sales team.
- **Sending:** daily limit, batch size, no-reply window, **Pause all sending**, and the test-inbox address.
- Gmail connections (sender, test inbox) with reconnect.
- Suppression list (view, add).
- Model routing mode, with model IDs shown read-only from env.
- Budgets (You.com cap).

---

## 6. Architecture

```
┌──────────────────────┐   HTTP + SSE   ┌──────────────────────┐
│ React SPA (Vite)     │ ─────────────▶ │ FastAPI  (api)       │
└──────────────────────┘                └──────────┬───────────┘
                                                   │
                                        ┌──────────▼───────────┐
                                        │ PostgreSQL           │
                                        │ app tables, jobs,    │
                                        │ traces, LangGraph    │
                                        │ checkpoints, cache   │
                                        └──────────▲───────────┘
                                                   │
┌──────────────────────────────────────────────────┴──────────────┐
│ Worker process                                                  │
│  • Job runner → LangGraph graphs (campaign, reply, learning)    │
│  • Send loop (Outreach service)                                 │
│  • Gmail poll loop (inbound mail)                               │
│  • Timers (backup activation, learning triggers)                │
└───────┬───────────────────────┬───────────────────────┬─────────┘
        │                       │                       │
┌───────▼─────────┐   ┌─────────▼─────────┐   ┌─────────▼─────────┐
│ Model gateway   │   │ Research provider │   │ Mail provider     │
│ fixed router    │   │ You.com + cache + │   │ Gmail API         │
│ Switchyard      │   │ budget guard      │   │ (sender account)  │
│ baselines       │   │ Mock (evals/tests)│   │                   │
│ → NVIDIA API    │   └───────────────────┘   └───────────────────┘
└─────────────────┘

┌───────────────────────────────┐
│ Reply simulator               │ ── Gmail API (test-inbox account)
└───────────────────────────────┘
```

- The **API** serves the UI, writes user actions, enqueues jobs, and streams events. It never runs long work inline.
- The **worker** runs everything long-running. Graph runs and loops share the database. LangGraph's Postgres checkpointer (`langgraph-checkpoint-postgres`) persists graph state so runs survive restarts and can pause for approval.
- The **model gateway, research provider, and mail provider** are in-process Python modules behind narrow interfaces, so tests and evals can swap in fakes.

**Suggested repo layout** (builder may adjust):

```
backend/covora/
  api/  graphs/  agents/  gateway/  research/  mail/  outreach/
  learning/  observability/  evals/  sim/  db/
frontend/
data/mock/             # generated mock dataset (JSONL)
evals/datasets/        # labeled eval sets
docker-compose.yml     # Postgres
.env.example
docs/
```

---

## 7. Agents, decision cycle, and memory

The brief proposed seven agents. Here is what each becomes. The rule: use a model only where judgment or language is needed, and keep everything with a single correct answer in plain code.

| Brief's agent | In this design | Model |
|---|---|---|
| 1. ICP Planning | One call in ICP Studio (vibe prompt → structured ICP + buyer map), plus query generation inside discovery | Super (ICP), Nano (queries) |
| 2. Company Discovery | Campaign graph nodes `discover_companies` and `score_companies` | Nano (extraction), Super (fit judgment) |
| 3. Decision-Maker Qualification | Campaign graph nodes `find_people` and `select_contacts` | Nano (extraction), Super (selection) |
| 4. Email Personalization | Campaign graph node `draft_emails` | Nano |
| 5. Outreach Management | **Plain service, no model.** Queue, limits, suppression, recipient rewrite, sending, round-robin. | — |
| 6. Response Analysis | Reply graph: the model classifies, code decides and acts | Nano (Super for low-confidence re-check) |
| 7. Recursive Learning | Learning graph: code computes statistics, the model writes findings and hypotheses, code validates them | Super |

All agents share state through PostgreSQL, and every model output is a Pydantic-validated structured object (§9, §12, §14).

Agent memory follows CoALA (Sumers, Yao, Narasimhan & Griffiths, *Cognitive Architectures for Language Agents*, arXiv 2309.02427). It has one short-term **working memory** and three long-term memories: **episodic**, **semantic**, and **procedural**.

### 7.1 The decision cycle

Every model-backed agent step runs the same cycle. It is implemented once as a shared helper, `run_step(...)`, so no agent reinvents it.

1. **Observe:** load the step's inputs. The IDs come from graph state; the records come from the database.
2. **Retrieve:** pull relevant long-term memories into working memory (§7.4). Each memory type has its own token budget.
3. **Reason:** one model-gateway call with working memory rendered into the prompt, returning structured output.
4. **Act:** an external action (a tool call, a draft, a database write) and/or an internal one (a memory write).
5. **Learn:** write an episodic record of what was decided and why. Its outcome is attached later, when known.

For every step, the helper logs what was in working memory: memory item IDs, type, why each was retrieved, and its rank. Those logs are spans, so the Agent Workflow can show "what the agent was looking at" for any decision.

### 7.2 Memory types

| Memory | What it holds in Covora | Where | Written by | Read by |
|---|---|---|---|---|
| **Working** | The current step's assembled context: task inputs, retrieved memories, goal, constraints. Across steps, LangGraph state holds the IDs that carry over. | In-process per step; LangGraph state and checkpoint across steps | `run_step` | The step's model call |
| **Episodic** | Experiences: <br>• *outreach episodes* (prospect snapshot + email attributes + outcome)<br>• *selection episodes* (who was picked at which kind of company, and what happened)<br>• *user corrections* (draft edits, rejections, ICP edits)<br>• *experiment episodes* (what was tried and the result) | `memory_item` (`kind=episodic`), linked to source rows, with an embedding | Outreach service (on outcome), review queue (on edit), ICP Studio (on save), learning cycle (on conclusion) | Personalization, contact selection, ICP parsing, learning |
| **Semantic** | Knowledge: company and contact facts (the `fact` table), the user's company profile, and *insights* promoted from validated learning findings, each with its evidence level | `fact`, `workspace`, `memory_item` (`kind=semantic`, `subtype=insight`) | Enrichment (facts), onboarding (profile), learning `validate_claims` (insights) | ICP parsing, fit scoring, selection, personalization, learning |
| **Procedural** | How to act: templates, versioned prompts, buyer map, routing table, thresholds | `template`, `prompt_version`, ICP/campaign config, config files | The user; the learning agent only through approved experiments | Every step |

### 7.3 Write, update, and decay rules

CoALA names the memory types but doesn't set how each one persists. Covora sets that explicitly:

- **Working memory** is discarded after each step. Only the logged item IDs remain.
- **Episodic memory** is append-only and never edited. Outcome fields are attached when known. Everything is kept, since the scale is small.
- **Semantic facts:**
  - A fact older than 30 days is refreshed when an agent is about to use it.
  - A newer fact supersedes an older one, and the older one is kept for history.
- **Semantic insights:**
  - Each carries its evidence level.
  - A later concluded experiment on the same dimension supersedes it.
  - Only `evidence` and `signal` insights are retrievable. `signal` ones are rendered as *tentative* in prompts. `assumption`s are never stored as insights.
- **Procedural memory:**
  - Every change creates a new version.
  - The learning agent can only *propose* changes. They take effect when the user approves an experiment, because procedural changes alter all future behavior.
- **Isolation:** every memory item records its `source`:
  - `research`: real-researched prospects
  - `gmail_sim`
  - `in_app_sim`
  - `mock_sim`: fast simulation on mock prospects

  Items from `mock_sim` are never retrieved for campaigns on real-researched prospects, and vice versa.
- **Provenance:** every memory item links to the rows it came from. Prompts cite memory item IDs, and outputs that rely on a memory cite it back.

### 7.4 Retrieval

- **Two stages:**
  1. Structured filters first: same offering type, segment, function and seniority, template attributes.
  2. Then similarity ranking with pgvector embeddings.
- Embeddings come from `nvidia/nemotron-3-embed-1b` through the model gateway, with task `embedding`, logged like any call.
- **The embedded text is a short canonical summary**, e.g. *"Operations Manager · 15-person metal fabrication shop · Ohio · short email, question CTA, pain angle → interested"*.

| Agent step | Retrieves into working memory |
|---|---|
| ICP parsing | User's company profile; past ICP versions and the user's edits to them; segment insights |
| Company fit | The ICP; the company's facts; segment insights |
| Contact selection | Buyer map; candidates' facts; selection episodes for similar titles and company sizes, with their outcomes; title insights |
| Email draft | The template; company and contact facts; the top 3 similar *positive* outreach episodes (as style examples, never copied); a summary of the user's past draft edits ("user prefers…"); style insights |
| Reply classification | The thread itself. Long-term memory is not needed beyond the labeled examples in its prompt. |
| Learning analysis | The stats snapshot (computed in code); all experiment episodes; current insights |

**Memory ablation:** every retrieval can be switched off per agent (`MEMORY_ENABLED_<AGENT>=false`), so evaluations can measure what memory adds (§17).

---

## 8. Workflows (LangGraph)

### Rules for all graphs

- **The database is the source of truth.** Graph state holds IDs and small control values only.
- **Every node is idempotent.** It upserts its outputs by natural keys and can be re-run safely.
- Every node opens a trace span and records its inputs (summarized), outputs, and status.
- A node failure marks the run `failed` with an error. The user can **Retry** from the failed node (the checkpoint resumes there).
- **Partial results are fine.** If 7 of 10 companies yield contacts, the run proceeds with 7 and reports the 3 misses with reasons.

### 8.1 Campaign pipeline (one run per campaign version)

```
discover_companies → score_companies → find_people → select_contacts
  → draft_first_batch → ⏸ approval (interrupt) → release_batch
  → draft_remaining → done
```

| Node | What it does |
|---|---|
| `discover_companies` | Runs in **waves** until the campaign has enough qualified companies for its sized target (§5.2), or a stop condition is hit (budget, or max waves, default 15). Each wave: Nano generates fresh search queries from the ICP, excluding domains already seen; run them through You.com; extract candidate companies; dedupe by domain. |
| `score_companies` | Runs per wave. Enrich each candidate (targeted search and/or the Contents API on the company's own site), extract facts with sources, then Super judges each ICP criterion. Code computes the fit score (§9.2). Companies above the minimum score qualify. |
| `find_people` | For each qualified company, run people searches and site pages, then extract named people with titles (§9.4). |
| `select_contacts` | Super picks a primary and a backup (or "no suitable contact") per company. Code validates the picks. |
| `draft_first_batch` | Draft emails for the first K prospects (default 10). Prospects are assigned to experiment arms before drafting (§14). |
| `approval` | LangGraph `interrupt()`. The UI shows the review queue; `POST /campaigns/{id}/approve` resumes with the user's edits, rejections, and approvals. A rejected draft's prospect becomes `skipped` and is not replaced. |
| `release_batch` | Approved drafts are marked `queued`; the send loop takes over. |
| `draft_remaining` | Draft emails for all remaining primaries. They go straight to `queued` (auto-send) without approval. |

A **new campaign version** (from an experiment) runs this same pipeline and gets its own first-batch approval. It may reuse the parent's qualified companies (see §14.4).

### 8.2 Reply handling (one run per inbound message)

```
classify → decide_action (code) → act → done
```

Actions are in §12. Low-confidence classifications are marked **Needs review**, and no automatic action is taken.

### 8.3 Learning cycle (triggered manually, or automatically when a version reaches its sample size)

```
compute_stats (code) → analyze (Super) → validate_claims (code)
  → ⏸ approval of proposed experiment (interrupt) → create_campaign_version → done
```

Creating the version enqueues its campaign pipeline. Details are in §14.

### 8.4 Plain worker loops (not graphs)

- **Send loop:** every few seconds, picks queued emails within limits and sends them (§11).
- **Gmail poll loop:** every 30 s (configurable), fetches new messages on the sender account, matches them to threads, records inbound emails, and enqueues a reply-handling run for each.
- **Timers:** activate backup contacts after the no-reply window; trigger learning when a version reaches its sample size.

---

## 9. Discovery and qualification

### 9.1 Structured ICP

Every leaf value carries `origin: "stated" | "inferred"`.

```json
{
  "summary": "US manufacturers, 5–25 employees, $5–20M revenue; ops and partnerships leaders",
  "industries": [{"value": "manufacturing", "origin": "stated"}],
  "locations": [{"value": {"country": "US"}, "origin": "stated"}],
  "employee_range": {"value": {"min": 5, "max": 25}, "origin": "stated"},
  "revenue_range_usd": {"value": {"min": 5000000, "max": 20000000}, "origin": "stated"},
  "other_criteria": [],
  "exclusions": [],
  "buyer_map": {
    "target_functions": [{"value": "operations", "origin": "stated"},
                         {"value": "business partnerships", "origin": "stated"}],
    "by_company_size": [
      {"employees": {"min": 1, "max": 50},
       "primary_titles": ["Owner", "CEO", "President", "COO", "Operations Manager"],
       "secondary_titles": ["Plant Manager", "Head of Partnerships"],
       "origin": "inferred"}
    ],
    "skip_titles": [{"value": "Recruiter", "origin": "inferred"}]
  },
  "assumptions": ["Read 'business partnerships' as BD/partnerships roles"],
  "search_queries": ["..."]
}
```

### 9.2 Company discovery and fit

- Candidate extraction (Nano) reads search result titles and snippets and returns `{name, domain, source_url}` items. **A company is only created if it appears in a result.**
- Enrichment gathers facts: employee count, revenue, industry, location, description, and notable recent events. It uses targeted searches and the company's own site (about/team pages via Contents).
- Super returns, for each ICP criterion, a status of `met | not_met | unknown` plus the fact IDs it relied on, a confidence (`high | medium | low`), and a one-to-two-sentence reason.
- **Fit score is computed in code**, so it is consistent and explainable. It is the weighted share of criteria met, where `unknown` counts as half and any `not_met` on a hard criterion (industry, location) caps the score low. Weights live in config.
- Revenue for small private companies is usually unknown. It is shown as **unknown**, lowers confidence, and is **never estimated as a number**.

### 9.3 Facts and verification labels

Every fact is stored as `{field, value, source_url, quote, label, retrieved_at}`.

| Label | Meaning |
|---|---|
| **verified** | Explicitly stated on the cited page. A short quote is stored. |
| **unverified** | Inferred from indirect evidence, or from an aggregator or low-reliability source. |
| **unknown** | Nothing found. |

The UI shows the label next to every fact, with a link to its source.

### 9.4 Finding and picking the person

- **People search:** queries such as `"<company>" operations manager linkedin` or `"<company>" leadership team`, plus Contents on the company's team/about page. Nano extracts only people **explicitly named** in a source, with title and source URL.
- Super receives the candidate list, the buyer map, the company's size, and what the user sells. It returns:

```json
{"company_id": "…",
 "primary": {"contact_id": "…", "reason": "…", "confidence": "high|medium|low"},
 "backup":  {"contact_id": "…", "reason": "…", "confidence": "…"},
 "no_suitable_contact": false}
```

- **Code validation:** picked `contact_id`s must be in the candidate list (no invented people), must not be suppressed, and must not be the same person twice. A failed validation is retried once, then the company is marked `needs_review`.
- **Low-confidence picks** are flagged in Prospects but not blocked.
- **No suitable contact:** the company is marked "no suitable contact" instead of getting a forced pick.

### 9.5 Email addresses

- An address is recorded **only if it appears verbatim in a source.**
  - **verified:** on a page that attributes it to that person.
  - **unverified:** a generic inbox (info@, sales@) or ambiguous attribution.
  - **missing:** nothing found.
- No pattern-guessing (e.g., first.last@domain).
- Every prospect is sendable in this version, because delivery always goes to the test inbox. The email-status badge still shows whether the address would be usable for real outreach (only `verified` would be).

### 9.6 You.com usage controls

- **Research provider interface:** `search(query, count) -> results` and `contents(urls) -> pages`. There are two implementations: `YouComProvider` and `MockProvider` (searches the mock dataset; used in tests and evals).
- **Cache:** key = sha256(endpoint + normalized params). Default TTL 14 days. Cache hits are logged as tool calls with `cache_hit=true` and cost 0.
- **Budget guard:**
  - Each call's estimated cost comes from a config price table; running spend is persisted.
  - Hard cap `YOUCOM_BUDGET_USD` (default 80), with a warning at 80% of the cap.
  - At the cap, discovery stops cleanly with a clear error and partial results kept.
- **Pre-launch estimate (§5.2):**
  - Default cost model: about 4 searches + 2 content pages per qualified prospect, doubled to allow for candidates that don't qualify. That's roughly $0.04 per prospect, so a 1,000-prospect campaign costs about $40.
  - The defaults are replaced by measured averages after the first campaign.
  - At this rate, the $100 credit supports roughly 2,000 real-researched prospects in total. That is why large learning experiments use mock prospects (§13–14).
- **Unverified assumption:** whether You.com honours `site:` operators. The builder should test early; if it doesn't, put "linkedin" in the query text instead.

---

## 10. Email personalization and templates

### Templates

- Seed 12 templates. Each has:
  - `name`
  - `angle`: pain / ROI / social-proof / curiosity / partnership / referral-ask
  - `length`: short / medium
  - `tone`: direct / warm / formal
  - `cta`: question / booking-link / soft
  - `subject_template` and `body_template` with placeholders (`{first_name}`, `{company}`, `{personal_hook}`, `{value_prop}`, `{cta}`)
  - an `offering_types` filter
- Users can create, edit, and deactivate templates.
- **Template attributes drive learning:** the learning loop compares angle, length, tone, and CTA, not just template IDs.

### Draft generation (Nano)

- Inputs: template, contact, company facts, the user's company profile, and the arm assignment.
- Output:

```json
{"template_id": "…", "subject": "…", "body": "…",
 "personalization": [{"text": "Saw you added a second CNC line in Dayton", "fact_ids": ["f_123"]}]}
```

### Code checks on every draft

- Every `personalization` item cites at least one fact ID belonging to this company or contact.
- All placeholders are resolved.
- Length is within the template's bounds.
- The body contains no email addresses, phone numbers, or URLs other than allowed ones (the user's website and the rep's booking link).
- The opt-out footer is appended **by code**, not by the model: *"Not relevant? Reply 'unsubscribe' and I won't email again."*
- A failed check triggers one regeneration. If it fails again, the draft is marked `needs_review`.

---

## 11. Outreach service (plain code)

### Send path, in order, for every outbound email

1. Status must be `queued`. Sending is idempotent per email ID: status is re-checked and flipped to `sending` inside a transaction.
2. **Suppression check** on the intended recipient address (normalized). A hit means the email is cancelled with status `suppressed`.
3. **Recipient rewrite:** every prospect address becomes `<test-inbox-local>+p<prospect_short_id>@<test-inbox-domain>`. Store both `intended_to` and `actual_to`. If the rewrite can't be done (no test inbox configured), the send fails. **There is no code path that sends to `intended_to`.** Rep CCs go to the reps' own addresses, since they are the user's team.
4. **Limits:**
   - Daily Gmail cold-send cap: default 100.
   - **Overflow:** the first batch always goes through Gmail. After that, cold emails beyond the day's Gmail cap are delivered **in-app**: written to the database as sent, with no Gmail call, and answered by the same simulator logic (§13). Each email records its `delivery` (`gmail` or `in_app`). The campaign setting "wait for tomorrow's Gmail quota instead" is off by default.
   - Minimum spacing with jitter: default 2–5 s.
   - Replies inside existing threads (e.g., the interested-prospect handoff) do **not** count against the cold cap and jump the queue.
   - **Pause all sending** halts everything.
5. **Send via Gmail API:** RFC 2822 message with our own `Message-ID` and a `List-Unsubscribe: <mailto:{sender}?subject=unsubscribe>` header. Store the Gmail message ID and thread ID.
6. **On failure:** retry with backoff up to 3 times. Permanent failure marks the email `failed` with the error. **Never double-send.**

### Round-robin rep assignment

- Pick the active rep with the oldest `last_assigned_at`, then update it in the same transaction.
- Every assignment is logged.

### Backup activation

- The backup contact gets drafted and queued when the primary:
  - bounces,
  - is classified `wrong_person`, or
  - has no reply within the no-reply window (default 10 minutes, since replies are simulated).
- The backup's draft goes straight to `queued`, because the campaign is already approved.

---

## 12. Reply handling rules

### Classifier output (Nano)

```json
{"label": "interested|not_now|not_interested|wrong_person|unsubscribe|out_of_office|other",
 "confidence": 0.0,
 "referral": {"name": "…", "title": "…"},
 "summary": "one line"}
```

- If confidence is below 0.7, re-check with Super. If confidence is still below 0.6, mark `needs_review`.
- **Rules in code override the model:**
  - Messages from mailer-daemon/postmaster are `bounce`.
  - Messages matching unsubscribe phrases ("unsubscribe", "remove me", "stop emailing") are always treated as `unsubscribe`, whatever the model says.

### Actions (decided by code)

| Label | Action |
|---|---|
| `interested` | Assign the next rep (round-robin). Send an in-thread reply drafted by Nano from the offering-type handoff template, CC the rep, and include the rep's booking link (required for `sales_call`; included if present for `dealer`). **Never mention prices or discounts.** Prospect status becomes `handed_off`. |
| `not_now` | Status `not_now`; no more emails in this campaign. |
| `not_interested` | Status `closed_lost`; no more emails. |
| `wrong_person` | Stop this contact and activate the backup. If a referral was given, show it in Inbox. Never auto-email a referral (we don't have a sourced address). |
| `unsubscribe` | Add to the suppression list immediately and cancel every queued email to that address in every campaign. |
| `out_of_office` | No status change; the no-reply window keeps running. |
| `bounce` | Email status `bounced`; activate the backup. |
| `other` / `needs_review` | Show in Inbox under Needs review; no automatic action. |

**Automatic actions happen at most once per prospect.** Once a prospect is `handed_off` or in a terminal status, later inbound messages on the thread are classified and shown in Inbox, but only `unsubscribe` triggers an action. The rep (or the user, from Inbox) takes it from there. This rule also prevents reply loops with the simulator.

A **meeting** counts when the user clicks *Mark meeting booked*, or when the reply simulator records a synthetic booking (§13).

---

## 13. Simulation: test inbox and reply simulator

All outreach is simulated. Research is real and the emails are real Gmail messages, but every prospect address is rewritten to the team's test inbox (§11).

### Reply simulator

A separate process. It connects to the **test-inbox Gmail account** with its own OAuth token. It answers only **cold emails** (the first Covora message in a thread), never handoff or manual replies. For each new cold email in the test inbox:

1. Parse the `+p<id>` tag and fetch that prospect's contact and company record from the API.
2. Decide the outcome **in code**, from a hidden preference profile (seeded random, so runs are reproducible).
3. Nano writes a reply in that persona that matches the chosen outcome.
4. After a random delay (default 10–120 s), reply in-thread from the test inbox.
5. For `interested` outcomes, with probability `p_book`, record a simulated meeting via `POST /api/sim/meetings`.

Covora ingests these replies through the normal Gmail poll loop; nothing is special-cased. Simulated replies and meetings are labeled **simulated** everywhere they appear.

### Hidden preference profile

Stored as YAML in the repo, e.g. `backend/covora/sim/profiles/default.yaml`:

There are two profiles:

- **`realistic`:** the default, `base_positive_rate: 0.01`, matching the owner's ~1% assumption.
- **`accelerated`:** `base_positive_rate: 0.06`, used to show the learning loop working at feasible sample sizes. It is always labeled as accelerated.

`accelerated` is shown below; `realistic` has the same structure.

```yaml
base_positive_rate: 0.06
multipliers:
  function: {operations: 2.0, partnerships: 1.5, finance: 0.6}
  seniority_by_size: {c_level_at_51_plus: 0.5}
  length: {short: 1.8, medium: 1.0}
  cta: {question: 1.3, booking-link: 0.8}
outcome_mix_when_not_positive: {none: 0.8, not_now: 0.08, not_interested: 0.07, wrong_person: 0.03, unsubscribe: 0.02}
p_book: 0.5
```

Because we planted these preferences, evaluation can check whether the learning loop finds them (§17).

### Three delivery paths, one simulator

| Path | Prospects | Delivery | Use |
|---|---|---|---|
| `gmail_sim` | Real-researched | Real Gmail to the test inbox | First batch, and everything up to the daily Gmail cap |
| `in_app_sim` | Real-researched | In-app: no Gmail, database only | Overflow beyond the Gmail cap (§11) |
| `mock_sim` | Mock dataset | In-app | **Fast simulation** for learning experiments at volume: `covora sim fast --campaign … --profile realistic\|accelerated`. No You.com cost. Drafts may use template-only filling (no model call) via `--no-llm-drafts` for speed. |

- All three use the same outcome logic and the same hidden profiles.
- `in_app_sim` and `mock_sim` replies are written straight to the database, attached to the right prospect, and then go through the normal reply-handling graph.
- `mock_sim` data is shown only when "Show mock simulation" is turned on in Campaigns and on the Overview.

### Mock dataset

- Generated once by a script into `data/mock/`. Roughly 200 companies and 1,500 people across several industries and sizes.
- **Ground-truth labels:**
  - ICP fit for each of 5 test ICPs.
  - The correct decision-maker per company and offering type.
  - Sourced facts with fake source URLs on a reserved domain such as `mock.covora.test`, so they can never be mistaken for real ones.
- Used by `MockProvider`, evals, and fast simulation only.

---

## 14. Recursive learning loop

### 14.1 What is measured

- **Primary metric:** positive reply rate = `interested` replies ÷ cold emails sent.
- **Secondary metric:** meetings ÷ sent.
- **Not used:** opens.
- **Dimensions:**
  - ICP segment (industry, size band, location)
  - contact function and seniority
  - template and template attributes (angle, length, tone, CTA)
  - experiment arm
  - campaign version

### 14.2 Statistics (code, not the model)

- For each group: n sent, positives, meetings, rate, and a 95% Wilson interval.
- Arm comparisons use Fisher's exact test (two-sided).
- **Planned sample size per arm** is computed in code before an experiment starts. It is a two-proportion power calculation from the baseline rate and the smallest lift worth detecting (`min_lift`, default 2×), at α = 0.05 and power = 0.8.
  - At a 1% baseline, detecting 2× needs **about 2,300 sends per arm**.
  - At 6%, it needs about 360.
  - The number is shown to the user before they approve.
- **Each group or comparison gets an evidence level:**
  - **evidence:** the planned sample size was reached and p < 0.05. Results are only judged at the planned size, with no early peeking.
  - **signal:** a directional difference before the planned size, or one that doesn't reach p < 0.05.
  - **insufficient:** too little data to say anything (fewer than 3 positives in the group).
- **At ~1% reply rates, real-researched campaigns will mostly produce `signal` and `insufficient`.** Saying so honestly is the feature. Firm conclusions come from `mock_sim` volume (§13), always labeled as such.

### 14.3 Analysis (Super)

- **Input:** the stats tables and the experiment history, not raw emails.
- **Output:**

```json
{"findings": [{"statement": "…", "evidence_level": "evidence|signal|assumption", "stat_refs": ["row ids"]}],
 "hypotheses": [{"id": "h1", "statement": "…", "rationale": "…"}],
 "proposed_experiment": {
   "hypothesis_id": "h1",
   "change": {"dimension": "target_titles|segment|template|style", "from": "…", "to": "…"},
   "primary_metric": "positive_reply_rate",
   "min_lift": 2.0}}
```

- **`validate_claims` (code) downgrades unsupported claims.** If a finding is labeled `evidence`, all its `stat_refs` must be rows the code flagged `evidence`; otherwise it becomes `signal` (or `assumption` if it has no refs). Every downgrade is logged and shown.
- **One change per experiment.**

### 14.4 Running an experiment

1. The user approves the proposed experiment. This creates **campaign version N+1**, linked to the experiment and its parent version.
2. The new version runs **two concurrent arms** on fresh prospects:
   - **A:** the current best configuration.
   - **B:** the proposed change.
3. Prospects are assigned to arms by a seeded hash of the prospect ID. Running the arms concurrently avoids comparing different weeks or different markets.
4. **Targeting changes** (titles, segment) run discovery/selection twice, once per arm configuration. Prospects are split before contact selection. Companies already contacted in earlier versions are excluded.
5. When both arms reach the planned sample size and the reply window has passed, the experiment result is computed (code) and labeled as in §14.2. The winning configuration becomes the new "current best" only when the result is `evidence`; otherwise it stays as it was.
6. **Version-to-version history** (v1 vs v2 vs v3) is shown as a chart, clearly labeled "not a controlled comparison".

### 14.5 Versioning

- ICPs, templates, and campaign configurations are versioned and immutable once used.
- Each campaign version stores its full configuration snapshot (ICP version, buyer map, template set, arm definitions), so any result can be traced back to exactly what ran.

---

## 15. Model gateway and routing

### 15.1 Interface

```python
result = await gateway.complete(
    task="contact_selection",      # TaskType enum
    messages=[...],
    schema=ContactSelection,       # Pydantic model, or None for free text
    ctx=run_ctx,                   # run/span ids for tracing
)
# result.output (validated), result.model, result.usage, result.latency_ms,
# result.routing (mode, decision, reason, fallback_used)
```

- Every agent calls the gateway; nothing calls NVIDIA directly.
- Transport: the OpenAI-compatible endpoint at `https://integrate.api.nvidia.com/v1` (`openai` SDK with `base_url`, or `httpx`).
- LangGraph nodes call the gateway as ordinary async functions.

### 15.2 Task tiers (fixed routing)

| Nano (`NEMOTRON_NANO_MODEL`) | Super (`NEMOTRON_SUPER_MODEL`) |
|---|---|
| `query_generation`, `company_extraction`, `fact_extraction`, `people_extraction`, `email_draft`, `handoff_reply_draft`, `reply_classification`, `sim_reply_writing`, `routing_judge` | `icp_parsing`, `company_fit`, `contact_selection`, `reply_reclassification`, `learning_analysis`, `eval_judge` |

Embeddings (`NEMOTRON_EMBED_MODEL`, default `nvidia/nemotron-3-embed-1b`) go through `gateway.embed(texts, ctx)` with task `embedding`. Routing modes don't apply to embeddings.

### 15.3 Routing modes (`ROUTING_MODE`, switchable in Settings)

| Mode | Behavior |
|---|---|
| `fixed` | The table above. **Default.** |
| `switchyard` | NeMo Switchyard (`nemo-switchyard`, embedded via its Python libsy API) picks between targets `nano` and `super` per request. The gateway still executes the call, owns retries, and logs Switchyard's decision (selected model and reason) as routing metadata. Start with the classifier-style ("Task" / `llm_classifier`, capability mode) algorithm; the builder may evaluate others. |
| `baseline_nano` | Every task goes to Nano. Evaluation baseline. |
| `baseline_super` | Every task goes to Super. Evaluation baseline. |

- Model calls that a Switchyard algorithm itself makes (e.g., the classifier judging a task) also go through the gateway, using Nano and the task name `routing_judge`, so their cost and latency appear in the routing comparison.
- Switchyard is added **after** the end-to-end loop works in `fixed` mode.
- If Switchyard errors, the gateway falls back to `fixed` for that call and logs it.

### 15.4 Structured output and fallback

- Request JSON output using whichever mechanism the hosted API supports for these models (verify: `response_format` / guided JSON). **Always** validate with Pydantic regardless.
- **Invalid output:** one repair retry (same model, with the validation error), then fall back to the other tier, then fail the call.
- **Transport errors / timeouts:** backoff retries (429/5xx), then fallback tier.
- Every fallback is recorded with its reason.
- Per-model concurrency semaphores and timeouts are configurable to respect rate limits.

### 15.5 Reasoning

- Nemotron 3 models support reasoning on/off. Default: **off for Nano tasks, on for Super tasks** (configurable per task).
- **Reasoning text is never stored, logged, or shown.** Only final outputs and token counts are kept. Each agent's output schema includes a short user-facing `reason` field for explanations.

### 15.6 Cost estimates

A config price table holds per-model input/output prices per 1M tokens. Costs shown in the UI are labeled **estimated**.

---

## 16. Observability

### 16.1 Trace model

The schema is OpenTelemetry-shaped and stored in Postgres, which is what the dashboard reads.

- **workflow_run:** one per graph run or eval run.
- **span:** `trace_id`, `span_id`, `parent_span_id`, `name`, `kind` (`stage | agent | llm | tool | http | db`), `status`, `started_at`, `duration_ms`, `attributes` (sanitized JSON), `error`.
- **llm_call:** links to a span. Holds `task`, `routing_mode`, `requested_model`, `actual_model`, `routing_reason`, `fallback_used`, `fallback_reason`, `prompt_tokens`, `completion_tokens`, `latency_ms`, `est_cost_usd`, `output_valid`, `retries`.
- **tool_call:** links to a span. Holds `provider` (`youcom | gmail`), `operation`, `request_summary` (e.g., the query text), `result_count`, `cache_hit`, `status`, `latency_ms`, `est_cost_usd`.
- **memory_read / memory writes:** each retrieval records the span, memory item, reason, and rank. Each memory write is a span of kind `memory` (§7).

### 16.2 Recording and live view

- A small tracing helper (context manager or decorator) is used by graph nodes, the gateway, and providers.
- **Optional:** the OpenTelemetry SDK also exports spans to an OTLP endpoint if `OTEL_EXPORTER_OTLP_ENDPOINT` is set (e.g., a local Phoenix or Jaeger).
- The UI's live view comes from SSE endpoints that stream new spans and status changes for a run (§19).

### 16.3 What is stored about model calls

- Prompts and final outputs are stored (for debugging and evals) after **redaction**.
- Redaction is a filter that strips known secret patterns, OAuth tokens, and any env-var values marked secret.
- Reasoning content is dropped before storage.
- A `LOG_LLM_PAYLOADS=false` switch stores summaries only.

### 16.4 Business-level observability

- Qualification results with evidence (§9).
- Campaign funnels and arm stats (§14).
- Experiment history.

All of these are shown in Prospects, Campaigns, and Agent Workflow.

---

## 17. Evaluation

**Runner:** `covora eval run --suite <name|all> --mode <fixed|switchyard|baseline_nano|baseline_super|all>`. Results are stored in `eval_run` / `eval_result` and shown in Agent Workflow → Evaluations. Model calls made during evals are traced like any other run.

| Suite | Dataset | Metrics |
|---|---|---|
| `icp_parsing` | ~20 vibe prompts with expected structured ICPs | field-level accuracy; stated/inferred labeling accuracy |
| `company_fit` | mock companies labeled fit/no-fit for 5 test ICPs | precision, recall, precision@10 |
| `contact_selection` | mock companies with candidates, labeled correct primary per offering | top-1 accuracy; primary-or-backup accuracy; "no suitable contact" correctness; invented-person rate (must be 0) |
| `reply_classification` | ~150 labeled replies (synthetic + hand-written edge cases) | accuracy, macro-F1, **unsubscribe recall (must be 100% with code rules)** |
| `email_groundedness` | drafts generated for mock prospects | share of personalization claims backed by cited facts; unsupported-claim rate (Super judge + code checks); template adherence |
| `learning_recovery` | `mock_sim` with the `accelerated` profile, plus a `realistic` run to confirm the loop correctly reports `insufficient` at small n | did the loop identify the planted top factor within K cycles; positive-rate uplift with CI; false "evidence" claims after validation (must be 0) |
| `memory_ablation` | `contact_selection`, `email_groundedness`, and `learning_recovery`, re-run with memory off (§7.4) | difference in each suite's metrics, memory on vs off |

- **Routing comparison:** each suite × each routing mode gives a table of quality vs tokens vs latency vs estimated cost. This is the fixed-model baseline comparison the brief asks for.
- **NeMo Agent Toolkit** (`nat eval` / profiler) is optional. The builder may wire it in alongside the in-house runner if it adds value, but the in-house runner is the baseline.

---

## 18. Data model (PostgreSQL)

Conventions:
- UUID primary keys; `created_at` / `updated_at` on every table.
- JSONB for structured blobs.
- Migrations via Alembic.
- A single workspace row is seeded on first run, and every domain table carries `workspace_id` so adding real accounts later doesn't require reshaping data.

**Workspace and setup**

| Table | Columns |
|---|---|
| `workspace` | `id`, `name`, `website`, `description`, `value_props`, `offering_type` (`sales_call`/`dealer`), `target_meetings`, `sender_name`, `sender_title`, `signature`, `timezone`, `settings` (JSONB: daily cap, batch size, no-reply window, test-inbox address, paused), `youcom_spend_usd` |
| `sales_rep` | `id`, `workspace_id`, `name`, `email`, `booking_url`, `active`, `last_assigned_at` |
| `mail_account` | `id`, `workspace_id`, `role` (`sender`/`test_inbox`), `email`, `encrypted_token`, `token_expires_at`, `status` |

**ICP and campaigns**

| Table | Columns |
|---|---|
| `icp_version` | `id`, `workspace_id`, `version`, `prompt_text`, `structured` (JSONB, §9.1), `parent_id`, `created_by` (`user`/`agent`) |
| `template` | `id`, `workspace_id`, `name`, `angle`, `length`, `tone`, `cta`, `subject_template`, `body_template`, `offering_types`, `active`, `version` |
| `campaign` | `id`, `workspace_id`, `name`, `root_campaign_id`, `version`, `parent_campaign_id`, `experiment_id`, `icp_version_id`, `config_snapshot` (JSONB: buyer map, templates, arms), `status` (`draft`/`running`/`awaiting_approval`/`sending`/`complete`/`failed`), `target_meetings` |
| `campaign_arm` | `id`, `campaign_id`, `key` (`A`/`B`), `config` (JSONB) |

**Companies, people, prospects**

| Table | Columns |
|---|---|
| `company` | `id`, `workspace_id`, `name`, `domain` (unique per workspace), `synthetic` |
| `fact` | `id`, `company_id`, `contact_id` (nullable), `field`, `value` (JSONB), `source_url`, `quote`, `label` (`verified`/`unverified`/`unknown`), `retrieved_at` |
| `campaign_company` | `campaign_id`, `company_id`, `arm_key`, `criteria` (JSONB), `fit_score`, `confidence`, `reason`, `rank`, `status` |
| `contact` | `id`, `company_id`, `full_name`, `title`, `function`, `seniority`, `linkedin_url`, `source_urls`, `email`, `email_status` (`verified`/`unverified`/`missing`), `email_source_url`, `synthetic` |
| `prospect` | `id`, `short_id`, `campaign_id`, `arm_key`, `contact_id`, `role` (`primary`/`backup`), `pick_reason`, `confidence`, `status` (`selected`/`drafted`/`queued`/`sent`/`replied`/`handed_off`/`not_now`/`closed_lost`/`bounced`/`suppressed`/`skipped`/`no_contact`/`needs_review`), `assigned_rep_id`, `meeting_booked_at`, `meeting_synthetic` |

**Email**

| Table | Columns |
|---|---|
| `email_message` | `id`, `campaign_id`, `prospect_id`, `direction` (`out`/`in`), `kind` (`cold`/`handoff`/`manual_reply`/`inbound`), `status` (`draft`/`needs_review`/`approved`/`queued`/`sending`/`sent`/`failed`/`suppressed`/`bounced`/`received`), `intended_to`, `actual_to`, `cc`, `subject`, `body`, `template_id`, `personalization` (JSONB), `gmail_message_id`, `gmail_thread_id`, `rfc_message_id`, `delivery` (`gmail`/`in_app`), `source` (`gmail_sim`/`in_app_sim`/`mock_sim`), `sent_at`, `received_at`, `error` |
| `reply_classification` | `email_message_id`, `label`, `confidence`, `model`, `referral` (JSONB), `summary`, `rule_override` |
| `rep_assignment` | `id`, `prospect_id`, `sales_rep_id`, `reason` |
| `suppression` | `email_normalized` (PK), `workspace_id`, `reason`, `source_email_id` |

**Learning**

| Table | Columns |
|---|---|
| `experiment` | `id`, `workspace_id`, `parent_campaign_id`, `variant_campaign_id`, `hypothesis`, `change` (JSONB), `primary_metric`, `min_lift`, `baseline_rate`, `planned_sends_per_arm`, `status` (`proposed`/`approved`/`declined`/`running`/`concluded`), `result` (JSONB: per-arm n/positives/rates/CI/p), `evidence_level` |
| `learning_analysis` | `id`, `workspace_id`, `run_id`, `stats_snapshot` (JSONB), `findings` (JSONB, after validation), `downgrades` (JSONB), `hypotheses` (JSONB) |

**Memory (§7)**

| Table | Columns |
|---|---|
| `memory_item` | `id`, `workspace_id`, `kind` (`episodic`/`semantic`), `subtype` (`outreach_episode`/`selection_episode`/`user_correction`/`icp_edit`/`experiment_episode`/`insight`), `source` (`research`/`gmail_sim`/`in_app_sim`/`mock_sim`), `summary` (the embedded text), `payload` (JSONB), `source_refs` (JSONB: table + id pairs), `outcome` (JSONB, nullable, attached later), `evidence_level` (insights only), `superseded_by`, `embedding` (`vector`, dimension from the embedding model) |
| `memory_read` | `span_id`, `memory_item_id`, `reason`, `rank` |
| `prompt_version` | `id`, `name`, `version`, `body`, `active` |

**Observability, jobs, cache, evals**

| Table | Columns |
|---|---|
| `workflow_run` | `id`, `kind` (`campaign`/`reply`/`learning`/`eval`), `campaign_id`, `status`, `started_at`, `ended_at`, `error`, `thread_id` (LangGraph) |
| `span`, `llm_call`, `tool_call` | as in §16.1 |
| `job` | `id`, `kind`, `payload`, `status`, `attempts`, `run_after`, `locked_at`. Picked with `FOR UPDATE SKIP LOCKED`. |
| `search_cache` | `key` (PK), `endpoint`, `params`, `response`, `created_at` |
| `eval_run`, `eval_result` | `suite`, `mode`, `metrics` (JSONB), per-sample rows |

LangGraph checkpoint tables are created by `langgraph-checkpoint-postgres` in their own schema.

---

## 19. API (FastAPI, JSON, prefix `/api`)

| Area | Endpoints |
|---|---|
| Workspace | `GET/PUT /workspace` · `GET/POST/PUT/DELETE /sales-reps[/{id}]` |
| Gmail | `GET /mail/accounts` · `POST /mail/connect?role=sender\|test_inbox` (returns Google OAuth URL) · `GET /mail/oauth/callback` · `POST /mail/accounts/{id}/disconnect` |
| ICP | `POST /icp/parse` (prompt → structured draft, synchronous Super call) · `POST /icps` (save version) · `GET /icps` · `GET /icps/{id}` |
| Campaigns | `POST /campaigns/estimate` (goal + rates → prospects needed, cost and call estimates, budget fit) · `POST /campaigns` (from ICP version) · `GET /campaigns` · `GET /campaigns/{id}` (incl. funnel, arm stats) · `POST /campaigns/{id}/run` · `POST /campaigns/{id}/retry` · `GET /campaigns/{id}/review` (first-batch drafts) · `PATCH /emails/{id}` (edit draft) · `POST /campaigns/{id}/approve` (body: approved/rejected IDs and edits; resumes graph) · `POST /campaigns/{id}/pause` |
| Prospects | `GET /campaigns/{id}/companies` · `GET /campaigns/{id}/prospects` · `GET /companies/{id}` (facts, evidence) · `GET /contacts/{id}` |
| Templates | `GET/POST/PUT /templates[/{id}]` · `POST /templates/{id}/deactivate` |
| Inbox | `GET /inbox/threads?filter=` · `GET /inbox/threads/{thread_id}` · `POST /inbox/threads/{thread_id}/reply` · `POST /prospects/{id}/meeting` |
| Learning | `POST /learning/analyze?campaign_id=` · `GET /learning/analyses/{id}` · `GET /experiments` · `POST /experiments/{id}/approve` · `POST /experiments/{id}/decline` |
| Observability | `GET /runs?kind=&campaign_id=` · `GET /runs/{id}` (span tree) · `GET /runs/{id}/events` (SSE) · `GET /events` (SSE, global activity) · `GET /metrics/routing?from=&to=` · `GET /metrics/overview` |
| Memory | `GET /memory?kind=&subtype=&source=` · `GET /memory/{id}` (with source rows) · `GET /runs/{id}/spans/{span_id}/memory` (working memory for one step) |
| Evals | `POST /evals/run` · `GET /evals` · `GET /evals/{id}` |
| Suppression | `GET /suppression` · `POST /suppression` |
| Exports | `GET /exports/companies.csv?campaign_id=` · `GET /exports/prospects.csv?campaign_id=` · `GET /exports/campaign-results.csv?campaign_id=` · `GET /exports/experiments.csv` |
| Simulation | `POST /sim/meetings` (used by the reply simulator) · `POST /sim/fast` |
| Health | `GET /health` (DB, NVIDIA reachability, You.com key present, Gmail token status) |

Errors use the shape `{"error": {"code": "...", "message": "...", "details": {...}}}`.

---

## 20. Error handling

- **External calls (NVIDIA, You.com, Gmail):** timeouts on every call; exponential backoff with jitter on 429/5xx (max 3); errors recorded on the span.
- **Model output:** Pydantic validation, then repair retry, then fallback tier, then node failure (§15.4).
- **Graph nodes:** idempotent. A failure marks the run `failed` with the node and error, and the UI offers Retry, which resumes from the checkpoint.
- **Budget exhaustion:** discovery stops cleanly, keeps partial results, and shows a clear message.
- **Gmail token expired/revoked:** sending and polling pause for that account, a banner appears with a one-click Reconnect, and queued emails wait. Nothing is lost.
- **Sending is never doubled:** status transitions happen in transactions, and send results are written immediately.
- **Inbound mail** that matches no known thread is stored as unmatched and shown in Inbox, with no automatic action.
- **Worker restart:** jobs with stale `locked_at` are re-picked, and graphs resume from checkpoints.

---

## 21. Security and privacy

- **Secrets:**
  - `.env` is gitignored and `.env.example` lists every variable without values.
  - Keys are never sent to the frontend.
  - OAuth tokens are encrypted at rest (Fernet, key from `TOKEN_ENCRYPTION_KEY`).
- **Local-only by default:** API and UI bind to localhost. CORS is limited to the frontend origin. There is no auth, because the app is single-user and local; this is acceptable only because it isn't deployed.
- **Gmail scopes:** `gmail.send` and `gmail.readonly` (or `gmail.modify` if the builder labels processed mail), and nothing broader.
- **Logs and traces:** redaction filter; reasoning text dropped; no tokens or keys anywhere (§16.3).
- **No real prospect is ever emailed:** the recipient rewrite and the suppression check are enforced in the send path and covered by tests. The unsubscribe footer and header are always present, so the unsubscribe flow works end to end.
- **Personal data:**
  - Only public professional information (name, title, company, source URLs, sourced email) is stored.
  - Deleting a contact removes its facts and drafts.
  - Suppressed addresses are kept (hashed is acceptable) so they're never re-contacted.

---

## 22. Testing

- **Unit tests (pure code):**
  - suppression and recipient rewrite (including "no path sends to `intended_to`")
  - send-path ordering and idempotency
  - limits and spacing
  - round-robin assignment
  - fit-score computation
  - draft checks
  - unsubscribe/bounce rules
  - Wilson intervals / Fisher test / evidence levels
  - claim validation and downgrades
  - redaction
- **Gateway tests:** a fake model backend covering validation, repair retry, fallback, and routing-mode selection (including a stubbed Switchyard decision).
- **Graph tests:** each graph run against a fake gateway, `MockProvider`, and a fake mail provider, including the approval interrupt/resume and retry-after-failure paths.
- **Provider contract tests:** recorded You.com and Gmail responses (fixtures). Live calls are behind an opt-in marker.
- **Frontend:** component tests for the review queue, Inbox, and run detail; one smoke test of the main flow against a seeded backend.
- **Evals (§17)** are separate from tests and are not part of the default test run.

---

## 23. Risks and unknowns

| Risk | Mitigation |
|---|---|
| You.com people results are thin, or LinkedIn pages don't show up. | Also mine company team/about pages via Contents. Test early. Report "no suitable contact" honestly instead of forcing picks. |
| Revenue is rarely public for small private companies. | Treat it as unknown (neutral, lower confidence); never invent a number. |
| Hosted Nemotron structured-output support or rate limits differ from assumptions. | Always validate with Pydantic; semaphores; verify the mechanism in the first integration task. |
| Switchyard is pre-1.0 and its API may shift. | Pin 0.3.0; isolate it behind the gateway; fixed mode is always available. |
| Gmail Testing-mode tokens expire after 7 days. | One-click reconnect; health endpoint shows token status. |
| At ~1% reply rates, experiments need about 2,300 sends per arm, more than the You.com budget can research. | Power-based sample sizes shown up front; firm conclusions come from `mock_sim`; real campaigns report `signal`/`insufficient` honestly. |
| A 1,000-prospect campaign means about 3,000+ model calls under hosted rate limits. | Per-model concurrency limits; waves show progress live; partial results are usable. |
| Model IDs change in the catalog. | Env-configured; `/health` checks they exist. |

---

## 24. Left to the builder

- Library choices within the stack: SQLAlchemy vs SQLModel, `uv` vs pip, state/data-fetching libraries in React (TanStack Query suggested), charting (Recharts suggested).
- Prompt wording, template copy, and the mock-dataset generation method.
- Visual design details within "minimal white SaaS with left navigation".
- Exact default thresholds, caps, and windows. Every number in this document is a configurable default.
- How SSE is fed (polling the span table vs Postgres LISTEN/NOTIFY).
- Which Switchyard algorithm to ship as the default `switchyard` mode, decided by the routing-comparison eval.
- Whether to add NeMo Agent Toolkit profiling/eval on top of the in-house harness.

---

## 25. Suggested build order

Each step ends in something runnable and tested.

1. **Skeleton:** repo layout, Docker Postgres, migrations, `.env.example`, FastAPI health, React shell with sidebar, and the worker with the job table.
2. **Model gateway + tracing + memory core:** fixed routing, validation, fallback, the `llm_call`/`span` tables, embeddings, `memory_item` + `run_step` (the decision cycle), and a minimal Agent Workflow run view.
3. **ICP Studio:** parse, edit, and versions.
4. **Discovery:** research provider (You.com + cache + budget + Mock), the `discover_companies`/`score_companies` nodes, and the Companies tab.
5. **Qualification:** the `find_people`/`select_contacts` nodes and the People tab with evidence.
6. **Drafts + approval:** templates, `draft_*` nodes, and the review queue with the interrupt/resume.
7. **Sending:** Gmail OAuth, the outreach service (recipient rewrite, suppression, limits), and the send loop.
8. **Replies:** poll loop, reply graph, handoff with round-robin, Inbox, and the reply simulator.
9. **Learning:** stats, analysis, validation, experiments and versions, and fast simulation.
10. **Evals + routing comparison:** suites, the mock dataset, Switchyard mode, and the Routing and Evaluations tabs.
11. **Polish:** Overview, exports, Settings completeness, and empty and error states.
