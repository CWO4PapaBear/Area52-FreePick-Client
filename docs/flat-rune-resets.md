# Area 52 flat rune resets

`client/FrameXML/Area52RuneResets.lua` is appended after the existing CharacterAdvancementUtil.lua definitions in the managed patch-B archive. It is shared FrameXML code, not an optional addon. Enable only with the paired server boolean `CONFIG_AREA52_FLAT_RUNE_RESETS` and the existing Hero purge boolean. Non-Hero and Wildcard clients retain native behavior.

A single selected-entry removal costs 250 Runes of Ascension (375250); each Reset All category costs 250 total. The client retains native eligibility restrictions while replacing the full-reset currency check, excludes bank holdings, always confirms, and rechecks affordability on acceptance. Server validation remains authoritative. Full resets retain the active build and its revision while disabling automatic learning; the saved library build remains. Books and trainers can still teach from the retained plan. Cancel does not send the reset request.

The confirmation includes the future Draft reward warning above level 10. Draft eligibility/reward enforcement is a separate, deferred system; the text is not proof that Draft support is implemented.

Verification: Lua 5.1 harness passed for 249/250 rune boundaries, combat/death/empty categories, confirmation and acceptance, mode gates, mastery notices and Draft warning threshold. The paired server passed four isolated exploratory native pricing tests; combined gameplay verification was unavailable because only external exploratory scenarios ran. All staged archive members were read back and verified. Real-client acceptance remains pending.

Run `tests/reset_ui_checks.py` through the CoA `tools/verify_all.py` harness entrypoint, setting AREA52_LUPA_PATH to an existing Lupa installation and AREA52_RESET_LUA to the Lua source. No client archive, installation or launcher channel promotion is included in this source commit.

The reset popup uses a red Cost label, a rune icon with a hover tooltip, a yellow Active Build label and separated saved-build text. Lua 5.1 checks exercise tooltip enter/leave as well as confirmation behavior. Visual placement still requires client acceptance.


The redundant �It will remain selected.� sentence is omitted from the confirmation; the server still retains the Active Build and disables only automatic learning.

Tester promotion (2026-10-07): channels/area52.json now selects manifest-resets-prestige-20261007.json. The patch-B component was reconstructed through the launcher installer and both new remote assets were downloaded and hash-verified. All other 503 baseline records remain unchanged. Paired Area 52 server binary: bb06454972575a468bd52ded00e5750406a077bfea1314b691b2b69497da6f8c. Existing launcher 0.3.7 or newer supports this feed; no executable change is required.
