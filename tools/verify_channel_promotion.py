import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--launcher", required=True, type=Path)
parser.add_argument("--channel", type=Path, default=Path(__file__).resolve().parents[1] / "channels/area52.json")
parser.add_argument("--live", action="store_true")
args = parser.parse_args()
sys.path[:0] = [str(args.launcher.resolve()), str((args.launcher / "tools").resolve())]
from launcher import updater

fetch = updater.fetch
if args.live:
    expected = json.loads(args.channel.read_bytes())
    def live_fetch(url):
        data = fetch(url)
        if url.endswith("/channels/area52.json"):
            actual = json.loads(data)
            if any(actual.get(key) != expected.get(key) for key in ("manifest_url", "manifest_sha256", "channel")):
                raise ValueError("Public feed has not converged to the expected channel pointer")
        return data
    updater.fetch = live_fetch
if not args.live:
    pointer = args.channel.read_bytes()
    def candidate_fetch(url):
        if url.endswith("/channels/area52.json"):
            return pointer
        return fetch(url)
    updater.fetch = candidate_fetch
manifest = updater.latest("area52")
print("PASS: actual launcher accepted the channel URL, downloaded manifest, checksum, release identity and baseline schema.")
print(manifest["tag"])
