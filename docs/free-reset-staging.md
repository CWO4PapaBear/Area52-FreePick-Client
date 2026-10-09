# Free reset client support

Individual ability/talent removals and Reset All show no currency cost when the Area 52 server advertises CONFIG_AREA52_FREE_RESETS. Existing mastery and Active Build warnings remain. Combat, battleground, arena and death restrictions are rechecked before sending a removal request. Servers without the new flag retain the previous paid behavior.

Lua 5.1 reset harness passed, including zero-rune removal, confirmation/acceptance checks, mode isolation and old-server compatibility. Matching patch-B archive is staged locally with all members read back. This source commit does not publish release assets or change the launcher channel.

Activation, 2026-10-09: the server package is live after the announced three-minute shutdown. Client release assets were uploaded and channel commit d372154 published; matching local patch-B and patch-D are installed with backups. Server binary SHA-256: a564c186b63fafc4a32a3b590ea4099a77fe0ced45b7a2d4001749e5caa86bfd. Launcher release validation passed before promotion. Discord delivery is gated on the public channel feed matching both client archive hashes.
