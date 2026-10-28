---
name: codex-standalone-symlink
description: "codex won't launch: (1) `no such file` = standalone `current` symlink written with HOME=/home/user; (2) `app server did not become ready` = dangling daemon socket, kill stale app-server"
metadata:
  type: reference
---

`~/.local/bin/codex` → `~/.codex/packages/standalone/current/bin/codex`. On 2026-09-25 13:49 the Codex CLI
auto-updater (0.157.0) rewrote `current` as `/home/user/.codex/packages/standalone/releases/<ver>` (wrong
home), so `codex` failed with "no such file or directory" although the release was installed under
`/home/andrey/...`. Fix (10 s):

```
ln -sfn ~/.codex/packages/standalone/releases/$(cat ~/.codex/packages/standalone/auto-update-version) ~/.codex/packages/standalone/current
codex --version
```

Check `readlink ~/.codex/packages/standalone/current` first if `codex` vanishes again after an update.

**Second failure mode (2026-09-29):** `codex` TUI exits with `app server did not become ready on
~/.codex/app-server-control/app-server-control.sock … File exists (os error 17)`. `codex exec` and
`--version` still work. Cause: the socket file under `/tmp/codex-daemon-1000/<hash>` had been deleted
while the old `codex app-server --managed-daemon` still listened on the unlinked inode, so the symlink
in `app-server-control/` dangled. Fix: `ss -xlp | grep codex` to find the stale daemon, kill it (and
its `codex-code-mode-host`), `rm ~/.codex/app-server-control/app-server-control.sock`, relaunch.
Killing it also kills any live TUI attached to it, so ask first; `codex --no-daemon` is the workaround
that leaves it alone. The state DB also holds stale `/home/user/.codex/sessions/...` rollout paths
from the same wrong-HOME bug; these only log errors.

**Root cause of both (per user, 2026-09-29):** the qmx63_firmware_main devcontainer
(`../qmx63_firmware_main/.devcontainer/devcontainer.json`) bind-mounts the host `~/.codex` at both
`/home/user/.codex` and `/home/andrey/.codex`. Codex inside the container (HOME=/home/user) shares the
daemon control dir and the auto-updater with WSL codex, so it writes `/home/user/...` paths and clobbers
the host daemon socket. An uncommitted edit there adds `--tmpfs` over `/home/user/.codex/app-server-{control,daemon}`,
but the container created 2026-09-28 predates it and needs a rebuild. That edit also leaves the
`/home/andrey/.codex` alias mount and `packages/standalone/current` exposed.

**2026-09-30:** the container was rebuilt and the tmpfs isolation works: the host `app-server-control/` stays
empty and the daemons no longer clash. The updater still clashes. Container 0.159.2 rewrote `standalone/current`
→ `/home/user/...` and WSL `codex` failed with "command not found". Fixed with a relative link:
`cd ~/.codex/packages/standalone && ln -sfn releases/<ver> current` (it resolves in both host and container).
