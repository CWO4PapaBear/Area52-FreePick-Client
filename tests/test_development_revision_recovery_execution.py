import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


def load_development():
    path = Path(__file__).parents[1] / 'tools/deployment/development_activation.py'
    spec = importlib.util.spec_from_file_location('development_recovery_execution', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DevelopmentRecoveryExecutionTests(unittest.TestCase):
    def exercise(self, explicit, returned, accepted):
        module = load_development()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            payload = base / 'payload'
            payload.mkdir()
            realm = base / 'realm'
            realm.mkdir()
            status = realm / 'status.json'
            status.write_text('original status')
            for item in ('worldserver', 'apply.sql', 'rollback.sql', 'status.json'):
                (payload / item).write_text(item)
            query = 'SELECT JSON_ARRAY(`id`) FROM spell_group WHERE id=1 ORDER BY `id`;'
            package = dict(schema=1, target='development', id='area52-recovery-execution',
                           extensions_dll='excluded', publication_scope='development_only', publish=[],
                           requires_client_closed=False, binary='worldserver', apply='apply.sql',
                           rollback='rollback.sql', status='status.json', verification_query=query,
                           runner_sha256=module.digest(module.__file__),
                           before_rows_sha256=hashlib.sha256(b'before\n').hexdigest(),
                           after_rows_sha256=hashlib.sha256(b'after\n').hexdigest(),
                           artifacts=[dict(path=p.name, sha256=module.digest(p)) for p in payload.iterdir()])
            if explicit:
                package['rollback_rows_sha256'] = hashlib.sha256(b'recovery\n').hexdigest()
            manifest = payload / 'package.json'
            manifest.write_text(json.dumps(package))
            reads = iter((b'before\n', b'after\n', returned))
            statements = []

            def fake_sql(statement):
                statements.append(statement)
                if statement == query:
                    return next(reads)
                return b''

            lock = types.SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *args: None)
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.dict('sys.modules', {'fcntl': lock}))
                stack.enter_context(patch.object(module, 'ROOT', realm))
                stack.enter_context(patch.object(module, 'STATUS', status))
                stack.enter_context(patch.object(module, 'preflight', return_value={}))
                stack.enter_context(patch.object(module, 'create_args', return_value=['offline-create']))
                stack.enter_context(patch.object(module, 'report_development_players', return_value=0))
                stack.enter_context(patch.object(module, 'check_deployment_target'))
                stack.enter_context(patch.object(module, 'inspect', return_value={'Id': 'preserved'}))
                command = stack.enter_context(patch.object(module, 'command', return_value=b''))
                stack.enter_context(patch.object(module, 'sql', side_effect=fake_sql))
                stack.enter_context(patch.object(module.subprocess, 'run', return_value=types.SimpleNamespace(returncode=1)))
                stack.enter_context(patch.object(module, 'ready', side_effect=RuntimeError('injected startup failure')))
                with self.assertRaisesRegex(RuntimeError, 'injected startup failure' if accepted else 'Rollback row mismatch'):
                    module.run(manifest, False)
            transaction = realm / 'deployments' / package['id']
            state = json.loads((transaction / 'state.json').read_text())
            self.assertEqual(state['failed_phase'], 'verifying_development')
            self.assertEqual(state['status'], 'rolled_back' if accepted else 'rollback_required')
            self.assertEqual(statements.count(query), 3)
            self.assertEqual(sum('rollback.sql' in text for text in statements), 1)
            restoration = ['docker', 'rename', module.retained_name(package), module.WORLD]
            self.assertEqual(any(call.args[0] == restoration for call in command.call_args_list), accepted)
            self.assertEqual(status.read_text(), 'original status' if accepted else 'status.json')
            if not accepted:
                self.assertNotEqual(command.call_args_list[-1].args[0], restoration)

    def test_forward_recovery_hash_accepted_in_actual_failure_path(self):
        self.exercise(True, b'recovery\n', True)

    def test_forward_recovery_rejects_original_and_wrong_rows(self):
        for rows in (b'before\n', b'wrong\n', b'recovery'):
            with self.subTest(rows=rows):
                self.exercise(True, rows, False)

    def test_existing_default_accepts_original_rows(self):
        self.exercise(False, b'before\n', True)

    def test_existing_default_rejects_different_recovery_rows(self):
        self.exercise(False, b'recovery\n', False)


if __name__ == '__main__':
    unittest.main()
