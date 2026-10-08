# Mystic Enchant commit feedback and fixed slots

Area52MysticRules preserves the server's 17 numbered slots instead of sorting
enchants by rarity. Empty slots remain empty. Initialization replaces previously
saved client display permutations with the authoritative slot order; existing
enchants may therefore appear in their actual saved positions on first use.
No server equipment or currency data is migrated.

After a locally initiated commit receives RE_COLLECTION_REFORGE_OK, the client
plays sound 54128 once and the existing shockwave texture expands from slot 1
(the Legendary-capable slot) to encompass all visible enchant slots. Failed,
unsolicited, duplicate and expired responses do not play success feedback.
The normal pending-placement effects remain unchanged. Other realms retain
their existing mapping behavior.

Verification: tools/test_mystic_feedback.py uses Lupa with a mocked client API
to exercise fixed mappings with holes/duplicates, stale saved mappings, rarity
capacity, result gating and shockwave dimensions. This does not verify rendering
or audio assets in the live client. In-game acceptance must check commit sound,
circle coverage, empty-slot preservation, removal, reload, logout and spec swaps.

Sources: installed Area 52 client Area52MysticRules.lua and patch-B.MPQ's
EnchantCollectionUtil.lua, SlotFrameSlotTab.lua, SlotFrameSlotMixin.lua and
SoundKit.lua. Server handler reviewed against the local Area 52 reconstruction;
upstream comparison pinned at afd8e940b654538f682185e9d82eaffde5bdfbf2.
The server already persists exact slot positions and returns the explicit result.

Deployment: install the Lua file into Interface/AddOns/Area52MysticRules with
the client closed, preserving a backup. No server restart is required. Publishing
this source does not promote a launcher manifest or client release asset.

## October 8 packaging repair

The public alpha.4 manifest and installed client still used the original 1,888-byte
rarity-sorting addon (SHA256 44701c4cbfafde247fc2bb642d520e8da9a9493aaac3ef06cbaf5687560c189a).
The fixed-slot source had not reached that package. The corrected component now
matches the reviewed source (SHA256 0860d0892c47a419320f2bb32e2d207f17073f5e9ed63de5713c72e4170432e4).
No server slot migration is needed: the existing server stores exact numbered slots.

The regression covers every accepted rarity/slot combination across repeated map,
preview and initialization calls with empty neighboring slots. The promotion verifier
now requires both the manifest baseline and component hash for this addon to match
the checked-in source. This prevents Check/Repair from reinstalling an old sorter.
Live rendering and reconnect acceptance remain player checks.

The owner confirmed on October 8 that the slot-placement repair worked in game.
This confirms the reported relocation fix; no separate reconnect or spec-swap
result was supplied. The public tester feed was rechecked through the actual
launcher validator after this confirmation and accepted the corrected manifest.
