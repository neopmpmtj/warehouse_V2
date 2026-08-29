# Company Voice — user manual

Company Voice is an internal suggestion box for all CentCompras staff. Anyone logged in (warehouse or branch) can post praise, concerns, suggestions, or wishes. Each post can have one inline reply thread (one level of sub-discussion).

**URL:** `/company-voice/`

---

## 1. Who can use it

| Role | Access |
|------|--------|
| Warehouse admin / manager / operator | Read and post |
| Branch admin / manager / operator | Read and post |
| Django superuser | Same as other users in the app; `/admin/` is inspect-only (no hard delete) |

No branch selection is required. Warehouse and branch users share the same feed.

Open the **Settings** gear (top-right) for **Signed in as** and a small **Sign out** link on the title row. **Help** is the blue **?** icon next to the gear (placeholder). **Language** (English / Português) is set on the staff dashboard (`/`) or the branch dashboard (`/branch/`) and remembered in this browser.

**CentCompras** (top-left) returns you to your dashboard: **`/`** for warehouse staff, **`/branch/`** for branch-only staff. It does not send branch staff to `/` (that page requires a warehouse catalogue permission).

---

## 2. Posting

1. Open **Company Voice** from the staff dashboard (`/`) or go to `/company-voice/`.
2. Optionally choose a **tag**: Praise, Concern, Suggestion, or Wish (or leave untagged).
3. Write your message in the text area (max **4000** characters).
4. Optionally tick **Post anonymously** — other users see **Anonymous** / **Anónimo** instead of your display name.
5. Click **Post**.

Use **Refresh** to load posts and replies written by other people since you opened the page. Your own successful Post / Send / Save / Delete already reloads the feed.

### Display names

- **Named post:** your first name if set on your account; otherwise the part of your email before `@`.
- **Anonymous post:** shown as **Anonymous** (English) or **Anónimo** (Português) to everyone (author is still stored server-side for audit).

---

## 3. Replies (sub-threads)

- Click **Reply** (or the reply count) under a post to expand the inline discussion.
- Anyone can add the first comment — this opens the one sub-thread for that post.
- Each top-level post can have **at most one** sub-thread (no deeper nesting).
- Comments support the same **anonymous** checkbox as top-level posts.
- The reply count is **live comments only** — deleted comments stay visible as `[Deleted by author]` but are not counted.

---

## 4. Edit and delete

| Action | Who | Rule |
|--------|-----|------|
| **Edit** | Author only | Within **15 minutes** of posting. The Edit link hides when the window expires (even if you leave the page open). |
| **Delete** | Author only | Soft delete — content replaced by `[Deleted by author]` |

- Deleting a **top-level post** also soft-deletes its entire sub-thread and all comments.
- Deleting a **comment** only removes that comment.
- **(edited)** appears next to the timestamp only after a real save — a brand-new post is never marked edited.
- Saving an edit while another tab already saved the same message returns a conflict; **Refresh** and try again.
- Press **Escape** to cancel an edit in progress. Changing language or expanding another reply keeps any comment you were typing.

---

## 5. Server messages (errors)

| Situation | Message (EN) | `code` |
|-----------|----------------|--------|
| Empty body | `Message body cannot be empty.` | `empty_body` |
| Body too long | `Message body cannot exceed 4000 characters.` | `body_too_long` |
| Edit after 15 minutes | `The edit window has expired.` | `edit_window_expired` |
| Not the author | `Only the author can change or delete this message.` | `not_author` |
| Already deleted | `This message has been deleted.` | `already_deleted` |
| Comment on deleted post | `This post has been deleted.` | `post_deleted` |
| Invalid tag | `Invalid tag.` | `invalid_tag` |
| Invalid JSON | `Request body must be valid JSON.` | `invalid_json` |
| Body not a string | `Body must be a string.` | `invalid_body` |
| Anonymous flag not boolean | `is_anonymous must be a boolean.` | `invalid_anonymous` |
| Stale edit (another tab saved first) | `This message was changed in another tab. Refresh and try again.` | `stale_edit` (HTTP **409**) |

The website shows the matching Portuguese string when the language is Português.

---

## 6. FAQ

**Can I edit anonymously after posting?**  
Yes, within 15 minutes, if you are the author. The anonymous flag is fixed at create time.

**Can warehouse admins remove someone else's post?**  
Not from the website. Superusers may **inspect** records in Django admin (`/admin/`) — they cannot hard-delete Voice rows. Authors soft-delete from `/company-voice/`.

**Is the feed paginated?**  
Not in the first release — the full history loads in one scrollable view.

**How is this different from Request threads?**  
Request threads (`/branch/threads/`, `/manage/threads/`) are for catalogue-gap items between a branch and the warehouse. Company Voice is company-wide feedback visible to all staff.

**Is there an audit trail?**  
Yes. Create, edit, and delete write a `VoiceChangeLog` row (who, action, when). Rotating app logs are extra, not the source of truth.
