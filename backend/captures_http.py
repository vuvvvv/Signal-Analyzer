"""Tiny static file server for backend/captures/ (spectrum PNGs + WAVs),
so Flutter can fetch them over plain HTTP instead of stuffing binary blobs
through the msgpack/WebSocket control channel. stdlib-only, runs in its
own thread — never touches the SDR/AI pipeline.
"""

from __future__ import annotations

import functools
import http.server
import logging
import threading

log = logging.getLogger(__name__)


class CapturesHttpServer:
    def __init__(self, directory: str, host: str = "0.0.0.0", port: int = 8766):
        self.directory = directory
        self.host = host
        self.port = port
        self._httpd: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=self.directory
        )
        self._httpd = http.server.ThreadingHTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="captures-http", daemon=True)
        self._thread.start()
        log.info(f"CapturesHttpServer: serving {self.directory} on {self.host}:{self.port}")

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd = None
