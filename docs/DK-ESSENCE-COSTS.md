# Area 52 Death Knight Ability Essence costs

The level-71+ active Death Knight advancement entries use half their previous Ability Essence prices: 46 entries change from 4 to 2, three from 6 to 3, and four from 2 to 1. The last group is Presence Mastery plus Blood, Frost, and Unholy Presence. The three 3-AE entries are Dancing Rune Weapon, Summon Gargoyle, and Anti-Magic Zone.

Rarity gems, talent essence, level requirements, spell/rank links, tooltip text, disabled entries, and other class catalogs are preserved. `tools/normalize_dk_essence.py` modifies only the AE field of the active Area 52 Death Knight rows. It accepts the recovered packed DBC schema (179 declared fields, 692-byte records) and is idempotent.

Apply to matching effective client/server CharacterAdvancement.dbc files. The client table belongs inside its Area 52 patch-D overlay; the server reads the same table at startup. Deploy them together with the usual client-close check and announced restart. Source publication does not activate these data files or promote the tester channel.

Verification: scoped unit checks cover costs, exclusions, unchanged bytes, schema rejection, and repeat application. The staged real dataset changes exactly 53 AE fields; the source server and client tables are identical, and every rebuilt archive member is checked against its expected bytes. No combat behavior is changed or claimed tested.
