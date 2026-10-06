"""Stage an isolated Avatar impact-visual experiment; never install it."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rows(data):
    magic, count, fields, size, strings = struct.unpack_from('<4s4I', data)
    assert magic == b'WDBC' and size == fields * 4
    assert len(data) == 20 + count * size + strings
    return count, fields, size, [struct.unpack_from('<' + 'I' * fields, data, 20 + i * size)
                                 for i in range(count)]


def patch(spells, visuals):
    count, fields, size, records = rows(visuals)
    original = next(r for r in records if r[0] == 20218)
    assert original[2] == 20386 and original[14] == 0
    visual_id = max(r[0] for r in records) + 1
    clone = list(original)
    clone[0], clone[2], clone[14] = visual_id, 0, 20386
    boundary = 20 + count * size
    new_visuals = bytearray(visuals[:boundary] + struct.pack('<' + 'I' * fields, *clone) + visuals[boundary:])
    struct.pack_into('<I', new_visuals, 4, count + 1)
    _, spell_fields, spell_size, spell_rows = rows(spells)
    assert spell_fields == 234
    index = next(i for i, r in enumerate(spell_rows) if r[0] == 86380)
    assert spell_rows[index][131] == 20218
    offset = 20 + index * spell_size + 131 * 4
    new_spells = bytearray(spells)
    struct.pack_into('<I', new_spells, offset, visual_id)
    assert new_spells[:offset] == spells[:offset] and new_spells[offset + 4:] == spells[offset + 4:]
    assert rows(new_visuals)[3][:-1] == records
    assert all(clone[i] == original[i] for i in range(fields) if i not in (0, 2, 14))
    return bytes(new_spells), bytes(new_visuals), visual_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', type=Path, required=True)
    parser.add_argument('--mpq-tools', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.mpq_tools.resolve()))
    from lib.mpq import MPQArchive, write_archive

    target = args.client / 'Data/area-52/patch-D.MPQ'
    with MPQArchive(target) as archive:
        files = {n: archive.read_file(n) for n in archive.read_file('(listfile)').decode().splitlines()
                 if n and n.lower() not in ('(listfile)', '(attributes)', '(signature)')}
    visual_name = 'DBFilesClient\\SpellVisual.dbc'
    spell_name = 'DBFilesClient\\Spell.dbc'
    with MPQArchive(args.client / 'Data/patch-S.MPQ') as archive:
        visuals = files.get(visual_name) or archive.read_file(visual_name)
        kit = next(r for r in rows(archive.read_file('DBFilesClient\\SpellVisualKit.dbc'))[3] if r[0] == 20386)
        attachments = [r for r in rows(archive.read_file('DBFilesClient\\SpellVisualKitModelAttach.dbc'))[3]
                       if r[1] == 20386]
        assert kit and len(attachments) == 2 and all(r[2] == 54806 for r in attachments)
    with MPQArchive(args.client / 'Data/patch-N.MPQ') as archive:
        model_hash = digest(archive.read_file('SPELLS\\warrior_avatar_cast.m2'))
    old_files = files.copy()
    files[spell_name], files[visual_name], visual_id = patch(files[spell_name], visuals)
    args.output.mkdir(parents=True, exist_ok=True)
    candidate = args.output / 'patch-D.MPQ'
    if candidate.exists():
        raise FileExistsError(candidate)
    write_archive(str(candidate), files)
    with MPQArchive(candidate) as archive:
        for name, data in files.items():
            assert archive.read_file(name) == data
        for name, data in old_files.items():
            if name not in (spell_name, visual_name):
                assert archive.read_file(name) == data
    report = dict(target=str(target), before=digest(target.read_bytes()), after=digest(candidate.read_bytes()),
                  spell=86380, original_visual=20218, test_visual=visual_id, kit=20386,
                  model_sha256=model_hash, installed=False,
                  change='Move cloned visual casting kit to caster impact; preserve state and all gameplay fields')
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
