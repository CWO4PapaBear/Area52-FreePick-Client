# Featured Build editor client source

The patch records the approved changes to three existing client Lua members. Apply it to the licensed baseline sources named in source-receipt.json, after normalizing text line endings to LF. The exact source member and delivered archive hashes are recorded. The full archive remains in launcher release assets, outside Git.

This contains the Build Architect filter/sort repair, fixed movable Preview Scene, larger rotatable animation models, vanity preload, stance/cast replay, in-window set buttons, saved weapon visibility and compact Character Creation summary selection. It retains rewards independently of preview weapon visibility. The portable worker and native validation are in server PR #121.

No DLL, personal settings, launcher executable or unfinished aura reward changes are included. Offline patch application reproduced all three candidate sources; the cumulative editor tests, catalog preservation and real-launcher live feed checks passed. New visual/gameplay certification remains tester-owned.
