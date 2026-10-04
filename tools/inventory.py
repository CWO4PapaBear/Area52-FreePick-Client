import argparse
import hashlib
import json
from pathlib import Path

EXCLUDED = {'wtf', 'cache', 'logs', 'dll_logs', 'errors', 'screenshots', '.bear-cave-launcher', '.git'}
RUNTIME = {'ascension.exe', 'ascension.ok', 'extensions.dll', 'discord_game_sdk.dll',
           'divxdecoder.dll', 'divxtac.dll', 'mmgr64.exe', 'wowerror.exe'}


def classify(relative):
    parts = relative.lower().split('/')
    name = parts[-1]
    if any(part in EXCLUDED for part in parts) or name.endswith(('.original', '.bak', '.log', '.dmp', '.wtf')):
        return 'exclude'
    if len(parts) == 1 and name in RUNTIME:
        return 'candidate'
    if parts[0] == 'data' and name.endswith('.mpq'):
        return 'candidate'
    return 'review'


def inventory(root, hashes=False):
    root = root.resolve(strict=True)
    if not (root / 'Ascension.exe').is_file():
        raise ValueError('Expected an Area 52 client containing Ascension.exe')
    records = []
    def walk(folder):
        for path in sorted(folder.iterdir()):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                records.append({'path': relative, 'decision': 'exclude', 'reason': 'linked path'})
            elif classify(relative) == 'exclude':
                records.append({'path': relative, 'decision': 'exclude'})
            elif path.is_dir():
                walk(path)
            elif path.is_file():
                decision = classify(relative)
                record = {'path': relative, 'bytes': path.stat().st_size, 'decision': decision}
                if hashes and decision == 'candidate':
                    before = path.stat()
                    with path.open('rb') as handle:
                        record['sha256'] = hashlib.file_digest(handle, 'sha256').hexdigest()
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise RuntimeError('File changed during inventory: ' + relative)
                records.append(record)
    walk(root)
    return {'schema': 1, 'channel': 'area52', 'approved': False, 'files': records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('client', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--hash', action='store_true')
    args = parser.parse_args()
    data = inventory(args.client, args.hash)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    for decision in ('candidate', 'review', 'exclude'):
        rows = [row for row in data['files'] if row['decision'] == decision]
        print(decision, len(rows), 'entries;', sum(row.get('bytes', 0) for row in rows), 'bytes')


if __name__ == '__main__':
    main()
