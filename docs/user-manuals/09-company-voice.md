# Company Voice — user manual

Company Voice is an internal suggestion box for all CentCompras staff. Anyone logged in (warehouse or branch) can post praise, concerns, suggestions, or wishes. Each post can have one inline reply thread (one level of sub-discussion).

**URL:** `/company-voice/`

---

## 1. Who can use it

| Role | Access |
|------|--------|
| Warehouse admin / manager / operator | Read and post |
| Branch admin / manager / operator | Read and post |
| Django superuser | Same as other users in the app; moderation only via `/admin/` |

No branch selection is required. Warehouse and branch users share the same feed.

---

## 2. Posting

1. Open **Company Voice** from the staff dashboard (`/`) or go to `/company-voice/`.
2. Optionally choose a **tag**: Praise, Concern, Suggestion, or Wish (or leave untagged).
3. Write your message in the text area.
4. Optionally tick **Post anonymously** — other users see "Anonymous" instead of your display name.
5. Click **Post**.

### Display names

- **Named post:** your first name if set on your account; otherwise the part of your email before `@`.
- **Anonymous post:** shown as **Anonymous** to everyone (author is still stored server-side for audit).

---

## 3. Replies (sub-threads)

- Click **Reply** (or the reply count) under a post to expand the inline discussion.
- Anyone can add the first comment — this opens the one sub-thread for that post.
- Each top-level post can have **at most one** sub-thread (no deeper nesting).
- Comments support the same **anonymous** checkbox as top-level posts.

---

## 4. Edit and delete

| Action | Who | Rule |
|--------|-----|------|
| **Edit** | Author only | Within **15 minutes** of posting |
| **Delete** | Author only | Soft delete — content replaced by `[Deleted by author]` |

- Deleting a **top-level post** also soft-deletes its entire sub-thread and all comments.
- Deleting a **comment** only removes that comment.
- Edited posts and comments show **(edited)** next to the timestamp.

---

## 5. Server messages (errors)

| Situation | Message |
|-----------|---------|
| Empty body | `Message body cannot be empty.` |
| Body too long | `Message body cannot exceed 4000 characters.` |
| Edit after 15 minutes | `The edit window has expired.` |
| Not the author | `Only the author can change or delete this message.` |
| Already deleted | `This message has been deleted.` |
| Comment on deleted post | `This post has been deleted.` |
| Invalid tag | `Invalid tag.` |

---

## 6. FAQ

**Can I edit anonymously after posting?**  
Yes, within 15 minutes, if you are the author. The anonymous flag is fixed at create time.

**Can warehouse admins remove someone else's post?**  
Not from the website. Superusers may inspect and manage records in Django admin (`/admin/`).

**Is the feed paginated?**  
Not in the first release — the full history loads in one scrollable view.

**How is this different from Request threads?**  
Request threads (`/branch/threads/`, `/manage/threads/`) are for catalogue-gap items between a branch and the warehouse. Company Voice is company-wide feedback visible to all staff.
