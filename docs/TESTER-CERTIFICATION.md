# Tester certification

On Area 52, the Character Advancement right-click menu offers **Mark as CERTIFIED** for
entries the server currently lists as VERIFIED. The existing learn and unlearn actions stay available.
The confirmation asks the tester to confirm expected function, logout/login persistence, and removal
from action bars when unlearned. Cancelling does nothing; CERTIFY submits the confirmation.

The server saves the first certification, including the account, character, time, three confirmed
checks, and verification-ledger digest. It immediately broadcasts the new status to online testers.
The next login or UI reload loads a fresh snapshot. No periodic refresh is used.

The client changes only the existing yellow VERIFIED tag to green CERTIFIED. It preserves the
original tooltip text, SHIFT sections, and spacing. There is no change to learned spells, action bars,
currencies, or builds. The confirmation does not automatically prove the three gameplay conditions;
it records the tester's attestation.

This source requires the matching Area 52 certification server package and its enabled configuration.
It is staged source, not a published client release. Without the service, no certification option is
offered. Mystic Enchant slots are outside this first advancement-menu implementation.
