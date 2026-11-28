import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    path = Path(__file__).parents[1] / 'tools/deployment' / (name + '_activation.py')
    spec = importlib.util.spec_from_file_location(name + '_crusader', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RevisionRecoveryTests(unittest.TestCase):
    def test_cloud_forward_recovery_hash_is_exact(self):
        module = load('cloud')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'rollback.sql').write_text('SELECT 1;')
            package = dict(before_rows_sha256='before', after_rows_sha256='after',
                           rollback_rows_sha256='recovery', rollback='rollback.sql')
            for result in ['recovery', 'before', 'other']:
                with self.subTest(result=result), patch.object(module, 'readback', side_effect=['after', result]), patch.object(module, 'sql') as sql:
                    if result == 'recovery':
                        module.restore_rows(package, root)
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'Rollback row mismatch'):
                            module.restore_rows(package, root)
                    sql.assert_called_once()

    def test_both_validate_only_scoped_read_queries(self):
        for name in ['cloud', 'development']:
            module = load(name)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for item in ['worldserver', 'apply.sql', 'rollback.sql', 'status.json']:
                    (root / item).write_text(item)
                package = dict(schema=1, target=name, id='area52-crusader-test',
                               publication_scope='cloud_server_only' if name == 'cloud' else 'development_only',
                               extensions_dll='excluded', publish=[], requires_client_closed=False,
                               binary='worldserver', apply='apply.sql', rollback='rollback.sql', status='status.json',
                               runner_sha256=module.digest(module.__file__), rollback_rows_sha256='a' * 64,
                               artifacts=[dict(path=p.name, sha256=module.digest(p)) for p in root.iterdir()])
                for table in ['creature_template', 'creature_template_model',
                              'acore_characters.area52_build_revision', 'acore_characters.area52_build_featured',
                              'acore_characters.area52_build_archetype']:
                    package['verification_query'] = 'SELECT JSON_ARRAY(`id`) FROM ' + table + ' WHERE id=1 ORDER BY `id`;'
                    module.validate(package, root)
                for query in ['DELETE FROM creature_template;',
                              'SELECT JSON_ARRAY(`id`) FROM acore_characters.characters WHERE id=1 ORDER BY `id`;',
                              'SELECT JSON_ARRAY(`id`) FROM creature_template WHERE id=1 FOR UPDATE;']:
                    package['verification_query'] = query
                    with self.assertRaisesRegex(RuntimeError, 'allowlisted'):
                        module.validate(package, root)


if __name__ == '__main__':
    unittest.main()
