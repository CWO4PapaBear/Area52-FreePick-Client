import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('activation', Path(__file__).parents[1] / 'tools/deployment/activate.py')
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = self.root / 'private'
        self.private.mkdir()
        self.compose = self.private / 'compose.json'
        self.compose.write_text(json.dumps({'services': {'worldserver': {'volumes': [], 'entrypoint': ['old']}}}))
        self.source = self.root / 'package'
        self.source.mkdir()
        (self.source / 'worldserver').write_bytes(b'new binary')
        (self.source / 'source.cpp').write_text('new source')
        self.target = self.private / 'source.cpp'
        self.target.write_text('old source')
        self.transaction = self.private / 'transaction'
        self.transaction.mkdir()
        self.package = {
            'schema': 1, 'id': 'test-package', 'requires_client_closed': False, 'extensions_dll': 'excluded',
            'announcement': 'Test repair.', 'binary': 'worldserver', 'expected_binary_sha256': 'old',
            'expected_compose_sha256': activation.digest(self.compose),
            'artifacts': [{'path': p.name, 'sha256': activation.digest(p)} for p in self.source.iterdir()],
            'replacements': [{'artifact': 'source.cpp', 'target': str(self.target),
                              'before_sha256': activation.digest(self.target)}], 'hooks': [], 'publish': []}
        for name, value in [('PRIVATE', self.private), ('COMPOSE', self.compose),
                            ('TRANSACTIONS', self.private / 'deployments')]:
            self.enterContext(patch.object(activation, name, value))

    def test_tampering_rejected(self):
        activation.validate(self.package, self.source)
        (self.source / 'worldserver').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
            activation.validate(self.package, self.source)

    def test_escape_and_stale_baseline_rejected(self):
        self.package['replacements'][0]['target'] = str(self.root / 'outside')
        with self.assertRaisesRegex(RuntimeError, 'outside'):
            activation.validate(self.package, self.source)
        self.package['replacements'][0]['target'] = str(self.target)
        self.target.write_text('unexpected edit')
        with self.assertRaisesRegex(RuntimeError, 'Installed file changed'):
            activation.check_baselines(self.package)

    def test_missing_rollback_rejected(self):
        self.package['hooks'] = [{'name': 'database', 'apply': {}}]
        with self.assertRaisesRegex(RuntimeError, 'Every hook'):
            activation.validate(self.package, self.source)

    def test_changed_compose_rejected(self):
        self.compose.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'configuration changed'):
            activation.check_baselines(self.package)

    def test_dll_package_rejected(self):
        self.package['extensions_dll'] = 'included'
        with self.assertRaisesRegex(RuntimeError, 'DLL changes'):
            activation.validate(self.package, self.source)

    def simulate(self, failure=None):
        def inspect(name):
            return {'State': {'StartedAt': 'unchanged', 'Running': False}}
        expected = activation.digest(self.source / 'worldserver')
        mocks = [patch.object(activation, 'inspect', side_effect=inspect),
                 patch.object(activation, 'execute', return_value=''),
                 patch.object(activation, 'gm'), patch.object(activation, 'compose'),
                 patch.object(activation, 'ready', side_effect=[RuntimeError('bad startup'), None] if failure == 'startup' else None),
                 patch.object(activation, 'current_binary', return_value='old' if failure == 'startup' else expected)]
        for mock in mocks:
            self.enterContext(mock)
        activation.activate(self.package, self.source, self.transaction)

    def test_success(self):
        self.simulate()
        self.assertEqual(self.target.read_text(), 'new source')
        self.assertEqual(json.loads((self.transaction / 'state.json').read_text())['status'], 'complete')
        activation.gm.assert_any_call('server shutdown 180')
        activation.compose.assert_called_once_with('up', '-d', '--no-deps', 'worldserver')

    def test_startup_failure_restores_files_and_compose(self):
        old = self.compose.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'bad startup'):
            self.simulate('startup')
        self.assertEqual(self.target.read_text(), 'old source')
        self.assertEqual(self.compose.read_bytes(), old)
        self.assertEqual(json.loads((self.transaction / 'state.json').read_text())['status'], 'rolled_back')

    def test_publish_failure_does_not_revert_running_server(self):
        self.package['publish'] = [{'script': 'release.py', 'args': [], 'timeout': 30}]
        self.enterContext(patch.object(activation, 'run_step', side_effect=RuntimeError('release failed')))
        self.enterContext(patch.object(activation, 'validate'))
        with self.assertRaisesRegex(RuntimeError, 'client publication failed'):
            self.simulate()
        self.assertEqual(self.target.read_text(), 'new source')
        self.assertEqual(json.loads((self.transaction / 'state.json').read_text())['status'], 'publish_failed')

    def test_partial_hook_apply_is_rolled_back(self):
        self.package['hooks'] = [{'name': 'migration', **{phase: {'phase': phase} for phase in
                                  ('preflight', 'backup', 'apply', 'verify', 'rollback')}}]
        phases = []

        def step(step, payload, transaction):
            phases.append(step['phase'])
            if step['phase'] == 'apply':
                raise RuntimeError('partial apply')

        self.enterContext(patch.object(activation, 'run_step', side_effect=step))
        self.enterContext(patch.object(activation, 'validate'))
        self.enterContext(patch.object(activation, 'inspect', return_value={'State': {'StartedAt': 'same', 'Running': False}}))
        self.enterContext(patch.object(activation, 'execute', return_value=''))
        self.enterContext(patch.object(activation, 'gm'))
        self.enterContext(patch.object(activation, 'compose'))
        self.enterContext(patch.object(activation, 'ready'))
        self.enterContext(patch.object(activation, 'current_binary', return_value='old'))
        with self.assertRaisesRegex(RuntimeError, 'partial apply'):
            activation.activate(self.package, self.source, self.transaction)
        self.assertEqual(phases, ['preflight', 'backup', 'apply', 'rollback'])
        self.assertEqual(self.target.read_text(), 'old source')


if __name__ == '__main__':
    unittest.main()
