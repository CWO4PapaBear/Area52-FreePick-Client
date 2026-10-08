import json
from pathlib import Path
import re
import unittest

class ChannelContractTest(unittest.TestCase):
    def test_area52_uses_launcher_supported_manifest_url(self):
        channel = json.loads((Path(__file__).resolve().parents[1] / "channels/area52.json").read_text())
        self.assertEqual(channel["channel"], "area52")
        self.assertRegex(channel["manifest_url"], r"^https://github\.com/CWO4PapaBear/Area52-FreePick-Client/releases/download/area52-[A-Za-z0-9._-]+/manifest\.json$")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", channel["manifest_sha256"]))

if __name__ == "__main__":
    unittest.main()
