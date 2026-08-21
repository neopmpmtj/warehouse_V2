(function () {
    const API = "/api/manage/approval-limits/";
    const canEdit = document.body.dataset.canEdit === "true";
    const banner = document.getElementById("banner");
    const body = document.getElementById("limits-body");

    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    }

    function showBanner(message, isError) {
        banner.hidden = false;
        banner.textContent = message;
        banner.className = isError ? "banner banner-error" : "banner";
    }

    async function api(url, options) {
        const response = await fetch(url, {
            ...options,
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
                ...(options && options.headers),
            },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || "The request could not be completed.");
        }
        return data;
    }

    function render(limits) {
        body.replaceChildren();
        limits.forEach((limit) => {
            const row = document.createElement("tr");
            const group = document.createElement("td");
            group.textContent = limit.group_name;
            const grade = document.createElement("td");
            grade.textContent = String(limit.grade);
            const approval = document.createElement("td");
            const self = document.createElement("td");
            const actions = document.createElement("td");
            const approvalInput = document.createElement("input");
            approvalInput.type = "text";
            approvalInput.value = limit.approval_limit;
            approvalInput.disabled = !canEdit;
            const selfInput = document.createElement("input");
            selfInput.type = "text";
            selfInput.value = limit.self_approval_limit;
            selfInput.disabled = !canEdit;
            approval.appendChild(approvalInput);
            self.appendChild(selfInput);
            if (canEdit) {
                const save = document.createElement("button");
                save.type = "button";
                save.className = "btn btn-primary";
                save.textContent = "Save";
                save.addEventListener("click", async () => {
                    try {
                        await api(`${API}${limit.id}/`, {
                            method: "PATCH",
                            body: JSON.stringify({
                                approval_limit: approvalInput.value,
                                self_approval_limit: selfInput.value,
                            }),
                        });
                        showBanner("Limit saved.");
                    } catch (error) {
                        showBanner(error.message, true);
                    }
                });
                actions.appendChild(save);
            }
            row.appendChild(group);
            row.appendChild(grade);
            row.appendChild(approval);
            row.appendChild(self);
            row.appendChild(actions);
            body.appendChild(row);
        });
    }

    api(API, { method: "GET" })
        .then((data) => render(data.limits || []))
        .catch((error) => showBanner(error.message, true));
})();
