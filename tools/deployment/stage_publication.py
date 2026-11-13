"""Stage current publication tools into a new, unpublished activation package."""
import argparse
import json
from pathlib import Path
import shutil

import os
from publication_common import GitHub, sha

FILES = ('publish_package.py', 'publication_common.py', 'announce_package.py',
         'area52-package-notes.yml', 'render_progress.py', 'CertificationIcon.tga', 'publication_tls.ps1')


def select_source_branch(config, root, api):
    repo = config.get('source_repo')
    if repo != 'CWO4PapaBear/azerothcore-wotlk-coa' or config.get('isolated_source_branch'):
        return
    branch = 'integration/area52-deployed'
    base = config['source_base']
    head = api.api(f'repos/{repo}/git/ref/heads/{branch}', missing=True)
    revision = head['object']['sha'] if head else base
    if revision != base:
        for item in config['source_files']:
            path = item['path']
            current = api.file(repo, path, revision)[0]
            if current != api.file(repo, path, base)[0] and current != (root / item['artifact']).read_bytes():
                raise RuntimeError('Reconcile shared branch changes before staging: ' + path)
    config.update(source_branch=branch, source_base=revision)


def stage(manifest):
    manifest = Path(manifest).resolve()
    package = json.loads(manifest.read_text(encoding='utf-8-sig'))
    root = manifest.parent / 'publication'
    # Never silently replace an existing package's hashed publication payload.
    if package.get('publish') or package.get('publication_preflight') or any((root / name).exists() for name in FILES):
        raise RuntimeError('Publication already staged; preserve the immutable package and use a new package directory/ID')
    config = json.loads((root / 'config.json').read_text(encoding='utf-8-sig'))
    if config['id'] != package['id']:
        raise RuntimeError('Publication package ID differs')
    for name in ('notes.md', 'snapshot.py'):
        if not (root / name).is_file():
            raise RuntimeError('Missing package-specific publication input: ' + name)
    if config.get('client_release'):
        from publish_client_release import validate_inputs
        validate_inputs(root)
    if config.get('source_repo'):
        gh = 'gh' if os.name == 'nt' else '/mnt/c/Program Files/GitHub CLI/gh.exe'
        select_source_branch(config, root, GitHub(gh))
        (root / 'config.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    for name in FILES:
        shutil.copy2(Path(__file__).parent / name, root / name)
    package['publication_preflight'] = [{'script': 'publication/publish_package.py', 'args': ['preflight'], 'timeout': 180}]
    package['publish'] = [{'script': 'publication/publish_package.py', 'args': ['publish'], 'timeout': 1500}]
    if config.get('client_release'):
        for name in ('release-config.json', 'release/manifest.json', 'release/area52.json',
                     'release-baseline/manifest.json', 'release-baseline/area52.json'):
            if not (root / name).is_file():
                raise RuntimeError('Missing client publication input: ' + name)
        shutil.copy2(Path(__file__).parent / 'publish_client_release.py', root / 'publish_client_release.py')
        shutil.copy2(Path(__file__).parent.parent / 'verify_channel_promotion.py', root / 'verify_channel_promotion.py')
        package['publication_preflight'].insert(0, {'script': 'publication/publish_client_release.py',
                                                   'args': ['preflight'], 'timeout': 300})
        package['publish'].insert(0, {'script': 'publication/publish_client_release.py',
                                     'args': ['publish'], 'timeout': 1800})
    records = {item['path']: item for item in package.get('artifacts', [])}
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            relative = path.relative_to(manifest.parent).as_posix()
            records[relative] = {'path': relative, 'sha256': sha(path.read_bytes())}
    package['artifacts'] = list(records.values())
    manifest.write_text(json.dumps(package, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    stage(parser.parse_args().manifest)
