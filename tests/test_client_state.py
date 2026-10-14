import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('client_state_guard',Path(__file__).parents[1]/'tools/deployment/client_state.py')
GUARD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)

class ClientStateTests(unittest.TestCase):
    def probe(self,closed=True,nonce='current',checked=100000):
        self.enterContext(patch.dict(os.environ,{'AREA52_CLIENT_STATE_FILE':'state.json','AREA52_CLIENT_STATE_NONCE':'current'}))
        self.enterContext(patch.object(GUARD.time,'time',return_value=100))
        self.enterContext(patch.object(GUARD.Path,'read_text',return_value=json.dumps({'closed':closed,'nonce':nonce,'checked_at_ms':checked})))

    def test_fresh_closed_probe_passes_without_interop(self):
        self.probe()
        with patch.object(GUARD.subprocess,'run') as process:
            GUARD.ensure_closed()
        process.assert_not_called()

    def test_open_game_blocks(self):
        self.probe(closed=False)
        with self.assertRaisesRegex(RuntimeError,'Close Ascension'):GUARD.ensure_closed()

    def test_stale_or_wrong_activation_blocks(self):
        for nonce,checked in [('other',100000),('current',90000),('current',120000)]:
            with self.subTest(nonce=nonce,checked=checked):
                with patch.dict(os.environ,{'AREA52_CLIENT_STATE_FILE':'state.json','AREA52_CLIENT_STATE_NONCE':'current'}), \
                     patch.object(GUARD.time,'time',return_value=100), \
                     patch.object(GUARD.Path,'read_text',return_value=json.dumps({'closed':True,'nonce':nonce,'checked_at_ms':checked})):
                    with self.assertRaisesRegex(RuntimeError,'stale'):GUARD.ensure_closed()

    def test_missing_probe_never_falls_back(self):
        with patch.dict(os.environ,{'AREA52_CLIENT_STATE_FILE':'state.json','AREA52_CLIENT_STATE_NONCE':'current'}), \
             patch.object(GUARD.Path,'read_text',side_effect=FileNotFoundError), \
             patch.object(GUARD.subprocess,'run') as process:
            with self.assertRaisesRegex(RuntimeError,'unavailable'):GUARD.ensure_closed()
            process.assert_not_called()

    def test_disabled_interop_requires_windows_wrapper(self):
        with patch.dict(os.environ,{'AREA52_CLIENT_STATE_FILE':'','AREA52_CLIENT_STATE_NONCE':''}), \
             patch.object(GUARD.subprocess,'run',side_effect=OSError('Exec format error')):
            with self.assertRaisesRegex(RuntimeError,'from Windows'):GUARD.ensure_closed()

if __name__=='__main__':unittest.main()
