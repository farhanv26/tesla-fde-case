# Tesla FDE — Key Findings

## Headline: Deployment Velocity is the Biggest Signal

Target: **4 weeks** to go-live. Actuals:

| Site | Actual weeks | Overrun |
| --- | --- | --- |
| Berlin | 6.5 | +2.5 wk (+62%) |
| Nevada | 5.0 | +1.0 wk (+25%) |
| Texas | 5.0 | +1.0 wk (+25%) |
| Mexico | 4.0 | 0.0 wk (0%) |
| Shanghai | 3.5 | -0.5 wk (-12%) |

**Spread:** Berlin took 6.5 weeks (62% over target). Shanghai landed in 3.5. Shanghai/Mexico are the playbook; Berlin is the anti-pattern.

## User Pain Themes (38 feedback items across 5 sites)

| Theme | Mentions | High-priority |
| --- | --- | --- |
| Change Mgmt (clicks/workflow) | 8 | 5 |
| Tekton <> Athena Sync | 8 | 4 |
| Milestones / Scheduling | 7 | 3 |
| Reporting / Variance / Rollups | 7 | 2 |
| Uncategorized | 6 | 5 |
| Integrations (Primavera/SAP/API) | 4 | 2 |
| Data Quality / Import | 3 | 2 |
| External Access / Permissions | 3 | 3 |

The top three themes account for the majority of all feedback. Any Austin plan that doesn't address change-management friction, Tekton sync, and reporting/rollup reliability is solving the wrong problem.

## Site-Level Composite Risk (directional, not calibrated)

| Site | Composite score |
| --- | --- |
| Berlin | 3.06 |
| Nevada | 2.52 |
| Texas | 2.15 |
| Shanghai | 1.12 |
| Mexico | 1.04 |

## Budget Control Failures

- Largest overrun: **Berlin / HVAC Systems** — $560,000 (12.0%).
- Targeted Savings across sites consistently underperformed plan (realized < budgeted).

## Top High-Priority Unresolved Items

- **Berlin** · External: GC Partner (Pain Point): 1 high-priority open (100% unresolved rate).
- **Berlin** · Foreman (Pain Point): 1 high-priority open (100% unresolved rate).
- **Berlin** · Procurement Team (Pain Point): 1 high-priority open (100% unresolved rate).
- **Berlin** · Project Controls (Pain Point): 1 high-priority open (100% unresolved rate).
- **Nevada** · Construction PM Team (Pain Point): 1 high-priority open (100% unresolved rate).

## Austin Estimate — Day-1 Data Quality Risks

| Field | Defect | Rows | Import impact |
| --- | --- | --- | --- |
| Project | Missing / blank | 1 | Would not import — required for Area/System root node. |
| Area/System | Missing / blank | 1 | Scope orphaned from Area/System hierarchy. |
| Labor Cost | Mixed format ($, commas, k/M suffixes) | 13 | Numeric parser would need pre-processing before load. |
| Material Cost | Mixed format ($, commas, k/M suffixes) | 6 | Numeric parser would need pre-processing before load. |
| Rental Cost | Mixed format ($, commas, k/M suffixes) | 2 | Numeric parser would need pre-processing before load. |
| Material Quantity | Mixed format ($, commas, k/M suffixes) | 18 | Numeric parser would need pre-processing before load. |

## Recommendations for Austin Deployment

1. **Freeze scope at kickoff** — enforce the Estimate as the single source for Areas/Systems/Scopes/Tasks. Fix data-quality defects before Day 1.
2. **Front-load integration risk (weeks 1–2)** — Primavera milestone sync and SAP budget-code mapping drove the longest Berlin blockers. Validate end-to-end in a staging environment before any user training.
3. **Publish a change-management cheat sheet before training** — the #1 pain theme across all 5 sites. 1-click small-change approvals (already prototyped in Texas) should be backported Day 1.
4. **Make Tekton offline-mode + photo upload a go-live blocker** — field crews at 4 of 5 sites hit this; zones C/D at Austin have known spotty cell coverage per the Technical Survey.
5. **Pre-stage role-based permissions** for 5 external contractors + 2 design partners (MEP, GC, Structural, Commissioning, Electrical; Architect, Structural Eng) — scoped RBAC was a blocker at Berlin and Nevada.
6. **Daily standup + weekly reporting template owned by FDE** — missing-status was the root cause of 22 / 38 feedback items going untriaged. Standardize the fields (site, priority, owner, SLA date).
7. **Named internal champion (P. Kumar)** from prior site; pair with Project Controls (R. Lopez) for weekly budget/variance review.