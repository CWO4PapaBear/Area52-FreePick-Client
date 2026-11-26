import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

path = Path(__file__).resolve().parents[1] / 'tools/deployment/combined_activation.py'
spec = importlib.util.spec_from_file_location('combined', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class CombinedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        entries = []
        artifacts = []
        for realm in ('development', 'cloud'):
            p = self.root / (realm + '.json')
            p.write_text(json.dumps({'target': realm, 'publish': []}))
            entries.append({'target': realm, 'manifest': p.name})
            artifacts.append({'path': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        self.manifest = self.root / 'package.json'
        self.manifest.write_text(json.dumps({'target': 'combined', 'publish': [], 'extensions_dll': 'excluded', 'children': entries, 'artifacts': artifacts, 'runner_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
    def tearDown(self):
        self.tmp.cleanup()
    def test_check_only(self):
        calls = []
        module.execute(self.manifest, True, lambda p,c: calls.append((p.stem,c)))
        self.assertEqual(calls, [('development',True),('cloud',True)])
    def test_all_preflight_before_execution(self):
        calls = []
        module.execute(self.manifest, False, lambda p,c: calls.append((p.stem,c)))
        self.assertEqual(calls, [('development',True),('cloud',True),('development',False),('cloud',False)])
    def test_failed_preflight_prevents_all_execution(self):
        calls = []
        def invoke(p,c):
            calls.append((p.stem,c))
            if p.stem == 'cloud': raise RuntimeError('preflight')
        with self.assertRaises(RuntimeError): module.execute(self.manifest,False,invoke)
        self.assertTrue(all(c for _,c in calls))
    def test_failed_first_activation_stops_second(self):
        calls = []
        def invoke(p,c):
            calls.append((p.stem,c))
            if not c: raise RuntimeError('activation')
        with self.assertRaises(RuntimeError): module.execute(self.manifest,False,invoke)
        self.assertEqual(calls[-1],('development',False))
        self.assertEqual(len(calls),3)
    def test_tamper_rejected_before_calls(self):
        (self.root/'cloud.json').write_text('{}')
        with self.assertRaises(ValueError): module.execute(self.manifest,False,lambda *a:self.fail('executed'))
    def test_stale_runner_rejected(self):
        p=json.loads(self.manifest.read_text());p['runner_sha256']='0'*64;self.manifest.write_text(json.dumps(p))
        with self.assertRaises(ValueError): module.children(self.manifest)

if __name__ == '__main__': unittest.main()
