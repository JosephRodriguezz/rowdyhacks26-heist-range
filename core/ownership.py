"""One runtime owner per persistent database; a second process cannot recover it."""

import os


class RuntimeOwnership:
    def __init__(self, db_path):
        self.fd = None
        if os.fspath(db_path) == ":memory:":
            return
        self.fd = os.open(os.fspath(db_path) + ".runtime.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(self.fd).st_size == 0:
                    os.write(self.fd, b"0")
                os.lseek(self.fd, 0, os.SEEK_SET)
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            self.fd = None
            raise ValueError("persistent database already has a runtime owner") from None

    def close(self):
        if self.fd is not None:
            # Closing releases the OS lock, including after a process crash.
            os.close(self.fd)
            self.fd = None
