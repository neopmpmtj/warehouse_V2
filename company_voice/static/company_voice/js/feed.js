(function () {
    const CSRF = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const LANG_KEY = "company_voice_lang";

    let lang = localStorage.getItem(LANG_KEY) || "en";
    let posts = [];
    const expandedPosts = new Set();

    function t(key, vars) {
        const dict = window.COMPANY_VOICE_I18N[lang] || window.COMPANY_VOICE_I18N.en;
        let text = dict[key] || window.COMPANY_VOICE_I18N.en[key] || key;
        if (vars) {
            Object.keys(vars).forEach((k) => {
                text = text.replace(`{${k}}`, vars[k]);
            });
        }
        return text;
    }

    function applyI18n() {
        document.querySelectorAll("[data-i18n]").forEach((el) => {
            el.textContent = t(el.getAttribute("data-i18n"));
        });
        document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
            el.placeholder = t(el.getAttribute("data-i18n-placeholder"));
        });
        document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
            el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
        });
        const langSelect = document.getElementById("lang-select");
        if (langSelect) {
            langSelect.value = lang;
        }
    }

    function showBanner(message) {
        const banner = document.getElementById("banner");
        banner.textContent = message;
        banner.classList.remove("hidden");
    }

    function hideBanner() {
        document.getElementById("banner").classList.add("hidden");
    }

    async function api(path, options = {}) {
        const headers = {
            "Content-Type": "application/json",
            "X-CSRFToken": CSRF,
            ...(options.headers || {}),
        };
        const response = await fetch(path, { ...options, headers });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        return data;
    }

    function formatTime(iso) {
        try {
            const d = new Date(iso);
            return d.toLocaleString(lang === "pt" ? "pt-PT" : "en-GB", {
                day: "2-digit",
                month: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
            });
        } catch (_e) {
            return iso;
        }
    }

    function deletedLabel() {
        return t("deletedByAuthor");
    }

    function renderTag(tag) {
        if (!tag) return "";
        return `<span class="tag-pill ${tag}">${t("tag" + tag.charAt(0).toUpperCase() + tag.slice(1))}</span>`;
    }

    function renderActions(item, type, postId) {
        if (item.deleted) return "";
        const parts = [];
        if (item.can_edit) {
            parts.push(`<button type="button" class="btn-link" data-action="edit-${type}" data-id="${item.id}" data-post-id="${postId || ""}">${t("edit")}</button>`);
        }
        if (item.can_delete) {
            parts.push(`<button type="button" class="btn-link danger" data-action="delete-${type}" data-id="${item.id}" data-post-id="${postId || ""}">${t("delete")}</button>`);
        }
        return parts.length ? `<div class="post-actions">${parts.join("")}</div>` : "";
    }

    function renderComment(comment, postId) {
        const body = comment.deleted
            ? `<p class="comment-body deleted-text">${deletedLabel()}</p>`
            : `<p class="comment-body">${escapeHtml(comment.body)}</p>`;
        const edited = comment.edited ? ` <span class="edited-mark">${t("edited")}</span>` : "";
        const name = comment.deleted ? deletedLabel() : escapeHtml(comment.display_name);
        return `
            <article class="comment" data-comment-id="${comment.id}">
                <div class="comment-meta">${name} · ${formatTime(comment.created_at)}${edited}</div>
                ${body}
                ${renderActions(comment, "comment", postId)}
            </article>
        `;
    }

    function renderSubThread(post) {
        const st = post.sub_thread;
        const expanded = expandedPosts.has(post.id);
        const count = st.comment_count || 0;
        const toggleLabel = expanded
            ? t("hideReplies")
            : (count > 0 ? t("replyCount", { n: count }) : t("reply"));
        const commentsHtml = (st.comments || []).map((c) => renderComment(c, post.id)).join("");
        return `
            <div class="post-actions">
                <button type="button" class="btn-link" data-action="toggle-reply" data-id="${post.id}">${toggleLabel}</button>
            </div>
            <div class="sub-thread ${expanded ? "" : "hidden"}" data-sub-thread="${post.id}">
                ${commentsHtml}
                ${post.deleted ? "" : `
                <div class="comment-compose">
                    <textarea data-comment-body="${post.id}" placeholder="${t("commentPlaceholder")}"></textarea>
                    <div class="comment-compose-actions">
                        <label class="checkbox-label">
                            <input type="checkbox" data-comment-anonymous="${post.id}">
                            <span>${t("commentAnonymous")}</span>
                        </label>
                        <button type="button" class="btn-primary" data-action="send-comment" data-id="${post.id}">${t("send")}</button>
                    </div>
                </div>`}
            </div>
        `;
    }

    function renderPost(post) {
        const body = post.deleted
            ? `<p class="post-body deleted-text">${deletedLabel()}</p>`
            : `<p class="post-body">${escapeHtml(post.body)}</p>`;
        const edited = post.edited ? ` <span class="edited-mark">${t("edited")}</span>` : "";
        const name = post.deleted ? deletedLabel() : escapeHtml(post.display_name);
        const tag = post.tag && !post.deleted ? renderTag(post.tag) : "";
        return `
            <article class="post-card ${post.deleted ? "deleted" : ""}" data-post-id="${post.id}">
                <div class="post-meta">
                    <span class="name">${name}</span>
                    ${tag}
                    <span>${formatTime(post.created_at)}${edited}</span>
                </div>
                ${body}
                ${renderActions(post, "post", post.id)}
                ${renderSubThread(post)}
            </article>
        `;
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function renderFeed() {
        const feed = document.getElementById("feed");
        const empty = document.getElementById("feed-empty");
        if (!posts.length) {
            feed.innerHTML = "";
            empty.classList.remove("hidden");
            return;
        }
        empty.classList.add("hidden");
        feed.innerHTML = posts.map(renderPost).join("");
        feed.scrollTop = feed.scrollHeight;
    }

    async function loadFeed() {
        hideBanner();
        try {
            const data = await api("/api/company-voice/feed/");
            posts = data.posts || [];
            renderFeed();
        } catch (err) {
            showBanner(t("loadError"));
        }
    }

    async function submitPost() {
        const body = document.getElementById("compose-body").value;
        const tag = document.getElementById("compose-tag").value;
        const isAnonymous = document.getElementById("compose-anonymous").checked;
        hideBanner();
        try {
            await api("/api/company-voice/posts/", {
                method: "POST",
                body: JSON.stringify({ body, tag: tag || null, is_anonymous: isAnonymous }),
            });
            document.getElementById("compose-body").value = "";
            document.getElementById("compose-anonymous").checked = false;
            document.getElementById("compose-tag").value = "";
            await loadFeed();
        } catch (err) {
            showBanner(err.message || t("postError"));
        }
    }

    async function sendComment(postId) {
        const textarea = document.querySelector(`[data-comment-body="${postId}"]`);
        const anon = document.querySelector(`[data-comment-anonymous="${postId}"]`);
        if (!textarea) return;
        const body = textarea.value;
        hideBanner();
        try {
            await api(`/api/company-voice/posts/${postId}/comments/`, {
                method: "POST",
                body: JSON.stringify({
                    body,
                    is_anonymous: anon ? anon.checked : false,
                }),
            });
            textarea.value = "";
            if (anon) anon.checked = false;
            expandedPosts.add(postId);
            await loadFeed();
        } catch (err) {
            showBanner(err.message || t("postError"));
        }
    }

    async function deletePost(postId) {
        if (!window.confirm(t("confirmDeletePost"))) return;
        hideBanner();
        try {
            await api(`/api/company-voice/posts/${postId}/delete/`, { method: "DELETE" });
            await loadFeed();
        } catch (err) {
            showBanner(err.message);
        }
    }

    async function deleteComment(commentId) {
        if (!window.confirm(t("confirmDeleteComment"))) return;
        hideBanner();
        try {
            await api(`/api/company-voice/comments/${commentId}/delete/`, { method: "DELETE" });
            await loadFeed();
        } catch (err) {
            showBanner(err.message);
        }
    }

    function startEdit(type, id, postId) {
        const post = posts.find((p) => p.id === Number(postId || id));
        let item;
        let container;
        if (type === "post") {
            item = post;
            container = document.querySelector(`[data-post-id="${id}"]`);
        } else {
            item = post?.sub_thread?.comments?.find((c) => c.id === Number(id));
            container = document.querySelector(`[data-comment-id="${id}"]`);
        }
        if (!item || !container || item.deleted) return;

        const isPost = type === "post";
        const form = document.createElement("div");
        form.className = "edit-form";
        form.innerHTML = `
            <textarea class="edit-body">${escapeHtml(item.body)}</textarea>
            ${isPost ? `
            <select class="edit-tag">
                <option value="" ${!item.tag ? "selected" : ""}>${t("tagNone")}</option>
                <option value="praise" ${item.tag === "praise" ? "selected" : ""}>${t("tagPraise")}</option>
                <option value="concern" ${item.tag === "concern" ? "selected" : ""}>${t("tagConcern")}</option>
                <option value="suggestion" ${item.tag === "suggestion" ? "selected" : ""}>${t("tagSuggestion")}</option>
                <option value="wish" ${item.tag === "wish" ? "selected" : ""}>${t("tagWish")}</option>
            </select>` : ""}
            <div class="edit-form-actions">
                <button type="button" class="btn-primary edit-save">${t("save")}</button>
                <button type="button" class="btn-link edit-cancel">${t("cancel")}</button>
            </div>
        `;
        container.querySelector(".post-body, .comment-body")?.replaceWith(form);

        form.querySelector(".edit-cancel").addEventListener("click", () => renderFeed());
        form.querySelector(".edit-save").addEventListener("click", async () => {
            const newBody = form.querySelector(".edit-body").value;
            hideBanner();
            try {
                if (isPost) {
                    const newTag = form.querySelector(".edit-tag").value;
                    await api(`/api/company-voice/posts/${id}/`, {
                        method: "PATCH",
                        body: JSON.stringify({ body: newBody, tag: newTag || "" }),
                    });
                } else {
                    await api(`/api/company-voice/comments/${id}/`, {
                        method: "PATCH",
                        body: JSON.stringify({ body: newBody }),
                    });
                }
                await loadFeed();
            } catch (err) {
                showBanner(err.message);
            }
        });
    }

    function bindEvents() {
        document.getElementById("compose-submit").addEventListener("click", submitPost);

        document.getElementById("lang-select").addEventListener("change", (e) => {
            lang = e.target.value;
            localStorage.setItem(LANG_KEY, lang);
            applyI18n();
            renderFeed();
        });

        document.getElementById("feed").addEventListener("click", (e) => {
            const btn = e.target.closest("[data-action]");
            if (!btn) return;
            const action = btn.getAttribute("data-action");
            const id = Number(btn.getAttribute("data-id"));
            const postId = btn.getAttribute("data-post-id");

            if (action === "toggle-reply") {
                if (expandedPosts.has(id)) {
                    expandedPosts.delete(id);
                } else {
                    expandedPosts.add(id);
                }
                renderFeed();
            } else if (action === "send-comment") {
                sendComment(id);
            } else if (action === "delete-post") {
                deletePost(id);
            } else if (action === "delete-comment") {
                deleteComment(id);
            } else if (action === "edit-post") {
                startEdit("post", id, id);
            } else if (action === "edit-comment") {
                startEdit("comment", id, postId);
            }
        });
    }

    applyI18n();
    bindEvents();
    loadFeed();
})();
