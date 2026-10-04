# Area 52 - Free Pick Alpha Dev

Private client-distribution metadata and packaging tools. The Bear Cave Launcher remains in its own repository.

Distribution is not enabled yet. Do not embed GitHub tokens or account credentials in the launcher. Approved testers will require a download-access service or an owner-distributed clean package until that service exists.

The baseline is the owner-designated active Area 52 client, including its effective overlays. Inventory is preparation, not approval to distribute. Runtime executables, DLLs, archives and reviewed addons must be pinned together with the matching server revision and tested as a pair. Upstream CoA updates are reviewed, never consumed automatically.

Run `python tools/inventory.py CLIENT --output local/inventory.json` to classify files without copying or altering the client. Add `--hash` to calculate candidate SHA256 hashes. Personal settings, caches, logs, screenshots, crash reports, backups and launcher state are excluded. Loose interface files require individual review because they can contain local customizations. Unknown files also require review. No original WTF directory or saved variables may be included; deployment must generate clean realm settings.

Before release, resolve every review entry, stage into a new directory, verify hashes, inspect the effective realm/overlay configuration, test fresh installation and repair, and publish a versioned manifest. Client archives belong in controlled release storage, never Git history. No account email addresses, requests or authentication database exports belong here.

## Invitation access service

An invitation is approval: no email or additional approval is required. The launcher submits the invitation, requested username, password and a durable random request credential over HTTPS. The access service reserves the invitation for that credential and queues an SRP6 verifier. The worker creates a normal privilege-zero account in the configured dedicated Area 52 authentication database, then marks the invitation consumed and permits future download authorization. It does not grant GM access or change existing accounts.

Source modules:
- `access/api.py`: WSGI enrollment/status boundary, HTTPS requirement, bounded requests and basic per-process throttling. Downloads return unavailable until a storage provider is connected.
- `access/store.py`: SQLite invitation reservations, hashed keys/tokens, concurrent redemption protection and a recoverable provisioning queue.
- `access/worker.py`: private MySQL worker. Run one job per invocation; schedule locally after deployment verification. Its separate transaction receipt makes a crash after MySQL commit safe to retry.
- `access/receipt.sql`: additive table in the dedicated Area 52 auth database. Apply explicitly during deployment, not to Bear Cave PTR.
- `access/admin.py`: local invitation issuance/revocation. GitHub key generation is intentionally not wired yet.

Run tests with `python -m unittest discover -s tests`. The worker was additionally exercised against disposable MySQL tables for creation, replay and duplicate-name rollback. Real client login with a provisioned account remains unverified.

### Deployment prerequisites � not activated

Choose HTTPS hosting and private download storage. Run this WSGI application with a production server behind a trusted TLS proxy; set the WSGI scheme and client address only through trusted proxy configuration. Add edge rate limiting (the included limiter is per process), request size/time limits, and redact authorization headers and all enrollment bodies from logs. Never expose a development server or MySQL publicly.

Initialize the SQLite store in a private directory with owner-only access. Treat pending SRP verifiers and database backups as sensitive. The API process needs the access store, but no MySQL credentials. The private worker shares that store on the same host and uses a dedicated MySQL credential file. Restrict its database grants to SELECT/INSERT on `account`, SELECT/INSERT on `realmcharacters`, and SELECT/INSERT/UPDATE on `area52_enrollment_receipt`. It needs no `account_access`, DELETE, DDL, or Bear Cave database permissions. Review the configured realm ID and dedicated database before enabling `worker.example.json`.

Create the WSGI application using `access.api.create_app(PRIVATE_STORE_PATH)`. The service must not be enabled in distributed launchers until TLS, proxy limits, worker permissions, restart recovery and real login are tested. Configure the launcher using a private `access.json` containing `{"channel":"area52","url":"https://YOUR_HOST"}`; no server secret belongs in it. The Windows launcher saves the request credential under DPAPI protection before enrollment, allowing retries after a lost response. Linux/Wine enrollment is not enabled.

A local administrator can issue a key with `python -m access.admin --store PRIVATE_STORE issue --output PRIVATE_KEY_FILE --days 7`. The output file must not exist. The raw key is written only there, not printed. Secure that directory on Windows with an appropriate ACL; deploy the service on Linux with owner-only directory/file permissions. A reservation made before expiry remains valid for provisioning retries. Revoking an invitation also revokes its download authorization; it does not ban an existing game account. Already downloaded files cannot be recalled.

Password resets, credential recovery, download signing, admin web UI and GitHub-triggered issuance are not implemented. Do not put keys in Git, release assets or CI logs. No operational keys or accounts were generated for release.
