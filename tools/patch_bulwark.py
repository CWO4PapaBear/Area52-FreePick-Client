import argparse
import json
from pathlib import Path
import struct


def patch(raw, changes):
    magic, count, fields, size, pool_size = struct.unpack_from('<4s4I', raw)
    if magic != b'WDBC' or fields < 226 or size != fields * 4 or len(raw) != 20 + count * size + pool_size:
        raise ValueError('Unsupported Spell.dbc layout')
    rows = bytearray(raw[:20 + count * size])
    pool = bytearray(raw[20 + count * size:])
    status = set(changes['status_spells'])
    numeric = {int(k): {int(f): v for f, v in fields.items()} for k, fields in changes['numeric'].items()}
    required = status | numeric.keys()
    seen = set()
    for i in range(count):
        offset = 20 + i * size
        spell = struct.unpack_from('<I', rows, offset)[0]
        if spell not in required:
            continue
        seen.add(spell)
        for field, value in numeric.get(spell, {}).items():
            struct.pack_into('<I', rows, offset + field * 4, value)
        if spell not in status:
            continue
        pointer = struct.unpack_from('<I', rows, offset + 170 * 4)[0]
        original = pool[pointer:pool.index(0, pointer)].decode('utf-8')
        updated = original.replace('|cffff0000NOT VERIFIED|r', '|cffffff00VERIFIED|r')
        if 'VERIFIED|r' not in updated and 'CERTIFIED|r' not in updated:
            updated = updated.rstrip() + '\n\n@ext:|cffffff00VERIFIED|r:ext@'
        if original != updated:
            struct.pack_into('<I', rows, offset + 170 * 4, len(pool))
            pool.extend(updated.encode('utf-8') + b'\0')
    if required - seen:
        raise ValueError(f'Missing spell records: {sorted(required - seen)}')
    struct.pack_into('<I', rows, 16, len(pool))
    return bytes(rows) + pool


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--changes', type=Path, default=Path(__file__).with_name('bulwark-spells.json'))
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Stage to a separate output file')
    args.output.write_bytes(patch(args.source.read_bytes(), json.loads(args.changes.read_text())))
