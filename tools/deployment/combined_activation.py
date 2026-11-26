import hashlib
import json
from pathlib import Path
import subprocess
import sys


def children(manifest):
    root = manifest.resolve().parent
    package = json.loads(manifest.read_text())
    if package.get('target') != 'combined' or package.get('publish') or package.get('extensions_dll') != 'excluded':
        raise ValueError('Invalid combined package scope')
    if package.get('runner_sha256') != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('Combined runner changed; requalify package')
    for row in package['artifacts']:
        path = (root / row['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Combined package integrity failed')
    result = []
    for entry in package['children']:
        path = (root / entry['manifest']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Invalid child manifest')
        child = json.loads(path.read_text())
        if child['target'] != entry['target'] or child.get('publish'):
            raise ValueError('Child target or publication mismatch')
        if not any(row['path'] == entry['manifest'] for row in package['artifacts']):
            raise ValueError('Child manifest not hash pinned')
        result.append(path)
    if [json.loads(p.read_text())['target'] for p in result] != ['development', 'cloud']:
        raise ValueError('Development and Cloud children required in order')
    return result


def execute(manifest, check_only, invoke):
    selected = children(manifest)
    for child in selected:
        invoke(child, True)
    if check_only:
        print('CHECK ONLY: both realm preflights passed; no activation or publication.')
        return
    for child in selected:
        invoke(child, False)
    print('Both realm activations completed. Client publication remains a separate authorized phase.')


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    wrapper = Path(__file__).with_name('Activate-Area52.ps1')
    def invoke(path, check):
        command = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(wrapper), '-Package', str(path)]
        if check:
            command.append('-CheckOnly')
        subprocess.run(command, check=True)
    execute(args.manifest, args.check_only, invoke)


if __name__ == '__main__':
    main()
