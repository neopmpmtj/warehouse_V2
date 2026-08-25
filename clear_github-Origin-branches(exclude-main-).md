### Yes — run this in your terminal (I tried from here but GitHub auth isn't available in this environment):

git branch -r \
  | grep 'origin/' \
  | grep -v 'origin/HEAD' \
  | grep -v 'origin/main$' \
  | sed 's|^[[:space:]]*origin/||' \
  | xargs -r -I{} git push origin --delete {}


### Afterward, verify:

git fetch origin --prune
git branch -r


`git branch -r` lists **remote-tracking branches** — local refs that mirror what Git last saw on the remote (usually `origin`).

**`-r`** means **remote** (as opposed to local branches).

Example output:

```text
  origin/main
  origin/cursor/company-voice-341e
  origin/Agent/branch-navigation-issues
```

Each line is a ref like `origin/<branch-name>`. It is **not** the live GitHub list by itself; it reflects your last `git fetch` / `git pull`. Run `git fetch origin --prune` first if you want an up-to-date view.

Related flags:

| Command | Shows |
|---------|--------|
| `git branch` | Local branches only |
| `git branch -r` | Remote-tracking branches |
| `git branch -a` | Both local and remote-tracking |

So in your delete pipeline, `git branch -r` is the input list of remote branch names (with the `origin/` prefix), then `grep`/`sed` strip out `main` and format them for `git push origin --delete`.




# To create a branch **on GitHub (`origin`)** from your terminal:

### 1. Create and switch to a new local branch
```bash
git checkout -b my-branch-name
```

### 2. Push it to `origin` and set upstream
```bash
git push -u origin my-branch-name
```

That creates `my-branch-name` on GitHub and links your local branch to it.

---

### If the branch already exists locally
```bash
git push -u origin my-branch-name
```

---

### One-liner (from current commit, new branch)
```bash
git checkout -b my-branch-name && git push -u origin my-branch-name
```

---

### Notes
- Replace `my-branch-name` with your branch (e.g. `cursor/phase-6-offline`).
- You need commits on the branch before pushing (or push an empty branch with `git push -u origin my-branch-name` after creating it — GitHub will accept an empty branch if you have at least one commit on it; typically you commit first).
- `-u` (`--set-upstream`) means later you can use `git push` / `git pull` without specifying the remote branch.

**Typical full flow:**
```bash
git checkout main
git pull origin main
git checkout -b my-branch-name
# make changes, then:
git add .
git commit -m "Your message"
git push -u origin my-branch-name
```

