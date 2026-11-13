import unittest
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import Mock
from test_publication_release_recovery import release


class CapacityTests(unittest.TestCase):
    def test_rollover_reuses_matching_remote_even_for_staged_chunks(self):
        repo = 'org/client'
        prefix = 'https://github.com/org/client/releases/download/area52-v1/'
        def chunk(name, value):
            return dict(asset=name, bytes=len(value), sha256=hashlib.sha256(value).hexdigest(), url=prefix+name)
        prior = chunk('prior.bin', b'old')
        landed = chunk('landed.bin', b'landed')
        missing = chunk('new.bin', b'new')
        baseline = dict(components=[dict(chunks=[prior])])
        candidate = dict(components=[dict(chunks=[prior, landed, missing])])
        api = Mock()
        rows = [dict(name=c['asset'], size=c['bytes'], digest='sha256:'+c['sha256']) for c in (prior, landed)]
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            (local/'new.bin').write_bytes(b'new')
            api.api.side_effect = [{'id': 1}, rows]
            result, uploads = release.rollover_manifest(api, repo, baseline, candidate, local, 'package')
            self.assertEqual(uploads, {'new.bin'})
            chunks = result['components'][0]['chunks']
            self.assertEqual(chunks[:2], [prior, landed])
            self.assertIn(result['tag']+'/', chunks[2]['url'])
            self.assertEqual(missing['url'], prefix+'new.bin')
            rows[0]['digest'] = 'sha256:wrong'
            api.api.side_effect = [{'id': 1}, rows]
            with self.assertRaisesRegex(RuntimeError, 'differs'):
                release.rollover_manifest(api, repo, baseline, candidate, local, 'package')

    def inventory(self, count):
        api = Mock()
        rows = [{'name': str(i)} for i in range(count)]
        api.api.side_effect = [{'id': 123}] + [rows[i:i+100] for i in range(0, count, 100)] + [[]]
        return api

    def test_existing_names_at_limit(self):
        release.check_release_capacity(self.inventory(1000), 'o/r', 'tag', {'999'})

    def test_backup_and_chunk_exceed_remaining_slot(self):
        with self.assertRaisesRegex(RuntimeError, 'needs 2 new slots'):
            release.check_release_capacity(self.inventory(999), 'o/r', 'tag', {'998', 'backup', 'chunk'})

    def test_final_slot_available(self):
        release.check_release_capacity(self.inventory(999), 'o/r', 'tag', {'chunk'})
