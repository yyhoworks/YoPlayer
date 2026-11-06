"""Bounded, process-local Browse snapshots; the only disk use is one OS lock."""
from contextlib import contextmanager
import json
import os
import time

PREFIX = 'YoPlayer.Infuse.Cache.Browse.'
INDEX = PREFIX + 'Index.v1'
MAX_ENTRIES = 8
MAX_BYTES = 4 * 1024 * 1024
MAX_ITEM_BYTES = 2 * 1024 * 1024
TTL = 15
SWEEP_INTERVAL = 5


@contextmanager
def exclusive(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    acquired = False
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        yield acquired
    finally:
        if acquired:
            if os.name == 'nt':
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


class Cache:
    def __init__(self, window, lock_path, clock=time.monotonic):
        self.window = window
        self.lock_path = lock_path
        self.clock = clock

    def index(self):
        try:
            value = json.loads(self.window.getProperty(INDEX))
            if not isinstance(value['entries'], dict) or len(value['entries']) > MAX_ENTRIES:
                raise ValueError('invalid index')
            for key, item in value['entries'].items():
                if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
                    raise ValueError('invalid key')
                if not (isinstance(item['bytes'], int) and 0 < item['bytes'] <= MAX_ITEM_BYTES
                        and isinstance(item['at'], (int, float)) and isinstance(item['used'], (int, float))):
                    raise ValueError('invalid entry')
            return value
        except (ValueError, KeyError, TypeError):
            return {'entries': {}, 'swept': 0}

    def publish(self, index):
        self.window.setProperty(INDEX, json.dumps(index, separators=(',', ':')))

    def remove(self, index, key):
        index['entries'].pop(key, None)
        self.window.clearProperty(PREFIX + key)

    def sweep(self, index, now):
        if 0 <= now - index.get('swept', 0) < SWEEP_INTERVAL:
            return
        for key, item in list(index['entries'].items()):
            if not 0 <= now - item['at'] < TTL:
                self.remove(index, key)
        index['swept'] = now

    def get(self, key, epoch):
        try:
            with exclusive(self.lock_path) as acquired:
                if not acquired:
                    return None
                now = self.clock()
                index = self.index()
                self.sweep(index, now)
                value = None
                if key in index['entries']:
                    item = index['entries'][key]
                    try:
                        data = json.loads(self.window.getProperty(PREFIX + key))
                        if (0 <= now - item['at'] < TTL and data['epoch'] == epoch
                                and isinstance(data['rows'], list) and type(data['total']) is int):
                            value = data
                            item['used'] = now
                        else:
                            self.remove(index, key)
                    except (ValueError, KeyError, TypeError):
                        self.remove(index, key)
                self.publish(index)
                return value
        except OSError:
            return None

    def put(self, key, rows, total, epoch):
        payload = json.dumps({'rows': rows, 'total': total, 'epoch': epoch}, ensure_ascii=False)
        size = len(payload.encode('utf-8'))
        try:
            with exclusive(self.lock_path) as acquired:
                if not acquired:
                    return False
                now = self.clock()
                index = self.index()
                self.sweep(index, now)
                self.remove(index, key)
                if size > MAX_ITEM_BYTES:
                    self.publish(index)
                    return False
                while (len(index['entries']) >= MAX_ENTRIES or
                       sum(item['bytes'] for item in index['entries'].values()) + size > MAX_BYTES):
                    oldest = min(index['entries'], key=lambda k: index['entries'][k]['used'])
                    self.remove(index, oldest)
                self.window.setProperty(PREFIX + key, payload)
                index['entries'][key] = {'at': now, 'used': now, 'bytes': size}
                self.publish(index)
                return True
        except OSError:
            return False
