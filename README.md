# Area 52 - Free Pick Alpha Dev client updates

Public update feed for Area 52-specific patches. Obtain the base client from the [COACore Discord](https://discord.gg/RAkxswQ7Gx). Request a game account through [Bear Cave Discord](https://discord.gg/ZkzWqsCqkt).

This repository hosts versioned client repair assets in GitHub Releases, never in Git history. Personal settings, account data, caches and optional addons are excluded. The Bear Cave Launcher has a separate Area 52 client folder, update feed and connection configuration. Downloads require no invitation keys. Game accounts are managed by the server owner.

`channels/area52.json` publishes the complete tested 503-file Area 52 client baseline. Full repair requires launcher 0.3.7 and covers every baseline file, including runtime and shared assets as well as Area 52 overlays. Only mismatched files are downloaded; originals are backed up and extra MPQs are quarantined. Realm addresses remain deployment configuration; external Area 52 access uses auth port 3725 and world port 8086.

Future releases must pin hashes and matching server revisions, preserve effective Area 52 overlays, and be tested before promotion. The inventory tool is read-only preparation and does not approve any file for redistribution. No proprietary client archives belong in Git history.

## Full repair coverage

The published alpha.4 release extends the 86-file baseline to required content data, cinematics, UI assets and Area 52 addons. `tools/prepare_full_client.py` packages the owner-tested client as independently hashed 256 MiB chunks, checks existing baseline hashes and detects source changes during packaging. Launcher 0.3.7 requires complete coverage of every baseline entry. It verifies assembled files before installation and reuses valid chunks after an interruption. Large files and the total baseline are no longer restricted by the legacy ZIP limits. Extra MPQs are quarantined with verified backups rather than left to override tested assets.

Only approved local client/server pairs are promoted. This package is not a claim to be the latest upstream Discord release. Upstream release identity and the current Discord attachment remain separate tracking gaps; no upstream feed is consumed automatically. Client repair publication requires staged-chunk verification, installation/rollback checks and remote asset verification before updating `channels/area52.json`.

The `access/` directory preserves an inactive invitation-service prototype from the earlier private-distribution design. It is not used by this public feed or by the launcher's Discord account flow. No service, credentials or provisioning worker is deployed. Tests: `python -m unittest discover -s tests`.

## Alpha.4 verification

All 503 files (46,511,924,062 bytes) passed an isolated installation and full baseline comparison. Personal settings and extra-archive backup preservation passed. All 642 remote release assets passed digest verification, with downloaded samples verified independently. Launcher tests: 85 run, one skipped; client repository tests: 8 passed. Launcher 0.3.7 and client alpha.4 are separate published releases.

## Outland altar marker revision

The alpha.4 manifest refresh adds three Area 52 Ancient Enchanting Altar map/minimap markers: Netherstorm (Top of the Violet Tower), Terokkar Forest (Balcony above Mana-Tombs), and Nagrand (Deep within Oshu'Gun). The existing native icon 188 and scale 1.5 match Azeroth. Source is under `client/Interface/AddOns/Area52MysticRules`; the existing addon loads the marker file. Repeated world-entry registration replaces markers by ID. Other realms do not register them.

The release retains the previous manifest as `manifest-before-altars.json`; unchanged chunks remain available. Full repair still covers all baseline files. This client-only marker change uses the existing saved server altar placements and needs no server restart. Lua 5.1 checks against the recovered map API passed for repeated registration, descriptions, icon, and realm gating. Visual gameplay verification remains pending. Upstream reviewed: `36a3d8b506f8dabaee3faac3cf117a9ee2d03f79`.

## Guardian heirloom shop update

The October 6 heirloom manifest refresh installs the paired ItemExtendedCost table for Area 52 server source 0b7e7e45a71ef961443a12ff0228f02034b68959. Browse Heirlooms opens Armor, Weapons and Accessories. Armor costs 500 Runes of Ascension; weapons, rings, necklaces and trinkets cost 1000; nine-piece armor caches cost 3600. Purchases require level 60. Added armor XP effects are server-side. The 504-file baseline remains fully covered; only the Area 52 overlay component changed. The new archive and manifest were downloaded and hash-verified before promotion. The previous manifest and assets remain available for rollback. Client visual acceptance remains pending.

