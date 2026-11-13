import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/deployment'))
from stage_publication import select_source_branch


class SharedBranch(unittest.TestCase):
    def test_reconciles_each_path_before_pinning_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'patch').write_bytes(b'new')
            for current, allowed in [(b'old', True), (b'new', True), (b'other', False)]:
                api = Mock()
                api.api.return_value = {'object': {'sha': 'head'}}
                api.file.side_effect = [(current, None), (b'old', None)]
                config = dict(source_repo='CWO4PapaBear/azerothcore-wotlk-coa',
                              source_base='base', source_files=[dict(path='file', artifact='patch')])
                if allowed:
                    select_source_branch(config, root, api)
                    self.assertEqual(config['source_branch'], 'integration/area52-deployed')
                    self.assertEqual(config['source_base'], 'head')
                else:
                    with self.assertRaisesRegex(RuntimeError, 'file'):
                        select_source_branch(config, root, api)
                    self.assertEqual(config['source_base'], 'base')
