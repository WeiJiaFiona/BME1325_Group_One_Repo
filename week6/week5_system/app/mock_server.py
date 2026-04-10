from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Dict, Tuple


class MockHandoffHandler(BaseHTTPRequestHandler):
    server_version = "MockHandoff/1.0"

    def _send_json(self, status: int, payload: Dict[str, object]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if self.path not in {"/handoff/request", "/handoff/complete"}:
            self._send_json(404, {"error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid_json"})
            return

        if self.path == "/handoff/request":
            required_unit = str(payload.get("required_unit", ""))
            accepted = required_unit in {"ICU", "WARD"}
            response = {
                "accepted": accepted,
                "receiver_system": required_unit,
                "accepted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "receiver_bed": "BED-1" if accepted else "",
            }
            self._send_json(200, response)
            return

        response = {
            "status": "ok",
            "accepted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self._send_json(200, response)


    def log_message(self, format: str, *args) -> None:
        return


def start_mock_server(host: str = "127.0.0.1", port: int = 0) -> Tuple[ThreadingHTTPServer, Thread]:
    server = ThreadingHTTPServer((host, port), MockHandoffHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_mock_server(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()
