import argparse
import json
from pathlib import Path
import struct


def normalize(data):
    magic, count, fields, size, string_size = struct.unpack_from('<4s4I', data)
    if magic != b'WDBC' or fields not in (173, 179) or size != 692 or len(data) != 20 + count * size + string_size:
        raise ValueError('Unexpected CharacterAdvancement schema')
    pool = data[20 + count * size:]
    output = bytearray(data)
    changes = []
    for index in range(count):
        offset = 20 + index * size
        row = struct.unpack_from('<173I', data, offset)
        kind = pool[row[1]:pool.index(b'\0', row[1])].decode()
        flags = struct.unpack_from('<I', data, offset + 479)[0]
        if row[32] != 11 or row[26] < 71 or kind not in ('Ability', 'TalentAbility'):
            continue
        if not data[offset + 483] or flags & (0x1800000 | 0x20000 | 9) or not row[14]:
            continue
        cost = 1 if row[0] == 1322 or any(row[154:157]) else (3 if row[14] in (3, 6) else 2)
        if row[14] == cost:
            continue
        changes.append(dict(entry=row[0], spell=row[5], level=row[26], old=row[14], new=cost,
                            mastery=list(row[154:157]), rarity_offset=row[16], rarity_cost=row[17]))
        struct.pack_into('<I', output, offset + 14 * 4, cost)
    return bytes(output), changes


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    data, changes = normalize(args.source.read_bytes())
    args.output.write_bytes(data)
    args.report.write_text(json.dumps(changes, indent=2) + '\n')
    print(f'Updated {len(changes)} active Area 52 Death Knight essence costs.')

