import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('dk', Path(__file__).resolve().parents[1] / 'tools/normalize_dk_essence.py')
dk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dk)


class EssenceTests(unittest.TestCase):
    def test_scope_mastery_and_unrelated_bytes(self):
        rows = []
        for entry, cls, level, cost, mastery, enabled in (
            (1, 11, 71, 4, 0, 1), (2, 11, 80, 2, 1322, 1), (3, 11, 71, 6, 0, 1),
            (1322, 11, 71, 2, 0, 1),
            (4, 11, 70, 4, 0, 1), (5, 10, 71, 4, 0, 1), (6, 11, 71, 4, 0, 0)):
            row = bytearray(692)
            for field, value in {0: entry, 1: 1, 5: 100 + entry, 14: cost, 17: 2,
                                 26: level, 32: cls, 154: mastery}.items():
                struct.pack_into('<I', row, field * 4, value)
            row[483] = enabled
            rows.append(row)
        pool = b'\0Ability\0'
        original = struct.pack('<4s4I', b'WDBC', 7, 179, 692, len(pool)) + b''.join(rows) + pool
        output, changes = dk.normalize(original)
        self.assertEqual([(r['entry'], r['new']) for r in changes], [(1, 2), (2, 1), (3, 3), (1322, 1)])
        expected = bytearray(original)
        for index, cost in enumerate((2, 1, 3, 1)):
            struct.pack_into('<I', expected, 20 + index * 692 + 56, cost)
        self.assertEqual(output, bytes(expected))
        self.assertEqual(dk.normalize(output), (output, []))

    def test_wrong_schema_rejected(self):
        with self.assertRaises(ValueError):
            dk.normalize(struct.pack('<4s4I', b'WDBC', 0, 1, 4, 0))
