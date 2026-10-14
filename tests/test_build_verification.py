import importlib.util
from pathlib import Path
import struct
import unittest

SPEC = importlib.util.spec_from_file_location('build_verification', Path(__file__).parents[1] / 'tools/stage_build_verification.py')
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)


def fixture(descriptions):
    pool = bytearray(b'\0')
    rows = bytearray()
    for sid, description in descriptions.items():
        row = [0] * 234
        row[0], row[170], row[95] = sid, len(pool), 107
        pool.extend(description.encode() + b'\0')
        rows.extend(struct.pack('<234I', *row))
    return struct.pack('<4s4I', b'WDBC', len(descriptions), 234, 936, len(pool)) + rows + pool


def description(raw, index):
    count = struct.unpack_from('<I', raw, 4)[0]
    pool = raw[20 + count * 936:]
    pointer = struct.unpack_from('<I', raw, 20 + index * 936 + 680)[0]
    return pool[pointer:pool.index(0, pointer)].decode()


class BuildVerificationTests(unittest.TestCase):
    def test_preserves_shift_text_certification_and_unrelated_rows(self):
        content = 'Description\n@ext:SHIFT detail\n\n' + STAGE.RED + ':ext@'
        raw = fixture({1: content, 2: STAGE.GREEN, 3: 'untouched'})
        after, receipt = STAGE.patch_spell_dbc(raw, [1, 2], [], {})
        self.assertEqual(description(after, 0), content.replace(STAGE.RED, STAGE.YELLOW))
        self.assertEqual(description(after, 1), STAGE.GREEN)
        self.assertEqual(description(after, 2), 'untouched')
        self.assertEqual(after[20 + 936:20 + 3 * 936], raw[20 + 936:20 + 3 * 936])
        self.assertEqual(receipt['certified_preserved'], [2])

    def test_idempotent_and_scoped_metadata(self):
        raw = fixture({1: STAGE.RED, 2: 'other'})
        once, _ = STAGE.patch_spell_dbc(raw, [1], [], {1: {95: 72}})
        twice, receipt = STAGE.patch_spell_dbc(once, [1], [], {1: {95: 72}})
        self.assertEqual(once, twice)
        self.assertEqual(receipt['changed'], [])
        self.assertEqual(once[20 + 936:20 + 2 * 936], raw[20 + 936:20 + 2 * 936])

    def test_demotes_only_verified_and_preserves_certified(self):
        raw = fixture({1: STAGE.YELLOW, 2: STAGE.GREEN})
        after, _ = STAGE.patch_spell_dbc(raw, [], [1, 2], {})
        self.assertEqual(description(after, 0), STAGE.RED)
        self.assertEqual(description(after, 1), STAGE.GREEN)

    def test_rejects_missing_conflicting_or_ambiguous_requests(self):
        raw = fixture({1: STAGE.YELLOW})
        for promote, demote in [([2], []), ([1], [1])]:
            with self.assertRaises(ValueError):
                STAGE.patch_spell_dbc(raw, promote, demote, {})
        with self.assertRaises(ValueError):
            STAGE.patch_spell_dbc(fixture({1: STAGE.RED + STAGE.YELLOW}), [1], [], {})

    def test_rejects_truncated_data(self):
        with self.assertRaises(ValueError):
            STAGE.patch_spell_dbc(fixture({1: 'text'})[:-1], [1], [], {})


if __name__ == '__main__':
    unittest.main()
