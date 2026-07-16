# KohakuSSHManager

A small internal web application for managing local Unix accounts and SSH public-key
access on independent Ubuntu/Mint machines (10-20 machines, 15-30 users).

```text
panel user <-> local machine account <-> SSH public keys
```

It is deliberately **small and robust**: one FastAPI process, one SQLite database,
Paramiko over a bounded thread pool. No brokers, no workers, no orchestration.

## What it does

- Register machines over SSH with explicit host-key fingerprint confirmation.
- Inspect real machine state: accounts, authorized keys, groups, hardware facts, mounts.
- Panel users manage their own SSH public keys and request machine access.
- Configurable approval: admin review by default, leader auto-approval within group scope.
- Approval creates/links the local account and installs the user's active keys.
- Revocation removes keys only — accounts, homes, and data are never deleted.
- One-time initialization of existing machines: archives (never deletes) current
  `authorized_keys` files and records discovered keys as no-owner until adopted.
- NFS/mount usage scans: total, by current owner UID, and by configured directory.
- Every remote operation is recorded as a `RemoteAction`; security events land in the audit log.
- Optional webhook notifications and periodic connectivity checks.

## Quickstart

Requirements: Python 3.10+ (Node is only needed to rebuild the frontend).

```bash
# install (uses the prebuilt panel bundled in src/kohakusshmanager/web_dist)
pip install -e .

# run — zero config needed for a first boot
kohakusshmanager
# or: python -m kohakusshmanager
```

Open http://127.0.0.1:8000. On first startup the app auto-generates:

- `./data/secret.key` — deployment secret (encrypts the SSH management private key), and
- `./data/admin_token.txt` — the admin token.

Log in with username `__token__` and the token from `data/admin_token.txt`.
Both values can instead be provided via `KSM_SECRET` / `KSM_ADMIN_TOKEN`
(or `*_FILE` variants) — see `.env.example` for every setting.
To reach the panel from other devices set `KSM_HOST=0.0.0.0`.

## Enrolling a machine

1. **Machines → Register** — name, address, port, management username. The management
   account must exist on the target with passwordless sudo.
2. Copy the shared management public key shown in the panel into that account's
   `~/.ssh/authorized_keys` on the machine.
3. **Enroll** — the app probes the machine and shows its host-key fingerprint.
   Verify it out-of-band and confirm. The app then checks SSH + sudo and reads
   machine facts. A changed host key is rejected from then on.

## Typical flow

1. A member adds their public key(s) on the dashboard.
2. They request access to a machine (target username defaults to their panel name).
3. An admin approves (or a leader inside their group scope auto-approves).
4. The app creates or adopts the local account and installs the member's active keys.
5. Revoking access later removes those keys and nothing else.

For machines with pre-existing users, run **Initialization** from the machine detail
page first: it renames each selected account's `authorized_keys` to a unique backup,
records the old keys as no-owner, and starts a fresh file. The management account is
never processed, backups are never overwritten, and no account or data is removed.

## Development

```bash
# backend
uv pip install -e ".[dev]"
pytest tests/ -q
black src tests && ruff check src tests

# frontend (Vue 3 + Vite + UnoCSS)
cd frontend
npm install
npm run dev        # dev server on :5173, proxies /api to :8000
npm run build      # outputs to src/kohakusshmanager/web_dist
npm run lint && npm run format:check
```

Design notes and the implementation plan live in `plans/`.

## Operational notes

- Back up the SQLite database (`data/ksm.db`) **and** `data/secret.key` together —
  without the secret the stored management private key cannot be decrypted.
- The management account has passwordless sudo, so the host running KohakuSSHManager
  and its database need root-equivalent protection.
- If the app is ever down, machines remain reachable with existing keys; archived
  key files (`authorized_keys.ksm-backup-<timestamp>`) can be restored manually
  by moving them back into place.
- Actions left `pending`/`running` across a restart are marked `interrupted` and can
  be retried from the UI.
