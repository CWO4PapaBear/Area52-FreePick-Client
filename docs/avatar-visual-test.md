# Avatar impact visual test

`tools/stage_avatar_visual.py` stages a complete Area 52 overlay from the installed
baseline without installing it. It retains existing archive members, clones visual
20218 into an unused ID and assigns that clone only to Avatar 86380. Kit 20386
moves from casting to caster impact; all other visual fields and Avatar combat
fields remain unchanged. The model already exists in patch-N.MPQ and its original
attachment references exist in patch-S.MPQ.

The staging command verifies the DBC structure, original kit attachments, unchanged
records, archive contents and before/after hashes. It does not verify rendering.
The accompanying server growth candidate is maintained separately in the CoA
fork's fix/area52-avatar-growth branch. Install with the game closed, preserve a
backup, and confirm the source hash still matches the staging manifest. Do not
promote this experiment to the tester channel until accepted in game.
