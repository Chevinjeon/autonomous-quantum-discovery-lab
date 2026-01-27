import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health"):
            data = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path not in ("/", "/solve"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(400, "invalid_json")
            return

        prices = payload.get("prices", {})
        if not isinstance(prices, dict) or not prices:
            self._send_error(400, "prices_required")
            return
        try:
            prices = {k: float(v) for k, v in prices.items()}
        except (TypeError, ValueError):
            self._send_error(400, "invalid_prices")
            return

        max_assets = payload.get("max_assets", 3)
        try:
            max_assets = int(max_assets)
        except (TypeError, ValueError):
            self._send_error(400, "invalid_max_assets")
            return
        if max_assets <= 0:
            self._send_error(400, "invalid_max_assets")
            return

        sorted_assets = sorted(prices, key=prices.get)
        chosen = sorted_assets[: max(max_assets, 1)]
        weight = 1.0 / len(chosen) if chosen else 1.0

        response = {"weights": {a: weight for a in chosen}}

        data = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status_code: int, code: str) -> None:
        data = json.dumps({"error": code}).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    print("Solver service running on :8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
