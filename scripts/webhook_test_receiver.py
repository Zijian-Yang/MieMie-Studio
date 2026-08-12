#!/usr/bin/env python3
"""Receive one local platform Webhook for deployment qualification."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            args.output.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            self.send_response(204)
            self.end_headers()
            self.server.shutdown_requested = True

        def log_message(self, format, *values):  # noqa: A002
            return

    server = HTTPServer((args.host, args.port), Handler)
    server.timeout = 1
    server.shutdown_requested = False
    while not server.shutdown_requested:
        server.handle_request()
    server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
