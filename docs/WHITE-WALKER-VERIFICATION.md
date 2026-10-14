# White Walker verification staging

The local revision-three White Walker audit prepares nine new yellow VERIFIED entries:
Honed Ice, Balance of Power, Precision, Piercing Ice, Seal Mastery, Advanced Finishing
Move Mastery, Slice and Dice, Focused Attacks and Rend. Applicable rank tooltips are
updated together. Existing tester CERTIFIED records remain unchanged.

Athletic Icing's Physical/Frost cost repair passes native tests, but its advertised
similar-enchant stacking exclusion remains unresolved, so it stays NOT VERIFIED.
Frozen Power's previous enchant verification is withdrawn pending evidence for its
target-conditioned damage. The legendary and its replacement/granted spells still
have blockers; this is not a claim that the entire build works.

The candidate compiles and passes four focused harnesses. Its real-clock native test
passes eighteen assertions for cost schools, removal, proc exclusions, copy scaling,
repeated casts, source removal and expiry. The tooltip stager preserves unrelated DBC
rows, SHIFT descriptions and CERTIFIED labels, and reads every archive member back.

`tools/stage_build_verification.py` consumes reviewed decisions with state
`verified_for_staging`, explicit promotion/demotion spell IDs and scoped metadata
overrides. Supply the installed archive, a new output path and the existing MPQ tools
directory. It refuses in-place writes and ambiguous status labels.

The prepared package pairs server, status and local client changes, with targeted
database/file backups and rollback. Activation, rendered-client acceptance and launcher
channel promotion remain separate. No new tester certification is claimed.
