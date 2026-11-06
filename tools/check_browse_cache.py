"""Real bounded-cache behaviour against a memory Window and temporary OS lock."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source/plugin.video.yoplayer.home/resources/lib'))
from browse_cache import Cache, INDEX, PREFIX, MAX_BYTES, MAX_ENTRIES, MAX_ITEM_BYTES, exclusive


def key(number):
    return hashlib.sha256(str(number).encode()).hexdigest()


class Window:
    def __init__(self): self.values = {}
    def getProperty(self, name): return self.values.get(name, '')
    def setProperty(self, name, value): self.values[name] = value
    def clearProperty(self, name): self.values.pop(name, None)


class BrowseCacheChecks(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = str(Path(self.folder.name) / 'cache.lock')
        self.window = Window()
        self.now = 100
        self.cache = Cache(self.window, self.path, lambda: self.now)

    def test_hit_and_event_epoch_invalidation(self):
        rows = [{'title': 'one'}]
        self.assertTrue(self.cache.put(key(1), rows, 1, 'event1'))
        self.assertEqual(self.cache.get(key(1), 'event1')['rows'], rows)
        self.assertIsNone(self.cache.get(key(1), 'event2'))
        self.assertEqual(self.window.getProperty(PREFIX + key(1)), '')

    def test_expiry_removes_the_payload_on_next_access(self):
        self.cache.put(key(1), [], 0, '')
        self.now += 16
        self.assertIsNone(self.cache.get(key(1), ''))
        self.assertEqual(self.cache.index()['entries'], {})
        self.assertEqual(self.window.getProperty(PREFIX + key(1)), '')

    def test_quantity_cap_and_lru_access(self):
        for number in range(MAX_ENTRIES):
            self.now += .1
            self.cache.put(key(number), [], 0, '')
        self.now += .1
        self.cache.get(key(0), '')
        self.now += .1
        self.cache.put(key(99), [], 0, '')
        entries = self.cache.index()['entries']
        self.assertEqual(len(entries), MAX_ENTRIES)
        self.assertIn(key(0), entries)
        self.assertNotIn(key(1), entries)
        self.assertEqual(self.window.getProperty(PREFIX + key(1)), '')

    def test_total_bytes_and_oversized_payload_are_bounded(self):
        for number in range(5):
            self.cache.put(key(number), [{'plot': 'x' * 1_100_000}], 1, '')
            self.now += .1
        entries = self.cache.index()['entries']
        self.assertLessEqual(sum(item['bytes'] for item in entries.values()), MAX_BYTES)
        self.assertLess(len(entries), 5)
        self.assertFalse(self.cache.put(key(99), [{'plot': 'x' * MAX_ITEM_BYTES}], 1, ''))
        self.assertEqual(self.window.getProperty(PREFIX + key(99)), '')

    def test_sweep_is_throttled_and_does_not_scan_directories(self):
        self.cache.put(key(1), [], 0, '')
        swept = self.cache.index()['swept']
        with patch('os.listdir', side_effect=AssertionError('directory scan')), \
                patch('os.scandir', side_effect=AssertionError('directory scan')):
            for _ in range(10):
                self.now += .1
                self.assertIsNotNone(self.cache.get(key(1), ''))
                self.assertEqual(self.cache.index()['swept'], swept)

    def test_busy_lock_falls_back_without_blocking_or_mutating(self):
        self.cache.put(key(1), [], 0, '')
        before = dict(self.window.values)
        with exclusive(self.path) as acquired:
            self.assertTrue(acquired)
            self.assertIsNone(self.cache.get(key(1), ''))
            self.assertFalse(self.cache.put(key(2), [], 0, ''))
        self.assertEqual(before, self.window.values)

    def test_corrupt_payload_is_a_miss_and_is_removed(self):
        self.cache.put(key(1), [], 0, '')
        self.window.setProperty(PREFIX + key(1), '{')
        self.assertIsNone(self.cache.get(key(1), ''))
        self.assertEqual(self.cache.index()['entries'], {})


if __name__ == '__main__':
    unittest.main()
