# Area 52 repair packages

Run from Windows PowerShell. WSL `dml-arch`, Docker, the existing Area 52 containers,
and the private Remote GM credentials must already be configured. The wrapper invokes
WSL as root; it does not put credentials in the package or command line.

```powershell
powershell -ExecutionPolicy Bypass -File "PATH\tools\deployment\Activate-Area52.ps1" -Package "PATH\package.json" -CheckOnly
powershell -ExecutionPolicy Bypass -File "PATH\tools\deployment\Activate-Area52.ps1" -Package "PATH\package.json"
```

Keep the window open until COMPLETE. Check-only validates artifact hashes, installed
baselines, client closure when required, and GM connectivity. It does not run package
hooks, announce, stop, install, or publish. Hook preflight and Docker configuration
validation also run before the real countdown. A restart-only script does not install
packages.

## Normal activation

The runner locks deployment, copies verified assets into a private transaction directory,
saves configuration and file backups, announces a three-minute graceful shutdown,
applies changes, starts worldserver, checks readiness and its binary hash, and executes
the package's verification and publication steps. Authserver and the database remain
running. Installed file/configuration drift stops activation. The same completed
package will not restart the server twice.

Transactions and backups live in WSL under
`/home/dml/games/ascension-freepick-test/private/deployments/PACKAGE-ID`.
Never publish that directory: configuration and database backups may contain private data.

Failed server activation attempts restore files, configuration and completed/partially
applied hooks, then restart the previous server. A rollback failure stops for operator
review. A publication failure leaves the checked server online and records
`publish_failed`; it does not attempt to undo a potentially partially distributed client
release. Do not delete state files or blindly retry incomplete transactions. Review and
repair the specific failed step, then reconcile state. Loss of the terminal, PC power,
or WSL can interrupt activation; the next invocation detects the incomplete transaction
and requires review rather than guessing how far it got.

## Package format (schema 1)

Each package is a directory with `package.json` and all its artifacts. Distribute locally
as a complete directory. Game binaries and client archives stay outside Git. Only run
trusted, reviewed packages: hashes establish integrity, not authorship. Hooks execute code
with administrator access.

Required fields:

- `schema`: `1`.
- `id`: unique lowercase letters/digits/hyphens, 3–80 characters.
- `announcement`: repair description added after the three-minute restart notice.
- `requires_client_closed`: true for every package modifying the local client.
- `extensions_dll`: `"excluded"`. DLL updates are held and rejected by this version.
- `expected_binary_sha256`: hash of the currently running `/proc/1/exe` in worldserver.
- `expected_compose_sha256`: hash of the currently installed private `compose.realm.json`.
- `artifacts`: list of `{ "path": "relative/file", "sha256": "..." }`.
- `binary`: optional relative artifact path for a replacement worldserver.
- `replacements`: list of `{ "artifact": "relative/file", "target": "/absolute/private/path", "before_sha256": "..." }`.
  Use null baseline for a file that must not already exist. Parent directory must exist.
  Direct replacements are limited to the server private tree, excluding deployment history
  and compose itself. Use hooks for database/client operations.
- `hooks`: ordered list of objects with `name`, `preflight`, `backup`, `apply`, `verify`, `rollback`.
- `publish`: ordered list of post-readiness release steps, empty when no release is required.

Each hook phase or publish step is
`{ "script": "hooks/change.py", "args": ["apply"], "timeout": 300 }`.
The script must be a listed SHA-256 artifact. Steps run in WSL Python with the private
payload directory as working directory. Environment variables `AREA52_PACKAGE_DIR`
and `AREA52_TRANSACTION_DIR` identify the immutable copied payload and backup directory.
Timeout must be 1–1800 seconds. Avoid secrets in arguments, stdout, or errors.

## Requirements for future package authors

Prepare every future deployment using this format. Rebase baselines on the currently
installed server/configuration, include all required assets, and perform repair-specific
builds and tests before packaging. Supply tested hook implementations when needed; the
runner does not infer migrations or publication commands from staging directories.

- Preflight must validate all dependencies, permissions, credentials, effective data,
  and required platform tools without changing game/server/release state.
- Backup must finish successfully before apply. Database backups must cover every
  touched object and preserve character/account data. Keep them private.
- Apply runs only after worldserver stops. Make operations idempotent where possible.
- Rollback must tolerate partial apply, restore the exact previous state, and fail loudly
  if unable to do so. A failed backup must not have modified live state.
- Verify checks the effective repair after startup. Returning zero means success.
- Local client hooks must recheck Ascension is closed immediately before writing, verify
  installed hashes, back up files, and restore on failure.
- Publication hooks must preserve previous manifests and immutable assets, validate with
  the real launcher before pushing a channel pointer, and verify the live feed afterward.
  Keep source pushes, asset uploads and channel promotion explicit. Include all Python
  dependencies or validate them before countdown. Release steps must be safely retryable
  by an operator after review; the runner deliberately does not auto-retry them.
- Discord posting is not automatic. Include it only in an explicitly authorized package,
  with duplicate-post protection and the test-team role mention.
- Keep normal packages small and independent. Do not include unrelated staging work.

The current Durotar area-lookup package has only a binary and matching source replacement;
it needs no client closure, database migration, release publication, or DLL change.

## Validation scope

`python3 -m unittest discover -s tests -p test_deployment.py` tests package rejection,
successful activation, startup rollback, and publication-failure isolation with mocked
services. Live check-only validates the current package without restarting. A full
real deployment is not claimed until the owner runs it and readiness checks complete.
