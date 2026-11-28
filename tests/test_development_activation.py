import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('development', Path(__file__).parents[1] /
                                            'tools/deployment/development_activation.py')
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)


class DevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('worldserver', 'apply.sql', 'rollback.sql', 'status.json'):
            (self.root / name).write_text(name)
        self.package = dict(schema=1, target='development', id='area52-development-test',
                            verification_query='SELECT JSON_ARRAY(`ID`) FROM spell_dbc WHERE ID=1 ORDER BY `ID`;',
                            extensions_dll='excluded', publication_scope='development_only', publish=[],
                            requires_client_closed=False, binary='worldserver', apply='apply.sql',
                            rollback='rollback.sql', status='status.json', runner_sha256=dev.digest(dev.__file__),
                            artifacts=[dict(path=p.name, sha256=dev.digest(p)) for p in self.root.iterdir()])
        self.manifest = self.root / 'package.json'
        self.manifest.write_text(json.dumps(self.package))
        self.current = dict(HostConfig=dict(NetworkMode='container:pilot-db', Privileged=False, PortBindings={}),
                            Mounts=[dict(Type='bind', Source='/old', Destination='/candidate', RW=False),
                                    dict(Type='bind', Source='/data', Destination='/data', RW=False)],
                            Config=dict(Env=['A=B'], WorkingDir='/workspace', User=''),
                            Path='/candidate', Args=['-c', '/config'], Image='sha256:expected')

    def test_development_online_check_reports_without_blocking_owner(self):
        for count in (0, 1, 20):
            with patch.object(dev, 'sql', return_value=str(count).encode()) as query:
                self.assertEqual(dev.report_development_players(), count)
                query.assert_called_once_with(
                    'SELECT COUNT(*) FROM acore_characters.characters WHERE online<>0;')
        for invalid in (b'', b'unknown', b'-1'):
            with patch.object(dev, 'sql', return_value=invalid):
                with self.assertRaisesRegex(RuntimeError, 'online player count'):
                    dev.report_development_players()
        with patch.object(dev, 'sql', side_effect=RuntimeError('read failed')):
            with self.assertRaisesRegex(RuntimeError, 'read failed'):
                dev.report_development_players()

    def test_readonly_does_not_execute(self):
        with patch.object(dev, 'preflight', return_value=self.current), patch.object(dev, 'command') as command:
            dev.run(self.manifest, True)
            command.assert_not_called()
        self.assertFalse((self.root / 'deployments').exists())

    def test_cache_catalog_readback_allowlist(self):
        for table, column in [('item_template', 'entry'), ('quest_template', 'ID'), ('item_loot_template', 'Entry'), ('quest_template_addon', 'ID')]:
            self.package['verification_query'] = (
                f'SELECT JSON_ARRAY(`{column}`) FROM {table} WHERE {column} IN (1,2) ORDER BY `{column}`;')
            dev.validate(self.package, self.root)
        for query in (
            'DELETE FROM item_template WHERE entry=1;',
            'DELETE FROM item_loot_template WHERE Entry=1397885;',
            'DELETE FROM quest_template_addon WHERE ID=10000;',
            'SELECT JSON_ARRAY(`Item`) FROM item_loot_template WHERE Entry=1397885 FOR UPDATE ORDER BY `Item`;',
            'SELECT JSON_ARRAY(`entry`) FROM item_template WHERE entry=1 FOR UPDATE ORDER BY `entry`;',
            'SELECT JSON_ARRAY(`id`) FROM account WHERE id=1 ORDER BY `id`;',
            "SELECT JSON_ARRAY(`entry`) FROM item_template WHERE entry=1 UNION SELECT 1 ORDER BY `entry`;",
        ):
            self.package['verification_query'] = query
            with self.assertRaisesRegex(RuntimeError, 'allowlisted'):
                dev.validate(self.package, self.root)

    def test_bot_catalog_readback_allowlist(self):
        for table in ('playerbots_legendary_class', 'playerbots_legendary_weight', 'playerbots_legendary_pick', 'playerbots_legendary_enchant'):
            self.package['verification_query'] = (
                f"SELECT JSON_ARRAY(`spec`) FROM acore_playerbots.{table} WHERE spec='defias-gunslinger' ORDER BY `spec`;")
            dev.validate(self.package, self.root)
        self.package['verification_query'] = "SELECT JSON_ARRAY(`name`) FROM acore_auth.account WHERE id=1 ORDER BY `name`;"
        with self.assertRaisesRegex(RuntimeError, 'allowlisted'):
            dev.validate(self.package, self.root)

    def test_configuration_target_is_development_world_only(self):
        target = str(dev.ROOT / 'etc/worldserver.conf')
        self.package['configuration'] = [dict(path=target, sha256='before')]
        self.package['configuration_replacements'] = [dict(target=target, artifact='status.json', before_sha256='before')]
        dev.validate(self.package, self.root)
        for bad in (str(dev.ROOT / 'etc/authserver.conf'), '/srv/area52-staging/etc/worldserver.conf'):
            self.package['configuration_replacements'][0]['target'] = bad
            with self.assertRaisesRegex(RuntimeError, 'configuration target'):
                dev.validate(self.package, self.root)

    def test_full_package_ids_do_not_share_backup_names(self):
        first = dict(self.package, id='area52-cache-delivery-development-20261118')
        second = dict(self.package, id='area52-cache-selection-development-20261118')
        self.assertEqual(first['id'][-18:], second['id'][-18:])
        self.assertNotEqual(dev.retained_name(first), dev.retained_name(second))
        self.assertTrue(dev.retained_name(second).endswith(second['id']))

    def test_destination_check_is_readonly_and_fails_closed(self):
        with patch.object(dev, 'ROOT', self.root), patch.object(dev, 'command', return_value=b'') as command:
            dev.check_deployment_target(self.package)
            self.assertEqual(command.call_args.args[0][:3], ['docker', 'container', 'ls'])
        with patch.object(dev, 'ROOT', self.root), patch.object(dev, 'command',
                return_value=(dev.retained_name(self.package) + '\n').encode()):
            with self.assertRaisesRegex(RuntimeError, 'backup container already exists'):
                dev.check_deployment_target(self.package)
        with patch.object(dev, 'ROOT', self.root), patch.object(dev, 'command', side_effect=RuntimeError('read failed')):
            with self.assertRaisesRegex(RuntimeError, 'read failed'):
                dev.check_deployment_target(self.package)
        (self.root / 'deployments' / self.package['id']).mkdir(parents=True)
        with patch.object(dev, 'ROOT', self.root), patch.object(dev, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'transaction requires review'):
                dev.check_deployment_target(self.package)
            command.assert_not_called()

    def test_command_diagnostic_does_not_expose_arguments_or_stderr(self):
        with patch.object(dev.subprocess, 'run') as process:
            process.return_value.returncode = 1
            process.return_value.stderr = b'private value'
            with self.assertRaises(RuntimeError) as error:
                dev.command(['docker', 'rename', 'private-name', 'another-private-name'])
            self.assertIn('docker rename; exit 1', str(error.exception))
            self.assertNotIn('private-name', str(error.exception))
            self.assertNotIn('private value', str(error.exception))

    @unittest.skipIf(__import__('os').name == 'nt', 'Execution runner uses Linux fcntl')
    def test_backup_collision_aborts_before_shutdown(self):
        with (patch.object(dev, 'ROOT', self.root),
              patch.object(dev, 'preflight', return_value=self.current),
              patch.object(dev, 'sql', return_value=b'0'),
              patch.object(dev, 'command',
                  return_value=(dev.retained_name(self.package) + '\n').encode()) as command):
            with self.assertRaisesRegex(RuntimeError, 'backup container already exists'):
                dev.run(self.manifest, False)
            self.assertFalse((self.root / 'deployments' / self.package['id']).exists())
            self.assertTrue(all(call.args[0][:3] == ['docker', 'container', 'ls']
                                for call in command.call_args_list))

    def test_no_publication_resume(self):
        with patch.object(dev, 'preflight') as preflight, self.assertRaises(RuntimeError):
            dev.run(self.manifest, True, True)
        preflight.assert_not_called()

    def test_ready_accepts_native_marker_case_and_checks_binary(self):
        for marker in (b'WORLD: World Initialized In 0 Minutes 30 Seconds',
                       b'WORLD: World initialized in 30 seconds'):
            with self.subTest(marker=marker), patch.object(dev, 'inspect', return_value={
                    'State': {'Running': True}}), patch.object(dev, 'command',
                    side_effect=[marker, b'expected  /proc/1/exe']) as command:
                dev.ready('expected')
                self.assertEqual(command.call_args.args[0],
                                 ['docker', 'exec', dev.WORLD, 'sha256sum', '/proc/1/exe'])

    def test_ready_rejects_wrong_binary(self):
        with patch.object(dev, 'inspect', return_value={'State': {'Running': True}}), \
                patch.object(dev, 'command', side_effect=[
                    b'WORLD: World Initialized In 0 Minutes 30 Seconds', b'wrong /proc/1/exe']), \
                self.assertRaisesRegex(RuntimeError, 'runtime hash mismatch'):
            dev.ready('expected')

    def test_ready_rejects_exit_and_missing_marker(self):
        with patch.object(dev, 'inspect', return_value={'State': {'Running': False}}), \
                patch.object(dev, 'command') as command, \
                self.assertRaisesRegex(RuntimeError, 'exited during startup'):
            dev.ready('expected')
        command.assert_not_called()
        with patch.object(dev, 'inspect', return_value={'State': {'Running': True}}), \
                patch.object(dev, 'command', return_value=b'Shared Manastorm backend initialized.'), \
                patch.object(dev.time, 'monotonic', side_effect=[0, 1, 181]), \
                patch.object(dev.time, 'sleep'), \
                self.assertRaisesRegex(RuntimeError, 'readiness timed out'):
            dev.ready('expected')

    def test_valid_artifacts(self):
        dev.validate(self.package, self.root)

    def test_mount_order_is_not_drift_but_mount_changes_are(self):
        expected = dev.fingerprint(self.current)
        self.current['Mounts'].reverse()
        self.assertEqual(dev.fingerprint(self.current), expected)
        self.current['Mounts'][0]['Source'] = '/changed'
        self.assertNotEqual(dev.fingerprint(self.current), expected)

    def test_client_archive_allowlist_and_closure(self):
        self.package['requires_client_closed'] = True
        self.package['client_replacements'] = [dict(target=str(dev.CLIENT / 'patch-E.MPQ'),
                                                   artifact='status.json', before_sha256='old')]
        dev.validate(self.package, self.root)
        self.package['client_replacements'][0]['target'] = str(dev.CLIENT / 'Extensions.dll')
        with self.assertRaises(RuntimeError):
            dev.validate(self.package, self.root)

    def test_tampered_artifact(self):
        (self.root / 'apply.sql').write_text('changed')
        with self.assertRaises(RuntimeError):
            dev.validate(self.package, self.root)

    def test_readonly_query_rejects_mutations(self):
        for query in ('DELETE FROM spell_dbc;', 'SELECT SLEEP(90);',
                      'SELECT JSON_ARRAY(`ID`) FROM spell_dbc WHERE ID=1 ORDER BY `ID`; DELETE FROM spell_dbc;'):
            with self.subTest(query=query), self.assertRaises(RuntimeError):
                dev.validate(dict(self.package, verification_query=query), self.root)

    def test_wrong_target_and_publication_rejected(self):
        for values in ({'target': 'cloud'}, {'publish': ['anything']}, {'publication_scope': 'tester'},
                       {'requires_client_closed': True}, {'extensions_dll': 'included'},
                       {'runner_sha256': 'stale'}):
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                dev.validate(dict(self.package, **values), self.root)

    def test_exact_development_container_and_mounts(self):
        args = dev.create_args(self.current, Path('/private/new-worldserver'))
        self.assertEqual(args[args.index('--name') + 1], 'area52-gm-pilot-worldserver')
        self.assertIn(str(Path('/private/new-worldserver')) + ':/candidate:ro', args)
        self.assertIn('/data:/data:ro', args)
        self.assertNotIn('ascension-freepick-worldserver', args)
        self.assertNotIn('/old:/candidate:ro', args)

    def test_unsupported_network_fails_before_create(self):
        self.current['HostConfig']['NetworkMode'] = 'host'
        with self.assertRaises(RuntimeError):
            dev.create_args(self.current, Path('/binary'))

    def test_preflight_failure_has_no_mutation(self):
        with (patch.object(dev, 'preflight', side_effect=RuntimeError('drift')),
              patch.object(dev, 'command') as command):
            with self.assertRaises(RuntimeError):
                dev.run(self.manifest, False)
            command.assert_not_called()

    @unittest.skipIf(__import__('os').name == 'nt', 'Execution runner uses Linux fcntl')
    def test_execution_and_startup_failure_rollback(self):
        for fail in (False, True):
            with self.subTest(startup_failure=fail), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                status = target / 'current-status.json'
                status.write_text('original status')
                archive = target / 'patch-E.MPQ'
                archive.write_text('original archive')
                config = target / 'etc/worldserver.conf'
                config.parent.mkdir()
                config.write_text('bots disabled')
                self.package['configuration'] = [dict(path=str(config), sha256=dev.digest(config))]
                self.package['configuration_replacements'] = [dict(target=str(config), artifact='status.json', before_sha256=dev.digest(config))]
                self.package.update(before_rows_sha256='before', after_rows_sha256='after')
                self.package.update(requires_client_closed=True, client_replacements=[dict(
                    target=str(archive), artifact='status.json', before_sha256=dev.digest(archive))])
                self.manifest.write_text(json.dumps(self.package))
                readbacks = ['before', 'after'] + (['before'] if fail else [])
                with (patch.object(dev, 'ROOT', target), patch.object(dev, 'STATUS', status),
                      patch.object(dev, 'CLIENT', target), patch.object(dev, 'client_closed') as closed,
                      patch.object(dev, 'preflight', return_value=self.current),
                      patch.object(dev, 'inspect', return_value={'Id': 'protected'}),
                      patch.object(dev, 'command', return_value=b'') as command,
                      patch.object(dev, 'sql', return_value=b'0') as sql,
                      patch.object(dev, 'readback', side_effect=readbacks),
                      patch.object(dev, 'ready', side_effect=RuntimeError('startup') if fail else None),
                      patch.object(dev.subprocess, 'run') as process):
                    process.return_value.returncode = 0
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, 'startup'):
                            dev.run(self.manifest, False)
                        self.assertEqual(status.read_text(), 'original status')
                        self.assertEqual(archive.read_text(), 'original archive')
                        self.assertEqual(config.read_text(), 'bots disabled')
                        self.assertIn('rollback.sql', sql.call_args.args[0])
                    else:
                        dev.run(self.manifest, False)
                        self.assertEqual(status.read_text(), 'status.json')
                        self.assertEqual(archive.read_text(), 'status.json')
                        self.assertEqual(config.read_text(), 'status.json')
                    closed.assert_called()
                    state = json.loads((target / 'deployments' / self.package['id'] / 'state.json').read_text())
                    self.assertEqual(state['status'], 'rolled_back' if fail else 'complete')
                    if fail:
                        self.assertEqual(state['failed_phase'], 'verifying_development')
                    for call in command.call_args_list:
                        args = call.args[0]
                        if args[:2] in (['docker', 'stop'], ['docker', 'start'], ['docker', 'rm']):
                            self.assertEqual(args[-1], dev.WORLD)


if __name__ == '__main__':
    unittest.main()
