# Client release promotion

Before every Area 52 channel promotion, run the following against the installed Bear Cave launcher source:

`python tools/verify_channel_promotion.py --launcher ../Bear-Cave-Launcher`

This uses the candidate local channel pointer but downloads the real remote manifest through the actual launcher validator. A nonzero exit blocks promotion: do not commit/push the channel pointer until corrected. Asset hash or fullclient.validate checks alone are insufficient.

The channel must target the release asset named `manifest.json`. Dated manifest names are backup/evidence assets only. Preserve the previous canonical manifest and assets before replacement. Keep the manifest digest synchronized with the downloaded canonical asset. Never loosen launcher URL or channel checks to accommodate an incorrectly published feed.

Run `python -m unittest discover -s tests -p test_channel_contract.py` before committing a channel change. After pushing, run the promotion verifier again with `--live`; report live-feed verification separately from local fixture validation. If a CDN still serves the previous pointer, report that rather than declaring the new feed verified.

Do not change launcher binaries when only client assets/feed changed. Preserve proprietary assets outside Git history, and keep personal files excluded.
