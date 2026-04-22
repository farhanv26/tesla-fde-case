# Tesla FDE — Interview Prep

**Format:** 15–20 min presentation + 10 min Q&A.
**What they grade on:** technical depth, user empathy, problem-solving approach.

The dashboard is a prop. The presentation is the deliverable. Own the narrative first, then use the dashboard to back up specific numbers when asked.

---

## 1. The 30-second pitch (memorize this)

> "Athena deployments are underperforming the 4-week target. Shanghai did it in 3.5 weeks, Berlin took 6.5 — a 2x spread.
> The data shows the cause isn't the platform, it's the **deployment process**: the same handful of friction themes (change-management clicks, Tekton sync, integration blockers, external partner permissions) show up at every site.
> For Austin I'd front-load those four risks in weeks 1–2, prototype two wins in weeks 3–4, and exit with a repeatable playbook that compresses future deployments toward the Shanghai number."

Everything else supports this. If you get cut off at 3 minutes, that's the pitch.

---

## 2. Numbers to memorize

| Fact | Number | Source |
|---|---|---|
| Sites analyzed | 5 (Nevada, Shanghai, Berlin, Texas, Mexico) | Challenge data |
| Deployment target | 4 weeks | Shanghai hit 3.5, Mexico hit 4.0 |
| Worst overrun | **Berlin: 6.5 wks (+62.5%)** | Closure events |
| Best | **Shanghai: 3.5 wks (-12.5%)** | Closure events |
| On/under target | 2 of 5 | Duration analysis |
| Feedback items captured | **38** across 5 sites | User Feedback sheet |
| Items with no status (untriaged) | **22 of 38 (58%)** | This is itself a pain signal |
| Top pain themes | Change Mgmt (8) · Tekton Sync (8) · Milestones (7) · Reporting (7) | Theme rollup |
| Every top theme appears at | ≥4 of 5 sites | It's platform-level, not site-specific |
| Largest cost overrun | Berlin HVAC: +$560K (+12%) | Financial variance |
| Deployment disruption cost (Berlin) | ~$192K over 19 delay-days / 8 events | Event log |
| Austin scope | 36 scopes across 4 Areas/Systems · Bldg 1 | Estimate |
| External partners needing scope access | 5 contractors + 2 design partners | Tech survey |
| Tekton field users / daily entries | 85 users · 420 hour entries / day | Tech survey |
| Offline exposure | Zones C/D: 2–3 hrs offline/day | Tech survey |
| Skill gap | 60% Primavera · 40% SAP · **25% PM software · 10% API** | Tech survey |
| Estimate defects found pre-import | 41 cells · 6 defect types | `austin_estimate_quality_issues.csv` |

---

## 3. The 15-20 min presentation (slide-by-slide with timing)

> Total budget: 18 minutes. Leave 2 minutes of slack. Don't overshoot — the panel will notice.

### Slide 1 · Title + framing (30s)
- "Athena deployment at Austin Building 1 — diagnosis, plan, and two prototypes."
- Name, role, one sentence on how you approached this: *"I used the five prior deployments as a reverse benchmark — what didn't work, why, and what to copy from the two sites that worked."*

### Slide 2 · What went wrong: deployment velocity (2 min)
- Hero chart: **actual weeks vs 4-week target**, 5 bars.
- Call out: Shanghai 3.5w / Mexico 4.0w / Nevada 5w / Texas 5w / **Berlin 6.5w**.
- "Same platform, same app teams, 2x spread in duration. Something about the deployment process — not the code — is the variable."
- **Don't claim** Berlin "failed" — say "Berlin took 63% longer than target" and let the panel draw conclusions.

### Slide 3 · What went wrong: where the time went (2 min)
- Scatter or list: delay-days × disruption cost by site. Berlin concentrates 19 of all delay-days, $192K of cost.
- Top three Berlin blockers you'd call out:
  1. GDPR / change-tracking audit (compliance wasn't engaged early)
  2. SAP budget-code integration (5-day block)
  3. Primavera milestone sync (5-day block at Nevada also, pattern not a one-off)
- Takeaway: **integration + compliance are the longest tails**, not core app bugs.

### Slide 4 · User pain: themes across all 5 sites (2.5 min)
- Theme chart + site heatmap.
- Read the top three: *"Change management clicks is the #1 complaint across every site I saw. Tekton-Athena sync is second. Reporting and milestones tied for third."*
- Important line: *"Every top theme shows up at ≥4 of 5 sites. These are platform gaps, not Berlin problems."*
- One specific quote from the data, e.g. *"Change management workflow is unclear — takes 10+ clicks to adjust scope hours."* Use it verbatim. It lands.
- Also call out: **22 of 38 feedback items have no status recorded.** That's a process pain point before it's a UX one — nobody owns triage.

### Slide 5 · Adoption friction trajectory (1 min)
- Blocked-user rate by week, by site.
- "Shanghai and Mexico drop to 0% blocked by week 3. Berlin is still at 14% at week 3. Whatever Shanghai/Mexico did, copy it."
- The obvious differentiator to highlight: training intensity and a site champion. Shanghai had a change-order workflow prototyped and shipped during deployment (2-day build). Mexico had a fast ramp with small daily training cohorts.

### Slide 6 · Austin situation brief (1.5 min)
- 4 Areas/Systems · 36 scopes · ~2,800 tasks (from tech survey)
- Integrations: Primavera (140 schedules) + SAP (budgets) — both are Berlin's largest blockers
- Field: 85 Tekton users, zones C/D have 2–3 hrs offline/day — **Tekton offline mode is a go-live blocker, not a nice-to-have**
- External partners: MEP, GC, Structural Eng, Electrical Sub, Commissioning + 2 design partners — 7 RBAC configurations required Day 1
- Skill gap: 10% API familiarity. 25% PM software. Training ≠ reading docs.

### Slide 7 · 4-week Austin deployment plan (3.5 min — **the core slide**)
Say this like a checklist, not a paragraph. See §4 below for the full plan.

| Wk | Focus | Owner | Exit criteria |
|---|---|---|---|
| 1 | Integrations + estimate load + RBAC | FDE + Controls + IT | Primavera/SAP staging green · estimate imported clean · 7 partner roles provisioned |
| 2 | Pilot team training + Tekton field trial | FDE + P. Kumar | 1 Area/System live · offline mode validated in zone C · 0 blocking defects |
| 3 | Full rollout + 1-click change approval live | FDE + PMs | All 4 Areas/Systems live · blocked-user rate ≤ 5% · change order SLA ≤ 24hr |
| 4 | Audit dry-run + compliance sign-off + handoff | FDE + Compliance | Audit-trail spot-check passes · FDE playbook handed to next site |

Key constraints built in:
- K. Abrams (owns milestone approvals) traveling Wed–Fri Sprint 2 → pre-approve Sprint 2 milestones Monday, delegate to S. Chen.
- D. Nakamura (VP) on-call Sprint 3 → weekly Friday summary, don't expect mid-week approvals.
- F. Mueller compliance audit Sprint 4 → dry-run Wednesday before audit.
- P. Kumar is your champion — pair him with skeptical teams in week 1.

### Slide 8 · Prototype picks for weeks 3–4 (1.5 min)
Two features, each justified by data:

1. **"1-click change approval for scopes < $5K"** — Texas already prototyped this (works for cost changes < $5K). Forward-port it. **Why:** the #1 pain theme is change-mgmt clicks; this clips ~80% of approval volume by value.
2. **Tekton offline-mode + batch-task auto-queue** — critical for Austin zones C/D and because offline data loss was a blocker at Berlin (8 hrs of entries) and Texas. Texas prototype works for 50 tasks; need to harden to 500+.

Explicitly de-prioritize: photo upload (8 weeks), cost forecasting (needs data scientist), RBAC overhaul (4 weeks). These are right to pursue eventually but not for this 4-week window.

### Slide 9 · Data quality risks to fix Day 1 (1 min)
Pull up the Austin Estimate defects:
- 1 row with missing Project
- 1 row with missing Area/System (scope would orphan)
- Mixed-format costs across 21 cells ($, commas, "420k", "45k" mixed with ints)

"If we load this estimate into Athena unchanged, the import either fails or silently miscategorizes. I'd fix these in a 30-min session with the Estimating team before kickoff."

### Slide 10 · Stakeholder engagement model (1 min)
- Daily 9am standup (mandatory per contact sheet)
- Weekly Thursday report to R. Lopez (Project Controls Lead) — she asked for it
- P. Kumar as champion & pairing partner
- External partners: weekly sync (their SLAs are 2 weeks for change requests — can't move faster)
- Compliance: bring F. Mueller in at kickoff, not sprint 4

### Slide 11 · Recap + ask (30s)
- Ship 4-week Austin deployment on target or faster
- Two prototypes that back-port wins from prior sites
- Exit with a playbook other FDEs can reuse
- "Happy to dig into any of this."

### Slide 12 · (backup) Composite risk + data sources
- Keep the composite score chart and method as backup material for Q&A.
- Keep the theme × site heatmap as backup.

---

## 4. The 4-week Austin plan (say this from memory)

### Pre-kickoff (week 0) — 2 days
- [ ] Load Austin estimate into staging, fix 41 data-quality defects with Estimating team
- [ ] Walkthrough with P. Kumar on what killed Nevada/Berlin — his lived experience
- [ ] Meet each external partner contact (V. Patel, C. Williams, H. Kim, N. Rodriguez, E. Johnson) — 30 min each
- [ ] Confirm SAP budget codes match Athena Area/System IDs (Berlin's #1 blocker)

### Week 1 — Infra, integrations, baseline data
- **Mon:** Kickoff. Estimate → Athena load. Compliance briefing with F. Mueller.
- **Tue–Wed:** Primavera milestone sync wired and tested in staging (140 existing schedules).
- **Thu:** SAP finance integration — budget codes validated end-to-end.
- **Fri:** RBAC: provision 5 contractor scopes + 2 partner APIs.
- **Exit criteria:** Primavera + SAP staging integrations pass; all 7 partner roles provisioned; estimate imports clean.
- **Key risk:** SAP budget code mismatch (happened at Berlin). Mitigation: dry run on Tuesday.

### Week 2 — Pilot team, Tekton field trial
- **Mon:** Pilot training for 1 Area/System team (pick Electrical — biggest scope count). P. Kumar pair-instructing.
- **Tue–Wed:** Tekton field trial in zone C (worst offline coverage). Field crew uses offline mode for real entries. **Do this in production, not staging** — that's what catches real bugs.
- **Wed/Thu:** K. Abrams traveling — pre-approve any milestones Monday, delegate to S. Chen.
- **Fri:** Retro with pilot team. Fix blocking defects.
- **Exit criteria:** 1 Area/System fully live; Tekton offline mode validated in zone C; 0 blocking defects.

### Week 3 — Full rollout + prototype 1
- **Mon:** Remaining 3 Areas/Systems go live in parallel. Training sessions for all 7 teams (45-min cohorts, hands-on only).
- **Tue–Wed:** Ship 1-click change approval (back-port from Texas).
- **Thu:** First weekly report to R. Lopez.
- **Fri:** D. Nakamura is oncall this week — weekly summary locked in by Thursday.
- **Exit criteria:** All 4 Areas/Systems live; blocked-user rate ≤ 5%; change-order cycle time ≤ 24hr.

### Week 4 — Audit, handoff, prototype 2
- **Mon:** Audit dry-run with F. Mueller (the real audit is mid-week).
- **Tue:** Compliance audit. *If dry-run caught things Mon, fix Tue AM.*
- **Wed–Thu:** Ship hardened Tekton offline mode (batch auto-queue for 500+ tasks).
- **Fri:** Handoff doc + runbook to next FDE. Exit interview with site leadership.
- **Exit criteria:** audit passes; 0 critical open items; playbook published.

---

## 5. Q&A — likely questions + prepared answers

### Technical

**Q: Your composite risk score — how should the panel trust it?**
> "It's a directional triage index, not a calibrated model. It blends normalized cost impact, delay-days, budget variance, high-priority open feedback, and blocked-user rate. I used it to confirm what the raw data already said: Berlin is the worst, Shanghai is the best. I wouldn't use it to auto-trigger anything — it's a prioritization aid, not a prediction. If I had another two days I'd validate it against a hold-out site but I only have five sites so cross-validation isn't meaningful."

**Q: What about data quality in the source workbooks?**
> "The data itself tells you the process is broken. Site names are double-labeled — 'Nevada' and 'GF Nevada' appear as separate sites. Priority is inconsistently capitalized. Cost impact mixes `$35,000`, `22k`, and raw integers. Day impact has `4 days` and `5` in the same column. 22 of 38 feedback items have no status. **None of this is a tool failure — it's a reporting-template failure.** The fix for Austin is a mandatory weekly reporting template the FDE owns. Standardize Site (single label), Priority (enum), Status (enum with SLA date), Cost Impact (numeric, USD)."

**Q: Why front-load integrations? Why not train users first?**
> "Because Berlin took 6.5 weeks and 4 of the 5 week-overrun were integration blockers — SAP (5 days), GDPR audit (4 days), GC partner audit (5 days), Primavera (already-existing 140 schedules they couldn't sync). Training users on Athena before integrations are verified means retraining when things break. Shanghai — fastest site — did integrations in week 1 and users in week 2."

**Q: What's different about Austin that worries you most?**
> "Two things. One, zones C and D have known spotty cell coverage — 2–3 hrs offline per day per the tech survey. Tekton offline mode hasn't been production-hardened above 50 tasks and we're looking at 420 daily entries across 85 users. That's the single biggest Day-1 go-live risk. Two, 10% API familiarity in the skill survey — the 2 design partners want API access and we have few internal people who can support that day one."

**Q: How would you handle a difficult user?**
> "Go sit with them. Most of the angry feedback in this dataset is from people who can't *do their job* — the MEP vendor who couldn't see their assigned scopes, the finance team whose monthly variance report broke. That's not a Training problem, that's an Athena-wasn't-ready problem. I'd triage their actual blocker, own it through to resolution, and use them as my first advocate when it's fixed. The Project Controls lead at Berlin asking for milestone dependency visualization — that's a user who cares enough to give you a spec. Those are gold."

### Deployment process

**Q: Shanghai went fast — why? Is it luck?**
> "Partly sequence, partly culture. Look at the Shanghai feedback: they shipped two features during deployment — change-order baseline tracking (took 2 days) and Slack milestone notifications (2 days). Fast, tactical wins during rollout built trust. They also only had 10 users blocked in week 1 vs 22 at Berlin — smaller Area/System bite size and a faster training cohort. Two copy-able things: ship one real feature in week 2 or 3, and size training cohorts to 40–50 users max."

**Q: What do you do if the audit (week 4) fails?**
> "Define 'fail.' If it's a process gap — missing sign-offs, unclear log format — I fix and resubmit same week. If it's a platform gap — audit trail missing fields — that's an app-team ask with a realistic 1–2 sprint build; I'd scope it, secure a conditional sign-off from F. Mueller for known-gap + documented-mitigation, and track to close. Berlin hit this with GDPR; the fix took 2 weeks post-go-live and was fine."

**Q: What are you NOT going to do in 4 weeks?**
> "Photo upload (8-week feature), cost forecasting (needs a data scientist and historical burn-rate we don't have yet), and a full RBAC overhaul (4-week project, touches auth). All three are legitimate asks but they're week-8+ work. I'd capture them into the post-go-live backlog with explicit next-FDE ownership and stop there."

**Q: What would break your plan?**
> "Three things. One: SAP integration blocking — if budget codes don't reconcile, week 1 goes long, which cascades. Two: a Priority 1 platform bug in Tekton offline mode we can't work around in zone C. Three: compliance pushback on audit trail before we can get F. Mueller in a room — that happened at Berlin. All three are mitigated by **week 1 integration validation + week 2 field trial + week 1 compliance kickoff** respectively."

### Product / platform

**Q: One feature you'd push the app teams to prioritize after you leave?**
> "**Change-management UX.** It's the #1 pain theme across every site and the 1-click approval prototype only covers small changes. A full workflow redesign — role-aware approvals, contextual approval trails, bulk edits — is the biggest single lever for user satisfaction and cycle time. Not a 1-sprint project. But it's the right thing to commit to."

**Q: What if you only had 2 weeks, not 4?**
> "I'd compress to two weeks by: dropping full training in favor of pair-instruction with P. Kumar, skipping the pilot and going straight to 2 Areas/Systems on Day 3 (not 4 Areas), and shipping only the 1-click change approval prototype. Trade-off: higher first-week incident rate, weaker handoff. I'd flag it upfront to R. Lopez as an explicit trade, not hide it."

---

## 6. Dashboard demo script (3-5 minutes max)

If they ask to see the dashboard:

1. **Start:** *"This is a diagnostic console I built from the five-site data. Four sections."*
2. **Velocity (top):** *"Here's the target-vs-actual — Shanghai hits 3.5, Berlin 6.5. On/under target is 2 of 5."*
3. **Interactive scatter:** Click Berlin → *"Berlin has 8 blockers, $192K in disruption cost, 19 delay-days. Click any site to deep-dive."*
4. **Pain themes:** *"These are the five themes that appear at 4 of 5 sites. This is what the platform needs to improve — not something Austin-specific."*
5. **Austin day-1:** *"Before I load the estimate into Athena, these are the 41 cells I'd fix first. One row with missing Area/System would orphan a scope. Mixed cost formats would crash the numeric parser."*
6. **Action block at bottom:** *"And the dashboard rolls up to a site-specific action for any focused site."*

**Don't** spend more than 5 minutes on the dashboard unless they ask. It's evidence, not the argument.

---

## 7. Things to NOT say

- Don't call Berlin a "failure." Call it "over-target." There are probably people on the panel who ran Berlin.
- Don't suggest scrapping or rewriting Athena. It's GA, production-ready, Tesla built it. You're deploying it.
- Don't over-index on your composite risk score. It's a triage tool. Say so proactively.
- Don't claim you'd "ship Tekton mobile improvements" — that's an app-team call. You can propose and prototype.
- Don't say "machine learning" or "AI" unless asked. Zero need.
- Don't apologize for data quality. Diagnose it as evidence of a process gap.

---

## 8. Pre-interview checklist (morning-of)

- [ ] Dashboard running locally (`./.venv/bin/streamlit run src/app.py`)
- [ ] All 5 site names memorized, with actual weeks
- [ ] Can you recite the four pain themes without looking?
- [ ] Can you name 3 stakeholders from the contact sheet with their role?
- [ ] Backup: the `outputs/cleaned/key_findings.md` has the numbers if the dashboard dies
- [ ] Test microphone / camera 20 min before
- [ ] One glass of water within arm's reach
- [ ] One tab with the PDF of the challenge open — shows you came prepared

Good luck.
