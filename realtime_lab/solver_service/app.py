import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        payload = json.loads(body)
        prices = payload.get("prices", {})
        max_assets = int(payload.get("max_assets", 3))

        sorted_assets = sorted(prices, key=prices.get)
        chosen = sorted_assets[: max(max_assets, 1)]
        weight = 1.0 / len(chosen) if chosen else 1.0

        response = {"weights": {a: weight for a in chosen}}

        data = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    print("Solver service running on :8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
