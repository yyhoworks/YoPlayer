"""Exclusive write guard for profile JSON files, matching catalog.py semantics.

The lock file intentionally persists: OS locks release after a crash, whereas
an exclusive-create sentinel would leave future writers blocked forever.
"""
import os
import time


def exclusive(target):
    """Acquire a non-blocking byte lock on target+'.lock' (5s wait), or raise FileExistsError."""
    class _Guard:
        def __enter__(self):
            self.fd = os.open(target + '.lock', os.O_RDWR | os.O_CREAT, 0o600)
            deadline = time.monotonic() + 5
            while True:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self
                except OSError:
                    if time.monotonic() > deadline:
                        os.close(self.fd)
                        raise FileExistsError('Another writer holds ' + target)
                    time.sleep(0.05)

        def __exit__(self, *exc):
            os.lseek(self.fd, 0, os.SEEK_SET)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
    return _Guard()
