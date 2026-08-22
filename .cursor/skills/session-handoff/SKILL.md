---
name: session-handoff
description: >-
  End-of-session documentation sync for CentCompras. Updates handoff.md,
  PROJECT-PLAN.md, README.md, AGENTS.md, active plans, and user manuals when
  needed. Use when the user says session handoff, wrap up, end session, update
  living docs, or before stopping work.
disable-model-invocation: true
---

# Session handoff (CentCompras)

Sync **living documents** at end of session so the next chat can start from `docs/handoff.md` without re-briefing.

## When to run

- User says: "session handoff", "wrap up", "update living docs", "we're done for today"
- Before ending a coding session with meaningful changes
- After completing a plan phase or fixing user-visible behaviour

## Do not

- Commit or push unless explicitly requested
- Edit archived docs under `docs/archive/` (except to archive a concluded review)
- Invent work that was not done — derive "landed" from conversation + `git diff`

## Workflow

### 1. Gather session facts

- Scan conversation for completed work, decisions, and explicit "next" task
- Run `git status` and `git diff` (or review unstaged changes)
- Run full tests and record count:
  `.venv/bin/python manage.py test products accounts procurement inventory branches orders --noinput`

### 2. Update living documents (required)

| File | Update |
|------|--------|
| `docs/handoff.md` | **Primary.** Timestamp (WEST). TL;DR phase table. "This session — landed" bullets. "Next session — do this" (numbered, actionable). Test count. Brief git note. Link active plan if any. |
| `docs/PROJECT-PLAN.md` | Header "Last updated" + current phase. §6 current state. §7 phase map. §15 status tracker ticks. New rows in §5 decisions (D*) for locked choices. Remove stale "not built" wording. |
| `README.md` | "Last updated". "Pick up here" / quick start step 4 → next task. Test count if changed. |
| `AGENTS.md` | Session handoff block only: **Done**, **Not done**, **Next** (one paragraph each). |

### 3. Active plans (if applicable)

- Under `.cursor/plans/*.plan.md`: mark completed todos; ensure **Next** in handoff matches plan phase/slice
- Do not delete plans; update frontmatter `status: completed` on todos

### 4. User manuals (conditional)

Follow `.cursor/rules/user-manuals.mdc` when this session changed:

- Validation constraints, error messages, state machines, or console workflow
- Update domain manual + `docs/user-manuals/05-edge-cases-and-limits.md` §2/§3/§4 as needed

Skip manual updates for refactors with no user-visible change.

### 5. handoff.md sections to refresh

Keep existing structure; update every session:

```markdown
> Last updated: DD Month YYYY, HH:MM WEST

## TL;DR — where we are
[phase table + one paragraph: what finished + what's next]

## Next session — do this
1. [Primary task with link to plan or PROJECT-PLAN §]
2. [Secondary / then-phase]
3. [Reminders: no stale review queues, test DB, do not start X without plan]

## This session (DD Mon YYYY) — landed
### [Feature/fix name]
- bullet facts
```

### 6. Reply to user

Short summary:

1. **Landed** — 3–6 bullets
2. **Next session** — one line
3. **Docs touched** — file list
4. **Tests** — count (or "not run")

## CentCompras conventions

- **Next task priority:** `docs/handoff.md` wins over PROJECT-PLAN header if user specified interim work (e.g. plan Phase 2 before Phase 6 email)
- **Reviews:** 1303 and 2208 are archived — never reopen as backlog
- **Tests:** use project venv; document exact count after run
- **Timestamps:** full date + time in doc filenames only; handoff uses "DD Month YYYY, HH:MM WEST"
