import unittest
from unittest.mock import Mock
from test_publication_release_recovery import release


class CapacityTests(unittest.TestCase):
    def inventory(self, count):
        api = Mock()
        rows = [{'name': str(i)} for i in range(count)]
        api.api.side_effect = [{'id': 123}] + [rows[i:i+100] for i in range(0, count, 100)] + [[]]
        return api

    def test_existing_names_at_limit(self):
        release.check_release_capacity(self.inventory(1000), 'o/r', 'tag', {'999'})

    def test_backup_and_chunk_exceed_remaining_slot(self):
        with self.assertRaisesRegex(RuntimeError, 'needs 2 new slots'):
            release.check_release_capacity(self.inventory(999), 'o/r', 'tag', {'998', 'backup', 'chunk'})

    def test_final_slot_available(self):
        release.check_release_capacity(self.inventory(999), 'o/r', 'tag', {'chunk'})
