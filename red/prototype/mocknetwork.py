"""A minimal mock network host for proving the TCP connect-scanner (network.py)
against real sockets. Deliberately not HTTP -- a few plain listening ports with
optional banners -- to prove the scanner works at the raw-socket level, not only
against the mock site's own HTTP port. This is a test host this team builds and
controls for its own prototype use, bound to 127.0.0.1 only.
"""

from __future__ import annotations

import socket
import threading
from typing import Any


class MockNetworkHost:
    """Opens real TCP listening sockets on 127.0.0.1, each optionally sending a
    banner to whatever connects, so the scanner's open/closed detection is proven
    against genuine accepted connections, not a simulation of one."""

    def __init__(self) -> None:
        self._banners: dict[int, str] = {}
        self._sockets: dict[int, socket.socket] = {}
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()

    def open_port(self, *, port: int = 0, banner: str | None = None) -> int:
        """Starts accepting real connections on the given port (0 = an ephemeral
        free port chosen by the OS) and returns the actual port bound."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        sock.listen(5)
        actual_port = sock.getsockname()[1]
        self._sockets[actual_port] = sock
        if banner:
            self._banners[actual_port] = banner
        thread = threading.Thread(target=self._accept_loop, args=(sock, actual_port), daemon=True)
        thread.start()
        self._threads.append(thread)
        return actual_port

    def reserve_closed_port(self, *, port: int = 0) -> int:
        """Returns a port number that is guaranteed not to be listening: briefly
        binds it, then releases it immediately, so a connect attempt there gets a
        real ECONNREFUSED -- a genuine 'closed' observation, not an assumption."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def _accept_loop(self, sock: socket.socket, port: int) -> None:
        sock.settimeout(0.5)
        while not self._stop.is_set():
            try:
                conn, _ = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                banner = self._banners.get(port)
                if banner:
                    conn.sendall(banner.encode("utf-8"))
            except OSError:
                pass
            finally:
                conn.close()

    def close(self) -> None:
        self._stop.set()
        for sock in self._sockets.values():
            sock.close()
        for thread in self._threads:
            thread.join(timeout=2)

    def __enter__(self) -> "MockNetworkHost":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
