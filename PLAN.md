# Repository foundation plan

Date: 2026-11-04. Updated: 2026-11-05. Phase A merged in PR #2, with validation correction PR #3.
All six business steps merged through PR #16, with green current-head CI,
independent reviews and static-report QA. Final delivery documentation is in review.
The tables below retain historical foundation evidence.

Checklist audit: the step table below records the repository setup sequence,
owner-approved stack adaptations, scope exclusions and verification evidence.
It is retained as delivery history and is self-contained for public visitors.

## Initial audit

Fetched main: `3f540e6` (specification PR #1), after initial commit `713887a`.
Only README, AGENTS and approved-scope research/spec documentation existed; no
application, tests, CI, packaging or project skills. Approval text was stale and
is corrected in this PR from the owner's explicit implementation authorization.

## Step status

| Step | Name | Type | Status | Decision / evidence |
|---|---|---|---|---|
| 0.1 | Work environment | choice | done | Existing isolated execution environment; no deployment setup. |
| 0.2 | Model allocation | 1:1 | done | Codex implementation; separate review owned by maintainer. No child tasks. |
| 0.3 | Repository authority | 1:1 | done | Fetched origin/main before audit. |
| 1.1 | Project route | choice | approved 2026-11-04 | Existing synthetic demo, explicit owner assignment. |
| 1.2 | Initial concept | choice | done | Business spec and source-system research already merged in PR #1. |
| 1.3 | Toolchain | 1:1 | done | Python 3.12.3, Git, Node 24.21.0, gh 2.102.0 available. |
| 1.4 | Environment selection | choice | done | Existing execution environment; no infrastructure changes. |
| 1.5 | Two skill-capable agents | 1:1 | out of scope | Agent runtime provisioning not repeated; both project skill paths installed. |
| 1.6 | Tracker authentication | 1:1 | done | Authenticated gh repository/default-branch and label reads succeed. |
| 1.7 | Scaffold | 1:1 order; choice tool | deviation | Existing documentation predates scaffold; approved Phase A adds Python src layout instead of Next.js. |
| 1.8 | Initial commit | 1:1 | done | Existing main initial commit 713887a; do not recreate history. |
| 1.9 | README | 1:1 | done | Fresh-clone smoke instructions and honest current scope. |
| 1.10 | Two-agent comparison | 1:1 | out of scope | Runtime training exercise; no fabricated comparison. |
| 1.11 | Commit and push habit | 1:1 | done | Isolated branch; reviewed PR delivery, no main push. |
| 1.12 | Skill installation timing | source gap | deviation | Installed at 3.3, where the installation command is defined. |
| 2.1 | Stack decision | choice | approved 2026-11-04 | Owner selected Python/SQLite/HTML/pytest+coverage/Ruff; adaptations below. |
| 2.2 | Stack record | 1:1 | done | README, AGENTS and engineering standards. |
| 2.3 | Agent settings | 1:1 | out of scope | Execution settings supplied externally; no personal configuration in repo. |
| 2.4 | Agent context structure | 1:1 | done | AGENTS, CLAUDE inclusion, specs/archive/implemented, runs, lessons. |
| 2.5 | Working principles | 1:1 | deviation | Codex applies planning, immediate lessons, reuse and smallest-change principles; no Claude implementation. |
| 2.6 | Retain instructions | 1:1 | done | AGENTS requires reading and updating repository context. |
| 2.7 | Structure commit | 1:1 | done | Foundation PR history records repository structure. |
| 2.8 | Package layout | choice | done | One src/propane_demo package, no speculative monorepo. |
| 2.9 | Tracker | choice | approved 2026-11-04 | GitHub Issues, code and PRs; default label taxonomy. |
| 2.10 | Application foundation | 1:1 process; choice stack | deviation | Approved minimal smoke path only; no ORM/DI/framework scaffolding. |
| 2.11 | Local database | choice | done | Standard-library in-memory SQLite, no service/credentials/Docker. |
| 2.12 | Engineering standards | 1:1 process; choice content | done | Standards merged in PR #2; no separate approval of every choice claimed. |
| 2.13 | Fresh checkout validation | 1:1 | done | Fresh archive of cb121f4: editable install and full make check passed. |
| 2.14 | PR CI | 1:1 process; choice tools | done | CI invokes make check; pinned actions; temporary SQLite and installed CLI E2E. |
| 2.15 | Coverage | 1:1; choice gate | done | All src discovered; separate exact 100% line/branch gates; negative gate tests. |
| 2.16 | Merge gate | 1:1; choice ruleset | done | Green current-head CI plus independent approval policy; no ruleset changes. |
| 2.17 | Safety-net evidence | 1:1 | done | PR #2 run 41845784755 green; downloaded HTML matches local artifact. |
| 2.18 | Commit and merge | 1:1 | done | Foundation PR #2 and correction PR #3 merged. |
| 3.1 | Pipeline prerequisites | 1:1 | deviation | Static HTML pytest E2E replaces browser automation by owner decision. |
| 3.2 | Skill roles | 1:1 | done | Read installed pipeline/open-PR instructions and references; author/reviewer/maintainer roles. |
| 3.3 | Project skill install | 1:1 | done | All open-mercato skills, Codex and Claude project scope, relative symlinks. |
| 3.4 | Skill version record | 1:1 | done | skills-lock.json stores source and computed hashes; vendored files committed. |
| 3.5 | Skill availability | 1:1 | done | SKILL.md files and relative symlink targets checked; cross-skill coverage verified. |
| 3.6 | GitHub CLI | 1:1 | done | Repository/default-branch reads and taxonomy operations work. |
| 3.7 | Pipeline configuration | 1:1 process; choice answers | approved 2026-11-04 | Owner delegated make check, GitHub, no browser, default labels, QA and docs. |
| 3.8 | Local equals CI | 1:1 | done | Both run make check; CI supplies only HTML artifact destination. |
| 3.9 | Generated file review | 1:1 | done | Static HTML QA adaptation; existing AGENTS preserved and extended in foundation step. |
| 3.10 | Open setup PR | 1:1 | done | PR #2 delivered and merged; correction PR #3 merged. |
| 3.11 | Local skill overrides | 1:1 | done | SDLC records .ai/skills/<exact-name>/SKILL.md convention; no speculative override. |
| 3.12 | First business issue | 1:1 process; choice task | done | Issue #4 implemented and merged in PR #10. |
| 3.13 | Implement issue | 1:1 | done | All six business steps merged through PR #16. |
| 3.14 | Independent review | 1:1 | done | Foundation delivered; step-6 review remains separate. |
| 3.15 | Override A/B exercise | 1:1; choice content | out of scope | Training exercise not needed for Phase A; no invented evidence. |
| 3.16 | Optional orchestration | choice | out of scope | No project orchestration infrastructure committed. |
| 3.17 | Later pipeline refresh | 1:1 | out of scope | Re-run after future toolchain/taxonomy updates. |

## Stack adaptations

| Element | Reference | Project | Decision |
|---|---|---|---|
| Language | TypeScript | Python 3.12 | Approved |
| Framework | Next.js | None | Approved |
| UI | React/Tailwind | Plain HTML | Approved |
| Database | PostgreSQL | SQLite | Approved |
| ORM/migrations | MikroORM | stdlib SQL | Adapted |
| DI | Container | Explicit args | Adapted |
| Validation | Zod | Boundary checks | Adapted |
| Tests | Vitest/browser | pytest E2E | Approved |
| Quality | JS toolchain | Ruff/coverage | Approved |

The owner's smallest-foundation instruction makes an ORM, automatic migrations,
DI container and browser service unnecessary here. SQLite schema is disposable
smoke state; persistent import schema/migrations belong to the import issue.
Explicit boundary validation uses ValueError and argparse today; source contracts
come later. These adaptations avoid framework dependencies and speculative code.
Rejecting the stack would require replacing packaging, CI, tests and smoke path;
business schema, rules, calculations and acceptance evidence would also need migration.

## Pipeline answers and limits

Owner-delegated answers: full validation `make check`; tracker GitHub Issues;
no browser (static HTML with pytest E2E); default labels; QA gate on, green CI and
independent approval; specs `.ai/specs`; all default process docs. Queue eligibility
and other optional settings retain skill defaults, without installing workers or
activating automerge labels. GitHub rulesets query returned an empty list; enforcement is process policy plus CI, not configured branch protection. No native approval is claimed.
The foundation standards merged in PR #2; validation correction merged in PR #3. Agent-runtime
provisioning, comparison exercises and override A/B homework are explicitly not
claimed as completed. The original steps 3.12–3.14 completed through the foundation delivery.

## Foundation acceptance

- [x] Synthetic-only package and installed CLI smoke path; safe failures and escaping.
- [x] 100% application line and branch gates independently checked without rounding.
- [x] Automated dependency-direction enforcement; no bypass exclusions.
- [x] Project skills, lock and relative symlinks; pipeline docs and tracker descriptor.
- [x] Fresh committed checkout passes installation and full validation.
- [x] PR CI green and uploaded HTML artifact inspected (run 41845784755; final head follow-up on PR).
- [x] Foundation merge in PR #2 and validation correction in PR #3.

The preserved smoke path generates only a synthetic marker through SQLite.
Business schema, generator, import ledger, checks, KPIs and report are now merged
through step 6, including optional narrative. Offline behavior
remains the default. No live vendor access, deployment or accounting write occurs.

## Business implementation status — 2026-11-05

The earlier sections describe the historical foundation setup, not current code.
Foundation merged in PR #2 with correction PR #3. Business steps 1–6 are merged:
fixtures PR #10, ingestion PR #11, rules PR #12, inventory PR #14,
KPI/report PR #15 and optional narrative PR #16 (main commit 379699a).
Issue #9 passed its native human gate, two independent reviews, green PR CI
and static-report QA. All six implementation issues are closed.
The completed business spec is in `.ai/specs/implemented/`; its original path remains
a compatibility index for reviewed issue and PR links.
Issue #13 remains an explicitly deferred policy decision, not unfinished demo scope.
No live integration or deployment is authorized or claimed.
