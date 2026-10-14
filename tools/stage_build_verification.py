import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

YELLOW = '|cffffff00VERIFIED|r'
RED = '|cffff0000NOT VERIFIED|r'
GREEN = '|cff00ff00CERTIFIED|r'
STATUS = re.compile(r'\|c[0-9a-fA-F]{8}(?:NOT VERIFIED|VERIFIED|CERTIFIED)\|r')


def patch_spell_dbc(raw, promote, demote, overrides):
    magic, count, fields, size, string_size = struct.unpack_from('<4s4I', raw)
    if magic != b'WDBC' or fields != 234 or size != 936 or len(raw) != 20 + count * size + string_size:
        raise ValueError('Unexpected Spell.dbc layout or length')
    promote, demote = set(promote), set(demote)
    if promote & demote:
        raise ValueError('A spell cannot be promoted and demoted together')
    overrides = {int(key): value for key, value in overrides.items()}
    rows = bytearray(raw[:20 + count * size])
    pool = bytearray(raw[20 + count * size:])
    seen, changed, protected = set(), [], []
    requested = promote | demote | set(overrides)
    for index in range(count):
        offset = 20 + index * size
        sid = struct.unpack_from('<I', raw, offset)[0]
        if sid in seen:
            raise ValueError('Duplicate spell ID')
        seen.add(sid)
        if sid not in requested:
            continue
        touched = False
        if sid in promote | demote:
            pointer = struct.unpack_from('<I', raw, offset + 170 * 4)[0]
            if pointer >= len(pool):
                raise ValueError('Invalid description offset')
            end = pool.find(b'\0', pointer)
            if end < 0:
                raise ValueError('Unterminated description')
            old = pool[pointer:end].decode('utf-8')
            if GREEN in old:
                protected.append(sid)
            else:
                target = YELLOW if sid in promote else RED
                if len(STATUS.findall(old)) > 1:
                    raise ValueError('Multiple existing status labels for ' + str(sid))
                new = STATUS.sub(lambda _: target, old) if STATUS.search(old) else old + '\n\n@ext:' + target + ':ext@'
                if new != old:
                    struct.pack_into('<I', rows, offset + 170 * 4, len(pool))
                    pool.extend(new.encode('utf-8') + b'\0')
                    touched = True
        for field, value in overrides.get(sid, {}).items():
            field, value = int(field), int(value)
            if not 0 <= field < fields or field == 0 or not 0 <= value <= 0xffffffff:
                raise ValueError('Invalid metadata field/value')
            previous = struct.unpack_from('<I', rows, offset + field * 4)[0]
            if previous != value:
                struct.pack_into('<I', rows, offset + field * 4, value)
                touched = True
        if touched:
            changed.append(sid)
    if requested - seen:
        raise ValueError('Requested spell IDs missing: ' + str(sorted(requested - seen)))
    struct.pack_into('<I', rows, 16, len(pool))
    return bytes(rows) + bytes(pool), {'changed': sorted(changed), 'certified_preserved': sorted(protected)}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--decisions', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mpq-tools', type=Path, required=True)
    args = parser.parse_args()
    if args.archive.resolve() == args.output.resolve() or args.output.exists():
        raise ValueError('Use a new output archive; installed archives are never edited in place')
    decisions = json.loads(args.decisions.read_text())
    if decisions.get('state') != 'verified_for_staging':
        raise ValueError('Completed engineering evidence is required before staging')
    sys.path.insert(0, str(args.mpq_tools))
    from lib.mpq import MPQArchive, write_archive
    reserved = {'(listfile)', '(signature)', '(attributes)'}
    with MPQArchive(args.archive) as archive:
        members = [name for name in archive.read_file('(listfile)').decode().splitlines()
                   if name and name.lower() not in reserved]
        files = {name: archive.read_file(name) for name in members}
    spell_key = next(name for name in files if name.lower() == 'dbfilesclient\\spell.dbc')
    modified, receipt = patch_spell_dbc(files[spell_key], decisions['promote_spells'],
                                       decisions['demote_spells'], decisions.get('metadata', {}))
    files[spell_key] = modified
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_archive(args.output, files)
    with MPQArchive(args.output) as archive:
        after = {name for name in archive.read_file('(listfile)').decode().splitlines()
                 if name and name.lower() not in reserved}
        if after != set(files):
            raise ValueError('Archive member inventory changed')
        for name, content in files.items():
            if archive.read_file(name) != content:
                raise ValueError('Archive member readback mismatch: ' + name)
    receipt.update(state='staged_not_installed', baseline_sha256=sha(args.archive), sha256=sha(args.output),
                   archive=str(args.archive), output=str(args.output), members_verified=len(files),
                   spell_sha256=hashlib.sha256(modified).hexdigest())
    args.output.with_suffix(args.output.suffix + '.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in ('state', 'changed', 'certified_preserved', 'members_verified')}))


if __name__ == '__main__':
    main()
