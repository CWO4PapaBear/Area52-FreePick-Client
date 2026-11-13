"""Publish a qualified changed-file release, preserving backups and retry receipts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import hashlib
import re
import time

from publication_common import GitHub, save, sha


def failure_category(stderr):
    """Return only allowlisted diagnostics; never echo URLs, bodies or credentials."""
    text = (stderr.decode('utf-8', errors='replace') if isinstance(stderr, bytes) else str(stderr)).lower()
    status = re.search(r'http(?:/\d(?:\.\d)?)?\s+(\d{3})\b', text)
    if status:
        return 'http-' + status.group(1)
    for category, patterns in (
        ('tls', ('certificate', 'x509', 'tls handshake')),
        ('dns', ('no such host', 'could not resolve', 'name resolution')),
        ('timeout', ('timed out', 'timeout', 'deadline exceeded')),
        ('connection', ('connection reset', 'connection refused', 'unexpected eof')),
        ('authentication', ('authentication', 'not logged', 'bad credentials')),
    ):
        if any(pattern in text for pattern in patterns):
            return category
    return 'unclassified'


def release_command(executable, repo, args, record=None):
    # Only reads may be automatically replayed. A failed upload has an uncertain outcome.
    read = tuple(args[:2]) in (('release', 'view'), ('release', 'download'))
    attempts = 3 if read else 1
    for attempt in range(1, attempts + 1):
        try:
            result = subprocess.run([executable, *args, '--repo', repo], capture_output=True, timeout=120)
            if result.returncode == 0:
                return result.stdout
            category, code = failure_category(result.stderr), result.returncode
        except subprocess.TimeoutExpired:
            category, code = 'timeout', None
        detail = dict(operation=' '.join(args[:2]), repository=repo, attempt=attempt,
                      category=category, exit_code=code, outcome='read-failed' if read else 'write-uncertain')
        if record:
            record(detail)
        if attempt < attempts:
            time.sleep(attempt)
    raise RuntimeError('Client release ' + detail['operation'] + ' failed: ' + category +
                       '; ' + detail['outcome'] + '; credentials withheld')


def reconcile_assets(records, remote, upload):
    def matches(name, expected):
        for attempt in range(3):
            if remote(name) == expected:
                return True
            if attempt < 2:
                time.sleep(attempt + 1)
        return False

    for name, path, replace in records:
        expected = sha(path.read_bytes())
        actual = remote(name)
        if actual == expected:
            continue
        if actual is not None and not replace:
            raise RuntimeError('Existing release asset differs: ' + name)
        try:
            upload(name, path, actual is not None)
        except (RuntimeError, subprocess.TimeoutExpired):
            # Lost responses do not mean the upload failed. Read back, never upload twice.
            if matches(name, expected):
                continue
            raise
        if not matches(name, expected):
            raise RuntimeError('Uploaded asset readback differs: ' + name)


def release_inventory(api, repo, tag):
    from urllib.parse import quote
    release = api.api(f'repos/{repo}/releases/tags/{quote(tag, safe="")}')
    names = {}
    for page in range(1, 12):
        rows = api.api(f"repos/{repo}/releases/{release['id']}/assets?per_page=100&page={page}")
        for row in rows:
            if row['name'] in names:
                raise RuntimeError('Release inventory changed during capacity check')
            names[row['name']] = row
        if len(rows) < 100:
            break
    return names


class ReleaseFull(RuntimeError):
    pass


def check_release_capacity(api, repo, tag, required):
    names = release_inventory(api, repo, tag)
    missing = required - names.keys()
    if len(names) + len(missing) > 1000:
        raise ReleaseFull(f'Release {tag} has {len(names)} assets and needs {len(missing)} new slots. '
                           'Prepare a new release tag before deployment.')


def rollover_manifest(api, repo, baseline, manifest, local, identity):
    from copy import deepcopy
    version = 'roll-' + sha(identity.encode())[:20]
    tag = 'area52-' + version
    root = f'https://github.com/{repo}/releases/download/'
    result = deepcopy(manifest)
    result.update(version=version, tag=tag, notes_url=root+tag+'/PATCH-NOTES.md', minimum_launcher_build=316)
    old = {(c['asset'], c['sha256'], c['bytes']): c for part in baseline['components'] for c in part['chunks']}
    inventories = {}
    uploads = set()
    for part in result['components']:
        for chunk in part['chunks']:
            name = chunk['asset']
            source = old.get((name, chunk['sha256'], chunk['bytes']), chunk)
            source_tag = source['url'].split('/')[-2]
            if not re.fullmatch(r'area52-[A-Za-z0-9][A-Za-z0-9._-]{0,70}', source_tag) or source['url'] != root+source_tag+'/'+name:
                raise RuntimeError('Invalid source chunk location')
            if source_tag not in inventories:
                inventories[source_tag] = release_inventory(api, repo, source_tag)
            row = inventories[source_tag].get(name)
            if row:
                if row.get('size') != chunk['bytes'] or row.get('digest') != 'sha256:'+chunk['sha256']:
                    raise RuntimeError('Source release chunk differs: '+name)
                chunk['url'] = source['url']
            else:
                path = local / name
                if not path.is_file() or path.stat().st_size != chunk['bytes'] or sha(path.read_bytes()) != chunk['sha256']:
                    raise RuntimeError('Missing verified source for chunk: '+name)
                uploads.add(name)
                chunk['url'] = root+tag+'/'+name
    if len(uploads)+2 > 1000:
        raise RuntimeError('New payload exceeds single release capacity')
    return result, uploads


def execute(root, tx, phase):
    config = json.loads((Path(root) / 'release-config.json').read_text())
    identity = hashlib.sha256(config['repo'].lower().encode()).hexdigest()
    path = Path(tempfile.gettempdir()) / ('area52-client-publication-' + identity + '.lock')
    with path.open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            if lock.tell() == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            return execute_locked(root, tx, phase)
        finally:
            if os.name == 'nt':
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def execute_locked(root, tx, phase):
    root, tx = Path(root), Path(tx)
    validate_inputs(root)
    config = json.loads((root / 'release-config.json').read_text())
    release, baseline = root / 'release', root / 'release-baseline'
    repo, tag = config['repo'], config['tag']
    api = GitHub(config['gh'])
    sys.path[:0] = [config['launcher'], str(Path(config['launcher']) / 'tools')]
    from launcher import fullclient
    manifest = fullclient.validate(json.loads((release / 'manifest.json').read_bytes()), repo)
    pointer = (release / 'area52.json').read_bytes()
    if json.loads(pointer)['manifest_sha256'] != sha((release / 'manifest.json').read_bytes()):
        raise RuntimeError('Candidate pointer differs from manifest')
    published, _ = api.file(repo, 'channels/area52.json')
    if not api.api(f'repos/{repo}').get('permissions', {}).get('push'):
        raise RuntimeError('Client repository write access unavailable')

    def gh(*args):
        def record(detail):
            detail.update(package=config['id'], phase=phase)
            if phase == 'publish':
                save(tx / 'publication' / 'client-operation-error.json', detail)
            print('Client release diagnostic: ' + json.dumps(detail), flush=True)
        return release_command(config['gh'], repo, args, record)

    def remote(name):
        assets = json.loads(gh('release', 'view', tag, '--json', 'assets'))['assets']
        if not any(a['name'] == name for a in assets):
            return None
        return sha(gh('release', 'download', tag, '--pattern', name, '--output', '-'))

    required = {p.name for p in release.glob('*.bin')}
    for name in ('manifest.json', 'PATCH-NOTES.md'):
        required.update((name, 'before-' + config['id'] + '-' + name))
    rolled = False
    selected = {p.name for p in release.glob('*.bin')}
    try:
        check_release_capacity(api, repo, tag, required)
    except ReleaseFull:
        manifest, selected = rollover_manifest(api, repo, json.loads((baseline/'manifest.json').read_bytes()),
                                               manifest, release, config['id'])
        fullclient.validate(manifest, repo)
        rolled = True
        tag = manifest['tag']
        prepared = tx/'publication'/'rollover'
        if phase == 'preflight':
            temporary = tempfile.TemporaryDirectory()
            prepared = Path(temporary.name)
        prepared.mkdir(parents=True, exist_ok=True)
        import shutil
        for name in selected | {'PATCH-NOTES.md'}:
            shutil.copyfile(release/name, prepared/name)
        release = prepared
        save(release/'manifest.json', manifest)
        channel = json.loads(pointer)
        channel.update(manifest_url=manifest['notes_url'].rsplit('/',1)[0]+'/manifest.json',
                       manifest_sha256=sha((release/'manifest.json').read_bytes()))
        save(release/'area52.json', channel)
        pointer = (release/'area52.json').read_bytes()
    if published not in ((baseline/'area52.json').read_bytes(), pointer):
        raise RuntimeError('Public channel changed; reconcile before publication')
    if rolled:
        endpoint = f'repos/{repo}/releases'
        existing = api.api(endpoint+'/tags/'+tag, missing=True)
        marker = 'Area 52 client rollover for '+config['id']
        if existing and existing.get('body') != marker:
            raise RuntimeError('Release tag belongs to another publication')
        if not existing and phase == 'publish':
            intent = tx/'publication'/'create-rollover.json'
            if intent.exists():
                raise RuntimeError('Unresolved release creation intent; reconcile before retry')
            save(intent, dict(tag=tag, repo=repo))
            api.api(endpoint, dict(tag_name=tag, name=tag, body=marker, make_latest='false'))
    previous = sha((baseline / 'manifest.json').read_bytes())
    candidate = sha((release / 'manifest.json').read_bytes())
    if not rolled and remote('manifest.json') not in (previous, candidate):
        raise RuntimeError('Canonical manifest changed; reconcile before publication')
    if rolled and existing and remote('manifest.json') not in (None, candidate):
        raise RuntimeError('Rollover canonical manifest differs')
    for component in manifest['components']:
        for chunk in component['chunks']:
            local = release / chunk['asset']
            if local.exists() and (local.stat().st_size != chunk['bytes'] or sha(local.read_bytes()) != chunk['sha256']):
                raise RuntimeError('Prepared client chunk changed')
    if phase == 'preflight':
        print('Client release preflight passed; no upload or promotion')
        return
    if phase != 'publish':
        raise ValueError('Unsupported client release phase')
    receipt = tx / 'publication' / 'client-release.json'
    state = json.loads(receipt.read_text()) if receipt.exists() else {'package': config['id']}
    if state['package'] != config['id']:
        raise RuntimeError('Client publication receipt belongs to another package')

    def upload(name, path, exists):
        if path.name != name:
            raise RuntimeError('Upload filename differs from reviewed asset name')
        gh('release', 'upload', tag, str(path), *(['--clobber'] if exists else []))

    backups = []
    for name in (() if rolled else ('manifest.json', 'PATCH-NOTES.md')):
        backup_name = 'before-' + config['id'] + '-' + name
        backup = tx / 'publication' / 'client-backups' / backup_name
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            with backup.open('xb') as stream:
                stream.write((baseline / name).read_bytes())
        if sha(backup.read_bytes()) != sha((baseline / name).read_bytes()):
            raise RuntimeError('Client baseline backup differs')
        backups.append((backup_name, backup, False))
    reconcile_assets(backups, remote, upload)
    chunks = [(name, release/name, False) for name in sorted(selected)]
    reconcile_assets(chunks, remote, upload)
    reconcile_assets([(n, release / n, True) for n in ('PATCH-NOTES.md', 'manifest.json')], remote, upload)
    state['assets_verified'] = True
    save(receipt, state)
    command = [sys.executable, str(root / 'verify_channel_promotion.py'), '--launcher', config['launcher'],
               '--channel', str(release / 'area52.json')]
    subprocess.run(command, check=True)
    from publish_package import commit_files
    head = api.api(f'repos/{repo}/git/ref/heads/main')['object']['sha']
    current, _ = api.file(repo, 'channels/area52.json')
    if current not in ((baseline / 'area52.json').read_bytes(), pointer):
        raise RuntimeError('Public channel changed before promotion')
    state['feed_commit'] = commit_files(api, repo, 'main', {'channels/area52.json': pointer},
                                       'Promote qualified client ' + config['id'], head,
                                       tx / 'publication' / 'feed-commit-intent.json')
    save(receipt, state)
    subprocess.run(command + ['--live'], check=True)
    state['status'] = 'complete'
    save(receipt, state)
    print('Client assets, launcher validation and live feed verified')


def validate_inputs(root):
    for folder in ('release', 'release-baseline'):
        for name in ('manifest.json', 'area52.json', 'PATCH-NOTES.md'):
            path = Path(root) / folder / name
            if not path.is_file() or not path.stat().st_size:
                raise RuntimeError('Missing or empty client publication input: ' + folder + '/' + name)


if __name__ == '__main__':
    if os.name == 'nt':
        execute(sys.argv[2], sys.argv[3], sys.argv[1])
    else:
        def windows(path):
            return subprocess.check_output(['wslpath', '-w', str(path)], text=True).strip()
        python = '/mnt/c/Users/danie/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
        subprocess.run([python, windows(__file__), sys.argv[1], windows(Path(__file__).parent),
                        windows(os.environ['AREA52_TRANSACTION_DIR'])], check=True)
