# Covora Plan 3 — Outreach, Replies, Learning, Evals & Switchyard: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Covora's loop. Covora drafts personalized emails from templates in two A/B arms, and the user approves the first batch. Everything is then delivered in-app to simulated prospects. A reply simulator with hidden preferences answers. Covora classifies each reply and hands interested prospects to the next salesperson with their booking link. The learning loop computes honest statistics, proposes one-change experiments, and runs them as new campaign versions. On top: evaluation suites compare routing modes (fixed, NeMo Switchyard, Nano-only, Super-only), and dashboards show routing, memory, evaluations and an overview.

**Why one plan:** the owner asked to finish soon. This plan replaces the spec's plans 3–6 with a trimmed combined version and is built straight through. It covers spec §5.4–§5.8, §10–§14, §15.3, §17, and the remaining parts of §16 and §19.

**Architecture:**
- **Campaign graph:** after `select_contacts`, it continues with `assign_arms → draft_first_batch → approval (interrupt) → release_batch → draft_remaining`.
- **Worker periodic loops:** sending every 2 s, and backup activation every 30 s.
- **Jobs:**
  - `sim.reply`: the simulator answers one cold email.
  - `reply.handle`: classify the reply, then act.
  - `learning.analyze`: run one learning analysis.
  - `eval.run`: run evaluation suites.
- **Delivery:** in-app now, behind a channel interface. A Gmail channel plugs in later without other changes.

**Spec:** `docs/superpowers/specs/2026-10-17-covora-design.md`.

**Builds on:** Plans 1–2 and all their ledger rulings, including:
- Postgres on port 5434.
- The light tier is `nemotron-3.5-lightning`, with `response_format` structured output and reasoning off.
- The output-schema rules: `$ref`s inlined and every property required.
- `clean_strings` on free text.
- Agent inputs are sent as one JSON user message.
- Memory degrades gracefully when it fails.
- Handlers live in `covora.jobs.registry`.
- Every model is imported via `covora.db.all_models`.

## Global Constraints

- Everything from Plans 1–2 applies.
- **Delivery:**
  - Every outbound email goes through the channel chosen by `choose_delivery()`. In this plan that is always `in_app`.
  - `actual_to` is never the prospect's real address. In-app mail records `actual_to = "in-app"`.
  - There is no code path that sends to `intended_to`.
- **Suppression** is checked inside the send path for every outbound email, and code rules for unsubscribe phrases win over the model's label.
- **Automatic actions** happen at most once per prospect. After `handed_off` or a terminal status, only `unsubscribe` still acts.
- **The simulator answers only cold emails.** Simulated outcomes are decided in code from a seeded random generator and a YAML profile; the model only writes the text.
- **Statistics** live in code (Wilson intervals, Fisher's exact test, power calculation). The learning model's `evidence` claims are downgraded unless code-computed rows back them.
- **Templates** use `{first_name}`, `{company}`, `{personal_hook}`, `{value_prop}`, `{cta}`, `{sender_name}`. The opt-out footer is appended by code: *"Not relevant? Reply 'unsubscribe' and I won't email again."*
- **Never mention prices or discounts** in any generated email.
- **Switchyard:** `nemo-switchyard==0.3.0`, `llm_task_classifier` with target names `efficient` → Nano and `capable` → Super. Any Switchyard error falls back to fixed routing and records the reason. Judge calls are logged with task `routing_judge`.
- **Polling, not SSE, for live views. Gmail and calendar integrations are out of this plan.**

## Review Focus

1. **A reply that says "unsubscribe" but reads as interested.** Code rules win: the prospect is suppressed, every queued email to that address is cancelled, and no handoff happens. Pinned in Task 7: `test_unsubscribe_phrase_overrides_interested_label`.
2. **The simulator answering Covora's own handoff reply.** That would make a loop; the simulator answers only cold emails, and automatic actions happen once per prospect. Pinned in Task 6 `test_simulator_ignores_handoff_replies` and Task 7 `test_second_interested_reply_takes_no_action`.
3. **Approving while the graph isn't paused, or approving twice.** The API returns 409, and nothing is sent twice. Pinned in Task 4: `test_approve_requires_awaiting_approval`.
4. **Small samples.** The learning model labels a finding `evidence` without rows that support it. Validation downgrades it to `signal`, or `assumption` when it has no references. Pinned in Task 10: `test_unsupported_evidence_claim_downgraded`.
5. **No sales rep configured when a prospect replies "interested".** The prospect goes to Needs review with "Add a sales rep in Settings", and no reply is sent. Pinned in Task 7: `test_interested_without_reps_needs_review`.

---

## File Structure

```
backend/covora/
  outreach/models.py          # Template, CampaignArm, EmailMessage, ReplyClassification, SalesRep, RepAssignment, Suppression
  outreach/templates.py       # seed (templates_seed.json), sync_templates, pick_default_templates
  outreach/templates_seed.json
  outreach/arms.py            # create_arms, arm_for
  outreach/drafts.py          # DraftEmail schema, draft_email (Nano), check_draft, fill_template
  outreach/delivery.py        # choose_delivery, InAppChannel
  outreach/send.py            # send_due (periodic), cancel_queued_to
  outreach/suppression.py     # normalize_email, is_suppressed, suppress
  sim/profiles/{realistic,accelerated}.yaml
  sim/simulator.py            # load_profile, features_for, decide_outcome, write_reply (Nano), sim.reply job
  sim/fast.py                 # fast simulation on mock prospects (no LLM, no web)
  replies/schemas.py          # ReplyLabel, ReplyClassification schema
  replies/handle.py           # classify, rule overrides, act; reply.handle job
  replies/backups.py          # activate_due_backups (periodic)
  replies/outcomes.py         # outreach episodes + selection-episode outcomes (memory)
  learning/stats.py           # wilson, fisher_exact, required_n_per_arm, evidence_level
  learning/tables.py          # outcome rows by arm and dimension
  learning/models.py          # Experiment, LearningAnalysis
  learning/analyze.py         # learning agent (Super), validate_claims, insights, learning.analyze job
  learning/experiments.py     # approve → new campaign version with arms A/B; conclude
  gateway/switchyard.py       # SwitchyardRouter
  evals/{__init__,__main__,runner,suites}.py ; evals/models.py (EvalRun, EvalResult)
  api/routes/{templates,reps,inbox,review,learning,evals,metrics,memory,sim}.py
  prompts/{email_draft,handoff_reply_draft,reply_classification,sim_reply_writing,learning_analysis}.md
backend/evals/datasets/{icp_parsing,reply_classification}.jsonl
frontend/src/
  features/review/ReviewQueue.tsx  features/templates/TemplatesTab.tsx
  features/settings/{SalesTeamForm,SimulationForm}.tsx
  pages/Inbox.tsx  features/inbox/{ThreadList,ThreadView}.tsx
  features/learning/{ArmStats,ExperimentsPanel}.tsx  pages/Overview.tsx
  features/runs/{RoutingTab,MemoryTab,EvalsTab}.tsx
```

---

### Task 1: Outreach data model, templates, sales reps, suppression

**Files:** `outreach/models.py`, `outreach/templates.py`, `outreach/templates_seed.json`, `outreach/suppression.py`, `api/routes/{templates,reps}.py`, migration `0011_outreach.py`, `db/all_models.py`, `workspace/settings.py`; tests `tests/test_outreach_models.py`.

**Interfaces:**
- **Tables** (spec §18):
  - `template`: `workspace_id, name, angle, length, tone, cta, subject_template, body_template, offering_types (JSONB), active, version`.
  - `campaign_arm`: `campaign_id, key (A|B), template_id, config (JSONB)`.
  - `email_message`: `campaign_id, prospect_id, arm_key, direction (out|in), kind (cold|handoff|manual_reply|inbound), status (draft|needs_review|approved|queued|sending|sent|failed|suppressed|bounced|received|rejected|cancelled), intended_to, actual_to, cc (JSONB list), subject, body, template_id, personalization (JSONB), delivery (gmail|in_app|null), source (in_app_sim|gmail_sim|mock_sim), sent_at, received_at, error`.
  - `reply_classification`: `email_message_id (PK), label, confidence, model, referral (JSONB), summary, rule_override`.
  - `sales_rep`: `workspace_id, name, email, booking_url, active, last_assigned_at`.
  - `rep_assignment`: `prospect_id, sales_rep_id, reason`.
  - `suppression`: `email_normalized (PK), workspace_id, reason, source_email_id`.
- `sync_templates(session, workspace_id) -> int`: idempotent by name. It seeds 12 templates from `templates_seed.json` that span angle (pain / roi / social-proof / curiosity / partnership / referral-ask) × length (short / medium) × cta (question / booking-link / soft), with `offering_types` covering `sales_call` and `dealer`.
- `pick_default_templates(session, workspace_id, offering_type) -> list[Template]`: the first two active templates for the offering, ordered by name, with different `length` where possible.
- **Suppression helpers:** `normalize_email(str) -> str`, `is_suppressed(session, workspace_id, email) -> bool`, and `suppress(session, workspace_id, email, reason, source_email_id=None)`. Suppressing is idempotent.
- **`WorkspaceSettings`** additions:
  - `sending.test_inbox_address: str | None = None`
  - `simulation: SimulationSettings(profile: Literal["realistic","accelerated"]="realistic", reply_delay_seconds: list[int]=[5, 30], seed: int = 7)`
- **Routes:** `GET/POST/PUT /api/templates[/{id}]`, `POST /api/templates/{id}/deactivate`, `GET/POST/PUT/DELETE /api/sales-reps[/{id}]`, and `GET/POST /api/suppression`.
- `create_app` lifespan calls `sync_templates`.

- [ ] Tests:
  - `test_templates_seeded_once` (12 templates after two syncs)
  - `test_default_templates_differ_in_length`
  - `test_suppress_is_idempotent_and_normalized` ("  Dana@X.test " is suppressed as "dana@x.test")
  - `test_sales_rep_crud` (via the API)
  - `test_settings_defaults_include_simulation`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(outreach): add outreach tables, templates, sales reps, suppression`.

### Task 2: A/B arms on campaigns

**Files:** `outreach/arms.py`, `campaigns/service.py`, `api/routes/campaigns.py`; tests `tests/test_arms.py`.

**Interfaces:**
- `create_arms(session, campaign, template_ids: list[UUID] | None) -> list[CampaignArm]`: arm `A` uses `template_ids[0]`, arm `B` uses `[1]`. With `None`, use `pick_default_templates`.
- `arm_for(prospect_id: UUID, keys: list[str]) -> str`: deterministic. It takes `sha256(prospect_id)` and picks `keys[int % len(keys)]`.
- `POST /api/campaigns` accepts an optional `template_ids` (exactly 2) and creates the arms.
- `GET /api/campaigns/{id}` adds `arms: [{key, template_id, template_name}]`.

- [ ] Tests:
  - `test_campaign_gets_two_arms_by_default`
  - `test_arm_assignment_is_stable_and_balanced` (1,000 IDs split 400–600)
  - `test_create_with_unknown_template_404`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(outreach): add A/B arms to campaigns`.

### Task 3: Drafting emails

**Files:** `outreach/drafts.py`, `prompts/email_draft.md`; tests `tests/test_drafts.py`, plus fake handlers `DraftEmail` and `HandoffReply` in `tests/fake_handlers.py`.

**Interfaces:**
- `DraftEmail(subject: str, body: str, personalization: list[{text: str, fact_ids: list[str]}])`, cleaned with `clean_strings_except({"fact_ids"})`.
- `check_draft(draft, *, template, allowed_fact_ids: set[str], allowed_urls: set[str]) -> list[str]` returns a list of problems; empty means valid. Checks:
  - no unresolved `{placeholder}`;
  - every personalization item cites at least one allowed fact ID;
  - word count ≤ 120 for `short`, ≤ 200 for `medium`;
  - no URL or email address in the body outside `allowed_urls`;
  - no price words (`$`, `price`, `discount`, `% off`).
- `FOOTER` (exact copy from the spec) and `finalize_body(body) -> str`, which appends it.
- `draft_email(prospect_id, *, ctx, services) -> EmailMessage`, a Nano `run_step` with `agent="email"`:
  - **Inputs:** seller profile, sender name, template, contact, company facts (with IDs), and arm.
  - **Memory queries:**
    - `MemoryQuery("episodic", ["outreach_episode"], "real", <features summary>, "similar positive outreach", filters={"outcome_label": "interested"}, k=3)`
    - `MemoryQuery("episodic", ["user_correction"], "real", "draft edits", "user's past edits", k=3)`
  - **Retry:** if `check_draft` reports problems, retry once with them appended. If the second draft still fails, the email is saved with status `needs_review` and the problems in `error`.
  - **Result:** an `email_message` with kind `cold`, status `draft`, `intended_to=contact.email`, and the template and personalization stored.
- `fill_template(template, *, first_name, company, sender_name) -> tuple[str, str]`: no model, used by fast simulation. The hook is "I came across {company}", the value prop is generic, and the CTA comes from the template.

- [ ] Tests:
  - `test_draft_valid_saved_with_footer`
  - `test_draft_with_uncited_claim_retried_then_needs_review`
  - `test_check_draft_rejects_prices_and_foreign_urls`
  - `test_fill_template_resolves_placeholders`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(outreach): draft personalized emails with code checks`.

### Task 4: The graph continues: drafts, approval, release

**Files:** `graphs/campaign.py`, `graphs/jobs.py`, `api/routes/review.py`; tests `tests/test_approval_flow.py`.

**Interfaces:**
- **Nodes after `select_contacts`:**
  - `assign_arms`: each primary prospect without an arm gets one via `arm_for`, stored on its future email's `arm_key`. The arm is tracked on the prospect through a new `prospect.arm_key` column in migration 0011.
  - `draft_first_batch`: drafts the first `sending.first_batch_size` primaries by company rank.
  - `approval`: `langgraph.types.interrupt({"campaign_id", "draft_ids"})`.
  - `release_batch`: applies the resume value `{approved: [ids], rejected: [ids]}`. Approved emails become `queued`; rejected ones become `rejected` and their prospect `skipped`.
  - `draft_remaining`: drafts every other primary and queues it directly.
- **Statuses:** campaign `awaiting_approval` while interrupted, `sending` after release, and `complete` once nothing is queued or sending (set by the send loop).
- **Job payload** `{campaign_id, resume: bool, resume_value: dict | None}`:
  - With `resume_value`, call `ainvoke(Command(resume=resume_value), config)`.
  - When `ainvoke` returns with `"__interrupt__"`, finish the run `succeeded` and set the campaign to `awaiting_approval`.
- **Routes:**
  - `GET /api/campaigns/{id}/review`: drafts with contact, company, arm, and problems.
  - `PATCH /api/emails/{id}`: `{subject?, body?}`, allowed only while the email is `draft` or `needs_review`. The edit is stored as an episodic `user_correction` memory, with the diff summarized in code.
  - `POST /api/campaigns/{id}/approve`: `{approved: [...], rejected: [...]}`, allowed only in `awaiting_approval`, otherwise 409. It enqueues the resume job and sets status `queued`.

- [ ] Tests (scripted backend plus mock web):
  - `test_pipeline_pauses_for_approval_with_first_batch`
  - `test_approve_releases_and_drafts_remaining`
  - `test_reject_skips_prospect`
  - `test_approve_requires_awaiting_approval` (409 before the pause and after approving)
  - `test_draft_edit_writes_user_correction`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(graphs): add drafting, approval interrupt, and release`.

### Task 5: Sending (in-app delivery) and worker loops

**Files:** `outreach/delivery.py`, `outreach/send.py`, `worker.py`; tests `tests/test_send.py`.

**Interfaces:**
- `choose_delivery(settings, ws_settings, *, sent_today_gmail: int) -> Literal["in_app"]`. It returns `gmail` only when a Gmail channel exists, which is not part of this plan.
- `send_due(services, *, limit=20) -> int`. It claims `queued` outbound emails (`FOR UPDATE SKIP LOCKED`), then for each one:
  1. If the intended address is suppressed, the email becomes `suppressed`.
  2. Otherwise: `delivery=in_app`, `actual_to="in-app"`, status `sent`, `sent_at=now`, prospect status `sent` (cold) or unchanged (handoff/manual).
  3. A cold email to a non-mock prospect also enqueues `sim.reply` with `run_after = now + uniform(reply_delay_seconds)`.
  - When a campaign in `sending` has no `queued` or `sending` cold emails left, it becomes `complete`.
- `cancel_queued_to(session, workspace_id, email) -> int`.
- `Worker` gains `periodic: list[tuple[float, Callable[[Services], Awaitable[int]]]]`, and `run_forever` runs each periodic function when it is due. `main()` registers `send_due` every 2 s and `activate_due_backups` every 30 s; the latter is added in Task 7.

- [ ] Tests:
  - `test_send_due_delivers_in_app_and_schedules_sim_reply`
  - `test_suppressed_recipient_not_sent`
  - `test_send_is_idempotent_under_concurrency` (two `send_due` calls at once send each email once)
  - `test_campaign_completes_when_queue_empty`
  - `test_actual_to_never_intended_address`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(outreach): send queued emails in-app with suppression and worker loops`.

### Task 6: The reply simulator

**Files:** `sim/profiles/{realistic,accelerated}.yaml`, `sim/simulator.py`, `prompts/sim_reply_writing.md`; tests `tests/test_simulator.py`.

**Interfaces:**
- **Profile YAML:** as in spec §13. `realistic` has `base_positive_rate: 0.01`, `accelerated` 0.06, both with the same multipliers: function (operations 2.0, partnerships 1.5, finance 0.6), length (short 1.8), cta (question 1.3, booking-link 0.8), and `seniority_by_size.c_level_at_51_plus: 0.5`. Also `outcome_mix_when_not_positive` and `p_book: 0.5`.
- `load_profile(name) -> Profile`.
- `features_for(session, email) -> dict`, with keys `function, seniority, company_size, length, cta, angle, tone`.
- `decide_outcome(profile, features, rng) -> Literal["interested","not_now","not_interested","wrong_person","unsubscribe","out_of_office","none"]`, deterministic for a given `rng`.
- `rng_for(prospect_id, seed) -> random.Random`.
- `simulate_reply(email_id, *, ctx, services) -> UUID | None`:
  - Only for `kind == "cold"` emails. Any other kind returns `None`.
  - The outcome is decided in code. `none` returns `None`. Otherwise Nano `sim_reply_writing` writes `{body}` in the persona's voice, matching the outcome, and an inbound `email_message` is created with `direction=in, kind=inbound, status=received, source=in_app_sim`, and the same `prospect_id`.
  - Then `reply.handle` is enqueued. This is job `sim.reply`.

- [ ] Tests:
  - `test_outcome_rate_matches_profile` (10,000 draws with accelerated, short, operations → positive rate within ±1.5 pp of 0.06×2×1.8)
  - `test_same_prospect_same_outcome`
  - `test_simulator_ignores_handoff_replies`
  - `test_reply_created_and_handling_enqueued`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(sim): add reply simulator with hidden preference profiles`.

### Task 7: Reply handling, handoff, backups, outcome memory

**Files:** `replies/{schemas,handle,backups,outcomes}.py`, `prompts/{reply_classification,handoff_reply_draft}.md`; tests `tests/test_replies.py`.

**Interfaces:**
- `ReplyClassificationOut(label: Literal[...7 labels incl. other], confidence: float (0–1), referral: {name, title} | None, summary: str)`.
- `rule_label(body: str, from_address: str | None) -> str | None`:
  - Unsubscribe phrases (`unsubscribe`, `remove me`, `stop emailing`, `take me off`) return `unsubscribe`.
  - A `mailer-daemon` or `postmaster` sender returns `bounce`.
- `handle_reply(email_id, *, ctx, services) -> str`, returning the final label. Steps:
  1. A rule label wins.
  2. Otherwise classify with Nano. Below confidence 0.7, re-check with Super (`reply_reclassification`); still below 0.6 → `needs_review`.
  3. Write the `reply_classification` row.
  4. Act per spec §12, at most once per prospect:
     - **Interested:** pick a rep round-robin (the active rep with the oldest `last_assigned_at`). Nano `handoff_reply_draft` writes the reply, which must include the rep's booking link if they have one and must not mention prices. A `handoff` email is queued with `cc=[rep.email]`. The prospect becomes `handed_off`, and a `rep_assignment` row is written.
     - **Simulated meeting:** for an in-app-sim reply, with probability `p_book` (same seeded RNG), set `meeting_booked_at` and `meeting_synthetic=True`.
     - **Unsubscribe:** suppress the address and `cancel_queued_to` it.
     - **Wrong person or bounce:** `activate_backup`.
     - **Not now / not interested:** status only.
     - **Out of office:** nothing.
  5. Outcome memory (`replies/outcomes.py`, errors suppressed):
     - Write an `outreach_episode`. The summary is built from features plus the label, the payload holds the features plus `outcome_label`, and the source is the email's source.
     - Attach the outcome to the prospect's `selection_episode` via `attach_outcome`, if it has none yet.
- `activate_backup(prospect_id, *, ctx, services) -> UUID | None`: drafts and queues the backup's cold email, once only.
- `activate_due_backups(services) -> int` (periodic): primaries that are `sent` with no inbound reply after `no_reply_window_minutes` become `no_reply`, and their backup is activated.
- Jobs: `reply.handle`.

- [ ] Tests:
  - `test_interested_hands_off_round_robin_with_booking_link` (two reps, two interested prospects → each rep gets one)
  - `test_unsubscribe_phrase_overrides_interested_label`
  - `test_second_interested_reply_takes_no_action`
  - `test_interested_without_reps_needs_review`
  - `test_wrong_person_activates_backup_once`
  - `test_no_reply_window_activates_backup`
  - `test_outcome_written_to_memory`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(replies): classify replies, hand off to reps, activate backups, remember outcomes`.

### Task 8: Inbox API

**Files:** `api/routes/inbox.py`; tests `tests/test_inbox_api.py`.

**Interfaces:**
- `GET /api/inbox/threads?filter=all|needs_review|interested&campaign_id=` returns one row per prospect with messages: `{prospect_id, contact, company, last_message_at, last_label, status, simulated, message_count}`.
- `GET /api/inbox/threads/{prospect_id}` returns `{prospect, contact, company, rep, messages: [{id, direction, kind, subject, body, status, delivery, intended_to, actual_to, cc, sent_at, received_at, label, confidence}]}`.
- `POST /api/inbox/threads/{prospect_id}/reply` with `{body}` queues a `manual_reply` email (finalized with the footer). A suppressed address returns 409 `suppressed`.
- `POST /api/prospects/{id}/meeting` sets `meeting_booked_at`.

- [ ] Tests:
  - `test_threads_filters`
  - `test_thread_detail_shows_simulated_delivery`
  - `test_manual_reply_queued`
  - `test_reply_to_suppressed_409`
  - `test_mark_meeting`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(api): add inbox threads, manual replies, and meetings`.

### Task 9: Statistics (pure)

**Files:** `learning/stats.py`; tests `tests/test_stats.py`.

**Interfaces:**
- `wilson(k, n, z=1.96) -> tuple[float, float]`.
- `fisher_exact(a, b, c, d) -> float`: two-sided, exact, via `math.comb`.
- `required_n_per_arm(p1, lift=2.0, alpha=0.05, power=0.8) -> int`: two-proportion normal approximation.
- `evidence_level(*, n_a, k_a, n_b, k_b, planned_n, alpha=0.05) -> Literal["evidence","signal","insufficient"]`:
  - `insufficient` if either arm has fewer than 3 positives in total;
  - `evidence` if both arms reached `planned_n` and p < alpha;
  - `signal` otherwise.

- [ ] Tests:
  - `test_wilson_known_values` (k=5, n=100 → (0.0215, 0.1118) to 3 decimal places)
  - `test_fisher_known_value` (a=1, b=9, c=11, d=3 → p ≈ 0.0028)
  - `test_required_n_matches_spec` (1% → ~2,300 per arm; 6% → ~360, each within ±5%)
  - `test_evidence_levels`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(learning): add honest statistics`.

### Task 10: The learning loop

**Files:** `learning/{models,tables,analyze,experiments}.py`, `prompts/learning_analysis.md`, `api/routes/learning.py`, migration `0012_learning.py`; tests `tests/test_learning.py`.

**Interfaces:**
- **Tables:** `experiment` (spec §18 plus `baseline_rate`, `planned_sends_per_arm`, `min_lift`) and `learning_analysis` (spec §18).
- `outcome_table(session, campaign_id) -> list[StatRow]`. A row is `{id, dimension, value, arm?, sends, positives, meetings, rate, ci_low, ci_high, level}`. It covers:
  - dimensions `arm`, `function`, `seniority`, `size_band` (1–10, 11–50, 51–200, 201+), `template_length`, `template_cta`, and `template_angle`;
  - levels from `evidence_level` comparing each value against the rest of its dimension.
- `analyze(campaign_id, *, ctx, services) -> LearningAnalysis`, a Super `run_step` with `agent="learning"`:
  - **Inputs:** stats rows, past experiments, current insights.
  - **Output:** `LearningOutput(findings: [{statement, evidence_level, stat_refs}], hypotheses: [{id, statement, rationale}], proposed_experiment: {hypothesis_id, change: {dimension in (template_length, template_cta, template_angle, template), from, to}, primary_metric, min_lift} | None)`.
  - **Then `validate_claims`:** a finding claiming `evidence` keeps it only if every ref is a row at `evidence`. Otherwise it becomes `signal`, or `assumption` with no refs. Every downgrade is recorded.
  - Findings at `evidence` or `signal` become semantic `insight` memories with `payload.dimension`, superseding the previous insight for the same dimension and value.
  - If a proposal is made, an `experiment` row with status `proposed` is created. Its `planned_sends_per_arm` is `required_n_per_arm(baseline_rate, min_lift)`.
  - This is job `learning.analyze`.
- `approve_experiment(session, experiment_id) -> Campaign`: creates campaign version N+1 with the same ICP, `parent_campaign_id`, and `experiment_id`. Arm A is the parent's best arm; arm B is that template with the change applied (the template with the requested attribute, closest otherwise). The campaign is created as `draft`, and the caller runs it.
- `conclude_experiment(session, experiment_id) -> Experiment`: computes per-arm results with Wilson CI and Fisher p, and sets `evidence_level`. It's called by `analyze` once both arms have the planned sends.
- **Routes:** `POST /api/learning/analyze?campaign_id=` (enqueues), `GET /api/learning/analyses?campaign_id=`, `GET /api/experiments`, `POST /api/experiments/{id}/approve` (creates and runs the version), `POST /api/experiments/{id}/decline`, `GET /api/campaigns/{id}/stats`.

- [ ] Tests:
  - `test_outcome_table_counts_and_ci`
  - `test_unsupported_evidence_claim_downgraded`
  - `test_insight_written_and_superseded`
  - `test_proposal_creates_experiment_with_power_sample`
  - `test_approve_creates_version_with_arms`
  - `test_conclude_labels_result`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(learning): add learning analysis, validated insights, and experiments`.

### Task 11: Fast simulation

**Files:** `sim/fast.py`, `api/routes/sim.py`, `sim/__main__.py`; tests `tests/test_fast_sim.py`.

**Interfaces:**
- `run_fast_sim(session, *, workspace_id, campaign_id: UUID | None, n_per_arm: int, profile: str, seed: int) -> Campaign`. It runs entirely in the database with no models and no web:
  1. Generate `2 × n_per_arm` mock companies and contacts (`synthetic=True`, `.test` domains). Contact functions, seniorities and company sizes are drawn from fixed distributions.
  2. Create a `mock_sim` campaign version with two arms that differ only in template length (or reuse the given campaign's arms).
  3. Fill drafts with `fill_template` and mark them sent in-app.
  4. Decide outcomes with `decide_outcome`, and write inbound replies with canned text per label and `reply_classification` rows with `rule_override="sim_truth"`.
  5. Write outcome memories with source `mock_sim`.
  6. Set status `complete`.
- `POST /api/sim/fast` with `{n_per_arm, profile, campaign_id?}` returns the campaign.
- CLI: `python -m covora.sim fast --n-per-arm 400 --profile accelerated`.

- [ ] Tests:
  - `test_fast_sim_volume_and_labels` (n_per_arm=200 gives 400 sends, all `mock_sim`)
  - `test_fast_sim_recovers_planted_length_effect` (accelerated, n=600: short arm's rate above medium's, and Fisher p < 0.05)
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(sim): add fast simulation on mock prospects`.

### Task 12: NeMo Switchyard routing mode

**Files:** `gateway/switchyard.py`, `gateway/gateway.py`, `pyproject.toml` (`nemo-switchyard==0.3.0`); tests `tests/test_switchyard.py`.

**Interfaces:**
- `SwitchyardRouter(backend: ChatBackend, settings, *, algorithm_factory=None)`. The default factory is `lambda: algorithms.llm_task_classifier(config=TaskClassifierConfig(base_threshold=0.5, response_format_type="json_object"))`.
- `choose(task, messages, ctx) -> RoutingDecision`:
  1. Build the libsy request `{"model": "auto", "messages": [{"role", "content": [{"type": "text", "text"}]}]}` and the targets `{"efficient": [nano], "capable": [super]}`.
  2. Iterate `algorithm.run_stream(request, targets)`. On `Step.CallModel`, run the judge call with Nano through the backend and log an `llm_call` with task `routing_judge`. Convert `call.request` messages to OpenAI format and respond with `LlmResponse.Agg({"model", "outputs": [{"role": "assistant", "content": [{"type": "text", "text"}]}]})`. On `Step.Done`, map `selected_model_ids[0]` to its tier.
  3. The reason is `"switchyard: <algorithm> chose <tier>"`.
  4. Any exception gives a fixed decision with the reason `"switchyard error: <type>; used fixed"`.
- `ModelGateway` uses `SwitchyardRouter` when `routing_mode == "switchyard"`. Embeddings and `routing_judge` itself are never routed through it.

- [ ] Tests:
  - `test_switchyard_choice_used_and_logged` (fake algorithm yields one `CallModel`, then `Done` choosing capable; the judge `llm_call` is logged and the decision is super)
  - `test_switchyard_error_falls_back_to_fixed`
  - `test_real_libsy_algorithm_constructs` (imports the package and builds the default algorithm without network)
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(gateway): add NeMo Switchyard routing mode`.

### Task 13: Evaluation harness

**Files:** `evals/{models,runner,suites,__main__}.py`, `api/routes/evals.py`, migration `0013_evals.py`, datasets in `backend/evals/datasets/`; tests `tests/test_evals.py`.

**Interfaces:**
- **Tables:** `eval_run(suite, mode, status, metrics JSONB, started_at, ended_at, error)` and `eval_result(eval_run_id, sample_id, expected JSONB, actual JSONB, score, notes)`.
- **Suites:** each is `async (services, mode, ctx) -> metrics dict`, and each runs with `settings.routing_mode` overridden to `mode`.
  - `icp_parsing`: 8 prompts. Field accuracy and origin accuracy.
  - `company_fit`: the fixture web's 6 companies against `EXAMPLE_ICP` with known labels. Precision and recall.
  - `contact_selection`: fixture-web companies with the correct primary labeled. Top-1 accuracy, primary-or-backup accuracy, and invented-person rate.
  - `reply_classification`: 40 labeled replies in JSONL. Accuracy, macro-F1, and unsubscribe recall.
  - `email_groundedness`: drafts for fixture prospects. Share of personalization items backed by cited facts.
  - `learning_recovery`: fast simulation (accelerated, n=600) then `analyze`. Whether the planted top factor (template length) is identified, the uplift with CI, and false-evidence claims.
  - `memory_ablation`: `contact_selection` with memory on vs off. Metric difference.
  - Every suite also reports tokens, mean latency, and estimated cost from its `llm_call`s.
- `run_evals(services, suites, modes) -> list[EvalRun]`, plus the CLI `python -m covora.evals run --suite all --mode all` and job `eval.run`.
- **Routes:** `POST /api/evals/run` with `{suites, modes}` (enqueues), `GET /api/evals`, and `GET /api/evals/{id}`.

- [ ] Tests (scripted backend):
  - `test_reply_classification_suite_scores_fake_model`
  - `test_runner_records_one_run_per_suite_and_mode`
  - `test_learning_recovery_suite_finds_length_effect`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(evals): add evaluation suites and routing-mode comparison`.

### Task 14: Metrics, memory browse, remaining exports

**Files:** `api/routes/{metrics,memory}.py`, `api/routes/exports.py`; tests `tests/test_metrics_api.py`.

**Interfaces:**
- `GET /api/metrics/routing` returns, by task and model: calls, tokens, p50/p95 latency, fallback rate, estimated cost; plus totals by routing mode.
- `GET /api/metrics/overview` returns `{sent, positive_replies, positive_rate, meetings, meeting_goal, active_campaigns, youcom_spend_usd, youcom_budget_usd, model_cost_usd, latest_runs: [...5], open_experiment}`. It counts only non-`mock_sim` data unless `include_mock=true`.
- `GET /api/memory?kind=&subtype=&source=&limit=` and `GET /api/memory/{id}` (with source rows).
- `GET /api/exports/campaign-results.csv?campaign_id=` (one row per prospect: company, contact, role, arm, email status, reply label, meeting) and `GET /api/exports/experiments.csv`.

- [ ] Tests:
  - `test_routing_metrics_aggregate`
  - `test_overview_excludes_mock_by_default`
  - `test_memory_list_filters`
  - `test_campaign_results_csv`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(api): add routing/overview metrics, memory browse, result exports`.

### Task 15: UI: review queue, templates, sales team, simulation settings

**Files:** `features/review/ReviewQueue.tsx` (in `CampaignDetail` when `awaiting_approval`), `features/templates/TemplatesTab.tsx` (on the Campaigns page as tab "Templates"), `features/settings/{SalesTeamForm,SimulationForm}.tsx`; tests in each.

**Behavior:**
- **Review queue:** lists drafts (to, company, arm, subject, body, problems), each with an Edit button (inline, which PATCHes) and an approve/reject toggle. **Approve batch** posts the selection.
- **Templates tab:** a list with attributes and an Active toggle, plus an edit dialog.
- **Sales team:** add, edit and remove reps (name, email, booking link).
- **Simulation settings:** profile (Realistic 1% / Accelerated 6%) and reply delay.

- [ ] Tests:
  - `approves selected drafts`
  - `edits a draft`
  - `adds a sales rep`
  - `toggles template active`
  - `saves simulation profile`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(web): add review queue, templates, sales team, simulation settings`.

### Task 16: UI: Inbox

**Files:** `pages/Inbox.tsx`, `features/inbox/{ThreadList,ThreadView}.tsx`; tests `features/inbox/inbox.test.tsx`.

**Behavior:**
- Filters: Needs review · Interested · All.
- Each thread shows a label badge with confidence, and the "Simulated: delivered in-app" badge shows the intended recipient (or "no address").
- A composer sends a manual reply; **Mark meeting booked** is available on every thread; and empty states are handled.

- [ ] Tests:
  - `filters threads`
  - `shows simulated delivery badge`
  - `sends a manual reply`
  - `marks meeting`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(web): add Inbox`.

### Task 17: UI: learning on the campaign page and the Overview

**Files:** `features/learning/{ArmStats,ExperimentsPanel}.tsx` (in `CampaignDetail`), `pages/Overview.tsx`; tests in each.

**Behavior:**
- **Arm stats:** a table per arm with sends, positives, rate, a 95% range bar and an evidence badge; then dimension rows.
- **Experiments panel:** an **Analyze** button; findings with level badges (downgrades marked "downgraded: not enough data"); and the proposed experiment with its planned sample size ("needs about 2,300 sends per arm") and Approve/Decline.
- **Version history:** a chart labeled "not a controlled comparison".
- **Overview:** KPI tiles, meetings vs goal, You.com spend vs budget, recent runs, and the open experiment. It has a "Show mock simulation" toggle.

- [ ] Tests:
  - `shows arm stats with ranges`
  - `marks downgraded findings`
  - `approves an experiment`
  - `overview KPIs and mock toggle`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(web): add learning panel and Overview`.

### Task 18: UI: Agent Workflow tabs (routing, memory, evaluations)

**Files:** `features/runs/{RoutingTab,MemoryTab,EvalsTab}.tsx`, `pages/AgentWorkflow.tsx` (tabs Runs · Routing · Memory · Evaluations); tests `features/runs/tabs.test.tsx`.

**Behavior:**
- **Routing:** a table by task and model, plus a mode comparison.
- **Memory:** filterable episodic and semantic items with evidence badges and sources.
- **Evaluations:** runs by suite and mode, showing metrics, tokens and cost side by side, with a **Run evals** button.

- [ ] Tests:
  - `routing table renders`
  - `memory filters`
  - `evals comparison by mode`
- [ ] Run and confirm they fail, implement, run and confirm they pass, then commit `feat(web): add routing, memory, and evaluation views`.

### Task 19: End-to-end verification, docs, final review

- [ ] Run all automated checks (ruff, pytest, vitest, typecheck, build).
- [ ] **Live run** with real models on the fixture web:
  1. Launch a 3-prospect campaign.
  2. Approve the batch.
  3. Watch it send in-app, simulated replies arrive, the interested ones get a handoff with the rep's booking link, and the Inbox fill up.
  4. Run fast simulation (accelerated) and **Analyze**: there's a finding on template length and a proposed experiment.
  5. Run evals for `reply_classification` and `icp_parsing` in modes `fixed` and `switchyard`, and record the comparison.
- [ ] Update `README.md`, `docs/PROGRESS.md` and `docs/DECISIONS.md`. Do the final self-review, and list the rulings and deferred minors.
- [ ] Commit `docs: record Plan 3 progress and decisions`.
