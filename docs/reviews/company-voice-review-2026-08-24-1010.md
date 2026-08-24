# Code Review — `company_voice` (Company Voice)

> **Status (24 August 2026, 10:10 WEST):** **ISSUES FOUND.** This is the live queue before Phase 6. Do **not** archive until H1 and M1–M9 are applied or explicitly deferred.

**Date:** 2026-08-24
**Method:** two sub-agents reviewed in parallel (backend; frontend + live API); parent reviewed independently; notes compared below. No source was changed for the review itself.
**Repo:** CentCompras (`warehouse_V2`)
**Code reviewed:** `company_voice/` on current tree (app landed in `fbe3702` / merge `5fd3bda` on `main`)
**Manual:** [`docs/user-manuals/09-company-voice.md`](../user-manuals/09-company-voice.md)
**Diff scope:** new `company_voice` app (models, services, permissions, console API, feed UI, admin, tests, migration `0001_initial`) + wiring (urls, settings example, dashboard link, user manual).

---

## How this review was done

| Reviewer | Scope | Method |
|----------|--------|--------|
| Sub-agent A (backend) | models, services, console views, permissions, admin, tests | Read-only code review, multiuser/race focus |
| Sub-agent B (frontend + live API) | `feed.js` / `feed.html` / i18n, XSS probe, live `/company-voice/` | Browser + API against the running app |
| Parent | Independent pass of the same tree, then empirical checks | Code + Django shell (not rubber-stamping either agent) |

Disagreements were resolved by parent verification (see [Comparison](#comparison--what-changed-in-the-merge)). The unified IDs below are the ones to act on.

---

## Summary

Company Voice is a company-wide suggestion box: any logged-in staff member can post (optional tag + anonymous flag), anyone can open **one** sub-thread per post, authors may edit within 15 minutes and soft-delete. The product shape matches the manual. Auth gating, author-only mutate, body/tag validation, and XSS escaping of message bodies held up under probe.

It has **not** been through the house review that request threads received. Compared with `threads`, this app is thinner on concurrency (`select_for_update` is missing), audit (no ChangeLog), and admin hard-delete policy. The shared feed is also a **multiuser surface**: two people looking at `/company-voice/` share one wall, and several bugs show up only then (or show up as a lie on every row).

**Empirically confirmed (parent, 24 Aug 10:11 UTC, PostgreSQL):**

- A freshly created, never-edited post had `updated_at > created_at` by **8 µs** → serializer `edited: true`.
- Invalid JSON / a JSON array on `POST /api/company-voice/posts/` raises **uncaught `ValidationError`** (Django turns that into **HTTP 500**).
- `"is_anonymous": "false"` created an **anonymous** post (`bool("false")` is true).
- After deleting one of two comments, `comment_count` was still **2**.

---

## Verdict: **ISSUES FOUND**

No Critical security defect (XSS probe did not fire; mutate is author-only; CSRF token is present). **Not ready to treat as done** until at least **H1**, **M1**, and **M2** are fixed. The rest of M3–M9 should be applied or explicitly deferred in the same pass.

| Count | Severity |
|-------|----------|
| 0 | Critical |
| 1 | High |
| 9 | Medium |
| 8 | Low |
| 3 | Nit |

---

## Findings (unified — act on these IDs)

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| H1 | High | `models.py` `auto_now`/`auto_now_add`; `console_views.py` `_serialize_post` / `_serialize_comment` | Every new post/comment is marked **(edited)** |
| M1 | Medium | `console_views.py` `post_create` / `post_update` / `comment_create` / `comment_update` | `_parse_json` sits **outside** `try` → invalid JSON is **HTTP 500** |
| M2 | Medium | `services.py` `delete_post` / `add_comment` / `_get_or_create_sub_thread` | No row lock; first comment vs parent delete can leave a live sub-thread on a deleted post; concurrent first comments can `IntegrityError` → 500 |
| M3 | Medium | `services.py` `edit_post` / `edit_comment` | Last-write-wins; no version / `updated_at` predicate |
| M4 | Medium | `feed.js` delete/edit error paths | Failed write leaves Edit/Delete/composer looking successful |
| M5 | Medium | `feed.js` `renderFeed()` | Full `innerHTML` rebuild wipes in-progress comment drafts (toggle / lang / cancel) |
| M6 | Medium | `console_views.py` `_serialize_sub_thread` | `comment_count` includes soft-deleted comments |
| M7 | Medium | `company_voice/admin.py` | Superuser can still **hard-delete** (threads admin disables delete) |
| M8 | Medium | models — missing | No ChangeLog (house style elsewhere; product may have omitted it) |
| M9 | Medium | `feed.js` `loadFeed` | Shared feed never refreshes other users' activity |
| L1 | Low | `services.py` `_validate_anonymous` | `bool("false")` is true |
| L2 | Low | `feed.js` `submitPost` / `sendComment` | Double-click creates duplicate posts/comments |
| L3 | Low | `feed.js` `can_edit` is server-only | Client never hides Edit after 15 minutes until reload |
| L4 | Low | `feed.js` `showBanner(err.message)` | pt-PT UI still shows English server `error` text; `code` ignored |
| L5 | Low | `feed.js` `escapeHtml` + `innerHTML` | Quotes not escaped; house-style is `textContent` (XSS probe still passed) |
| L6 | Low | `services.py` `edit_post` | `PATCH` with `"tag": null` does not clear the tag |
| L7 | Low | `feed.html` / `feed.js` | Console drift: `company_voice_lang` vs `cc-lang`; hardcoded `/static/…`; no Escape-to-cancel edit |
| L8 | Low | `console_views.py` / `feed_i18n.js` | Dead `is_mine`; unused i18n `anonymous`; server `display_name` hard-codes English `"Anonymous"` |
| N1 | Nit | `get_feed` / `feed_api` | Unbounded feed — **already deferred** in the manual (§6 FAQ) |
| N2 | Nit | `feed.js` `renderTag` | Tag interpolated into a CSS class (server allow-list makes this safe today) |
| N3 | Nit | `services.py` `delete_post` | Reverse OneToOne `DoesNotExist` alias is correct but easy to break; prefer `hasattr` / `select_related` + `None` |

---

### H1 — Every new post/comment shows **(edited)**

`VoicePost` / `VoiceComment` use `created_at = auto_now_add` and `updated_at = auto_now`. Django calls `timezone.now()` **once per field** on insert, so `updated_at` is typically a few microseconds later. Serializer:

```python
"edited": not deleted and post.updated_at > post.created_at
```

**Parent probe:** create_post → `updated_at - created_at = 8 µs` → `serialized.edited is True`. Same for a never-edited comment. Sub-agent B saw this on the live feed for every row.

**Why it matters (multiuser):** the whole company wall labels every message as edited. The manual §4 says *(edited)* means the author changed the text. The badge becomes noise and hides real edits.

**Suggested fix:** do not infer edits from `auto_now`. Prefer a nullable `edited_at` set only in `edit_post` / `edit_comment`, or stop using `auto_now` and set `updated_at = created_at` on insert. Assert `edited is False` on the create-API tests.

**Test gap:** `test_create_post_via_api` never checks `edited`.

---

### M1 — Invalid JSON → uncaught `ValidationError` → HTTP 500

`_parse_json` raises `ValidationError` for bad JSON / non-object payloads. `post_create` (and the other three mutate views) call it **before** the `try/except ValidationError`.

**Parent probe:** `POST` body `not-json` and `[]` → `UNCAUGHT ValidationError`. (A typed `"body": 123` is inside the service `try` and correctly returns 400 `invalid_body`.)

**Why it matters:** same class as the threads-review JSON 500s — a buggy or scripted client takes down the request with a traceback. Wrap `_parse_json` in the existing `try`, or catch `ValidationError` at the view boundary.

---

### M2 — Parent delete vs first comment; no `select_for_update`

`delete_post` and `add_comment` are `@transaction.atomic` but neither locks the `VoicePost` row.

Sequence (two users, no comments yet):

1. User B loads the post (`deleted_at` is null) and starts `add_comment`.
2. User A (`delete_post`) sets `deleted_at` and finds **no** sub-thread, so there is nothing to cascade.
3. User B's `_get_or_create_sub_thread` still holds the **stale in-memory** post (`deleted` is false), creates a `VoiceSubThread` + `VoiceComment`.

Result: a live sub-thread hanging off a tombstoned parent. The feed will show `[Deleted by author]` on the post and live replies underneath.

Second race: two users sending the **first** comment together. `get_or_create` on the OneToOne can raise `IntegrityError` → uncaught **500**.

**Suggested fix:** `VoicePost.objects.select_for_update().get(pk=post.pk)` at the start of `delete_post` and `add_comment`; re-read `deleted`; catch `IntegrityError` on `get_or_create` and fetch the winner. Add a `TransactionTestCase` for comment-vs-delete (same shape as threads post-vs-close).

---

### M3 — Lost updates on PATCH

`edit_post` / `edit_comment` save without a version check. Author-only, so this is usually the **same person in two tabs** (or a retry). Last write wins; the other body disappears with HTTP 200.

**Suggested fix:** require `updated_at` (or an integer version) in the PATCH body and reject with 409 if it does not match. Optional for v1 if H1/M1/M2 land first; still worth doing because the 15-minute window invites two-tab edits.

---

### M4 — Failed write leaves a stale console

On delete/edit failure, `feed.js` only `showBanner(err.message)` and does **not** `loadFeed()`. Edit/Delete buttons and the composer stay as if the write succeeded. Combined with M9, the author and everyone else can disagree about what is live.

**Suggested fix:** `loadFeed()` in the `catch` (or disable actions while in-flight and refresh on any non-2xx).

---

### M5 — `renderFeed()` wipes in-progress drafts

`renderFeed` does `feed.innerHTML = posts.map(renderPost).join("")`. That runs on reply-toggle, language change, and edit-cancel. A comment typed into another post's composer is destroyed. On a shared wall, expanding a neighbour's thread is a normal action.

**Suggested fix:** preserve textarea values (and anonymous ticks) keyed by `post.id` across re-render, or patch the DOM instead of replacing the whole feed.

---

### M6 — `comment_count` includes tombstones

`_serialize_sub_thread` sets `"comment_count": len(comments)` on the prefetched list, including `deleted=true` rows. Parent probe: two comments, one deleted → `comment_count == 2`. The toggle label `{n} replies` then overstates live discussion.

**Suggested fix:** count `not c.deleted` (and ignore rows already covered by a deleted parent). Keep tombstones in `comments` for the placeholder UI.

---

### M7 — Admin hard-delete still enabled

`VoicePostAdmin` / `VoiceCommentAdmin` mark fields readonly but do **not** override `has_add_permission` / `has_change_permission` / `has_delete_permission`. Django admin default delete remains. `threads` admin explicitly disables add/change/delete. Manual §6 says superusers “inspect and manage records in Django admin” — hard delete would skip the `[Deleted by author]` contract and break FKs/`PROTECT` on authors only, not the soft-delete story.

**Suggested fix:** match threads (read-only module, no hard delete), or add a documented superuser soft-delete action.

---

### M8 — No ChangeLog

Catalogue, POs, stock, and request threads all write `*ChangeLog` rows. Company Voice only has `centcompras.company_voice` logger lines. Anonymous posts still store `author_id`, but there is no durable “who edited/deleted when” table if logs rotate.

**Product decision:** add `VoicePostChangeLog` / `VoiceCommentChangeLog` (created / edited / deleted) **or** explicitly defer audit-log tables in the manual. Do not leave it implicit.

---

### M9 — Shared feed never refreshes other users' activity

`loadFeed()` runs at startup and after **this browser's** successful writes. There is no poll, focus refresh, or Refresh button. User A posts; User B stares at an empty/stale wall until they reload.

Sub-agent B rated this **High**. Parent **downgrades to Medium**: the manual does not promise realtime, and this is stale-read UX rather than data corruption. It is still a gap on a **company-wide** wall. A Refresh control is the minimum; light polling can wait.

---

### Lows (short)

- **L1** — `_validate_anonymous` is `return bool(is_anonymous)`. Parent probe: JSON `"false"` → anonymous post. Require `isinstance(..., bool)` (and reject `int`).
- **L2** — Post/Send have no in-flight lock; double-click duplicates. Disable the button until the request finishes.
- **L3** — `can_edit` is computed at serialize time; a tab left open still shows Edit after 15 minutes. Server still rejects (`EditWindowExpiredError`). Hide on a timer or re-fetch.
- **L4** — `api()` throws `data.error` (English). `code` is unused. Map `code` → `t(...)`.
- **L5** — `escapeHtml` via `textContent` → `innerHTML` is fine for **text nodes**; it does not escape quotes. Threads consoles use `textContent` / `el()`. XSS probe against bodies/names did **not** fire. Residual risk if someone later interpolates into attributes (`data-*`, `class`).
- **L6** — `edit_post`: `if tag is not None` so `"tag": null` is a no-op. The UI sends `""` to clear, so the shipped client is fine; document or treat `null` as clear.
- **L7** — `LANG_KEY = "company_voice_lang"` vs other consoles' `cc-lang`; `feed.html` hardcodes `/static/company_voice/...` instead of `{% static %}`; edit form has no Escape handler.
- **L8** — `is_mine` is serialized and never read. I18n key `anonymous` is unused because `display_name()` always returns English `"Anonymous"`.

### Nits (short)

- **N1** — Full history in one GET. Manual FAQ already says pagination is out of scope for v1. Revisit if M9 grows a poller.
- **N2** — `renderTag` puts `tag` in a class name. Server allow-list today.
- **N3** — `except VoiceSubThread.DoesNotExist` works for the reverse OneToOne today (`RelatedObjectDoesNotExist` subclasses it). A refactor that catches the wrong class would skip cascade.

---

## Comparison — what changed in the merge

| Topic | Sub-agent A (backend) | Sub-agent B (frontend) | Parent | Unified |
|-------|-------------------------|------------------------|--------|---------|
| `edited` always true | Not raised | **High (H1)** | Confirmed in DB + serializer | **H1 High** |
| No live refresh | Not raised | **High (H2)** | Manual does not promise realtime; stale-read only | **M9 Medium** |
| JSON 500 | Medium | Medium | Confirmed uncaught `ValidationError` | **M1** |
| Delete vs first comment / no lock | Medium | Not raised | Confirmed in code (stale in-memory post) | **M2** |
| Last-write-wins edits | Medium | Not raised | Real; mostly two-tab | **M3** |
| Unbounded feed | Nit | Medium | Manual already defers pagination | **N1 Nit** |
| Client edit window never expires | — | Medium | Server still enforces | **L3 Low** |
| XSS | — | Probed; did not fire | `escapeHtml` on bodies/names | **Not a finding** (see L5 residual) |
| ChangeLog missing | Medium | — | House-style gap | **M8** (product decision) |
| Admin hard-delete | Medium | — | Confirmed; threads disables it | **M7** |
| `comment_count` tombstones | — | Medium | Confirmed count=2 with one deleted | **M6** |
| Stale UI after failed write / innerHTML wipe | — | Medium | Confirmed in `feed.js` | **M4**, **M5** |
| `"false"` anonymous | Low | — | Confirmed 201 + `is_anonymous: true` | **L1** |

---

## What is done well (verified)

- **Auth:** `login_required_active` + `deny_if_inactive`; page redirects anonymous users; API 401. Warehouse **and** branch users share the feed by design (no tenancy leak — there is no branch scope).
- **Author-only mutate:** `NotAuthorError` on edit/delete; API test `test_non_author_cannot_delete`.
- **Soft delete:** parent delete cascades sub-thread + comments; comment delete is local; feed placeholder `[Deleted by author]`; body nulled in the serializer.
- **Validation:** empty / too-long / non-string body; invalid tag; 15-minute edit window (`EditWindowExpiredError`).
- **XSS (bodies / display names):** `escapeHtml` before `innerHTML`; live probe with script payloads did not execute. (See L5 for the house-style caveat.)
- **CSRF:** `meta csrf-token` + `X-CSRFToken` on `fetch`; logout form has `{% csrf_token %}`. No `@csrf_exempt`. (Same caveat as threads: tests use `enforce_csrf_checks=False`.)
- **Query shape:** feed uses `select_related` + `prefetch_related("sub_thread__comments__author")` — no N+1 on the list path.
- **i18n chrome:** EN + pt-PT strings for the shell (errors still English — L4).
- **Tests:** 18 tests covering create/edit/window/non-author, cascade delete, comment create, feed page for warehouse+branch, deleted placeholder, comment API, edit API.

---

## Test gap notes

These would have caught the High/Medium items:

1. **`edited is False` on create** (H1) and `edited is True` only after `edit_post`.
2. **Invalid JSON / non-object body → 400** not 500 (M1).
3. **Concurrent first comment vs `delete_post`** (`TransactionTestCase` + threads) (M2).
4. **Concurrent two first-comments** — no 500, one sub-thread (M2).
5. **`comment_count` after a comment soft-delete** (M6).
6. **`"is_anonymous": "false"` / `1` rejected** (L1).
7. **Admin `has_delete_permission` is False** (M7).
8. **CSRF-enforced client** on POST/PATCH/DELETE.
9. No browser test that `renderFeed` preserves an in-progress comment draft (M5).

---

## Suggested act-on order

Do **not** start Phase 6 email until this queue is worked or explicitly skipped.

1. **H1** — edited heuristic (user-visible lie on every row).
2. **M1** — `_parse_json` inside `try` → 400.
3. **M2** — `select_for_update` + `IntegrityError` handling; race test.
4. **M4 + M5** — failed-write refresh; preserve drafts.
5. **M6** — live `comment_count`.
6. **M3** — PATCH version / 409 (or defer with a note in the manual).
7. **M7** — admin: no hard delete (match threads) unless product says otherwise.
8. **M8** — ChangeLog **or** written deferral in `09-company-voice.md`.
9. **M9** — at least a Refresh button; polling optional.
10. **L1–L8** as a follow-up slice; **N1–N3** optional.

---

## Out of scope / not findings

- Phase 6 email, offline, shared chrome.
- Request-threads leftover nits N1–N6 (optional, already recorded).
- Pagination of the voice feed (manual FAQ: not in v1) — logged only as N1.
- Realtime/WebSocket — not promised; M9 is “stale shared wall”, not “missing sockets”.

---

*Report produced 24 August 2026, 10:10 WEST. Read-only review; this file is the work queue.*
