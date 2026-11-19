import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path('/srv/area52-staging')
WORLD = 'area52-staging-worldserver-1'
DATABASE = 'area52-staging-database-1'
STATUS = ROOT / 'etc/pilot-verified-access.json'
CLIENT = Path('/mnt/d/DML WOTLK Client Side/Ascension A52 Free Pick/ascension-live/ascension-live/Data/area-52')
CLIENT_CERTIFICATION = CLIENT.parents[1] / 'Interface/AddOns/Area52MysticRules/TesterCertification.lua'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def command(args, data=None, timeout=120):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    operation = args[0]
    if args[0] == 'docker' and len(args) > 1 and args[1] in (
            'inspect', 'container', 'exec', 'stop', 'rename', 'create', 'start', 'rm', 'logs'):
        operation += ' ' + args[1]
    require(result.returncode == 0,
            'Cloud operation failed: ' + operation + '; exit ' + str(result.returncode)
            + '; private diagnostics withheld')
    return result.stdout


def inspect(name):
    return json.loads(command(['docker', 'inspect', name]))[0]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sql(query):
    return command(['docker', 'exec', '-i', DATABASE, 'sh', '-c',
                    'MYSQL_PWD="$(cat /run/secrets/mysql-root-password)" exec mysql -uroot -BN --raw acore_world'],
                   query.encode())


def fingerprint(container):
    data = {key: container[key] for key in ('Config', 'HostConfig', 'Mounts', 'Path', 'Args')}
    data['Mounts'] = sorted(data['Mounts'], key=lambda mount: mount['Destination'])
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def validate(package, payload):
    require(package.get('schema') == 1 and package.get('target') == 'cloud', 'Cloud target required')
    require(re.fullmatch(r'[a-z0-9-]{3,80}', package.get('id', '')), 'Invalid package identifier')
    require(package.get('extensions_dll') == 'excluded', 'DLL changes excluded')
    require(package.get('publication_scope') == 'cloud_server_only' and not package.get('publish'),
            'Cloud activation cannot publish')
    clients = package.get('client_replacements', [])
    require(not clients, 'Cloud client delivery must use the launcher release')
    require(bool(package.get('requires_client_closed')) == bool(clients), 'Client closure requirement mismatch')
    names = set()
    for artifact in package['artifacts']:
        path = (payload / artifact['path']).resolve()
        require(path.is_relative_to(payload.resolve()) and path.is_file(), 'Invalid artifact path')
        require(artifact['path'] not in names, 'Duplicate artifact')
        names.add(artifact['path'])
        require(digest(path) == artifact['sha256'], 'Artifact hash mismatch: ' + artifact['path'])
    for key in ('binary', 'apply', 'rollback', 'status'):
        require(package[key] in names, 'Missing declared artifact: ' + key)
    targets = set()
    for item in clients:
        target = Path(item['target'])
        require((target.parent == CLIENT and target.name in ('patch-D.MPQ', 'patch-E.MPQ'))
                or target == CLIENT_CERTIFICATION,
                'Unapproved cloud client target')
        require(str(target) not in targets and item['artifact'] in names, 'Invalid client artifact')
        targets.add(str(target))
    require(package['runner_sha256'] == digest(__file__), 'Cloud runner changed; requalify package')
    columns = r'`[A-Za-z0-9_]+`(?:,`[A-Za-z0-9_]+`)*'
    tables = r'(?:spell_script_names|spell_proc|spell_dbc|spell_group|spell_group_stack_rules|item_template|quest_template|quest_template_addon|item_loot_template)'
    pattern = r'SELECT JSON_ARRAY\(' + columns + r'\) FROM ' + tables
    literal = r"(?:-?[0-9]+|'[A-Za-z0-9_-]+')"
    term = r'[A-Za-z0-9_]+\s*(?:=\s*' + literal + r'|IN\s*\(' + literal + r'(?:,\s*' + literal + r')*\))'
    pattern += r' WHERE ' + term + r'(?:\s+(?:AND|OR)\s+' + term + r')* ORDER BY ' + columns
    queries = [query.strip() for query in package['verification_query'].split(';') if query.strip()]
    require(queries and all(re.fullmatch(pattern, query) for query in queries),
            'Preflight requires allowlisted read-only row queries')


def readback(package):
    return hashlib.sha256(sql(package['verification_query'])).hexdigest()


def restore_rows(package, payload):
    current = readback(package)
    if current == package['before_rows_sha256']:
        return
    require(current == package['after_rows_sha256'],
            'Cloud rollback blocked by unexpected database state; retain transaction for review')
    sql('START TRANSACTION;\n' + (payload / package['rollback']).read_text() + '\nCOMMIT;')
    require(readback(package) == package['before_rows_sha256'], 'Rollback row mismatch')


def retained_name(package):
    return WORLD + '-before-' + package['id']


def check_deployment_target(package):
    require(not (ROOT / 'deployments' / package['id']).exists(),
            'Existing cloud transaction requires review; no automatic replay')
    names = command(['docker', 'container', 'ls', '--all', '--format', '{{.Names}}']).decode().splitlines()
    require(retained_name(package) not in names,
            'Cloud backup container already exists; preserve it and prepare a fresh package ID')


def preflight(package, payload):
    validate(package, payload)
    client_closed(package)
    for item in package.get('client_replacements', []):
        require(digest(item['target']) == item['before_sha256'], 'Local client archive drift')
    current = inspect(WORLD)
    require(current['State']['Running'], 'Cloud worldserver is not running')
    require(fingerprint(current) == package['expected_container_sha256'], 'Cloud container drift')
    require(command(['docker', 'exec', WORLD, 'sha256sum', '/proc/1/exe']).decode().split()[0]
            == package['expected_binary_sha256'], 'Cloud binary drift')
    require(digest(STATUS) == package['expected_status_sha256'], 'Cloud status drift')
    for item in package['configuration']:
        path = Path(item['path'])
        require(path.resolve().is_relative_to((ROOT / 'etc').resolve()), 'Invalid configuration guard')
        require(digest(path) == item['sha256'], 'Cloud configuration drift')
    require(readback(package) == package['before_rows_sha256'], 'Cloud database rows changed')
    check_deployment_target(package)
    print('Cloud-only integrity, binary, configuration, status and SQL preflight passed.', flush=True)
    return current


def client_closed(package):
    if package.get('requires_client_closed'):
        from client_state import ensure_closed
        ensure_closed()


def create_args(current, binary):
    host = current['HostConfig']
    require(host['NetworkMode'].startswith('container:'), 'Unexpected cloud network')
    require(not host.get('Privileged') and not host.get('PortBindings'), 'Unsupported cloud host options')
    restart = host.get('RestartPolicy', {}).get('Name', 'no')
    require(restart in ('no', 'always', 'unless-stopped'), 'Unsupported cloud restart policy')
    args = ['docker', 'create', '--name', WORLD, '--network', host['NetworkMode'], '--restart', restart]
    for mount in current['Mounts']:
        require(mount['Type'] == 'bind', 'Unsupported cloud mount')
        source = str(binary) if mount['Destination'] == '/candidate' else mount['Source']
        args += ['-v', source + ':' + mount['Destination'] + (':ro' if not mount['RW'] else '')]
    config = current['Config']
    for value in config.get('Env') or []:
        args += ['-e', value]
    if config.get('WorkingDir'):
        args += ['-w', config['WorkingDir']]
    if config.get('User'):
        args += ['--user', config['User']]
    args += ['--entrypoint', current['Path'], current['Image'], *current['Args']]
    return args


def ready(expected):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        require(inspect(WORLD)['State']['Running'], 'Cloud worldserver exited during startup')
        logs = command(['docker', 'logs', WORLD])
        if b'world initialized' in logs.lower():
            require(command(['docker', 'exec', WORLD, 'sha256sum', '/proc/1/exe']).decode().split()[0]
                    == expected, 'Cloud runtime hash mismatch')
            return
        time.sleep(2)
    raise RuntimeError('Cloud startup readiness timed out')


def run(manifest, check_only, resume_publish=False):
    require(not resume_publish, 'Cloud packages have no publication to resume')
    payload = manifest.parent
    package = json.loads(manifest.read_text())
    current = preflight(package, payload)
    create_args(current, payload / package['binary'])
    if check_only:
        print('CHECK ONLY: Cloud Server; no activation, restart, installation or publication performed.')
        return
    import fcntl
    transactions = ROOT / 'deployments'
    transactions.mkdir(exist_ok=True)
    with (transactions / 'activation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        preflight(package, payload)
        require(sql('SELECT COUNT(*) FROM acore_characters.characters WHERE online<>0 AND account NOT IN (30,31);').strip() == b'0',
                'Log all characters out of Cloud before activation')
        tx = transactions / package['id']
        check_deployment_target(package)
        protected = {name: inspect(name)['Id'] for name in
                     ('area52-staging-database-1', 'area52-staging-authserver-1')}
        tx.mkdir(mode=0o700)
        shutil.copytree(payload, tx / 'payload')
        payload = tx / 'payload'
        validate(package, payload)
        shutil.copy2(STATUS, tx / 'status.before.json')
        for index, item in enumerate(package.get('client_replacements', [])):
            shutil.copy2(item['target'], tx / ('client-before-' + str(index)))
        (tx / 'container.before.json').write_text(json.dumps(current))
        retained = retained_name(package)
        state = {'status': 'prepared', 'retained_container': retained}
        def record(value):
            state['status'] = value
            (tx / 'state.json').write_text(json.dumps(state, indent=2))
        renamed = False
        changed = False
        changed_clients = []
        try:
            record('stopping_cloud')
            command(['docker', 'stop', '--time', '60', WORLD])
            require(readback(package) == package['before_rows_sha256'], 'SQL changed while stopping')
            record('retaining_cloud')
            command(['docker', 'rename', WORLD, retained])
            renamed = True
            changed = True
            record('applying_payload')
            sql('START TRANSACTION;\n' + (payload / package['apply']).read_text() + '\nCOMMIT;')
            require(readback(package) == package['after_rows_sha256'], 'Applied SQL readback mismatch')
            temporary = STATUS.with_suffix('.activation-tmp')
            require(not temporary.exists(), 'Status temporary file exists')
            shutil.copy2(payload / package['status'], temporary)
            os.replace(temporary, STATUS)
            for index, item in enumerate(package.get('client_replacements', [])):
                client_closed(package)
                require(digest(item['target']) == item['before_sha256'], 'Client archive changed during activation')
                target = Path(item['target'])
                temporary = target.with_suffix('.activation-tmp')
                require(not temporary.exists(), 'Client temporary file exists')
                shutil.copy2(payload / item['artifact'], temporary)
                changed_clients.append((index, item))
                os.replace(temporary, target)
                require(digest(target) == digest(payload / item['artifact']), 'Client archive readback mismatch')
            record('creating_cloud')
            command(create_args(current, payload / package['binary']))
            record('starting_cloud')
            command(['docker', 'start', WORLD])
            expected = digest(payload / package['binary'])
            record('verifying_cloud')
            ready(expected)
            require(all(inspect(name)['Id'] == identity for name, identity in protected.items()),
                    'Protected container identity changed')
            record('complete')
            print('Cloud activation complete. Original container retained; nothing published.')
        except Exception as error:
            state['failed_phase'] = state['status']
            state['error_category'] = type(error).__name__
            record('rollback_required')
            if renamed:
                exists = subprocess.run(['docker', 'inspect', WORLD], capture_output=True).returncode == 0
                if exists:
                    command(['docker', 'stop', '--time', '60', WORLD])
                    command(['docker', 'rm', WORLD])
                if changed:
                    restore_rows(package, payload)
                    shutil.copy2(tx / 'status.before.json', STATUS)
                for index, item in reversed(changed_clients):
                    client_closed(package)
                    require(digest(item['target']) in (item['before_sha256'], digest(payload / item['artifact'])),
                            'Client rollback blocked by unrelated file change')
                    shutil.copy2(tx / ('client-before-' + str(index)), item['target'])
                    require(digest(item['target']) == item['before_sha256'], 'Client rollback mismatch')
                command(['docker', 'rename', retained, WORLD])
            command(['docker', 'start', WORLD])
            record('rolled_back')
            raise


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    run(args.manifest, args.check_only)
