# Free reset client support

Individual ability/talent removals and Reset All show no currency cost when the Area 52 server advertises CONFIG_AREA52_FREE_RESETS. Existing mastery and Active Build warnings remain. Combat, battleground, arena and death restrictions are rechecked before sending a removal request. Servers without the new flag retain the previous paid behavior.

Lua 5.1 reset harness passed, including zero-rune removal, confirmation/acceptance checks, mode isolation and old-server compatibility. Matching patch-B archive is staged locally with all members read back. This source commit does not publish release assets or change the launcher channel.
