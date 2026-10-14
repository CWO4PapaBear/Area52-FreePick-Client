"""Prepared-package activation; run inside dml-arch as root through the PowerShell wrapper."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client_state import ensure_closed

PRIVATE = Path('/home/dml/games/ascension-freepick-test/private')
COMPOSE = PRIVATE / 'compose.realm.json'
TRANSACTIONS = PRIVATE / 'deployments'
WORLD = 'ascension-freepick-worldserver'
PROTECTED = ('ascension-freepick-authserver', 'ascension-freepick-database')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def execute(args, timeout=60):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=timeout)
    require(result.returncode == 0, 'Command failed: ' + ' '.join(args[:3]) + '\n' + result.stdout[-3000:])
    return result.stdout


def inspect(name):
    return json.loads(execute(['docker', 'inspect', name]))[0]


def compose(*args):
    return execute(['docker', 'compose', '-p', 'ascension-freepick-runtime', '-f', str(COMPOSE),
                    '--profile', 'world-data-ready', *args], timeout=180)


def atomic_copy(source, target):
    target = Path(target)
    temporary = target.with_name(target.name + '.activation-tmp')
    require(not temporary.exists(), 'Temporary file already exists: ' + str(temporary))
    shutil.copy2(source, temporary)
    os.replace(temporary, target)


def relative_file(root, name):
    require(isinstance(name, str) and not Path(name).is_absolute(), 'Package paths must be relative')
    candidate = (root / name).resolve()
    require(candidate.is_relative_to(root.resolve()) and candidate.is_file(), 'Invalid package file: ' + name)
    return candidate


def validate(package, root):
    require(package.get('schema') == 1, 'Unsupported package schema')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{2,79}', package.get('id', '')), 'Invalid package id')
    require(isinstance(package.get('requires_client_closed'), bool), 'Client closure flag required')
    require(package.get('extensions_dll') == 'excluded', 'DLL changes require a separately reviewed runner revision')
    require(isinstance(package.get('announcement'), str) and 1 <= len(package['announcement']) <= 300,
            'An announcement is required')
    require('\n' not in package['announcement'], 'Announcement must be one line')
    artifacts = package.get('artifacts', [])
    require(artifacts, 'Package is empty')
    names = set()
    for artifact in artifacts:
        name = artifact['path']
        require(name not in names, 'Duplicate artifact')
        names.add(name)
        require(digest(relative_file(root, name)) == artifact['sha256'], 'Artifact hash mismatch: ' + name)
    targets = set()
    for replacement in package.get('replacements', []):
        target = Path(replacement['target'])
        require(target.is_absolute() and target.resolve().is_relative_to(PRIVATE) and
                not target.resolve().is_relative_to(TRANSACTIONS), 'Replacement target outside server private directory')
        require(target.resolve() != COMPOSE.resolve(), 'Compose changes must be made by the runner, not replacements')
        require(str(target.resolve()) not in targets, 'Duplicate replacement target')
        targets.add(str(target.resolve()))
        require(replacement['artifact'] in names, 'Undeclared replacement artifact')
        require('before_sha256' in replacement, 'Missing replacement baseline')
    for hook in package.get('hooks', []):
        require(set(hook) == {'name', 'preflight', 'backup', 'apply', 'verify', 'rollback'},
                'Every hook requires preflight, backup, apply, verify and rollback')
        for phase in ('preflight', 'backup', 'apply', 'verify', 'rollback'):
            validate_step(hook[phase], names)
    for step in package.get('publish', []):
        validate_step(step, names)
    require(package.get('expected_binary_sha256'), 'Current binary baseline is required')
    require(package.get('expected_compose_sha256'), 'Current configuration baseline is required')
    if package.get('binary'):
        require(package['binary'] in names, 'Undeclared server binary')


def validate_step(step, names):
    require(set(step) == {'script', 'args', 'timeout'}, 'Invalid hook step')
    require(step['script'] in names and step['script'].endswith('.py'), 'Hook script must be a hashed Python artifact')
    require(isinstance(step['args'], list) and all(isinstance(x, str) for x in step['args']), 'Invalid hook arguments')
    require(isinstance(step['timeout'], int) and 1 <= step['timeout'] <= 1800, 'Invalid hook timeout')


def check_baselines(package):
    require(digest(COMPOSE) == package['expected_compose_sha256'], 'Server configuration changed; rebase this package')
    for item in package.get('replacements', []):
        target = Path(item['target'])
        actual = digest(target) if target.is_file() else None
        require(actual == item['before_sha256'], 'Installed file changed: ' + str(target))
        require(target.parent.is_dir(), 'Missing target directory: ' + str(target.parent))


def current_binary():
    return execute(['docker', 'exec', WORLD, 'sha256sum', '/proc/1/exe']).split()[0]


def client_closed(package):
    if not package['requires_client_closed']:
        return
    ensure_closed()


def run_step(step, payload, transaction):
    env = os.environ.copy()
    env['AREA52_PACKAGE_DIR'] = str(payload)
    env['AREA52_TRANSACTION_DIR'] = str(transaction)
    subprocess.run(['python3', str(relative_file(payload, step['script'])), *step['args']],
                   check=True, timeout=step['timeout'], env=env, cwd=payload)


def ready(timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = inspect(WORLD)['State']
        require(state['Running'], 'Worldserver exited during startup')
        logs = execute(['docker', 'logs', '--since', state['StartedAt'], WORLD])
        if '(worldserver-daemon) ready...' in logs:
            return
        time.sleep(2)
    raise RuntimeError('Worldserver readiness timed out')


def gm(command):
    import base64
    import xml.etree.ElementTree as ET
    from xml.sax.saxutils import escape
    credentials = json.loads((PRIVATE / 'remote-gm/credentials.json').read_text())
    body = ('<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="urn:AC">'
            '<SOAP-ENV:Body><ns1:executeCommand><command>' + escape(command) +
            '</command></ns1:executeCommand></SOAP-ENV:Body></SOAP-ENV:Envelope>')
    authorization = base64.b64encode((credentials['username'] + ':' + credentials['password']).encode()).decode()
    child = ('import json,sys,urllib.request\nr=json.load(sys.stdin)\n'
             'q=urllib.request.Request("http://127.0.0.1:7878/",data=r["body"].encode(),'
             'headers={"Content-Type":"text/xml; charset=utf-8","SOAPAction":"urn:AC#executeCommand",'
             '"Authorization":"Basic "+r["authorization"]})\n'
             'with urllib.request.urlopen(q,timeout=30) as s: print(s.read().decode())\n')
    result = subprocess.run(['nsenter', '-t', str(inspect(WORLD)['State']['Pid']), '-n', 'python3', '-c', child],
                            input=json.dumps({'body': body, 'authorization': authorization}),
                            text=True, capture_output=True, timeout=40)
    require(result.returncode == 0, 'GM command failed; credentials were not displayed')
    response = ET.fromstring(result.stdout)
    require(not any(e.tag.endswith('Fault') for e in response.iter()), 'GM command returned a SOAP fault')


def write_state(transaction, status, **fields):
    record = {'status': status, 'updated': time.time(), **fields}
    temporary = transaction / 'state.tmp'
    temporary.write_text(json.dumps(record, indent=2) + '\n')
    os.replace(temporary, transaction / 'state.json')
    print(status.replace('_', ' ').upper(), flush=True)


def activate(package, source, transaction):
    payload = transaction / 'payload'
    payload.mkdir()
    for artifact in package['artifacts']:
        target = payload / artifact['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(relative_file(source, artifact['path']), target)
    validate(package, payload)
    (transaction / 'package.json').write_text(json.dumps(package, indent=2))
    protected = {n: inspect(n)['State']['StartedAt'] for n in PROTECTED}
    old_compose = transaction / 'compose.before.json'
    shutil.copy2(COMPOSE, old_compose)
    candidate = json.loads(COMPOSE.read_text())
    if package.get('binary'):
        binary = payload / package['binary']
        binary.chmod(0o755)
        service = candidate['services']['worldserver']
        service['volumes'] = [v for v in service['volumes'] if ':/area52-package:' not in v]
        service['volumes'].append(str(payload) + ':/area52-package:ro')
        service['entrypoint'] = ['/area52-package/' + package['binary']]
    candidate_path = transaction / 'compose.candidate.json'
    candidate_path.write_text(json.dumps(candidate, indent=2))
    execute(['docker', 'compose', '-f', str(candidate_path), '--profile', 'world-data-ready', 'config', '--quiet'])
    backups = []
    applied_hooks = []
    countdown = False
    stopped = False
    try:
        for hook in package.get('hooks', []):
            run_step(hook['preflight'], payload, transaction)
        client_closed(package)
        gm('server info')
        gm('announce Area 52 restart in 3 minutes. ' + package['announcement'])
        countdown = True
        gm('server shutdown 180')
        write_state(transaction, 'countdown')
        deadline = time.monotonic() + 300
        while inspect(WORLD)['State']['Running']:
            require(time.monotonic() < deadline, 'Graceful shutdown timed out; no forced stop attempted')
            time.sleep(2)
        stopped = True
        write_state(transaction, 'applying')
        require(digest(COMPOSE) == digest(old_compose), 'Compose configuration changed during countdown')
        check_baselines(package)
        client_closed(package)
        for index, replacement in enumerate(package.get('replacements', [])):
            target = Path(replacement['target'])
            backup = transaction / ('file-' + str(index) + '.before')
            existed = target.exists()
            if existed:
                shutil.copy2(target, backup)
            backups.append((target, backup, existed))
            atomic_copy(payload / replacement['artifact'], target)
        for hook in package.get('hooks', []):
            run_step(hook['backup'], payload, transaction)
            applied_hooks.append(hook)
            run_step(hook['apply'], payload, transaction)
        atomic_copy(candidate_path, COMPOSE)
        compose('up', '-d', '--no-deps', 'worldserver')
        ready()
        expected = next((a['sha256'] for a in package['artifacts'] if a['path'] == package.get('binary')),
                        package['expected_binary_sha256'])
        require(current_binary() == expected, 'Running binary hash mismatch')
        for hook in package.get('hooks', []):
            run_step(hook['verify'], payload, transaction)
        require(protected == {n: inspect(n)['State']['StartedAt'] for n in protected},
                'Authentication or database service restarted unexpectedly')
    except BaseException as error:
        if stopped:
            try:
                compose('stop', '-t', '60', 'worldserver')
                for hook in reversed(applied_hooks):
                    run_step(hook['rollback'], payload, transaction)
                for target, backup, existed in reversed(backups):
                    if existed:
                        atomic_copy(backup, target)
                    else:
                        target.unlink(missing_ok=True)
                atomic_copy(old_compose, COMPOSE)
                compose('up', '-d', '--no-deps', 'worldserver')
                ready()
                require(current_binary() == package['expected_binary_sha256'], 'Rollback binary mismatch')
                write_state(transaction, 'rolled_back', error=str(error))
            except BaseException as rollback_error:
                write_state(transaction, 'rollback_failed', error=str(error), rollback_error=str(rollback_error))
                raise RuntimeError('Rollback incomplete. Stop and inspect ' + str(transaction)) from rollback_error
        else:
            if countdown:
                try:
                    gm('server shutdown cancel')
                except Exception:
                    write_state(transaction, 'cancel_failed', error=str(error))
                    raise RuntimeError('Could not confirm countdown cancellation. Inspect worldserver immediately.') from error
            write_state(transaction, 'aborted', error=str(error))
        raise
    write_state(transaction, 'server_ready')
    try:
        for step in package.get('publish', []):
            run_step(step, payload, transaction)
    except BaseException as error:
        write_state(transaction, 'publish_failed', error=str(error))
        raise RuntimeError('Server is ready, but client publication failed. Do not re-activate; inspect ' + str(transaction)) from error
    write_state(transaction, 'complete', client_release='published' if package.get('publish') else 'not required')


def main():
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    TRANSACTIONS.mkdir(parents=True, exist_ok=True)
    with (TRANSACTIONS / 'activation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        package = json.loads(args.package.read_text())
        validate(package, args.package.parent)
        transaction = TRANSACTIONS / package['id']
        if transaction.exists():
            state = json.loads((transaction / 'state.json').read_text()) if (transaction / 'state.json').exists() else {}
            require(state.get('status') == 'complete', 'Previous attempt needs review: ' + str(transaction))
            print('Package already completed. No restart performed.')
            return
        for folder in TRANSACTIONS.iterdir():
            if folder.is_dir():
                state = json.loads((folder / 'state.json').read_text()) if (folder / 'state.json').exists() else {}
                require(state.get('status') in ('complete', 'rolled_back', 'aborted'),
                        'Unfinished deployment needs review: ' + str(folder))
        require(inspect(WORLD)['State']['Running'], 'Worldserver must be running for an announced activation')
        require(current_binary() == package['expected_binary_sha256'], 'Server version changed; rebase this package')
        check_baselines(package)
        client_closed(package)
        gm('server info')
        print('Package integrity and installed baselines passed.', flush=True)
        if args.check_only:
            for hook in package.get('hooks', []):
                run_step(hook['preflight'], args.package.parent, TRANSACTIONS / 'check-only')
            print('CHECK ONLY: hook preflight passed; no announcement, shutdown, installation or publication performed.')
            return
        transaction.mkdir()
        write_state(transaction, 'preparing')
        activate(package, args.package.parent, transaction)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('ACTIVATION STOPPED: ' + str(error), file=sys.stderr)
        sys.exit(1)
