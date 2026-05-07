"""
A2UI streaming demo server — stdlib only, no pip installs needed.

Streams a JSONL UI definition over Server-Sent Events (SSE), which is the
canonical A2UI transport per the v0.8 spec. The client (streaming-client.html)
renders messages as they arrive.

Run:
    python3 server.py

Then open in a browser:
    http://localhost:8080/                       (loads the client)
    http://localhost:8080/?example=profile       (different example)
    http://localhost:8080/?example=streaming

Endpoints:
    GET  /                       -> streaming-client.html
    GET  /stream?example=NAME    -> SSE stream of A2UI JSONL messages
"""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 8080
HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# Example A2UI streams. Each is a list of (delay_seconds, message_dict) pairs.
# The delay simulates a real agent producing components incrementally.
# ---------------------------------------------------------------------------

EXAMPLES = {
    "hello": [
        (0.0, {"surfaceUpdate": {"components": [
            {"id": "root", "component": {"Text": {"text": {"literalString": "Hello, World!"}}}}
        ]}}),
        (0.8, {"beginRendering": {"root": "root"}}),
    ],

    "profile": [
        (0.0, {"surfaceUpdate": {"components": [{"id": "root", "component": {"Column": {"children": {"explicitList": ["profile_card"]}}}}]}}),
        (0.4, {"surfaceUpdate": {"components": [{"id": "profile_card", "component": {"Card": {"child": "card_content"}}}]}}),
        (0.4, {"surfaceUpdate": {"components": [{"id": "card_content", "component": {"Column": {"children": {"explicitList": ["header_row", "bio_text"]}}}}]}}),
        (0.4, {"surfaceUpdate": {"components": [{"id": "header_row", "component": {"Row": {"alignment": "center", "children": {"explicitList": ["avatar", "name_column"]}}}}]}}),
        (0.4, {"surfaceUpdate": {"components": [{"id": "avatar", "component": {"Image": {"url": {"literalString": "https://api.dicebear.com/7.x/shapes/svg?seed=a2ui"}}}}]}}),
        (0.4, {"surfaceUpdate": {"components": [{"id": "name_column", "component": {"Column": {"alignment": "start", "children": {"explicitList": ["name_text", "handle_text"]}}}}]}}),
        (0.4, {"surfaceUpdate": {"components": [{"id": "name_text", "component": {"Text": {"usageHint": "h3", "text": {"literalString": "A2A Fan"}}}}]}}),
        (0.4, {"surfaceUpdate": {"components": [{"id": "handle_text", "component": {"Text": {"usageHint": "body2", "text": {"literalString": "@a2a_fan"}}}}]}}),
        (0.4, {"surfaceUpdate": {"components": [{"id": "bio_text", "component": {"Text": {"text": {"literalString": "Building beautiful apps from a single codebase."}}}}]}}),
        (0.4, {"beginRendering": {"root": "root"}}),
    ],

    "streaming": [
        (0.0, {"surfaceUpdate": {"components": [
            {"id": "root", "component": {"Column": {"alignment": "start", "children": {"explicitList": ["title", "status_label", "status_text", "progress_text"]}}}}
        ]}}),
        (0.3, {"surfaceUpdate": {"components": [{"id": "title", "component": {"Text": {"usageHint": "h2", "text": {"literalString": "Agent task"}}}}]}}),
        (0.3, {"surfaceUpdate": {"components": [{"id": "status_label", "component": {"Text": {"usageHint": "body2", "text": {"literalString": "Status:"}}}}]}}),
        (0.3, {"surfaceUpdate": {"components": [{"id": "status_text", "component": {"Text": {"usageHint": "h3", "text": {"path": "/status", "literalString": "Initializing…"}}}}]}}),
        (0.3, {"surfaceUpdate": {"components": [{"id": "progress_text", "component": {"Text": {"usageHint": "body2", "text": {"path": "/progress"}}}}]}}),
        (0.3, {"beginRendering": {"root": "root"}}),
        (1.2, {"dataModelUpdate": {"contents": [
            {"key": "status", "valueString": "Connecting to model…"},
            {"key": "progress", "valueString": "step 1 of 4"},
        ]}}),
        (1.5, {"dataModelUpdate": {"contents": [
            {"key": "status", "valueString": "Generating response…"},
            {"key": "progress", "valueString": "step 2 of 4"},
        ]}}),
        (1.5, {"dataModelUpdate": {"contents": [
            {"key": "status", "valueString": "Formatting output…"},
            {"key": "progress", "valueString": "step 3 of 4"},
        ]}}),
        (1.5, {"dataModelUpdate": {"contents": [
            {"key": "status", "valueString": "Done ✓"},
            {"key": "progress", "valueString": "step 4 of 4 · complete"},
        ]}}),
    ],
}


class A2UIHandler(BaseHTTPRequestHandler):
    """Serves the client HTML and the SSE stream of A2UI messages."""

    def log_message(self, fmt, *args):
        # Quieter logging — one line per request, no headers spam.
        print(f"[{self.log_date_time_string()}] {self.command} {self.path}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_client()
        elif parsed.path == "/stream":
            params = parse_qs(parsed.query)
            example = params.get("example", ["hello"])[0]
            self._serve_stream(example)
        else:
            self.send_error(404)

    # -- /  ------------------------------------------------------------------

    def _serve_client(self):
        client_path = HERE / "streaming-client.html"
        if not client_path.exists():
            self.send_error(500, "streaming-client.html not found next to server.py")
            return
        body = client_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- /stream  ------------------------------------------------------------

    def _serve_stream(self, example_name):
        if example_name not in EXAMPLES:
            self.send_error(404, f"unknown example: {example_name}")
            return

        # SSE headers
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")  # dev-only convenience
        self.end_headers()

        # Stream messages with timing. Each SSE event has a single `data:` line
        # holding one A2UI JSONL message.
        try:
            for delay, message in EXAMPLES[example_name]:
                if delay > 0:
                    time.sleep(delay)
                payload = json.dumps(message)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected — totally fine.
            pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), A2UIHandler)
    print(f"\n  A2UI streaming demo")
    print(f"  -------------------")
    print(f"  open  →  http://localhost:{PORT}/")
    print(f"  examples: ?example=hello | profile | streaming")
    print(f"  Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.server_close()


if __name__ == "__main__":
    main()
