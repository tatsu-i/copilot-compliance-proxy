import os
import json
import time
import requests
import logging
from pythonjsonlogger import jsonlogger
from module import check_payload, load_settings
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler

PORT = 8000
handler = logging.FileHandler('/logs/audit.log')
handler.setFormatter(jsonlogger.JsonFormatter(json_ensure_ascii=False))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

settings = load_settings('/settings.yaml')

class ApiHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/v1/engines/copilot-codex/completions":
            # Read the request body
            content_len = int(self.headers.get("content-length"))
            post_body = self.rfile.read(content_len).decode("utf-8")
            payload = json.loads(post_body)
            # Check the payload
            try:
                payload["prompt"] = check_payload(payload["prompt"], settings)
                payload["suffix"] = check_payload(payload["suffix"], settings)
            except Exception as e:
                print(e)
                print(payload)
                self.send_response(200)
                self.end_headers()
                data = {
                    "id": "cmpl",
                    "created": int(time.time()),
                    "model": "cushman-ml",
                    "choices": [{"delta": {"content": str(e)}, "index": 0, "finish_reason": None, "logprobs": None}],
                }
                self.wfile.write(b"data: " + json.dumps(data).encode() + b"\n\n")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                logger.info(str(e), extra={"type": "ignore", "client_address": self.client_address[0], "payload": payload})
                return

            logger.info("request", extra={"type": "request", "client_address": self.client_address[0], "payload": payload})

            # Send the request to the real API
            with requests.post(
                "https://copilot-proxy.githubusercontent.com/v1/engines/copilot-codex/completions",
                json=payload,
                headers=self.headers,
                stream=True,
            ) as resp:
                self.send_response(200)

                for header, value in resp.headers.items():
                    self.send_header(header, value)
                self.end_headers()
                for line in resp.iter_lines():
                    if line:
                        logger.info("completion", extra={"type": "response", "client_address": self.client_address[0], "data": line.decode()})
                        self.wfile.write(line + b'\n\n')
                        self.wfile.flush()

if __name__ == "__main__":
    # Start the server
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, ApiHandler)
    httpd.serve_forever()