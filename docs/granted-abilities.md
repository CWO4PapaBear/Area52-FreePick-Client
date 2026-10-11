# Granted abilities in Character Advancement

The Area 52 sidebar includes source-granted abilities in its existing search and learned/unlearned
filters. It displays the highest known rank, identifies the granting Mystic Enchant, ability or talent
in the SHIFT tooltip, and leaves source-managed rows read-only. Right-clicking the icon or name offers
certification only for a currently learned, VERIFIED family. Certification belongs to the granted
ability, independently of its source. Original tooltip content remains intact, with blank lines before
source notes and status. Native Advancement entries are reused rather than duplicated.

`tools/build_granted_abilities.py` generates the catalog and matching server ledger from the effective
spell audit, current status evidence and existing certification ledger. It follows explicit learn,
replacement-grant and reviewed scripted-grant links, never ordinary damage triggers. The current
catalog contains 48 families; 15 additional families have all recovered ranks covered by existing
VERIFIED audit evidence. Other families remain NOT VERIFIED. Missing grant links are not inferred.
Future audit changes require regenerating both catalog and server ledger; parent certification does
not certify a child ability.

Generate with `python tools/build_granted_abilities.py --effective EFFECTIVE.json --status STATUS.json
--ledger CURRENT_LEDGER.json --output STAGE`. Copy the resulting GrantedAbilityCatalog.lua into the
addon alongside GrantedAbilities.lua and TesterCertification.lua, preserving their TOC order.

`tools/stage_granted_abilities.py --archive PATH/patch-B.MPQ --output STAGE/patch-B.MPQ --mpq-tools TOOLS`
patches the two Advancement interfaces and shared spell-list row. TOOLS must contain the existing
`lib.mpq` reader/writer. The tool preserves and verifies every archive member and refuses in-place
output. Proprietary client archives are not distributed in this repository.

Pair this client with the Area 52 granted-ability certification server extension and regenerated
ledger. Deploy both together; publishing this source does not install the package or promote the
launcher channel. Keep the live client's current archive as the staging baseline.

Verification: six Lua 5.1/generator tests, existing certification protocol/UI regression, changed Lua
syntax, idempotent archive patching and readback of all 1,301 archive members passed. Area 52 server
build and two focused certification harnesses passed. In-game visual acceptance is pending.

This milestone is staged, not activated or released to testers.
