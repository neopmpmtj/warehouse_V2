---
name: session-handoff
description: End-of-session wrap-up — sync all living documents for the next session
---

Read and follow the **session-handoff** skill (`.cursor/skills/session-handoff/SKILL.md`).

End-of-session wrap-up: update all living documents so the next session can resume without re-explaining context.

Do this in one pass:

1. Read the conversation and `git diff`; summarize what landed this session.
2. Update `docs/handoff.md` (TL;DR, "This session — landed", "Next session — do this", test count, timestamp WEST).
3. Update `docs/PROJECT-PLAN.md` (header current phase, §6 current state, §7 phase map, §15 status tracker, new locked decisions D* if any; fix stale wording).
4. Update `README.md` (last updated, next task pointer, test count if changed).
5. Update `AGENTS.md` session handoff block (Done / Not done / Next).
6. If an active `.cursor/plans/*.plan.md` applies: tick completed todos, note next step.
7. If behaviour/constraints/errors changed: update `docs/user-manuals/` per `.cursor/rules/user-manuals.mdc`.
8. Run the full test suite: `.venv/bin/python manage.py test products accounts procurement inventory branches orders --noinput`
9. Do not commit unless I ask.

Reply with: what changed in docs, next session task (one line), and test count.
