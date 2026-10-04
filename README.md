# Area 52 - Free Pick Alpha Dev client updates

Public update feed for Area 52-specific patches. Obtain the base client from the [COACore Discord](https://discord.gg/RAkxswQ7Gx). Request a game account through [Bear Cave Discord](https://discord.gg/ZkzWqsCqkt).

This repository does not distribute the full client, personal settings or caches. The Bear Cave Launcher has a separate Area 52 client folder, update feed and connection configuration. Patch downloads require no invitation keys. Game accounts are managed by the server owner.

`channels/area52.json` remains disabled until a reviewed patch is published. Realm addresses are deployment configuration; no external Area 52 address has been activated. The initial launcher test uses a local-only address in an unpublished build.

Future releases must pin hashes and matching server revisions, preserve effective Area 52 overlays, and be tested before promotion. The inventory tool is read-only preparation and does not approve any file for redistribution. No proprietary client archives belong in Git history.

The `access/` directory preserves an inactive invitation-service prototype from the earlier private-distribution design. It is not used by this public feed or by the launcher's Discord account flow. No service, credentials or provisioning worker is deployed. Tests: `python -m unittest discover -s tests`.
